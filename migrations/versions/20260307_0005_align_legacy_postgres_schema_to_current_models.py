from __future__ import annotations

from alembic import op


revision = "20260307_0005"
down_revision = "20260304_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(64)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(32)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ")
    op.execute("ALTER TABLE users ALTER COLUMN email DROP NOT NULL")
    op.execute(
        """
        UPDATE users
        SET username =
            LEFT(
                REGEXP_REPLACE(
                    COALESCE(
                        NULLIF(SPLIT_PART(LOWER(COALESCE(email, '')), '@', 1), ''),
                        NULLIF(LOWER(external_subject), ''),
                        'user'
                    ),
                    '[^a-z0-9_]+',
                    '_',
                    'g'
                ),
                55
            ) || '_' || SUBSTR(REPLACE(id::text, '-', ''), 1, 8)
        WHERE username IS NULL OR username = ''
        """
    )
    op.execute("UPDATE users SET password_hash = '' WHERE password_hash IS NULL")
    op.execute("UPDATE users SET status = 'active' WHERE status IS NULL OR status = ''")
    op.execute("UPDATE users SET is_super_admin = FALSE WHERE is_super_admin IS NULL")
    op.execute("UPDATE users SET updated_at = COALESCE(created_at, now()) WHERE updated_at IS NULL")
    op.execute("ALTER TABLE users ALTER COLUMN username SET NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN status SET NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN is_super_admin SET NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN updated_at SET NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN status SET DEFAULT 'active'")
    op.execute("ALTER TABLE users ALTER COLUMN is_super_admin SET DEFAULT FALSE")
    op.execute("ALTER TABLE users ALTER COLUMN updated_at SET DEFAULT now()")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username ON users(username)")

    op.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS code VARCHAR(64)")
    op.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS description TEXT")
    op.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS status VARCHAR(32)")
    op.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ")
    op.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ")
    op.execute("UPDATE projects SET description = '' WHERE description IS NULL")
    op.execute("UPDATE projects SET status = 'active' WHERE status IS NULL OR status = ''")
    op.execute("UPDATE projects SET updated_at = COALESCE(created_at, now()) WHERE updated_at IS NULL")
    op.execute("ALTER TABLE projects ALTER COLUMN description SET NOT NULL")
    op.execute("ALTER TABLE projects ALTER COLUMN status SET NOT NULL")
    op.execute("ALTER TABLE projects ALTER COLUMN updated_at SET NOT NULL")
    op.execute("ALTER TABLE projects ALTER COLUMN description SET DEFAULT ''")
    op.execute("ALTER TABLE projects ALTER COLUMN status SET DEFAULT 'active'")
    op.execute("ALTER TABLE projects ALTER COLUMN updated_at SET DEFAULT now()")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_projects_code ON projects(code)")

    op.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS project_id UUID")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_project_id ON audit_logs(project_id)")


def downgrade() -> None:
    pass
