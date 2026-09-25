"""Verify laboratory boundaries and public contracts without Docker/network."""

import json
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from experiments import lab
from experiments.contracts import accepted, error_response, metadata
from experiments.fixtures import fixtures
from experiments.summarize import expected_failure, summarize

FIXTURE_COUNT = 6


def test_fixtures_are_small_deterministic_documents() -> None:
    first = fixtures()
    assert first == fixtures()
    assert len(first) == FIXTURE_COUNT
    assert len({item.name for item in first}) == len(first)
    assert all(0 < len(item.data) <= 64 * 1024 for item in first)
    assert all(item.data.startswith(b'%PDF-') for item in first[:2])
    assert all(item.data.endswith(b'%%EOF\n') for item in first[:2])
    assert all(
        item.data.startswith(b'\x89PNG\r\n\x1a\n') for item in first[2:4]
    )
    assert all(
        item.data.startswith(b'\xff\xd8\xff')
        and item.data.endswith(b'\xff\xd9')
        for item in first[4:]
    )


def test_acceptance_and_metadata_detect_false_success() -> None:
    document_id, correlation_id = uuid4(), uuid4()
    response = {
        'document_id': str(document_id),
        'correlation_id': str(correlation_id),
        'status': 'STORED',
        'received_at': datetime(2026, 9, 24, tzinfo=UTC).isoformat(),
    }
    assert accepted(response, str(correlation_id)) == (
        document_id,
        correlation_id,
    )
    with pytest.raises(ValueError, match='correlation'):
        accepted(response, str(uuid4()))
    fixture = fixtures()[0]
    body = {
        'document_id': str(document_id),
        'original_name': 'run-0001-a.pdf',
        'media_type': fixture.media_type,
        'size_bytes': len(fixture.data),
        'sha256': fixture.sha256,
        'correlation_id': str(correlation_id),
        'status': 'PUBLISHED',
    }
    metadata(
        body,
        document_id=document_id,
        name='run-0001-a.pdf',
        fixture=fixture,
        correlation_id=correlation_id,
    )
    with pytest.raises(ValueError, match='storage'):
        metadata(
            body | {'storage_key': 'private.blob'},
            document_id=document_id,
            name='run-0001-a.pdf',
            fixture=fixture,
            correlation_id=correlation_id,
        )
    assert (
        error_response(
            {
                'error': {
                    'code': 'storage_unavailable',
                    'message': 'Unavailable',
                    'correlation_id': str(correlation_id),
                }
            },
            str(correlation_id),
        )
        == 'storage_unavailable'
    )


def test_run_id_rejects_traversal_and_foreign_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for invalid in ('../other', 'docpipe-lab-other', 'lab-20260924t120000-x'):
        with pytest.raises(ValueError, match='run ID'):
            lab.report_dir(invalid)
    manifest = {
        'run_id': 'lab-20260924t120000-1234abcd',
        'project': 'docpipe-lab-20260924t120000-1234abcd',
    }
    monkeypatch.setattr(lab, 'compose', lambda *_args, **_kwargs: 'container')
    monkeypatch.setattr(
        lab, '_call', lambda *_args, **_kwargs: 'other-project'
    )
    with pytest.raises(RuntimeError, match='does not belong'):
        lab._container(manifest, 'rabbitmq')
    with pytest.raises(ValueError, match='allowlist'):
        lab._container(manifest, 'some-other-container')


def test_preflight_blocks_before_starting_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def command(args: list[str], **_kwargs: object) -> str:
        if args[1] == 'context':
            return 'unix:///var/run/docker.sock'
        if args[1] == 'info':
            return f'{3 * lab.GIB} 4'
        raise AssertionError('unexpected command')

    monkeypatch.setattr(lab, '_call', command)
    monkeypatch.setattr(lab, '_mem_available', lambda: 6 * lab.GIB)
    monkeypatch.setattr(lab, '_swap_used', lambda: 0)
    monkeypatch.setattr(
        shutil,
        'disk_usage',
        lambda _path: type('Disk', (), {'free': 10 * lab.GIB})(),
    )
    with pytest.raises(RuntimeError, match='insufficient memory'):
        lab.preflight()


def test_preflight_rejects_remote_docker_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        lab, '_call', lambda *_args, **_kwargs: 'tcp://remote:2375'
    )
    with pytest.raises(RuntimeError, match='local Unix socket'):
        lab.preflight()


def test_resource_guard_stops_sustained_low_memory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lab.GUARD_STATE.clear()
    monkeypatch.setattr(lab, 'report_dir', lambda _run_id: tmp_path)
    monkeypatch.setattr(
        lab,
        '_resource_sample',
        lambda _manifest: {
            'mem_available_bytes': lab.GIB,
            'host_cpu_percent': 0,
            'swap_used_bytes': 0,
            'disk_free_bytes': 10 * lab.GIB,
            'containers': [],
        },
    )
    times = iter((0.0, 11.0))
    monkeypatch.setattr(time, 'monotonic', lambda: next(times))
    manifest = {'run_id': 'lab-20260924t120000-1234abcd', 'scenario': 'smoke'}
    lab._guard(manifest)
    with pytest.raises(RuntimeError, match='memory guard'):
        lab._guard(manifest)
    lab.GUARD_STATE.clear()


