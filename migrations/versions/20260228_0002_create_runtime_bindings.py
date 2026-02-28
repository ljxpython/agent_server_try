from __future__ import annotations

from alembic import op


revision = "20260228_0002"
down_revision = "20260228_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
          id UUID PRIMARY KEY,
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          name VARCHAR(128) NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_projects_tenant_id ON projects(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_projects_name ON projects(name)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agents (
          id UUID PRIMARY KEY,
          project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          name VARCHAR(128) NOT NULL,
          graph_id VARCHAR(128) NOT NULL,
          runtime_base_url VARCHAR(512) NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_agents_project_id ON agents(project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agents_name ON agents(name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agents_graph_id ON agents(graph_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_bindings (
          id UUID PRIMARY KEY,
          agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
          environment VARCHAR(32) NOT NULL,
          langgraph_assistant_id VARCHAR(128) NOT NULL,
          langgraph_graph_id VARCHAR(128) NOT NULL,
          runtime_base_url VARCHAR(512) NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT uq_runtime_bindings_agent_env UNIQUE (agent_id, environment)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_runtime_bindings_agent_id ON runtime_bindings(agent_id)")


def downgrade() -> None:
    pass
