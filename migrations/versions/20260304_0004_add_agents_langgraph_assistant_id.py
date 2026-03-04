from __future__ import annotations

from alembic import op


revision = "20260304_0004"
down_revision = "20260228_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE agents
        ADD COLUMN IF NOT EXISTS langgraph_assistant_id VARCHAR(128) NOT NULL DEFAULT ''
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_agents_langgraph_assistant_id
        ON agents(langgraph_assistant_id)
        """
    )


def downgrade() -> None:
    pass
