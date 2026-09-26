"""Summarize raw local evidence without inventing missing measurements."""

import argparse
import csv
import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, cast

HTTP_UNAVAILABLE = 503
RUN_PATTERN = re.compile(r'lab-[0-9]{8}t[0-9]{6}-[0-9a-f]{8}')


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding='utf-8')))


def _lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding='utf-8').splitlines()
        if line
    ]


def expected_failure(scenario: str, item: dict[str, Any]) -> bool:
    if item.get('invalid_contract'):
        return False
    if item['phase'] != 'failure':
        return False
    if item['kind'] == 'post_error':
        return scenario in {'azurite', 'postgres', 'api'} and (
            item.get('status_code') == HTTP_UNAVAILABLE or 'error' in item
        )
    if item['kind'] == 'get_error':
        return scenario in {'postgres', 'api'} and (
            item.get('status_code') == HTTP_UNAVAILABLE or 'error' in item
        )
    return False


def _stats(folder: Path) -> dict[str, Any]:
    stats = {}
    for path in sorted(folder.glob('locust-*_stats.csv')):
        with path.open(newline='', encoding='utf-8') as stream:
            rows = list(csv.DictReader(stream))
        stats[path.name] = [
            {
                'method': row.get('Type'),
                'name': row.get('Name'),
                'requests': row.get('Request Count'),
                'failures': row.get('Failure Count'),
                'rps': row.get('Requests/s'),
                'p50_ms': row.get('50%'),
                'p95_ms': row.get('95%'),
                'p99_ms': row.get('99%'),
            }
            for row in rows
            if row.get('Name') != 'Aggregated'
        ]
    return stats


def _accepted_rate(
    accepted: list[dict[str, Any]], manifest: dict[str, Any]
) -> dict[str, float] | None:
    duration = manifest.get('configuration', {}).get('measure_seconds')
    if not duration:
        return None
    measured = Counter(
        item.get('stage', 'locust')
        for item in accepted
        if item['phase'] == 'measure'
    )
    return {stage: count / duration for stage, count in measured.items()}


def _publication_estimate(
    accepted: list[dict[str, Any]],
    audit: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if audit is None:
        return None
    responses = {
        item['document_id']: datetime.fromisoformat(item['time_utc'])
        for item in accepted
        if 'time_utc' in item
    }
    differences = sorted(
        (
            datetime.fromisoformat(record['published_at'])
            - responses[record['document_id']]
        ).total_seconds()
        for record in audit['documents']
        if record.get('published_at') is not None
        and record['document_id'] in responses
    )
    if not differences:
        return None

    def percentile(percent: int) -> float:
        index = max(0, math.ceil(len(differences) * percent / 100) - 1)
        return differences[index]

    return {
        'kind': 'estimate',
        'definition': 'outbox attempt start minus client-recorded HTTP 202',
        'count': len(differences),
        'negative_count': sum(value < 0 for value in differences),
        'p50_seconds': percentile(50),
        'p95_seconds': percentile(95),
        'p99_seconds': percentile(99),
    }


def _backlog_recovery(
    timeline: list[dict[str, Any]],
    samples: list[dict[str, Any]],
) -> float | None:
    failures = [item for item in timeline if item['event'] == 'failure_start']
    restored = [
        item
        for item in timeline
        if item['event'] in {'dependency_restored', 'worker_restarted'}
    ]
    if not failures or not restored:
        return None
    failure_at = datetime.fromisoformat(failures[-1]['time_utc'])
    restored_at = datetime.fromisoformat(restored[-1]['time_utc'])
    had_backlog = any(
        item.get('pending', 0) > 0
        and datetime.fromisoformat(item['time_utc']) >= failure_at
        for item in samples
    )
    if not had_backlog:
        return None
    for item in samples:
        observed_at = datetime.fromisoformat(item['time_utc'])
        if (
            observed_at >= restored_at
            and item.get('pending') == 0
            and not item.get('database_unavailable')
        ):
            return (observed_at - restored_at).total_seconds()
    return None


def summarize(folder: Path) -> dict[str, Any]:
    manifest = _json(folder / 'manifest.json')
    outcomes = _lines(folder / 'outcomes.jsonl')
    timeline = _lines(folder / 'timeline.jsonl')
    resources = _lines(folder / 'resources.jsonl')
    service_samples = _lines(folder / 'service-samples.jsonl')
    audit_path = folder / 'audit.json'
    audit = _json(audit_path) if audit_path.exists() else None
    errors = [item for item in outcomes if item['kind'].endswith('_error')]
    accepted = [item for item in outcomes if item['kind'] == 'accepted']
    samples = [
        sample['mem_available_bytes']
        for sample in resources
        if 'mem_available_bytes' in sample
    ]
    swap = [
        sample['swap_used_bytes']
        for sample in resources
        if 'swap_used_bytes' in sample
    ]
    cpu = [
        sample['host_cpu_percent']
        for sample in resources
        if sample.get('host_cpu_percent') is not None
    ]
    output = {
        'run_id': manifest['run_id'],
        'scenario': manifest['scenario'],
        'terminal_events': [item['event'] for item in timeline[-4:]],
        'http_requests_observed': len(outcomes),
        'documents_accepted_http': len(accepted),
        'accepted_by_phase': dict(Counter(item['phase'] for item in accepted)),
        'documents_accepted_per_measure_second': _accepted_rate(
            accepted, manifest
        ),
        'acceptance_to_publication_estimate': _publication_estimate(
            accepted, audit
        ),
        'sampled_backlog_recovery_seconds': _backlog_recovery(
            timeline, service_samples
        ),
        'errors_expected_in_failure_window': sum(
            expected_failure(manifest['scenario'], item) for item in errors
        ),
        'errors_unexpected_or_uncertain': sum(
            not expected_failure(manifest['scenario'], item) for item in errors
        ),
        'errors_by_phase': dict(Counter(item['phase'] for item in errors)),
        'locust_measurements': _stats(folder),
        'host_min_memory_available_bytes': min(samples) if samples else None,
        'host_max_swap_used_bytes': max(swap) if swap else None,
        'host_max_cpu_percent': max(cpu) if cpu else None,
        'host_mean_cpu_percent': mean(cpu) if cpu else None,
        'audit': {
            key: value for key, value in audit.items() if key != 'documents'
        }
        if audit is not None
        else None,
    }
    if audit is not None:
        accepted_ids = {item['document_id'] for item in accepted}
        persisted_ids = {item['document_id'] for item in audit['documents']}
        output['accepted_without_persisted_document'] = sorted(
            accepted_ids - persisted_ids
        )
        output['persisted_without_recorded_http_acceptance'] = sorted(
            persisted_ids - accepted_ids
        )
        output['blobs_with_invalid_integrity'] = sum(
            not item['blob_verified'] for item in audit['documents']
        )
    (folder / 'summary.json').write_text(
        json.dumps(output, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    args = parser.parse_args()
    if RUN_PATTERN.fullmatch(args.run_id) is None:
        parser.error('invalid laboratory run ID')
    root = Path(__file__).resolve().parents[1] / 'artifacts/experiments'
    print(json.dumps(summarize(root / args.run_id), indent=2))


if __name__ == '__main__':
    main()
