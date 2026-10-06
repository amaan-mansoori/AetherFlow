"""add restricted demo role

Revision ID: 0007_demo_role
Revises: 0006_durable_scheduling
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "0007_demo_role"
down_revision: str | None = "0006_durable_scheduling"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    roles = sa.table("roles", sa.column("id", sa.Uuid()), sa.column("name", sa.String()))
    op.bulk_insert(roles, [{"id": uuid4(), "name": "DEMO"}])


def downgrade() -> None:
    bind = op.get_bind()
    demo_role_id = bind.execute(
        sa.text("SELECT id FROM roles WHERE name = 'DEMO'")
    ).scalar_one_or_none()
    if demo_role_id is None:
        return
    assigned = bind.execute(
        sa.text("SELECT 1 FROM user_roles WHERE role_id = :role_id LIMIT 1"),
        {"role_id": demo_role_id},
    ).first()
    if assigned is not None:
        raise RuntimeError("Cannot remove DEMO role while it is assigned to users.")
    bind.execute(sa.text("DELETE FROM roles WHERE id = :role_id"), {"role_id": demo_role_id})
