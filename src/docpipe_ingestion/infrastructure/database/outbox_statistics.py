from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select

from docpipe_ingestion.infrastructure.database.engine import SessionFactory
from docpipe_ingestion.infrastructure.database.models import OutboxEventModel


@dataclass(frozen=True, slots=True)
class OutboxStatistics:
    pending: int
    exhausted: int
    oldest_age_seconds: float


def read_outbox_statistics(
    session_factory: SessionFactory, *, max_attempts: int
) -> OutboxStatistics:
    pending_filter = OutboxEventModel.published_at.is_(None)
    with session_factory() as session:
        pending = (
            session.scalar(
                select(func.count())
                .select_from(OutboxEventModel)
                .where(pending_filter)
            )
            or 0
        )
        exhausted = (
            session.scalar(
                select(func.count())
                .select_from(OutboxEventModel)
                .where(
                    pending_filter, OutboxEventModel.attempts >= max_attempts
                )
            )
            or 0
        )
        oldest = session.scalar(
            select(func.min(OutboxEventModel.created_at)).where(pending_filter)
        )
    age = 0.0
    if oldest is not None:
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=UTC)
        age = max(0.0, (datetime.now(UTC) - oldest).total_seconds())
    return OutboxStatistics(int(pending), int(exhausted), age)
