"""Controlled operator requeue for exhausted outbox events."""

import logging
from collections.abc import Callable
from uuid import UUID

from docpipe_ingestion.application.errors import (
    OutboxEventNotFoundError,
    OutboxEventNotRequeueableError,
)
from docpipe_ingestion.application.ports import UnitOfWork

type UnitOfWorkFactory = Callable[[], UnitOfWork]
logger = logging.getLogger(__name__)


class RequeueOutboxEvent:
    """Make one exhausted, unpublished event eligible for the worker."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        max_attempts: int,
    ) -> None:
        if max_attempts < 1:
            raise ValueError('max_attempts must be positive')
        self._unit_of_work_factory = unit_of_work_factory
        self._max_attempts = max_attempts

    def execute(self, event_id: UUID) -> None:
        with self._unit_of_work_factory() as unit_of_work:
            event = unit_of_work.outbox_events.get(event_id)
            if event is None:
                raise OutboxEventNotFoundError('outbox event was not found')
            if (
                event.published_at is not None
                or event.attempts < self._max_attempts
            ):
                raise OutboxEventNotRequeueableError(
                    'outbox event is published or not exhausted'
                )
            updated = unit_of_work.outbox_events.requeue_exhausted(
                event_id,
                max_attempts=self._max_attempts,
            )
            if not updated:
                raise OutboxEventNotRequeueableError(
                    'outbox event changed during requeue'
                )
            unit_of_work.commit()
        logger.info(
            'outbox event requeued',
            extra={
                'operation': 'outbox.requeue',
                'status': 'requeued',
                'event_id': str(event_id),
            },
        )
