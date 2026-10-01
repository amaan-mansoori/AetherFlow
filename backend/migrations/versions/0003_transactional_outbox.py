"""add transactional dispatch outbox

Revision ID: 0003_transactional_outbox
Revises: 0002_jobs_and_idempotency
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_transactional_outbox"
down_revision: str | None = "0002_jobs_and_idempotency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbox_dispatches",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("message_type", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("job_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("job_version", sa.Integer(), nullable=False),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index("ix_outbox_dispatches_lease_until", "outbox_dispatches", ["lease_until"])
    op.create_index(
        "ix_outbox_unpublished_created",
        "outbox_dispatches",
        ["published_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_unpublished_created", table_name="outbox_dispatches")
    op.drop_index("ix_outbox_dispatches_lease_until", table_name="outbox_dispatches")
    op.drop_table("outbox_dispatches")
