"""Preserve legacy expenses in the canonical ledger; allow phone-only identities.

Revision ID: 0004
Revises: 0003
"""
from uuid import NAMESPACE_URL, uuid4, uuid5

from alembic import context, op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("users", "email", existing_type=sa.String(254), nullable=True)
    # SQL only, so offline migration scripts remain executable and reviewable.
    # UUIDs are deterministically derived from existing IDs, preserving cross-link identity.
    op.execute("""
        INSERT INTO businesses (id, owner_id, kind, name)
        SELECT md5('taxiaibooks-business:' || owner_id::text)::uuid, owner_id, 'self_employment', 'Taxi business'
        FROM expenses GROUP BY owner_id
        ON CONFLICT (owner_id, kind) DO NOTHING
    """)
    categories = {code: str(uuid5(NAMESPACE_URL, f"https://taxiaibooks/reference/category/{code}"))
                  for code in ("fuel", "maintenance", "insurance", "licensing", "parking", "other")}
    cases = "CASE e.category " + " ".join(f"WHEN '{code}' THEN '{id}'::uuid" for code,id in categories.items()) + " END"
    op.execute(f"""
        INSERT INTO transactions (id,owner_id,business_id,kind,amount_pence,currency,occurred_on,
          category_id,legacy_expense_id,payment_method,description,business_use_percent,deductible_pence,
          review_status,claim_status,eligibility_reason_codes,mutation_id)
        SELECT e.id,e.owner_id,b.id,'expense',e.amount_pence,'GBP',e.expense_date,{cases},e.id,'other',e.note,
          100,CASE WHEN e.category IN ('parking','licensing') THEN e.amount_pence ELSE 0 END,
          CASE WHEN e.deleted_at IS NULL THEN 'confirmed' ELSE 'reversed' END,
          CASE WHEN e.category IN ('parking','licensing') THEN 'claimable' ELSE 'excluded' END,
          CASE WHEN e.category IN ('parking','licensing') THEN '[]'::jsonb
            WHEN e.category='other' THEN '["specialist_review_required"]'::jsonb
            ELSE '["vehicle_context_required"]'::jsonb END,
          md5('taxiaibooks-mutation:' || e.id::text)::uuid
        FROM expenses e JOIN businesses b ON b.owner_id=e.owner_id AND b.kind='self_employment'
        ON CONFLICT (legacy_expense_id) DO NOTHING
    """)
    op.execute("""
        INSERT INTO book_mutations (id,owner_id,resource_type,resource_id,action,after)
        SELECT mutation_id,owner_id,'transactions',id,'legacy_migration',to_jsonb(t) - 'owner_id'
        FROM transactions t WHERE legacy_expense_id IS NOT NULL
        ON CONFLICT (id) DO NOTHING
    """)


def downgrade():
    # Never erase phone identities to force a downgrade. Operators must resolve
    # incompatible accounts deliberately; no downgrade is performed automatically.
    if not context.is_offline_mode():
        if op.get_bind().scalar(sa.text("SELECT count(*) FROM users WHERE email IS NULL")):
            raise RuntimeError("Cannot downgrade while phone-only users exist; data has been preserved")
    op.alter_column("users", "email", existing_type=sa.String(254), nullable=False)
