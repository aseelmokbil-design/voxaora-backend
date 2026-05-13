"""add_deals_banners_extra_images

Revision ID: 0002
Revises: 400115b81ec3
Create Date: 2026-05-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0002'
down_revision = '400115b81ec3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── deals ──────────────────────────────────────────────────────────────
    op.create_table(
        'deals',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('merchant_id', UUID(as_uuid=True), nullable=True),
        sa.Column('product_id', UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('title_ar', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('original_price', sa.Float(), nullable=True),
        sa.Column('discounted_price', sa.Float(), nullable=True),
        sa.Column('discount_pct', sa.Integer(), nullable=True),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('placement', sa.String(length=50), nullable=False, server_default='home'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('extra_images', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_deals_id', 'deals', ['id'], unique=False)
    op.create_index('ix_deals_merchant_id', 'deals', ['merchant_id'], unique=False)

    # ── banners ────────────────────────────────────────────────────────────
    op.create_table(
        'banners',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('title_ar', sa.String(length=255), nullable=True),
        sa.Column('subtitle_ar', sa.String(length=500), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=False),
        sa.Column('link_url', sa.String(length=500), nullable=True),
        sa.Column('placement', sa.String(length=50), nullable=False, server_default='home'),
        sa.Column('merchant_id', UUID(as_uuid=True), nullable=True),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('bg_color', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_banners_id', 'banners', ['id'], unique=False)
    op.create_index('ix_banners_merchant_id', 'banners', ['merchant_id'], unique=False)

    # ── products.extra_images ──────────────────────────────────────────────
    op.add_column('products', sa.Column('extra_images', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'extra_images')
    op.drop_index('ix_banners_merchant_id', table_name='banners')
    op.drop_index('ix_banners_id', table_name='banners')
    op.drop_table('banners')
    op.drop_index('ix_deals_merchant_id', table_name='deals')
    op.drop_index('ix_deals_id', table_name='deals')
    op.drop_table('deals')
