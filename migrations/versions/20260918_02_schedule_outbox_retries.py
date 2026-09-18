"""Schedule outbox retries and support concurrent publishers.

Revision ID: 20260918_02
Revises: 20260917_01
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260918_02'
down_revision: str | None = '20260917_01'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('outbox_events') as batch_op:
        batch_op.add_column(
            sa.Column('next_attempt_at', sa.DateTime(), nullable=True)
        )
        batch_op.create_index(
            'ix_outbox_events_next_attempt_at',
            ['next_attempt_at'],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('outbox_events') as batch_op:
        batch_op.drop_index('ix_outbox_events_next_attempt_at')
        batch_op.drop_column('next_attempt_at')
