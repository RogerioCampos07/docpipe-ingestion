"""Run local experiments only in an identified Compose project."""

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from experiments.fixtures import fixtures
from experiments.summarize import expected_failure, summarize

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / 'artifacts' / 'experiments'
SCENARIOS = json.loads(
    (ROOT / 'experiments/scenarios.json').read_text(encoding='utf-8')
)
RUN_PATTERN = re.compile(r'lab-[0-9]{8}t[0-9]{6}-[0-9a-f]{8}')
DEPENDENCIES = ('postgres', 'rabbitmq', 'azurite')
GIB = 1024**3
REPLICAS = 2
MIN_DOCKER_CPUS = 4
MAX_BACKLOG = 500
MAX_HOST_CPU_PERCENT = 90
MAX_LOCUST_CPU_PERCENT = 36
MAX_UNEXPECTED_STREAK = 10
MAX_POSTS = 2000
MAX_USERS = 8
MAX_SPAWN_RATE = 2
MIN_TASK_WAIT = 2
MAX_TASK_WAIT = 10
MAX_PREFILL = 100
GUARD_STATE: dict[str, Any] = {}


def run_id() -> str:
    return datetime.now(UTC).strftime('lab-%Y%m%dt%H%M%S-') + uuid4().hex[:8]


def validate_run_id(value: str) -> str:
    if RUN_PATTERN.fullmatch(value) is None:
        raise ValueError('run ID is not a laboratory identifier')
    return value


def report_dir(value: str) -> Path:
    validate_run_id(value)
    path = (REPORT_ROOT / value).resolve()
    if path.parent != REPORT_ROOT.resolve():
        raise ValueError('report path escaped the laboratory root')
    return path


def _call(
    args: list[str], *, env: dict[str, str] | None = None, timeout: int = 120
) -> str:
    result = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f'{args[0]} command failed ({result.returncode}): '
            f'{result.stderr[-600:]}'
        )
    return result.stdout.strip()


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding='utf-8')))


def _save(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def _event(folder: Path, event: str, **fields: object) -> None:
    record = {
        'time_utc': datetime.now(UTC).isoformat(),
        'event': event,
        **fields,
    }
    with (folder / 'timeline.jsonl').open('a') as stream:
        stream.write(json.dumps(record, sort_keys=True) + '\n')


def _project(value: str) -> str:
    return 'docpipe-' + validate_run_id(value)


def _env(manifest: dict[str, Any], **extra: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        'LAB_RUN_ID': manifest['run_id'],
        'LAB_PROJECT': manifest['project'],
        'LAB_OUTBOX_MAX_ATTEMPTS': (
            '10' if manifest['scenario'] == 'rabbitmq' else '5'
        ),
        **extra,
    })
    return env


def _compose_args(manifest: dict[str, Any]) -> list[str]:
    args = [
        'docker',
        'compose',
        '--env-file',
        '/dev/null',
        '-f',
        'docker-compose.experiments.yml',
    ]
    if (
        manifest.get('scenario') == 'api-scale'
        and manifest.get('apis') == REPLICAS
    ):
        args += [
            '-f',
            'docker-compose.experiments.api-scale.yml',
            '--profile',
            'api-scale',
        ]
    if (
        manifest.get('scenario') == 'worker-scale'
        and manifest.get('workers') == REPLICAS
    ):
        args += [
            '-f',
            'docker-compose.experiments.worker-scale.yml',
            '--profile',
            'worker-scale',
        ]
    return args + ['--project-name', manifest['project']]


def compose(
    manifest: dict[str, Any], *args: str, timeout: int = 120, **extra: str
) -> str:
    return _call(
        _compose_args(manifest) + list(args),
        env=_env(manifest, **extra),
        timeout=timeout,
    )


def _container(manifest: dict[str, Any], service: str) -> str:
    if service not in {
        *DEPENDENCIES,
        'api',
        'api2',
        'worker',
        'worker2',
        'locust',
        'collector',
    }:
        raise ValueError('service is outside the laboratory allowlist')
    container_id = compose(manifest, 'ps', '--all', '-q', service)
    if not container_id:
        raise RuntimeError(f'{service} is absent from the laboratory')
    label = _call([
        'docker',
        'inspect',
        '--format',
        '{{index .Config.Labels "com.docker.compose.project"}}',
        container_id,
    ])
    if label != manifest['project']:
        raise RuntimeError('container does not belong to this laboratory')
    return container_id


