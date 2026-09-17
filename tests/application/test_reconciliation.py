from datetime import timedelta
from pathlib import Path

import pytest

from docpipe_ingestion.application.reconciliation import ReconcileStorage
from docpipe_ingestion.infrastructure.database.engine import SessionFactory
from docpipe_ingestion.infrastructure.database.unit_of_work import (
    SqlAlchemyUnitOfWork,
)
from docpipe_ingestion.infrastructure.storage.local import LocalDocumentStorage


def test_reconciliation_rejects_non_positive_incomplete_age(
    session_factory: SessionFactory,
    tmp_path: Path,
) -> None:
    storage = LocalDocumentStorage(tmp_path / 'documents')

    with pytest.raises(ValueError, match='positive'):
        ReconcileStorage(
            storage=storage,
            unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(session_factory),
            incomplete_file_age=timedelta(0),
        )
