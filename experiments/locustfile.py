"""Bounded HTTP tasks; no consumer of the RabbitMQ business queue."""

import itertools
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import gevent
from locust import HttpUser, between, events, task

from experiments.contracts import accepted, error_response, metadata
from experiments.fixtures import Fixture, fixtures

RUN_ID = os.environ['LAB_RUN_ID']
STAGE = os.environ.get('LAB_CSV_PREFIX', 'locust')
TARGETS = tuple(os.environ.get('LAB_TARGETS', 'http://api:8000').split(','))
if not TARGETS or any(
    target not in {'http://api:8000', 'http://api2:8000'} for target in TARGETS
):
    raise ValueError('LAB_TARGETS must contain only laboratory API services')
DOCUMENTS = fixtures()
WAIT = float(os.environ.get('LAB_WAIT_SECONDS', '2'))
WARMUP = int(os.environ.get('LAB_WARMUP', '10'))
MAX_POSTS = int(os.environ.get('LAB_MAX_POSTS', '2000'))
REPORTS = Path('/reports')
TARGET_CYCLE = itertools.cycle(TARGETS)
FIXTURE_CYCLE = itertools.cycle(DOCUMENTS)
STATE = {'started': time.monotonic(), 'posts': 0}
HTTP_ACCEPTED = 202
HTTP_OK = 200


def _phase() -> str:
    phase_file = REPORTS / 'phase.json'
    if phase_file.exists():
        try:
            return str(json.loads(phase_file.read_text())['phase'])
        except OSError, ValueError, KeyError:
            return 'unknown'
    return (
        'warmup' if time.monotonic() - STATE['started'] < WARMUP else 'measure'
    )


def _record(kind: str, **fields: object) -> None:
    record = {
        'time_utc': datetime.now(UTC).isoformat(),
        'phase': _phase(),
        'stage': STAGE,
        'kind': kind,
        **fields,
    }
    with (REPORTS / 'outcomes.jsonl').open('a') as stream:
        stream.write(json.dumps(record, sort_keys=True) + '\n')


@events.test_start.add_listener
def _test_start(environment, **kwargs) -> None:  # type: ignore[no-untyped-def]
    del kwargs
    STATE['started'] = time.monotonic()
    if WARMUP:
        gevent.spawn_later(WARMUP, environment.stats.clear_all)


class IngestionUser(HttpUser):
    wait_time = between(WAIT, WAIT)

    @task
    def upload_and_read(self) -> None:
        if STATE['posts'] >= MAX_POSTS:
            self.environment.runner.quit()
            return
        STATE['posts'] += 1
        number = STATE['posts']
        fixture: Fixture = next(FIXTURE_CYCLE)
        target = next(TARGET_CYCLE)
        name = f'{RUN_ID}-{number:06d}-{fixture.name}'
        document_id: UUID | None = None
        try:  # noqa: PLW0717 - validation belongs to this HTTP request
            with self.client.post(
                f'{target}/v1/documents',
                files={'file': (name, fixture.data, fixture.media_type)},
                name='POST /v1/documents',
                timeout=15,
                catch_response=True,
            ) as response:
                code = response.status_code
                if code == HTTP_ACCEPTED:
                    document_id, correlation = accepted(
                        response.json(),
                        response.headers.get('X-Correlation-ID'),
                    )
                    response.success()
                    _record(
                        'accepted',
                        document_id=str(document_id),
                        correlation_id=str(correlation),
                        fixture=fixture.name,
                        name=name,
                        target=target,
                        size=len(fixture.data),
                        sha256=fixture.sha256,
                        status_code=code,
                    )
                elif code == 0:
                    response.failure('connection or timeout')
                    _record(
                        'post_error',
                        error='connection_or_timeout',
                        target=target,
                    )
                else:
                    error_code = error_response(
                        response.json(),
                        response.headers.get('X-Correlation-ID'),
                    )
                    response.failure(f'unexpected HTTP {code}')
                    _record(
                        'post_error',
                        status_code=code,
                        target=target,
                        fixture=fixture.name,
                        error_code=error_code,
                    )
        except OSError as error:
            _record('post_error', error=type(error).__name__, target=target)
            return
        except (ValueError, KeyError) as error:
            _record(
                'post_error',
                error=type(error).__name__,
                invalid_contract=True,
                target=target,
            )
            return
        if document_id is None:
            return
        read_target = (
            TARGETS[1]
            if len(TARGETS) > 1 and target == TARGETS[0]
            else TARGETS[0]
        )
        try:  # noqa: PLW0717 - validation belongs to this HTTP request
            with self.client.get(
                f'{read_target}/v1/documents/{document_id}',
                name='GET /v1/documents/{document_id}',
                timeout=15,
                catch_response=True,
            ) as response:
                code = response.status_code
                if code == HTTP_OK:
                    metadata(
                        response.json(),
                        document_id=document_id,
                        name=name,
                        fixture=fixture,
                        correlation_id=correlation,
                    )
                    response.success()
                    _record('read_ok', status_code=code, target=read_target)
                elif code == 0:
                    response.failure('connection or timeout')
                    _record(
                        'get_error',
                        error='connection_or_timeout',
                        target=read_target,
                    )
                else:
                    error_code = error_response(
                        response.json(),
                        response.headers.get('X-Correlation-ID'),
                    )
                    response.failure(f'unexpected HTTP {code}')
                    _record(
                        'get_error',
                        status_code=code,
                        error_code=error_code,
                        target=read_target,
                    )
        except OSError as error:
            _record(
                'get_error', error=type(error).__name__, target=read_target
            )
        except (ValueError, KeyError) as error:
            _record(
                'get_error',
                error=type(error).__name__,
                invalid_contract=True,
                target=read_target,
            )