def _healthy(manifest: dict[str, Any], service: str) -> bool:
    container_id = _container(manifest, service)
    result = _call([
        'docker',
        'inspect',
        '--format',
        '{{.State.Health.Status}}',
        container_id,
    ])
    return result == 'healthy'


def wait_healthy(
    manifest: dict[str, Any], services: tuple[str, ...], seconds: int = 120
) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if all(_healthy(manifest, service) for service in services):
                return
        except RuntimeError:
            pass
        time.sleep(2)
    raise RuntimeError(f'health deadline exceeded: {services}')


def _mem_available() -> int:
    for line in Path('/proc/meminfo').read_text(encoding='ascii').splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) * 1024
    raise RuntimeError('MemAvailable is unavailable')


def _swap_used() -> int:
    info = {}
    for line in Path('/proc/meminfo').read_text(encoding='ascii').splitlines():
        if line.startswith(('SwapTotal:', 'SwapFree:')):
            key, value, _unit = line.split()
            info[key.removesuffix(':')] = int(value)
    return (info['SwapTotal'] - info['SwapFree']) * 1024


def _cpu_ticks() -> tuple[int, int]:
    parts = Path('/proc/stat').read_text(encoding='ascii').splitlines()[0]
    values = [int(part) for part in parts.split()[1:]]
    return sum(values), values[3] + values[4]


def _cpu_percent(previous: tuple[int, int], current: tuple[int, int]) -> float:
    total = current[0] - previous[0]
    idle = current[1] - previous[1]
    return 0.0 if total <= 0 else max(0.0, 100 * (total - idle) / total)


def preflight() -> dict[str, object]:
    context = _call([
        'docker',
        'context',
        'inspect',
        '--format',
        '{{.Endpoints.docker.Host}}',
    ])
    if not context.startswith('unix://'):
        raise RuntimeError('Docker context is not a local Unix socket')
    daemon = _call([
        'docker',
        'info',
        '--format',
        '{{.MemTotal}} {{.NCPU}}',
    ]).split()
    docker_memory, docker_cpus = int(daemon[0]), int(daemon[1])
    available = _mem_available()
    free = shutil.disk_usage(ROOT).free
    facts: dict[str, object] = {
        'host_memory_available_bytes': available,
        'docker_memory_bytes': docker_memory,
        'docker_cpus': docker_cpus,
        'disk_free_bytes': free,
        'swap_used_bytes': _swap_used(),
    }
    if min(available, docker_memory) < int(4.5 * GIB):
        raise RuntimeError(f'insufficient memory for laboratory: {facts}')
    if docker_cpus < MIN_DOCKER_CPUS:
        raise RuntimeError(f'insufficient CPU for laboratory: {facts}')
    if free < 5 * GIB:
        raise RuntimeError(f'insufficient disk space: {facts}')
    return facts


def _allowed_overrides(scenario: str) -> set[str]:
    allowed = {'users', 'spawn_rate', 'wait_seconds', 'max_posts'}
    if scenario in {'rabbitmq', 'azurite', 'postgres', 'worker', 'api'}:
        allowed.add('failure_seconds')
    elif scenario == 'worker-scale':
        allowed.remove('max_posts')
    else:
        allowed.update({'warmup_seconds', 'measure_seconds'})
    return allowed


def _configuration(
    scenario: str, overrides: dict[str, int] | None = None
) -> dict[str, Any]:
    config = dict(SCENARIOS[scenario])
    if overrides and set(overrides) - _allowed_overrides(scenario):
        raise ValueError('option is not supported by this scenario')
    if overrides and 'users' in overrides and 'steps' in config:
        raise ValueError('progressive users are defined by steps')
    config.update(overrides or {})
    if not 1 <= config.get('users', 1) <= MAX_USERS:
        raise ValueError('users must be between one and eight')
    if any(not 1 <= user <= MAX_USERS for user in config.get('steps', [])):
        raise ValueError('progressive steps must fit eight users')
    if not 0 < config['spawn_rate'] <= MAX_SPAWN_RATE:
        raise ValueError('spawn rate must be at most two users per second')
    if not MIN_TASK_WAIT <= config['wait_seconds'] <= MAX_TASK_WAIT:
        raise ValueError('task wait must be between two and ten seconds')
    for key, limit in (
        ('warmup_seconds', 30),
        ('measure_seconds', 180),
        ('healthy_seconds', 30),
        ('failure_seconds', 30),
        ('observe_seconds', 180),
    ):
        if key in config and not 0 <= config[key] <= limit:
            raise ValueError(f'{key} is outside the laboratory limit')
    if not 1 <= config.get('max_posts', MAX_POSTS) <= MAX_POSTS:
        raise ValueError('POST limit is outside the laboratory limit')
    if not 1 <= config.get('documents', 1) <= MAX_PREFILL:
        raise ValueError('prefill document count is outside the limit')
    return config