def test_recovery_targets_only_broker_and_worker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(lab, 'report_dir', lambda _run_id: tmp_path)
    monkeypatch.setattr(lab, '_container', lambda *_args: 'owned-container')

    def fake_compose(
        _manifest: dict[str, object], *args: str, **_kwargs: object
    ) -> str:
        calls.append(args)
        return ''

    monkeypatch.setattr(
        lab,
        'compose',
        fake_compose,
    )
    monkeypatch.setattr(lab, 'wait_healthy', lambda *_args: None)
    manifest = {
        'run_id': 'lab-20260924t120000-1234abcd',
        'scenario': 'rabbitmq',
    }
    lab._restore(manifest, 'rabbitmq')
    assert calls[0][-1] == 'rabbitmq'
    assert calls[1][-1] == 'worker'
    assert len(calls) == lab.REPLICAS


def test_progressive_profile_runs_all_bounded_stages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    users_seen: list[int] = []

    class Finished:
        @staticmethod
        def poll() -> int:
            return 0

    monkeypatch.setattr(lab, 'report_dir', lambda _run_id: tmp_path)
    monkeypatch.setattr(lab, '_phase', lambda *_args: None)
    monkeypatch.setattr(lab, '_wait', lambda *_args: None)
    monkeypatch.setattr(lab, '_drain', lambda *_args: None)
    monkeypatch.setattr(lab, '_stop_locust', lambda *_args: None)

    def fake_locust(
        _manifest: dict[str, object], *, users: int, **_kwargs: object
    ) -> Finished:
        users_seen.append(users)
        return Finished()

    monkeypatch.setattr(lab, '_locust', fake_locust)
    lab._normal({
        'run_id': 'lab-20260924t120000-1234abcd',
        'configuration': lab.SCENARIOS['progressive'],
    })
    assert users_seen == [2, 4, 8]


def test_failure_classification_is_limited_to_dependency_window() -> None:
    unavailable = {
        'phase': 'failure',
        'kind': 'post_error',
        'status_code': 503,
    }
    assert expected_failure('azurite', unavailable)
    assert expected_failure('postgres', unavailable)
    assert not expected_failure('rabbitmq', unavailable)
    assert not expected_failure('azurite', unavailable | {'phase': 'recovery'})
    assert not expected_failure('postgres', unavailable | {'status_code': 500})


def test_summary_keeps_http_acceptance_separate_from_publication(
    tmp_path: Path,
) -> None:
    (tmp_path / 'manifest.json').write_text(
        json.dumps({
            'run_id': 'lab-20260924t120000-1234abcd',
            'scenario': 'rabbitmq',
        })
    )
    (tmp_path / 'outcomes.jsonl').write_text(
        json.dumps({
            'kind': 'accepted',
            'phase': 'measure',
            'document_id': 'doc-1',
        })
        + '\n'
    )
    (tmp_path / 'audit.json').write_text(
        json.dumps({
            'documents': [{'document_id': 'doc-1', 'blob_verified': True}],
            'pending': 1,
            'exhausted': 0,
        })
    )
    result = summarize(tmp_path)
    assert result['documents_accepted_http'] == 1
    assert result['audit']['pending'] == 1
    assert result['accepted_without_persisted_document'] == []
    assert result['locust_measurements'] == {}


def test_publication_delay_is_labeled_as_estimate(
    tmp_path: Path,
) -> None:
    (tmp_path / 'manifest.json').write_text(
        json.dumps({
            'run_id': 'lab-20260924t120000-1234abcd',
            'scenario': 'baseline',
            'configuration': {'measure_seconds': 180},
        })
    )
    (tmp_path / 'outcomes.jsonl').write_text(
        json.dumps({
            'kind': 'accepted',
            'phase': 'measure',
            'stage': 'locust-1',
            'document_id': 'doc-1',
            'time_utc': '2026-09-24T12:00:00+00:00',
        })
        + '\n'
    )
    (tmp_path / 'audit.json').write_text(
        json.dumps({
            'documents': [
                {
                    'document_id': 'doc-1',
                    'blob_verified': True,
                    'published_at': '2026-09-24T11:59:59+00:00',
                }
            ],
            'pending': 0,
        })
    )
    result = summarize(tmp_path)
    estimate = result['acceptance_to_publication_estimate']
    assert estimate['kind'] == 'estimate'
    assert estimate['negative_count'] == 1
    assert estimate['p50_seconds'] == -1
    assert result['documents_accepted_per_measure_second'] == {
        'locust-1': 1 / 180,
    }
