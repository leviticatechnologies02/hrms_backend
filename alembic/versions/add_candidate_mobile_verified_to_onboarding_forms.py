"""add candidate_mobile_verified to onboarding_forms

Revision ID: add_candidate_mobile_verified
Revises: 
Create Date: 2026-06-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_candidate_mobile_verified'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('onboarding_forms', sa.Column('candidate_mobile_verified', sa.Boolean(), nullable=True, server_default=sa.text('false')))


def downgrade():
    op.drop_column('onboarding_forms', 'candidate_mobile_verified')