def _manifest(
    scenario: str,
    apis: int,
    workers: int,
    overrides: dict[str, int] | None = None,
) -> dict[str, Any]:
    if scenario not in SCENARIOS:
        raise ValueError('scenario is unknown')
    if apis not in {1, REPLICAS} or workers not in {1, REPLICAS}:
        raise ValueError('replicas must be one or two')
    if apis == REPLICAS and scenario != 'api-scale':
        raise ValueError('two APIs require the api-scale scenario')
    if workers == REPLICAS and scenario != 'worker-scale':
        raise ValueError('two workers require the worker-scale scenario')
    value = run_id()
    dirty = bool(_call(['git', 'status', '--porcelain=v1']))
    return {
        'run_id': value,
        'project': _project(value),
        'scenario': scenario,
        'configuration': _configuration(scenario, overrides),
        'apis': apis,
        'workers': workers,
        'created_at_utc': datetime.now(UTC).isoformat(),
        'commit': _call(['git', 'rev-parse', 'HEAD']),
        'working_tree_dirty': dirty,
        'uv_lock_sha256': hashlib.sha256(
            (ROOT / 'uv.lock').read_bytes()
        ).hexdigest(),
        'versions': {
            'python': sys.version.split()[0],
            'uv': _call(['uv', '--version']),
            'docker': _call(['docker', '--version']),
            'compose': _call(['docker', 'compose', 'version']),
            'locust': _call([
                'uv',
                'run',
                '--locked',
                'locust',
                '--version',
            ]).split()[1],
        },
        'fixtures': [
            {
                'name': item.name,
                'media_type': item.media_type,
                'size_bytes': len(item.data),
                'sha256': item.sha256,
            }
            for item in fixtures()
        ],
    }


def _load(value: str) -> dict[str, Any]:
    manifest = _read_json(report_dir(value) / 'manifest.json')
    if manifest['run_id'] != value or manifest['project'] != _project(value):
        raise RuntimeError('manifest does not match requested project')
    return manifest


def _prepare(manifest: dict[str, Any]) -> None:
    folder = report_dir(manifest['run_id'])
    existing = _call([
        'docker',
        'ps',
        '-aq',
        '--filter',
        f'label=com.docker.compose.project={manifest["project"]}',
    ])
    if existing:
        raise RuntimeError('a container already uses this project name')
    compose(manifest, 'config', '--quiet')
    _event(folder, 'dependencies_starting')
    compose(
        manifest,
        'up',
        '-d',
        '--wait',
        '--wait-timeout',
        '120',
        *DEPENDENCIES,
        timeout=240,
    )
    wait_healthy(manifest, DEPENDENCIES)
    compose(manifest, 'build', 'api', 'locust', timeout=600)
    compose(
        manifest,
        'run',
        '--rm',
        '--no-deps',
        'api',
        'alembic',
        'upgrade',
        'head',
        timeout=120,
    )
    compose(
        manifest,
        'run',
        '--rm',
        '--no-deps',
        'api',
        'python',
        '-m',
        'docpipe_ingestion.init_blob_storage',
    )
    base: tuple[str, ...] = ('api', 'collector')
    if manifest['scenario'] != 'worker-scale':
        base += ('worker',)
    if manifest['apis'] == REPLICAS:
        base += ('api2',)
    compose(
        manifest,
        'up',
        '-d',
        '--wait',
        '--wait-timeout',
        '120',
        *base,
        timeout=240,
    )
    wait_healthy(
        manifest,
        DEPENDENCIES + tuple(item for item in base if item != 'collector'),
    )
    manifest['image_ids'] = _image_ids(manifest)
    _save(folder / 'manifest.json', manifest)
    _event(folder, 'laboratory_ready')


