"""add missing localized columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # These columns are present in ORM/models and used by scripts/routes,
    # but were missed in the initial schema migration.
    op.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS name_uz_latn TEXT")
    op.execute("ALTER TABLE uom ADD COLUMN IF NOT EXISTS name_uz_latn VARCHAR(100)")
    op.execute("ALTER TABLE uom ADD COLUMN IF NOT EXISTS name_uz_cyrl VARCHAR(100)")


def downgrade() -> None:
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS name_uz_latn")
    op.execute("ALTER TABLE uom DROP COLUMN IF EXISTS name_uz_latn")
    op.execute("ALTER TABLE uom DROP COLUMN IF EXISTS name_uz_cyrl")
