"""Staff membership, accountant handoffs and collaboration.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("staff_teams", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("name", sa.String(100), nullable=False, unique=True))
    op.create_table("staff_accounts",
        sa.Column("id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False), sa.Column("role", sa.String(24), nullable=False),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("staff_teams.id")),
        sa.Column("active", sa.Boolean(), nullable=False), sa.Column("totp_secret", sa.LargeBinary(), nullable=False),
        sa.Column("last_totp_counter", sa.Integer(), nullable=False),
        sa.CheckConstraint("role IN ('accountant','senior_accountant','admin','support')", name="role_valid"))
    op.create_index("ix_staff_accounts_team_id", "staff_accounts", ["team_id"])
    op.create_table("driver_assignments",
        sa.Column("driver_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("accountant_id", sa.Uuid(), sa.ForeignKey("staff_accounts.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False))
    op.create_index("ix_driver_assignments_accountant_id", "driver_assignments", ["accountant_id"])
    op.create_table("accountant_handoffs",
        sa.Column("id", sa.Uuid(), sa.ForeignKey("support_records.id"), primary_key=True),
        sa.Column("driver_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tax_year", sa.String(7)),
        sa.Column("status", sa.String(24), nullable=False), sa.Column("filing_reference", sa.String(200)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('new','in_review','waiting_on_driver','ready_to_file','filed')", name="status_valid"))
    op.create_index("ix_accountant_handoffs_driver_id", "accountant_handoffs", ["driver_id"])
    op.create_table("staff_entries",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("driver_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("staff_id", sa.Uuid(), sa.ForeignKey("staff_accounts.id")), sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("body", sa.String(8000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_staff_entries_driver_id", "staff_entries", ["driver_id"])
    op.create_table("staff_audit",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("staff_accounts.id"), nullable=False),
        sa.Column("driver_id", sa.Uuid(), sa.ForeignKey("users.id")), sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.Uuid()), sa.Column("before", postgresql.JSONB()), sa.Column("after", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    for column in ("actor_id", "driver_id"):
        op.create_index(f"ix_staff_audit_{column}", "staff_audit", [column])
    op.create_table("staff_views",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("staff_id", sa.Uuid(), sa.ForeignKey("staff_accounts.id"), nullable=False),
        sa.Column("resource", sa.String(64), nullable=False), sa.Column("name", sa.String(100), nullable=False),
        sa.Column("query", postgresql.JSONB(), nullable=False))
    op.create_index("ix_staff_views_staff_id", "staff_views", ["staff_id"])
    op.execute("INSERT INTO accountant_handoffs (id, driver_id, status, version) SELECT id, owner_id, 'new', 1 FROM support_records WHERE kind = 'accountant_request'")
    op.execute("UPDATE accountant_handoffs h SET tax_year = e.tax_year FROM support_records r, exports e WHERE h.id = r.id AND e.id::text = r.data->>'export_id' AND e.owner_id = h.driver_id")


def downgrade():
    for name in ("staff_views", "staff_audit", "staff_entries", "accountant_handoffs", "driver_assignments", "staff_accounts", "staff_teams"):
        op.drop_table(name)
