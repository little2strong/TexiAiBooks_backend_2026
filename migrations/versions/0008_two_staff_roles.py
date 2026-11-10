"""Two staff roles (admin, accountant); teams removed.

Senior accountants and support staff become accountants: the least-privileged
remaining role. An admin can promote anyone who needs more access.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(op.f("ck_staff_accounts_role_valid"), "staff_accounts", type_="check")
    # A role change must end the person's current sessions, as it does in the panel.
    op.execute("""UPDATE device_sessions SET revoked_at = now() WHERE revoked_at IS NULL AND user_id IN
        (SELECT id FROM staff_accounts WHERE role IN ('senior_accountant', 'support'))""")
    op.execute("""UPDATE staff_accounts SET role = 'accountant', version = version + 1
        WHERE role IN ('senior_accountant', 'support')""")
    op.create_check_constraint("role_valid", "staff_accounts", "role IN ('accountant','admin')")
    op.drop_index(op.f("ix_staff_accounts_team_id"), table_name="staff_accounts")
    op.drop_constraint(op.f("fk_staff_accounts_team_id_staff_teams"), "staff_accounts", type_="foreignkey")
    op.drop_column("staff_accounts", "team_id")
    op.drop_table("staff_teams")


def downgrade():
    # Former senior/support roles cannot be restored; everyone keeps their current role.
    op.create_table("staff_teams", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True))
    op.add_column("staff_accounts", sa.Column("team_id", sa.Uuid(), sa.ForeignKey("staff_teams.id")))
    op.create_index("ix_staff_accounts_team_id", "staff_accounts", ["team_id"])
    op.drop_constraint(op.f("ck_staff_accounts_role_valid"), "staff_accounts", type_="check")
    op.create_check_constraint("role_valid", "staff_accounts", "role IN ('accountant','senior_accountant','admin','support')")
