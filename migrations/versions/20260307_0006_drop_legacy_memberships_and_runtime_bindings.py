from __future__ import annotations

from alembic import op


revision = "20260307_0006"
down_revision = "20260307_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS runtime_bindings")
    op.execute("DROP TABLE IF EXISTS memberships")


def downgrade() -> None:
    pass
