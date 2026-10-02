"""Report storage objects without matching metadata."""

import argparse
import json
from datetime import timedelta

from docpipe_ingestion.application.reconciliation import ReconcileStorage
from docpipe_ingestion.infrastructure.composition import (
    create_azure_blob_storage,
)
from docpipe_ingestion.infrastructure.database.engine import (
    create_database_engine,
    create_session_factory,
)
from docpipe_ingestion.infrastructure.database.unit_of_work import (
    SqlAlchemyUnitOfWork,
)
from docpipe_ingestion.infrastructure.settings import Settings


def reconcile(settings: Settings) -> dict[str, list[str]]:
    """List orphan and incomplete uploads without deleting any object."""
    engine = create_database_engine(settings)
    storage = create_azure_blob_storage(settings)
    try:
        session_factory = create_session_factory(engine)
        use_case = ReconcileStorage(
            storage=storage,
            unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(
                session_factory,
                backend=settings.database_backend,
            ),
            incomplete_file_age=timedelta(
                seconds=settings.incomplete_file_age_seconds
            ),
        )
        report = use_case.execute()
        return {
            'orphaned_keys': sorted(report.orphaned_keys),
            'incomplete_keys': sorted(report.incomplete_keys),
        }
    finally:
        close = getattr(storage, 'close', None)
        if close is not None:
            close()
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(reconcile(Settings()), indent=2))


if __name__ == '__main__':
    main()
