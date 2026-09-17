"""Create documents and outbox events.

Revision ID: 20260917_01
Revises:
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260917_01'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'documents',
        sa.Column(
            'id',
            sa.Uuid(as_uuid=True, native_uuid=False),
            nullable=False,
        ),
        sa.Column('original_name', sa.String(), nullable=False),
        sa.Column('media_type', sa.String(length=255), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('storage_key', sa.String(), nullable=False),
        sa.Column('status', sa.String(length=9), nullable=False),
        sa.Column(
            'correlation_id',
            sa.Uuid(as_uuid=True, native_uuid=False),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            'size_bytes > 0',
            name='ck_documents_size_positive',
        ),
        sa.CheckConstraint(
            'length(sha256) = 64',
            name='ck_documents_sha256_length',
        ),
        sa.CheckConstraint(
            "status IN ('RECEIVED', 'STORED', 'PUBLISHED', 'FAILED')",
            name='document_status',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('storage_key'),
    )
    op.create_table(
        'outbox_events',
        sa.Column(
            'id',
            sa.Uuid(as_uuid=True, native_uuid=False),
            nullable=False,
        ),
        sa.Column(
            'aggregate_id',
            sa.Uuid(as_uuid=True, native_uuid=False),
            nullable=False,
        ),
        sa.Column('event_type', sa.String(length=255), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column(
            'attempts',
            sa.Integer(),
            server_default='0',
            nullable=False,
        ),
        sa.Column('last_error', sa.String(), nullable=True),
        sa.CheckConstraint(
            'attempts >= 0',
            name='ck_outbox_events_attempts_non_negative',
        ),
        sa.ForeignKeyConstraint(
            ['aggregate_id'],
            ['documents.id'],
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('outbox_events')
    op.drop_table('documents')
