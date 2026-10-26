"""Add revocable sessions, hashed credentials, provider identities and security events.

Revision ID: 0002_auth_security
Revises: 0001_users_expenses
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_auth_security"
down_revision = "0001_users_expenses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(100), nullable=True))
    op.create_table(
        "device_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("device_name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reauthenticated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_device_sessions_user_id", "device_sessions", ["user_id"])
    op.create_table(
        "refresh_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["device_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_refresh_credentials_session_id", "refresh_credentials", ["session_id"])
    op.create_table(
        "auth_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("target_hash", sa.String(64), nullable=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["device_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    for column in ("kind", "user_id", "target_hash", "expires_at"):
        op.create_index(f"ix_auth_challenges_{column}", "auth_challenges", [column])
    op.create_table(
        "external_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "subject"),
    )
    op.create_index("ix_external_identities_user_id", "external_identities", ["user_id"])
    op.create_table(
        "security_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("actor_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_security_events_user_id", "security_events", ["user_id"])
    op.create_table(
        "auth_rate_limits",
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("window_start", sa.Integer(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    # Destructive only to Phase 02 records; existing users/expenses are retained.
    op.drop_table("auth_rate_limits")
    op.drop_index("ix_security_events_user_id", "security_events")
    op.drop_table("security_events")
    op.drop_index("ix_external_identities_user_id", "external_identities")
    op.drop_table("external_identities")
    for column in ("expires_at", "target_hash", "user_id", "kind"):
        op.drop_index(f"ix_auth_challenges_{column}", "auth_challenges")
    op.drop_table("auth_challenges")
    op.drop_index("ix_refresh_credentials_session_id", "refresh_credentials")
    op.drop_table("refresh_credentials")
    op.drop_index("ix_device_sessions_user_id", "device_sessions")
    op.drop_table("device_sessions")
    op.drop_column("users", "display_name")