def _image_ids(manifest: dict[str, Any]) -> dict[str, str]:
    images = {
        'postgres': 'postgres:17.6-bookworm',
        'rabbitmq': 'rabbitmq:4.1.4-management',
        'azurite': 'mcr.microsoft.com/azure-storage/azurite:3.35.0',
        'api_worker': manifest['project'] + '-app',
        'locust': manifest['project'] + '-locust',
    }
    return {
        name: _call([
            'docker',
            'image',
            'inspect',
            '--format',
            '{{.Id}}',
            image,
        ])
        for name, image in images.items()
    }


def _phase(folder: Path, name: str) -> None:
    _save(folder / 'phase.json', {'phase': name})
    _event(folder, 'phase', name=name)


def _resource_sample(manifest: dict[str, Any]) -> dict[str, Any]:
    folder = report_dir(manifest['run_id'])
    ids = _call([
        'docker',
        'ps',
        '-q',
        '--filter',
        f'label=com.docker.compose.project={manifest["project"]}',
    ]).splitlines()
    stats = ''
    if ids:
        stats = _call(
            [
                'docker',
                'stats',
                '--no-stream',
                '--format',
                '{{json .}}',
                *ids,
            ],
            timeout=30,
        )
    current_ticks = _cpu_ticks()
    previous_ticks = GUARD_STATE.get('cpu_ticks')
    GUARD_STATE['cpu_ticks'] = current_ticks
    sample = {
        'time_utc': datetime.now(UTC).isoformat(),
        'mem_available_bytes': _mem_available(),
        'swap_used_bytes': _swap_used(),
        'disk_free_bytes': shutil.disk_usage(ROOT).free,
        'host_cpu_percent': (
            _cpu_percent(previous_ticks, current_ticks)
            if previous_ticks is not None
            else None
        ),
        'containers': [json.loads(line) for line in stats.splitlines()],
    }
    with (folder / 'resources.jsonl').open('a') as stream:
        stream.write(json.dumps(sample) + '\n')
    return sample


def _check_outcomes(manifest: dict[str, Any], folder: Path) -> None:
    outcomes = folder / 'outcomes.jsonl'
    if outcomes.exists():
        entries = outcomes.read_text(encoding='utf-8').splitlines()
        if (
            sum(
                json.loads(line)['kind'] in {'accepted', 'post_error'}
                for line in entries
            )
            >= MAX_POSTS
        ):
            raise RuntimeError('POST count guard stopped load')
        streak = 0
        for line in reversed(entries):
            item = json.loads(line)
            if item['kind'] not in {'post_error', 'get_error'}:
                break
            if expected_failure(manifest['scenario'], item):
                break
            streak += 1
            if streak >= MAX_UNEXPECTED_STREAK:
                raise RuntimeError('unexpected HTTP error guard stopped load')


def _guard(manifest: dict[str, Any]) -> None:
    sample = _resource_sample(manifest)
    now = time.monotonic()
    generator_busy = any(
        '-locust-' in item.get('Name', '')
        and float(item.get('CPUPerc', '0%').removesuffix('%'))
        > MAX_LOCUST_CPU_PERCENT
        for item in sample['containers']
    )
    for name, bad, duration in (
        ('memory', sample['mem_available_bytes'] < int(1.5 * GIB), 10),
        (
            'cpu',
            (sample['host_cpu_percent'] or 0) > MAX_HOST_CPU_PERCENT,
            30,
        ),
        (
            'swap',
            sample['swap_used_bytes']
            > GUARD_STATE.setdefault('initial_swap', sample['swap_used_bytes'])
            + 128 * 1024 * 1024,
            30,
        ),
        ('generator_cpu', generator_busy, 30),
    ):
        if bad:
            GUARD_STATE.setdefault(name + '_since', now)
            if now - GUARD_STATE[name + '_since'] >= duration:
                raise RuntimeError(f'{name} guard stopped the experiment')
        else:
            GUARD_STATE.pop(name + '_since', None)
    if sample['disk_free_bytes'] < 2 * GIB:
        raise RuntimeError('disk guard stopped the experiment')
    folder = report_dir(manifest['run_id'])
    if (
        sum(
            path.stat().st_size for path in folder.rglob('*') if path.is_file()
        )
        > 2 * GIB
    ):
        raise RuntimeError('artifact size guard stopped the experiment')
    snapshot = folder / 'snapshot.json'
    if snapshot.exists():
        state = _read_json(snapshot)
        if state.get('pending', 0) > MAX_BACKLOG:
            raise RuntimeError('outbox backlog guard stopped the experiment')
    _check_outcomes(manifest, folder)


