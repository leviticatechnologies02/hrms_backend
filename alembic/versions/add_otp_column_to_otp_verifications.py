"""add otp column to otp_verifications

Revision ID: add_otp_column_to_otp_verifications
Revises: 
Create Date: 2026-05-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_otp_column_to_otp_verifications'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('otp_verifications', sa.Column('otp', sa.String(length=16), nullable=True))


def downgrade():
    op.drop_column('otp_verifications', 'otp')
