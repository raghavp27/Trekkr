"""add_spatial_indexes_for_reverse_geocoding

Revision ID: 20251226_0005
Revises: 20251226_0004
Create Date: 2025-12-26
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers
revision: str = "20251226_0005"
down_revision: Union[str, None] = "20251226_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create GIST indexes on geometry columns for fast spatial queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_regions_country_geom
        ON regions_country USING GIST (geom)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_regions_state_geom
        ON regions_state USING GIST (geom)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_regions_country_geom")
    op.execute("DROP INDEX IF EXISTS ix_regions_state_geom")