def _wait(
    manifest: dict[str, Any],
    seconds: int,
    process: subprocess.Popen[str] | None = None,
) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        _guard(manifest)
        if process is not None and process.poll() is not None:
            if process.returncode:
                raise RuntimeError('Locust exited with an error')
            return
        time.sleep(min(5, max(0, deadline - time.monotonic())))


def _drain(manifest: dict[str, Any], seconds: int = 180) -> None:
    folder = report_dir(manifest['run_id'])
    deadline = time.monotonic() + seconds
    time.sleep(6)
    while time.monotonic() < deadline:
        _guard(manifest)
        snapshot = folder / 'snapshot.json'
        if snapshot.exists():
            state = _read_json(snapshot)
            if state.get('pending') == 0 and not state.get(
                'database_unavailable'
            ):
                return
        time.sleep(5)
    raise RuntimeError('outbox did not drain within the observation window')


def _locust(
    manifest: dict[str, Any],
    *,
    users: int,
    warmup: int,
    seconds: int,
    prefix: str,
) -> subprocess.Popen[str]:
    config = manifest['configuration']
    targets = 'http://api:8000'
    if manifest['apis'] == REPLICAS:
        targets += ',http://api2:8000'
    env = _env(
        manifest,
        LAB_USERS=str(users),
        LAB_SPAWN_RATE=str(config['spawn_rate']),
        LAB_WAIT_SECONDS=str(config['wait_seconds']),
        LAB_WARMUP=str(warmup),
        LAB_RUN_TIME=f'{seconds}s',
        LAB_CSV_PREFIX=prefix,
        LAB_MAX_POSTS=str(
            config.get('max_posts', config.get('documents', MAX_POSTS))
        ),
        LAB_TARGETS=targets,
    )
    command = _compose_args(manifest) + [
        'up',
        '--no-deps',
        '--force-recreate',
        '--exit-code-from',
        'locust',
        'locust',
    ]
    log = (report_dir(manifest['run_id']) / f'{prefix}.log').open('w')
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    log.close()
    return process


def _stop_locust(
    manifest: dict[str, Any], process: subprocess.Popen[str] | None
) -> None:
    try:
        _container(manifest, 'locust')
    except RuntimeError:
        pass
    else:
        compose(manifest, 'stop', '--timeout', '10', 'locust', timeout=30)
    if process is not None:
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)


def _restore(manifest: dict[str, Any], service: str) -> None:
    folder = report_dir(manifest['run_id'])
    _container(manifest, service)
    compose(
        manifest,
        'up',
        '-d',
        '--wait',
        '--wait-timeout',
        '120',
        service,
        timeout=180,
    )
    wait_healthy(manifest, (service, 'api'))
    _event(folder, 'dependency_restored', service=service)
    if service in {'rabbitmq', 'postgres'}:
        compose(
            manifest,
            'up',
            '-d',
            '--force-recreate',
            '--wait',
            '--wait-timeout',
            '120',
            'worker',
            timeout=180,
        )
        wait_healthy(manifest, ('worker',))
        _event(folder, 'worker_restarted')


def _failure(manifest: dict[str, Any], process: subprocess.Popen[str]) -> None:
    scenario = manifest['scenario']
    folder = report_dir(manifest['run_id'])
    config = manifest['configuration']
    _phase(folder, 'healthy')
    _wait(manifest, config['healthy_seconds'], process)
    if process.poll() is not None:
        raise RuntimeError('Locust stopped before the planned failure')
    outcomes = folder / 'outcomes.jsonl'
    if not outcomes.exists() or not any(
        json.loads(line).get('kind') == 'accepted'
        for line in outcomes.read_text(encoding='utf-8').splitlines()
    ):
        raise RuntimeError('no document was accepted before the failure')
    service = 'postgres' if scenario == 'postgres' else scenario
    required = DEPENDENCIES + ('api', 'worker')
    wait_healthy(manifest, required)
    _container(manifest, service)
    _event(folder, 'failure_start', service=service)
    _phase(folder, 'failure')
    try:
        stop_seconds = 90 if service == 'worker' else 10
        compose(
            manifest,
            'stop',
            '--timeout',
            str(stop_seconds),
            service,
            timeout=stop_seconds + 30,
        )
        _event(folder, 'service_stopped', service=service)
        _wait(manifest, config['failure_seconds'], process)
    finally:
        _restore(manifest, service)
    _phase(folder, 'recovery')
    _wait(manifest, config['observe_seconds'], process)


