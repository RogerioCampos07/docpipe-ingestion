"""Read-only consistency report, with optional drain of the isolated queue."""

import argparse
import hashlib
import json
from collections import Counter

import pika  # type: ignore[import-untyped]
from azure.storage.blob import BlobServiceClient
from sqlalchemy import select

from docpipe_ingestion.application.events import DocumentReceivedV1
from docpipe_ingestion.infrastructure.database.engine import (
    create_database_engine,
    create_session_factory,
)
from docpipe_ingestion.infrastructure.database.models import (
    DocumentModel,
    OutboxEventModel,
)
from docpipe_ingestion.infrastructure.settings import Settings


def _database(run_id: str, settings: Settings) -> tuple[list, int]:
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            rows = session.execute(
                select(DocumentModel, OutboxEventModel)
                .outerjoin(
                    OutboxEventModel,
                    OutboxEventModel.aggregate_id == DocumentModel.id,
                )
                .where(DocumentModel.original_name.startswith(run_id + '-'))
            ).all()
            document_total = session.query(DocumentModel).count()
    finally:
        engine.dispose()
    return rows, document_total


def _objects(
    rows: list, settings: Settings
) -> tuple[list[dict], int, int, int]:
    secret = settings.blob_connection_string
    assert secret is not None
    blob = BlobServiceClient.from_connection_string(
        secret.get_secret_value(),
        retry_total=1,
    )
    container = blob.get_container_client(settings.blob_container)
    records = []
    keys = set()
    try:
        for document, event in rows:
            keys.add(document.storage_key)
            digest = hashlib.sha256()
            actual_size = 0
            for chunk in (
                container
                .get_blob_client(document.storage_key)
                .download_blob()
                .chunks()
            ):
                digest.update(chunk)
                actual_size += len(chunk)
            records.append({
                'document_id': str(document.id),
                'event_id': str(event.id) if event is not None else None,
                'status': document.status.value,
                'size_bytes': document.size_bytes,
                'created_at': document.created_at.isoformat(),
                'attempts': event.attempts if event is not None else None,
                'published_at': (
                    event.published_at.isoformat()
                    if event is not None and event.published_at
                    else None
                ),
                'blob_verified': (
                    actual_size == document.size_bytes
                    and digest.hexdigest() == document.sha256
                ),
            })
        all_keys = {
            item.name
            for item in container.list_blobs()
            if item.name.endswith('.blob')
        }
        markers = sum(
            1 for _ in container.list_blobs(name_starts_with='_uploads/')
        )
    finally:
        blob.close()
    return records, len(all_keys), len(all_keys - keys), markers


def _queue(
    settings: Settings, known_events: set[str], *, drain: bool
) -> tuple[int, list[str]]:
    connection = pika.BlockingConnection(
        pika.URLParameters(settings.rabbitmq_url)
    )
    event_ids: list[str] = []
    try:
        channel = connection.channel()
        queue = channel.queue_declare(
            queue=settings.rabbitmq_queue, passive=True
        )
        initial_messages = queue.method.message_count
        if drain:
            while True:
                method, _properties, body = channel.basic_get(
                    queue=settings.rabbitmq_queue,
                    auto_ack=False,
                )
                if method is None:
                    break
                try:
                    parsed = DocumentReceivedV1.model_validate_json(body)
                    if str(parsed.event_id) not in known_events:
                        raise ValueError(
                            'queue contains event outside this run'
                        )
                    event_ids.append(str(parsed.event_id))
                except Exception:
                    channel.basic_nack(method.delivery_tag, requeue=True)
                    raise
                channel.basic_ack(method.delivery_tag)
    finally:
        connection.close()
    return initial_messages, event_ids


def audit(run_id: str, *, drain: bool = False) -> dict[str, object]:
    settings = Settings()
    rows, document_total = _database(run_id, settings)
    records, blob_count, orphans, markers = _objects(rows, settings)
    known_events = {
        str(record['event_id'])
        for record in records
        if record['event_id'] is not None
    }
    initial_messages, event_ids = _queue(settings, known_events, drain=drain)

    counts = Counter(record['status'] for record in records)
    events = Counter(event_ids)
    return {
        'run_id': run_id,
        'documents': records,
        'document_count': len(records),
        'foreign_documents': document_total - len(records),
        'documents_without_event': sum(
            record['event_id'] is None for record in records
        ),
        'statuses': dict(counts),
        'pending': sum(
            r['event_id'] is not None and r['published_at'] is None
            for r in records
        ),
        'exhausted': sum(
            r['event_id'] is not None
            and r['published_at'] is None
            and r['attempts'] >= settings.outbox_max_attempts
            for r in records
        ),
        'blobs': blob_count,
        'orphan_blobs': orphans,
        'incomplete_markers': markers,
        'broker_queue_before_audit': initial_messages,
        'broker_messages_audited': len(event_ids) if drain else None,
        'duplicate_event_ids': sum(n - 1 for n in events.values() if n > 1)
        if drain
        else None,
        'unknown_event_ids': sorted(
            set(event_ids) - {str(record['event_id']) for record in records}
        )
        if drain
        else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    parser.add_argument('--drain', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.run_id, drain=args.drain), sort_keys=True))


if __name__ == '__main__':
    main()
