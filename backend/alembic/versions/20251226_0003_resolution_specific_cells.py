"""Replace land_cells_total with resolution-specific columns."""

from alembic import op
import sqlalchemy as sa


revision = "20251226_0003"
down_revision = "20251225_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns for regions_country
    op.add_column(
        "regions_country",
        sa.Column("land_cells_total_resolution6", sa.Integer(), nullable=True)
    )
    op.add_column(
        "regions_country",
        sa.Column("land_cells_total_resolution8", sa.Integer(), nullable=True)
    )

    # Add new columns for regions_state
    op.add_column(
        "regions_state",
        sa.Column("land_cells_total_resolution6", sa.Integer(), nullable=True)
    )
    op.add_column(
        "regions_state",
        sa.Column("land_cells_total_resolution8", sa.Integer(), nullable=True)
    )

    # Drop old columns from regions_country
    op.drop_column("regions_country", "land_cells_total")

    # Drop old columns from regions_state
    op.drop_column("regions_state", "land_cells_total")


def downgrade() -> None:
    # Add back old columns for regions_country
    op.add_column(
        "regions_country",
        sa.Column("land_cells_total", sa.Integer(), nullable=True)
    )

    # Add back old columns for regions_state
    op.add_column(
        "regions_state",
        sa.Column("land_cells_total", sa.Integer(), nullable=True)
    )

    # Drop new columns from regions_country
    op.drop_column("regions_country", "land_cells_total_resolution8")
    op.drop_column("regions_country", "land_cells_total_resolution6")

    # Drop new columns from regions_state
    op.drop_column("regions_state", "land_cells_total_resolution8")
    op.drop_column("regions_state", "land_cells_total_resolution6")

