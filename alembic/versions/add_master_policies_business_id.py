"""add_master_policies_business_id

Revision ID: add_master_policies_business_id
Revises: 13327e55d52a
Create Date: 2026-05-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_master_policies_business_id'
down_revision: Union[str, None] = '13327e55d52a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('master_policies')]

    if 'business_id' not in cols:
        # Add nullable business_id column first
        op.add_column('master_policies', sa.Column('business_id', sa.Integer(), nullable=True))
        # Create FK and index
        op.create_foreign_key('fk_master_policies_business_id', 'master_policies', 'businesses', ['business_id'], ['id'])
        op.create_index(op.f('ix_master_policies_business_id'), 'master_policies', ['business_id'], unique=False)


def downgrade() -> None:
    # Remove index, constraint and column if present
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('master_policies')]

    if 'business_id' in cols:
        try:
            op.drop_index(op.f('ix_master_policies_business_id'), table_name='master_policies')
        except Exception:
            pass
        try:
            op.drop_constraint('fk_master_policies_business_id', 'master_policies', type_='foreignkey')
        except Exception:
            pass
        op.drop_column('master_policies', 'business_id')
