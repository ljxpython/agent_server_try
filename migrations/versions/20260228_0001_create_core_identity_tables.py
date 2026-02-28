from __future__ import annotations

from alembic import op


revision = "20260228_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tenants (
          id UUID PRIMARY KEY,
          name VARCHAR(128) NOT NULL,
          slug VARCHAR(128) NOT NULL,
          status VARCHAR(32) NOT NULL DEFAULT 'active',
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS slug VARCHAR(128)")
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS status VARCHAR(32)")
    op.execute("UPDATE tenants SET status = 'active' WHERE status IS NULL")
    op.execute("UPDATE tenants SET slug = id::text WHERE slug IS NULL OR slug = ''")
    op.execute("ALTER TABLE tenants ALTER COLUMN slug SET NOT NULL")
    op.execute("ALTER TABLE tenants ALTER COLUMN status SET NOT NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_tenants_slug ON tenants(slug)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
          id UUID PRIMARY KEY,
          external_subject VARCHAR(255) NOT NULL UNIQUE,
          email VARCHAR(255) NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS memberships (
          id UUID PRIMARY KEY,
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          role VARCHAR(32) NOT NULL DEFAULT 'member',
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT uq_memberships_tenant_user UNIQUE (tenant_id, user_id)
        )
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS ix_memberships_tenant_id ON memberships(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_memberships_user_id ON memberships(user_id)")


def downgrade() -> None:
    pass
