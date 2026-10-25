"""Create users and user-owned expenses.

Revision ID: 0001_users_expenses
Revises: None
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_users_expenses"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("amount_pence", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("note", sa.String(2000), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount_pence > 0", name=op.f("ck_expenses_amount_positive")),
        sa.CheckConstraint("currency = 'GBP'", name=op.f("ck_expenses_currency_gbp")),
        sa.CheckConstraint(
            "category IN ('fuel', 'maintenance', 'insurance', 'licensing', 'parking', 'other')",
            name=op.f("ck_expenses_category_valid"),
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_expenses_owner_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_expenses"),
    )
    op.create_index("ix_expenses_owner_id", "expenses", ["owner_id"])
    op.create_index(
        "ix_expenses_owner_date", "expenses", ["owner_id", "expense_date", "created_at", "id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_expenses_owner_date", table_name="expenses")
    op.drop_index("ix_expenses_owner_id", table_name="expenses")
    op.drop_table("expenses")
    op.drop_table("users")

