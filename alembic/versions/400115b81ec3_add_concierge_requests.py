"""add_concierge_requests

Revision ID: 400115b81ec3
Revises: 0001
Create Date: 2026-05-12 00:43:23.205848

"""
from alembic import op
import sqlalchemy as sa

revision = '400115b81ec3'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'concierge_requests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('request_text', sa.Text(), nullable=False),
        sa.Column('category_hint', sa.String(length=100), nullable=True),
        sa.Column('user_phone', sa.String(length=30), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('is_voice_request', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_concierge_requests_user_id', 'concierge_requests', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_concierge_requests_user_id', table_name='concierge_requests')
    op.drop_table('concierge_requests')
