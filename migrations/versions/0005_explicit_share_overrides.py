"""Distinguish explicitly reviewed work shares from inherited defaults.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision="0005"
down_revision="0004"
branch_labels=None
depends_on=None


def upgrade():
    # Existing financial decisions are explicit; default changes must not rewrite them.
    op.add_column("transactions",sa.Column("business_use_override",sa.Boolean(),server_default=sa.true(),nullable=False))


def downgrade():
    op.drop_column("transactions","business_use_override")
