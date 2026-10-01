"""add bounded outbox retry metadata and execution leases

Revision ID: 0004_dispatch_recovery
Revises: 0003_transactional_outbox
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_dispatch_recovery"
down_revision: str | None = "0003_transactional_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("execution_owner", sa.String(length=128)))
    op.add_column("jobs", sa.Column("execution_dispatch_version", sa.Integer()))
    op.add_column("jobs", sa.Column("execution_lease_until", sa.DateTime(timezone=True)))
    op.add_column("outbox_dispatches", sa.Column("last_error_at", sa.DateTime(timezone=True)))
    op.add_column("outbox_dispatches", sa.Column("failure_category", sa.String(length=64)))
    op.add_column(
        "outbox_dispatches",
        sa.Column(
            "publication_state",
            sa.String(length=32),
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.add_column("outbox_dispatches", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
    op.create_index(
        "ix_outbox_retry_eligibility",
        "outbox_dispatches",
        ["publication_state", "next_attempt_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_retry_eligibility", table_name="outbox_dispatches")
    op.drop_column("outbox_dispatches", "next_attempt_at")
    op.drop_column("outbox_dispatches", "publication_state")
    op.drop_column("outbox_dispatches", "failure_category")
    op.drop_column("outbox_dispatches", "last_error_at")
    op.drop_column("jobs", "execution_lease_until")
    op.drop_column("jobs", "execution_dispatch_version")
    op.drop_column("jobs", "execution_owner")
