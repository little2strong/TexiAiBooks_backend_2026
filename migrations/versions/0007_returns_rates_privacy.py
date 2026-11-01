"""Tax return workspace, admin-managed rates, AI feedback, documents and privacy requests.

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def owned_columns():
    return [sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]


def upgrade():
    op.add_column("staff_accounts", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.create_table("tax_returns", *owned_columns(), sa.Column("tax_year", sa.String(7), nullable=False),
        sa.Column("status", sa.String(24), nullable=False), sa.Column("review_version", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB()), sa.Column("earlier_snapshots", postgresql.JSONB(), nullable=False),
        sa.Column("driver_decided_at", sa.DateTime(timezone=True)), sa.Column("driver_note", sa.String(2000)),
        sa.Column("filing_reference", sa.String(200)), sa.Column("filed_at", sa.DateTime(timezone=True)),
        sa.Column("filed_by", sa.Uuid(), sa.ForeignKey("staff_accounts.id")),
        sa.UniqueConstraint("owner_id", "tax_year"),
        sa.CheckConstraint("status IN ('in_preparation','awaiting_driver','driver_approved','filed')", name="status_valid"))
    op.create_index("ix_tax_returns_owner_id", "tax_returns", ["owner_id"])
    op.create_table("tax_adjustments", *owned_columns(), sa.Column("return_id", sa.Uuid(), sa.ForeignKey("tax_returns.id"), nullable=False),
        sa.Column("tax_year", sa.String(7), nullable=False), sa.Column("target", sa.String(24), nullable=False),
        sa.Column("amount_pence", sa.BigInteger(), nullable=False), sa.Column("record_type", sa.String(32)), sa.Column("record_id", sa.Uuid()),
        sa.Column("reason", sa.String(500), nullable=False), sa.Column("created_by", sa.Uuid(), sa.ForeignKey("staff_accounts.id"), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True)), sa.Column("voided_by", sa.Uuid(), sa.ForeignKey("staff_accounts.id")),
        sa.Column("void_reason", sa.String(500)),
        sa.CheckConstraint("amount_pence <> 0", name="amount_nonzero"),
        sa.CheckConstraint("target IN ('income','expenses','capital_allowances')", name="target_valid"))
    op.create_index("ix_tax_adjustments_owner_id", "tax_adjustments", ["owner_id"])
    op.create_index("ix_tax_adjustments_return_id", "tax_adjustments", ["return_id"])
    op.create_table("driver_documents", *owned_columns(), sa.Column("doc_type", sa.String(24), nullable=False),
        sa.Column("reference", sa.String(100)), sa.Column("expires_on", sa.Date()),
        sa.Column("vehicle_id", sa.Uuid(), sa.ForeignKey("vehicles.id")), sa.Column("file_id", sa.Uuid(), sa.ForeignKey("private_files.id")),
        sa.Column("active", sa.Boolean(), nullable=False))
    op.create_index("ix_driver_documents_owner_id", "driver_documents", ["owner_id"])
    op.create_index("ix_driver_documents_expiry", "driver_documents", ["owner_id", "expires_on"])
    op.create_table("privacy_requests", *owned_columns(), sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("detail", sa.String(2000)),
        sa.Column("due_on", sa.Date(), nullable=False), sa.Column("retain_until", sa.Date()), sa.Column("resolution", sa.String(2000)),
        sa.Column("handled_by", sa.Uuid(), sa.ForeignKey("staff_accounts.id")), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("kind IN ('export','access','correction','deletion')", name="kind_valid"),
        sa.CheckConstraint("status IN ('received','in_progress','completed','rejected')", name="status_valid"))
    op.create_index("ix_privacy_requests_owner_id", "privacy_requests", ["owner_id"])
    op.create_table("tax_rates", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("tax_year", sa.String(7), nullable=False),
        sa.Column("region", sa.String(24), nullable=False), sa.Column("code", sa.String(32), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False), sa.Column("status", sa.String(16), nullable=False),
        sa.Column("official_url", sa.String(500), nullable=False), sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("created_by", sa.Uuid(), sa.ForeignKey("staff_accounts.id"), nullable=False),
        sa.Column("approved_by", sa.Uuid(), sa.ForeignKey("staff_accounts.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('draft','approved','active','retired')", name="status_valid"),
        sa.CheckConstraint("region IN ('england_wales_ni','scotland','uk')", name="region_valid"))
    op.create_index("uq_tax_rates_active", "tax_rates", ["tax_year", "region", "code"], unique=True,
        postgresql_where=sa.text("status = 'active'"))
    op.create_table("ai_feedback", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("receipt_id", sa.Uuid(), sa.ForeignKey("receipts.id"), nullable=False),
        sa.Column("driver_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False), sa.Column("staff_id", sa.Uuid(), sa.ForeignKey("staff_accounts.id"), nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False), sa.Column("corrections", postgresql.JSONB(), nullable=False), sa.Column("reason", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("verdict IN ('accepted','corrected','rejected')", name="verdict_valid"))
    op.create_index("ix_ai_feedback_receipt_id", "ai_feedback", ["receipt_id"])
    op.create_index("ix_ai_feedback_driver_id", "ai_feedback", ["driver_id"])


def downgrade():
    # Refuse to discard review, consent or filing evidence.
    connection = op.get_bind()
    for table in ("tax_returns", "tax_adjustments", "privacy_requests", "tax_rates", "ai_feedback", "driver_documents"):
        if connection.scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")):
            raise RuntimeError(f"Refusing downgrade: {table} contains records")
    for table in ("ai_feedback", "tax_rates", "privacy_requests", "driver_documents", "tax_adjustments", "tax_returns"):
        op.drop_table(table)
    op.drop_column("staff_accounts", "version")
