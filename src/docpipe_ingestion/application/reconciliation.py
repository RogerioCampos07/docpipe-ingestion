from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from docpipe_ingestion.application.ingest_document import Clock, utc_now
from docpipe_ingestion.application.ports import DocumentStorage, UnitOfWork
from docpipe_ingestion.domain.models import ensure_utc

type UnitOfWorkFactory = Callable[[], UnitOfWork]


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    """Non-destructive report of storage inconsistencies."""

    orphaned_keys: frozenset[str]
    incomplete_keys: frozenset[str]


class ReconcileStorage:
    """Find files that require controlled operator action."""

    def __init__(
        self,
        *,
        storage: DocumentStorage,
        unit_of_work_factory: UnitOfWorkFactory,
        incomplete_file_age: timedelta,
        clock: Clock = utc_now,
    ) -> None:
        if incomplete_file_age <= timedelta(0):
            raise ValueError('incomplete_file_age must be positive')
        self._storage = storage
        self._unit_of_work_factory = unit_of_work_factory
        self._incomplete_file_age = incomplete_file_age
        self._clock = clock

    def execute(self) -> ReconciliationReport:
        """Return candidates without deleting or modifying any file."""
        now = ensure_utc(self._clock(), field_name='clock')
        stored_keys = self._storage.list_keys()
        incomplete_keys = self._storage.list_incomplete(
            older_than=now - self._incomplete_file_age
        )
        with self._unit_of_work_factory() as unit_of_work:
            registered_keys = unit_of_work.documents.list_storage_keys()
        return ReconciliationReport(
            orphaned_keys=frozenset(stored_keys - registered_keys),
            incomplete_keys=frozenset(incomplete_keys),
        )