def _normal(manifest: dict[str, Any]) -> None:
    folder = report_dir(manifest['run_id'])
    config = manifest['configuration']
    steps = config['steps'] if 'steps' in config else [config['users']]
    for index, users in enumerate(steps, 1):
        _phase(folder, 'warmup')
        process = _locust(
            manifest,
            users=users,
            warmup=config['warmup_seconds'],
            seconds=config['warmup_seconds'] + config['measure_seconds'],
            prefix=f'locust-{index}',
        )
        try:
            _wait(manifest, config['warmup_seconds'], process)
            _phase(folder, 'measure')
            _wait(manifest, config['measure_seconds'] + 20, process)
            if process.poll() is None:
                raise RuntimeError('Locust exceeded its run deadline')
        finally:
            _stop_locust(manifest, process)
    _phase(folder, 'drain')
    _drain(manifest)


def _worker_scale(manifest: dict[str, Any]) -> None:
    folder = report_dir(manifest['run_id'])
    config = manifest['configuration']
    _phase(folder, 'prefill')
    process = _locust(
        manifest,
        users=config['users'],
        warmup=0,
        seconds=360,
        prefix='prefill',
    )
    try:
        _wait(manifest, 370, process)
        if process.poll() is None:
            raise RuntimeError('prefill did not finish')
    finally:
        _stop_locust(manifest, process)
    deadline = time.monotonic() + 20
    pending = 0
    while time.monotonic() < deadline:
        snapshot = folder / 'snapshot.json'
        if snapshot.exists():
            pending = _read_json(snapshot).get('pending', 0)
            if pending >= config['documents']:
                break
        time.sleep(2)
    if pending < config['documents']:
        raise RuntimeError('prefill did not create the requested backlog')
    workers = (
        ('worker', 'worker2')
        if manifest['workers'] == REPLICAS
        else ('worker',)
    )
    _event(folder, 'worker_drain_started', workers=len(workers))
    _phase(folder, 'drain')
    compose(
        manifest,
        'up',
        '-d',
        '--wait',
        '--wait-timeout',
        '120',
        *workers,
        timeout=180,
    )
    _drain(manifest, config['observe_seconds'])


def _audit(manifest: dict[str, Any], *, drain: bool = False) -> dict[str, Any]:
    arguments = [
        'run',
        '--rm',
        '--no-deps',
        'api',
        'python',
        '/app/experiments/audit.py',
        manifest['run_id'],
    ]
    if drain:
        arguments.append('--drain')
    result = cast(
        dict[str, Any],
        json.loads(compose(manifest, *arguments, timeout=300)),
    )
    folder = report_dir(manifest['run_id'])
    _save(folder / ('audit-drained.json' if drain else 'audit.json'), result)
    return result


def _existing_services(manifest: dict[str, Any]) -> list[str]:
    services = []
    for service in (
        *DEPENDENCIES,
        'api',
        'api2',
        'worker',
        'worker2',
        'locust',
        'collector',
    ):
        try:
            _container(manifest, service)
        except RuntimeError:
            continue
        services.append(service)
    return services


def _logs(manifest: dict[str, Any]) -> None:
    services = _existing_services(manifest)
    if not services:
        return
    folder = report_dir(manifest['run_id'])
    try:
        logs = compose(manifest, 'logs', '--no-color', *services)
        (folder / 'service-logs.txt').write_text(logs + '\n')
    except RuntimeError:
        _event(folder, 'log_collection_failed')


def _stop_all(manifest: dict[str, Any]) -> None:
    services = _existing_services(manifest)
    if services:
        compose(manifest, 'stop', '--timeout', '90', *services, timeout=180)


