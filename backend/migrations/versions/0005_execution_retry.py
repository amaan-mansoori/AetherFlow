"""add durable execution retry dispatch scheduling

Revision ID: 0005_execution_retry
Revises: 0004_dispatch_recovery
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_execution_retry"
down_revision: str | None = "0004_dispatch_recovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    op.create_table(
        "_outbox_dispatches_phase6",
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
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_category", sa.String(length=64), nullable=True),
        sa.Column(
            "publication_state",
            sa.String(length=32),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("job_id", "job_version", name="uq_outbox_job_version"),
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO _outbox_dispatches_phase6 (
                id, message_type, schema_version, job_id, job_version,
                enqueued_at, created_at, published_at, attempt_count,
                last_error, last_error_at, failure_category, publication_state,
                available_at, next_attempt_at, lease_owner, lease_until
            )
            SELECT id, message_type, schema_version, job_id, job_version,
                   enqueued_at, created_at, published_at, attempt_count,
                   last_error, last_error_at, failure_category, publication_state,
                   NULL, next_attempt_at, lease_owner, lease_until
            FROM outbox_dispatches
            """
        )
    )
    op.drop_table("outbox_dispatches")
    op.rename_table("_outbox_dispatches_phase6", "outbox_dispatches")
    op.create_index("ix_outbox_dispatches_lease_until", "outbox_dispatches", ["lease_until"])
    op.create_index(
        "ix_outbox_unpublished_created",
        "outbox_dispatches",
        ["published_at", "created_at"],
    )
    op.create_index(
        "ix_outbox_retry_eligibility",
        "outbox_dispatches",
        ["publication_state", "next_attempt_at", "created_at"],
    )
    op.create_index(
        "ix_outbox_available_at",
        "outbox_dispatches",
        ["publication_state", "available_at", "created_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    duplicate = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM outbox_dispatches
            GROUP BY job_id
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot downgrade execution retry schema while multiple dispatch intents exist."
        )
    op.drop_index("ix_outbox_available_at", table_name="outbox_dispatches")
    op.drop_index("ix_outbox_retry_eligibility", table_name="outbox_dispatches")
    op.drop_index("ix_outbox_unpublished_created", table_name="outbox_dispatches")
    op.drop_index("ix_outbox_dispatches_lease_until", table_name="outbox_dispatches")
    op.create_table(
        "_outbox_dispatches_phase6_downgrade",
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
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_category", sa.String(length=64), nullable=True),
        sa.Column(
            "publication_state",
            sa.String(length=32),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("job_id"),
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO _outbox_dispatches_phase6_downgrade (
                id, message_type, schema_version, job_id, job_version,
                enqueued_at, created_at, published_at, attempt_count,
                last_error, lease_owner, lease_until
            )
            SELECT id, message_type, schema_version, job_id, job_version,
                   enqueued_at, created_at, published_at, attempt_count,
                   last_error, lease_owner, lease_until
            FROM outbox_dispatches
            """
        )
    )
    op.drop_table("outbox_dispatches")
    op.rename_table("_outbox_dispatches_phase6_downgrade", "outbox_dispatches")
    op.create_index("ix_outbox_dispatches_lease_until", "outbox_dispatches", ["lease_until"])
    op.create_index(
        "ix_outbox_unpublished_created",
        "outbox_dispatches",
        ["published_at", "created_at"],
    )
