from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from time import monotonic

from azure.storage.blob import BlobServiceClient
from sqlalchemy import create_engine, inspect, text

from docpipe_ingestion.infrastructure.settings import Settings


class ReadinessChecker:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _database(self) -> bool:
        settings = self._settings
        if settings.database_backend == 'sqlite':
            database = settings.database_url.removeprefix('sqlite:///')
            if database != ':memory:' and not Path(database).is_file():
                return False
        engine = create_engine(
            settings.database_url,
            connect_args=(
                {'timeout': settings.readiness_database_timeout_seconds}
                if settings.database_backend == 'sqlite'
                else {
                    'connect_timeout': max(
                        1, round(settings.readiness_database_timeout_seconds)
                    )
                }
            ),
        )
        try:
            with engine.connect() as connection:
                connection.execute(text('SELECT 1'))
                tables = set(inspect(connection).get_table_names())
                return {'documents', 'outbox_events'} <= tables
        finally:
            engine.dispose()

    def _storage(self) -> bool:
        settings = self._settings
        if settings.storage_backend == 'local':
            root = settings.storage_root.expanduser()
            return root.is_dir() and root.resolve(strict=True).is_dir()
        secret = settings.blob_connection_string
        if secret is None:
            return False
        service = BlobServiceClient.from_connection_string(
            secret.get_secret_value(),
            api_version=settings.blob_api_version,
            connection_timeout=settings.readiness_storage_timeout_seconds,
            read_timeout=settings.readiness_storage_timeout_seconds,
            retry_total=0,
        )
        try:
            container = service.get_container_client(settings.blob_container)
            timeout = max(1, round(settings.readiness_storage_timeout_seconds))
            properties = container.get_container_properties(timeout=timeout)
            return properties.public_access is None
        finally:
            service.close()

    def check(self) -> dict[str, bool]:
        pool = ThreadPoolExecutor(max_workers=2)
        try:
            deadline = (
                monotonic() + self._settings.readiness_total_timeout_seconds
            )
            futures = {
                'database': pool.submit(self._database),
                'storage': pool.submit(self._storage),
            }
            results: dict[str, bool] = {}
            for name, future in futures.items():
                dependency_timeout = (
                    self._settings.readiness_database_timeout_seconds
                    if name == 'database'
                    else self._settings.readiness_storage_timeout_seconds
                )
                timeout = max(
                    0.0,
                    min(dependency_timeout, deadline - monotonic()),
                )
                try:
                    results[name] = future.result(timeout=timeout)
                except Exception, TimeoutError:
                    results[name] = False
            return results
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
