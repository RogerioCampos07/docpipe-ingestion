"""Persist private W3C trace context for outbox delivery.

Revision ID: 20260918_03
Revises: 20260918_02
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260918_03'
down_revision: str | None = '20260918_02'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('outbox_events') as batch_op:
        batch_op.add_column(sa.Column('trace_context', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('outbox_events') as batch_op:
        batch_op.drop_column('trace_context')
