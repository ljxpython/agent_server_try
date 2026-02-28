from __future__ import annotations

from alembic import op


revision = "20260228_0003"
down_revision = "20260228_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
          id UUID PRIMARY KEY,
          request_id VARCHAR(64) NOT NULL,
          plane VARCHAR(32) NOT NULL,
          method VARCHAR(16) NOT NULL,
          path VARCHAR(1024) NOT NULL,
          query TEXT NOT NULL DEFAULT '',
          status_code INTEGER NOT NULL,
          duration_ms INTEGER NOT NULL,
          tenant_id UUID NULL,
          user_id UUID NULL,
          user_subject VARCHAR(255) NULL,
          client_ip VARCHAR(128) NULL,
          user_agent VARCHAR(1024) NULL,
          response_size INTEGER NULL,
          metadata_json JSONB NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs(created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_request_id ON audit_logs(request_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_tenant_id ON audit_logs(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_plane ON audit_logs(plane)")


def downgrade() -> None:
    pass
