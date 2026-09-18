from dataclasses import dataclass

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

HTTP_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1,
    2.5,
    5,
    10,
    30,
    60,
)
DEPENDENCY_BUCKETS = (
    0.001,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1,
    2.5,
    5,
    10,
    30,
    60,
)


@dataclass(slots=True)
class Metrics:
    registry: CollectorRegistry
    http_requests: Counter
    http_duration: Histogram
    http_errors: Counter
    uploads: Counter
    documents_accepted: Counter
    request_body_bytes: Counter
    validation_failures: Counter
    database_backend: Gauge
    database_duration: Histogram
    database_errors: Counter
    database_transactions: Counter
    storage_duration: Histogram
    storage_backend: Gauge
    storage_bytes: Counter
    storage_errors: Counter
    storage_orphans: Gauge
    outbox_pending: Gauge
    outbox_oldest_age: Gauge
    outbox_exhausted: Gauge
    publication_attempts: Counter
    publications_confirmed: Counter
    publication_failures: Counter
    publication_duration: Histogram
    worker_cycles: Counter
    worker_cycle_duration: Histogram
    readiness: Gauge


def create_metrics(registry: CollectorRegistry | None = None) -> Metrics:
    r = registry or CollectorRegistry()
    prefix = 'docpipe_ingestion_'
    return Metrics(
        registry=r,
        http_requests=Counter(
            prefix + 'http_requests_total',
            'HTTP requests',
            ('method', 'route', 'status_code'),
            registry=r,
        ),
        http_duration=Histogram(
            prefix + 'http_request_duration_seconds',
            'HTTP duration',
            ('method', 'route', 'status_code'),
            buckets=HTTP_BUCKETS,
            registry=r,
        ),
        http_errors=Counter(
            prefix + 'http_errors_total',
            'HTTP errors',
            ('route', 'error_category'),
            registry=r,
        ),
        uploads=Counter(
            prefix + 'uploads_total',
            'Upload outcomes',
            ('outcome',),
            registry=r,
        ),
        documents_accepted=Counter(
            prefix + 'documents_accepted_total',
            'Accepted documents',
            registry=r,
        ),
        request_body_bytes=Counter(
            prefix + 'http_request_body_bytes_total',
            'Request body bytes',
            ('route',),
            registry=r,
        ),
        validation_failures=Counter(
            prefix + 'validation_failures_total',
            'Validation failures',
            ('reason',),
            registry=r,
        ),
        database_backend=Gauge(
            prefix + 'database_backend_info',
            'Configured DB backend',
            ('backend',),
            registry=r,
        ),
        database_duration=Histogram(
            prefix + 'database_operation_duration_seconds',
            'Database operation duration',
            ('backend', 'operation', 'outcome'),
            buckets=DEPENDENCY_BUCKETS,
            registry=r,
        ),
        database_errors=Counter(
            prefix + 'database_errors_total',
            'Database failures',
            ('backend', 'operation', 'error_category'),
            registry=r,
        ),
        database_transactions=Counter(
            prefix + 'database_transactions_total',
            'Database transactions',
            ('backend', 'kind', 'outcome'),
            registry=r,
        ),
        storage_duration=Histogram(
            prefix + 'storage_upload_duration_seconds',
            'Storage duration',
            ('backend', 'outcome'),
            buckets=HTTP_BUCKETS,
            registry=r,
        ),
        storage_backend=Gauge(
            prefix + 'storage_backend_info',
            'Configured storage backend',
            ('backend',),
            registry=r,
        ),
        storage_bytes=Counter(
            prefix + 'storage_committed_bytes_total',
            'Stored bytes',
            ('backend',),
            registry=r,
        ),
        storage_errors=Counter(
            prefix + 'storage_errors_total',
            'Storage failures',
            ('backend', 'operation', 'error_category'),
            registry=r,
        ),
        storage_orphans=Gauge(
            prefix + 'storage_orphan_candidates',
            'Storage orphan candidates',
            ('backend',),
            registry=r,
        ),
        outbox_pending=Gauge(
            prefix + 'outbox_pending_events',
            'Pending outbox events',
            registry=r,
        ),
        outbox_oldest_age=Gauge(
            prefix + 'outbox_oldest_pending_age_seconds',
            'Age of oldest pending event',
            registry=r,
        ),
        outbox_exhausted=Gauge(
            prefix + 'outbox_exhausted_events',
            'Exhausted outbox events',
            registry=r,
        ),
        publication_attempts=Counter(
            prefix + 'outbox_publication_attempts_total',
            'Outbox publication attempts',
            registry=r,
        ),
        publications_confirmed=Counter(
            prefix + 'rabbitmq_publications_confirmed_total',
            'RabbitMQ confirmed publications',
            registry=r,
        ),
        publication_failures=Counter(
            prefix + 'outbox_publication_failures_total',
            'Outbox publication failures',
            ('error_category',),
            registry=r,
        ),
        publication_duration=Histogram(
            prefix + 'rabbitmq_publish_duration_seconds',
            'RabbitMQ publication duration',
            ('outcome',),
            buckets=DEPENDENCY_BUCKETS,
            registry=r,
        ),
        worker_cycles=Counter(
            prefix + 'worker_cycles_total',
            'Worker cycles',
            ('outcome',),
            registry=r,
        ),
        worker_cycle_duration=Histogram(
            prefix + 'worker_cycle_duration_seconds',
            'Worker cycle duration',
            ('outcome',),
            buckets=DEPENDENCY_BUCKETS,
            registry=r,
        ),
        readiness=Gauge(
            prefix + 'readiness_dependency_available',
            'Readiness dependency state',
            ('dependency', 'backend'),
            registry=r,
        ),
    )
