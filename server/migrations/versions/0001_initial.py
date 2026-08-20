"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-20T23:02:31.354933
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'app_user',
        sa.Column('uid', sa.String(length=128), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=True),
        sa.Column('seeded', sa.Boolean(), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('uid'),
    )
    op.create_table(
        'candidate',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.String(length=128), nullable=False),
        sa.Column('ext_id', sa.String(length=64), nullable=False),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('link', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('lon', sa.Float(), nullable=True),
        sa.Column('photos', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('answers', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('travel', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('scrape', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status_override', sa.String(length=32), nullable=True),
        sa.Column('archived', sa.Boolean(), nullable=False),
        sa.Column('client_updated_at', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['app_user.uid'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uid', 'ext_id', name='uq_candidate_uid_ext'),
    )
    op.create_index('ix_candidate_uid_archived', 'candidate', ['uid', 'archived'], unique=False)
    op.create_index('ix_candidate_uid', 'candidate', ['uid'], unique=False)
    op.create_table(
        'category',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.String(length=128), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('color', sa.String(length=32), nullable=False),
        sa.Column('sort', sa.Integer(), nullable=False),
        sa.Column('archived', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['app_user.uid'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uid', 'key', name='uq_category_uid_key'),
    )
    op.create_index('ix_category_uid', 'category', ['uid'], unique=False)
    op.create_table(
        'place',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.String(length=128), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('lon', sa.Float(), nullable=True),
        sa.Column('weight', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('depart_hour', sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column('modes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('sort', sa.Integer(), nullable=False),
        sa.Column('archived', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['app_user.uid'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uid', 'key', name='uq_place_uid_key'),
    )
    op.create_index('ix_place_uid', 'place', ['uid'], unique=False)
    op.create_table(
        'setting',
        sa.Column('uid', sa.String(length=128), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['app_user.uid'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('uid', 'key'),
    )
    op.create_table(
        'criterion',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.String(length=128), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=200), nullable=False),
        sa.Column('hint', sa.Text(), nullable=True),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('importance', sa.String(length=16), nullable=False),
        sa.Column('weight_override', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('scored', sa.Boolean(), nullable=False),
        sa.Column('photo_evidence', sa.Boolean(), nullable=False),
        sa.Column('scrapable', sa.Boolean(), nullable=False),
        sa.Column('sort', sa.Integer(), nullable=False),
        sa.Column('archived', sa.Boolean(), nullable=False),
        sa.Column('builtin', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['app_user.uid'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['category.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uid', 'key', name='uq_criterion_uid_key'),
    )
    op.create_index('ix_criterion_uid', 'criterion', ['uid'], unique=False)
    op.create_index('ix_criterion_uid_archived', 'criterion', ['uid', 'archived'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_criterion_uid', table_name='criterion')
    op.drop_index('ix_criterion_uid_archived', table_name='criterion')
    op.drop_table('criterion')
    op.drop_table('setting')
    op.drop_index('ix_place_uid', table_name='place')
    op.drop_table('place')
    op.drop_index('ix_category_uid', table_name='category')
    op.drop_table('category')
    op.drop_index('ix_candidate_uid_archived', table_name='candidate')
    op.drop_index('ix_candidate_uid', table_name='candidate')
    op.drop_table('candidate')
    op.drop_table('app_user')
