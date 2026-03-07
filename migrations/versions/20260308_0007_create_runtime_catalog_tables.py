from __future__ import annotations

from alembic import op


revision = "20260308_0007"
down_revision = "20260307_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE agents
        ADD COLUMN IF NOT EXISTS sync_status VARCHAR(32) NOT NULL DEFAULT 'ready',
        ADD COLUMN IF NOT EXISTS last_sync_error TEXT,
        ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_agents_project_name ON agents(project_id, name)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_agents_project_langgraph_assistant ON agents(project_id, langgraph_assistant_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_catalog_graphs (
            id UUID PRIMARY KEY,
            runtime_id VARCHAR(128) NOT NULL,
            graph_key VARCHAR(255) NOT NULL,
            display_name VARCHAR(255),
            description TEXT,
            source_type VARCHAR(64) NOT NULL DEFAULT 'assistant_search',
            raw_payload_json JSON NOT NULL DEFAULT '{}'::json,
            sync_status VARCHAR(32) NOT NULL DEFAULT 'ready',
            last_seen_at TIMESTAMPTZ,
            last_synced_at TIMESTAMPTZ,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_runtime_catalog_graphs_runtime_graph ON runtime_catalog_graphs(runtime_id, graph_key)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_catalog_models (
            id UUID PRIMARY KEY,
            runtime_id VARCHAR(128) NOT NULL,
            model_key VARCHAR(255) NOT NULL,
            display_name VARCHAR(255),
            is_default_runtime BOOLEAN NOT NULL DEFAULT FALSE,
            raw_payload_json JSON NOT NULL DEFAULT '{}'::json,
            sync_status VARCHAR(32) NOT NULL DEFAULT 'ready',
            last_seen_at TIMESTAMPTZ,
            last_synced_at TIMESTAMPTZ,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_runtime_catalog_models_runtime_model ON runtime_catalog_models(runtime_id, model_key)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_catalog_tools (
            id UUID PRIMARY KEY,
            runtime_id VARCHAR(128) NOT NULL,
            tool_key VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            source VARCHAR(255),
            description TEXT,
            raw_payload_json JSON NOT NULL DEFAULT '{}'::json,
            sync_status VARCHAR(32) NOT NULL DEFAULT 'ready',
            last_seen_at TIMESTAMPTZ,
            last_synced_at TIMESTAMPTZ,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_runtime_catalog_tools_runtime_tool ON runtime_catalog_tools(runtime_id, tool_key)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS project_graph_policies (
            id UUID PRIMARY KEY,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            graph_catalog_id UUID NOT NULL REFERENCES runtime_catalog_graphs(id) ON DELETE CASCADE,
            is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            display_order INTEGER,
            note TEXT,
            updated_by UUID,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_project_graph_policies_project_graph ON project_graph_policies(project_id, graph_catalog_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS project_model_policies (
            id UUID PRIMARY KEY,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            model_catalog_id UUID NOT NULL REFERENCES runtime_catalog_models(id) ON DELETE CASCADE,
            is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            is_default_for_project BOOLEAN NOT NULL DEFAULT FALSE,
            temperature_default NUMERIC(4, 2),
            note TEXT,
            updated_by UUID,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_project_model_policies_project_model ON project_model_policies(project_id, model_catalog_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS project_tool_policies (
            id UUID PRIMARY KEY,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            tool_catalog_id UUID NOT NULL REFERENCES runtime_catalog_tools(id) ON DELETE CASCADE,
            is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            display_order INTEGER,
            note TEXT,
            updated_by UUID,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_project_tool_policies_project_tool ON project_tool_policies(project_id, tool_catalog_id)"
    )


def downgrade() -> None:
    pass
