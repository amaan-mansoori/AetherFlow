"""add durable one-shot scheduling metadata

Revision ID: 0006_durable_scheduling
Revises: 0005_execution_retry
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_durable_scheduling"
down_revision: str | None = "0005_execution_retry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("schedule_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_schedule_at", "jobs", ["schedule_at"])
    op.create_index(
        "ix_jobs_scheduled_due",
        "jobs",
        ["state", "schedule_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_scheduled_due", table_name="jobs")
    op.drop_index("ix_jobs_schedule_at", table_name="jobs")
    op.drop_column("jobs", "schedule_at")
