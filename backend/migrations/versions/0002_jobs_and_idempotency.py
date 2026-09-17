"""create jobs and idempotency schema

Revision ID: 0002_jobs_and_idempotency
Revises: 0001_identity_access
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_jobs_and_idempotency"
down_revision: str | None = "0001_identity_access"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("retry_policy", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    op.create_index("ix_jobs_type", "jobs", ["type"])
    op.create_index("ix_jobs_state", "jobs", ["state"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])
    op.create_index("ix_jobs_user_created", "jobs", ["user_id", "created_at"])
    op.create_index("ix_jobs_state_created", "jobs", ["state", "created_at"])

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("principal_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False, server_default="201"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["principal_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_idempotency_records_principal_id", "idempotency_records", ["principal_id"])
    op.create_index("ix_idempotency_records_job_id", "idempotency_records", ["job_id"])
    op.create_index("ix_idempotency_records_created_at", "idempotency_records", ["created_at"])
    op.create_index(
        "uq_idempotency_principal_key",
        "idempotency_records",
        ["principal_id", "idempotency_key"],
        unique=True,
    )

    op.create_table(
        "job_attempts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("job_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("error_class", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_decision", sa.String(length=64), nullable=True),
        sa.Column("usage", sa.JSON(), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_job_attempts_job_id", "job_attempts", ["job_id"])
    op.create_index(
        "uq_job_attempts_job_number",
        "job_attempts",
        ["job_id", "attempt_number"],
        unique=True,
    )

    op.create_table(
        "job_results",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("job_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False, server_default="v1"),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index("ix_job_results_job_id", "job_results", ["job_id"])

    op.create_table(
        "job_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("job_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("prior_state", sa.String(length=32), nullable=True),
        sa.Column("next_state", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_job_events_job_id", "job_events", ["job_id"])
    op.create_index("ix_job_events_event_type", "job_events", ["event_type"])
    op.create_index("ix_job_events_created_at", "job_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_job_events_created_at", table_name="job_events")
    op.drop_index("ix_job_events_event_type", table_name="job_events")
    op.drop_index("ix_job_events_job_id", table_name="job_events")
    op.drop_table("job_events")

    op.drop_index("ix_job_results_job_id", table_name="job_results")
    op.drop_table("job_results")

    op.drop_index("uq_job_attempts_job_number", table_name="job_attempts")
    op.drop_index("ix_job_attempts_job_id", table_name="job_attempts")
    op.drop_table("job_attempts")

    op.drop_index("uq_idempotency_principal_key", table_name="idempotency_records")
    op.drop_index("ix_idempotency_records_created_at", table_name="idempotency_records")
    op.drop_index("ix_idempotency_records_job_id", table_name="idempotency_records")
    op.drop_index("ix_idempotency_records_principal_id", table_name="idempotency_records")
    op.drop_table("idempotency_records")

    op.drop_index("ix_jobs_state_created", table_name="jobs")
    op.drop_index("ix_jobs_user_created", table_name="jobs")
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_index("ix_jobs_state", table_name="jobs")
    op.drop_index("ix_jobs_type", table_name="jobs")
    op.drop_index("ix_jobs_user_id", table_name="jobs")
    op.drop_table("jobs")
