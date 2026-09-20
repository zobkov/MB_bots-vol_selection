"""add_stage2_applications

Revision ID: 20260920_stage2
Revises: 55443d1dee2b
Create Date: 2026-09-20 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20260920_stage2'
down_revision: Union[str, None] = '55443d1dee2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stage2_applications',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('role_type', sa.String(length=50), nullable=False),
        sa.Column('q1_about_mb', sa.Text(), nullable=True),
        sa.Column('q2_motivation', sa.Text(), nullable=True),
        sa.Column('q3_well_organized', sa.Text(), nullable=True),
        sa.Column('vq1_file_id', sa.String(length=255), nullable=True),
        sa.Column('vq2_file_id', sa.String(length=255), nullable=True),
        sa.Column('vq3_file_id', sa.String(length=255), nullable=True),
        sa.Column('vq4_file_id', sa.String(length=255), nullable=True),
        sa.Column('vq5_file_id', sa.String(length=255), nullable=True),
        sa.Column('media_has_equipment', sa.Boolean(), nullable=True),
        sa.Column('media_experience', sa.Text(), nullable=True),
        sa.Column('media_portfolio', sa.Text(), nullable=True),
        sa.Column('reviewed', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )


def downgrade() -> None:
    op.drop_table('stage2_applications')