def execute(
    scenario: str,
    *,
    apis: int = 1,
    workers: int = 1,
    overrides: dict[str, int] | None = None,
) -> Path:
    manifest = _manifest(scenario, apis, workers, overrides)
    folder = report_dir(manifest['run_id'])
    folder.mkdir(parents=True, exist_ok=False)
    print(folder, flush=True)
    _save(folder / 'manifest.json', manifest)
    _event(folder, 'preflight_start')
    process = None
    failure_service = None
    try:  # noqa: PLW0717 - experiment steps share restoration logic
        manifest['resources'] = preflight()
        _save(folder / 'manifest.json', manifest)
        _event(folder, 'preflight_passed')
        _prepare(manifest)
        if scenario == 'worker-scale':
            _worker_scale(manifest)
        elif scenario in {'rabbitmq', 'azurite', 'postgres', 'worker', 'api'}:
            config = manifest['configuration']
            duration = (
                config['healthy_seconds']
                + config['failure_seconds']
                + config['observe_seconds']
                + (120 if scenario == 'worker' else 30)
            )
            process = _locust(
                manifest,
                users=config['users'],
                warmup=0,
                seconds=duration,
                prefix='locust-failure',
            )
            failure_service = (
                'postgres' if scenario == 'postgres' else scenario
            )
            _failure(manifest, process)
        else:
            _normal(manifest)
        _stop_locust(manifest, process)
        process = None
        result = _audit(manifest)
        if result['pending'] or result['exhausted']:
            _event(folder, 'recovery_incomplete', pending=result['pending'])
        else:
            _event(folder, 'experiment_complete')
    except (Exception, KeyboardInterrupt) as error:
        _event(folder, 'experiment_interrupted', reason=type(error).__name__)
        if str(error).startswith('insufficient '):
            _save(folder / 'blocked.json', {'reason': str(error)})
        if failure_service is not None:
            try:
                if not _healthy(manifest, failure_service):
                    _restore(manifest, failure_service)
            except Exception:
                _event(
                    folder, 'automatic_restore_failed', service=failure_service
                )
        raise
    finally:
        try:
            _stop_locust(manifest, process)
            _logs(manifest)
            _stop_all(manifest)
        except Exception:
            _event(folder, 'automatic_stop_failed')
        summarize(folder)
    return folder


def main() -> None:  # noqa: PLR0912 - CLI routes independent subcommands
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('preflight')
    run = commands.add_parser('run')
    run.add_argument('scenario', choices=sorted(SCENARIOS))
    run.add_argument('--apis', type=int, choices=(1, 2), default=1)
    run.add_argument('--workers', type=int, choices=(1, 2), default=1)
    for flag in (
        'users',
        'spawn_rate',
        'wait_seconds',
        'warmup_seconds',
        'measure_seconds',
        'failure_seconds',
        'max_posts',
    ):
        run.add_argument('--' + flag.replace('_', '-'), type=int)
    for action in ('recover', 'audit', 'stop'):
        sub = commands.add_parser(action)
        sub.add_argument('run_id')
        if action == 'audit':
            sub.add_argument('--drain', action='store_true')
    args = parser.parse_args()
    if args.action == 'preflight':
        print(json.dumps(preflight(), indent=2))
    elif args.action == 'run':
        overrides = {
            key: value
            for key, value in vars(args).items()
            if key
            in {
                'users',
                'spawn_rate',
                'wait_seconds',
                'warmup_seconds',
                'measure_seconds',
                'failure_seconds',
                'max_posts',
            }
            and value is not None
        }
        print(
            execute(
                args.scenario,
                apis=args.apis,
                workers=args.workers,
                overrides=overrides,
            )
        )
    else:
        manifest = _load(args.run_id)
        if args.action == 'audit':
            print(json.dumps(_audit(manifest, drain=args.drain), indent=2))
            summarize(report_dir(args.run_id))
        elif args.action == 'recover':
            for service in DEPENDENCIES:
                _container(manifest, service)
            for service in DEPENDENCIES:
                compose(manifest, 'up', '-d', '--wait', service, timeout=180)
            targets = ['api', 'worker']
            if manifest['apis'] == REPLICAS:
                targets.append('api2')
            if manifest['workers'] == REPLICAS:
                targets.append('worker2')
            for service in targets:
                if compose(manifest, 'ps', '--all', '-q', service):
                    _container(manifest, service)
            compose(manifest, 'up', '-d', '--wait', *targets, timeout=180)
            wait_healthy(manifest, DEPENDENCIES + tuple(targets))
            _event(report_dir(args.run_id), 'manual_recovery_complete')
            print(json.dumps(_audit(manifest), indent=2))
        elif args.action == 'stop':
            _stop_all(manifest)
            _event(report_dir(args.run_id), 'manual_stop')


if __name__ == '__main__':

    def stop_signal(signum: int, frame: object) -> None:
        del signum, frame
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_signal)
    main()
