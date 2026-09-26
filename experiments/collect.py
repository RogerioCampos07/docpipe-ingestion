"""Persist bounded snapshots without a telemetry backend."""

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from sqlalchemy import func, select

from docpipe_ingestion.infrastructure.database.engine import (
    create_database_engine,
    create_session_factory,
)
from docpipe_ingestion.infrastructure.database.models import OutboxEventModel
from docpipe_ingestion.infrastructure.settings import Settings

REPORTS = Path('/reports')
SETTINGS = Settings()
ENGINE = create_database_engine(SETTINGS)
FACTORY = create_session_factory(ENGINE)


def _backlog() -> dict[str, int]:
    with FACTORY() as session:
        pending = session.scalar(
            select(func.count())
            .select_from(OutboxEventModel)
            .where(OutboxEventModel.published_at.is_(None))
        )
        exhausted = session.scalar(
            select(func.count())
            .select_from(OutboxEventModel)
            .where(
                OutboxEventModel.published_at.is_(None),
                OutboxEventModel.attempts >= SETTINGS.outbox_max_attempts,
            )
        )
    return {'pending': pending or 0, 'exhausted': exhausted or 0}


def _metrics() -> dict[str, str | None]:
    result = {}
    for service, port in (
        ('api', 8000),
        ('api2', 8000),
        ('worker', 9001),
        ('worker2', 9002),
    ):
        try:
            with urlopen(
                f'http://{service}:{port}/metrics', timeout=2
            ) as response:
                result[service] = response.read().decode()
        except OSError, URLError:
            result[service] = None
    return result


def main() -> None:
    try:
        while True:
            record: dict[str, object] = {
                'time_utc': datetime.now(UTC).isoformat(),
            }
            try:
                record.update(_backlog())
            except Exception:
                record['database_unavailable'] = True
            record['metrics'] = _metrics()
            with (REPORTS / 'service-samples.jsonl').open('a') as stream:
                stream.write(json.dumps(record) + '\n')
            summary = {
                key: value for key, value in record.items() if key != 'metrics'
            }
            temporary = REPORTS / 'snapshot.tmp'
            temporary.write_text(json.dumps(summary))
            temporary.replace(REPORTS / 'snapshot.json')
            time.sleep(5)
    finally:
        ENGINE.dispose()


if __name__ == '__main__':
    main()
