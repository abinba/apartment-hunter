"""client_updated_at must hold epoch milliseconds

Date.now() is about 1.79e12, which overflows a 32-bit integer. Any candidate
save failed with asyncpg DataError until this widened the column.

Revision ID: 0002_bigint_ts
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_bigint_ts"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("candidate", "client_updated_at",
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)


def downgrade() -> None:
    # Narrowing would truncate every real timestamp; refuse rather than corrupt.
    raise RuntimeError(
        "cannot downgrade: existing client_updated_at values exceed int32")
