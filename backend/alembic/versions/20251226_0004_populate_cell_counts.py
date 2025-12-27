"""Populate resolution-specific cell counts using area-based estimation."""

from alembic import op
import sqlalchemy as sa


revision = "20251226_0004"
down_revision = "20251226_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the area-based cell count estimation script."""
    import subprocess
    import sys
    from pathlib import Path

    # Get path to computation script
    backend_dir = Path(__file__).parent.parent.parent
    script_path = backend_dir / "scripts" / "compute_region_cell_counts.py"

    print(f"\n{'='*80}")
    print(f"Running area-based H3 cell count estimation: {script_path}")
    print(f"{'='*80}\n")

    # Run the script
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(backend_dir),
        capture_output=True,
        text=True
    )

    # Print output
    if result.stdout:
        print(result.stdout)

    if result.returncode != 0:
        print(f"\n❌ ERROR: Script failed with return code {result.returncode}")
        if result.stderr:
            print("STDERR:", result.stderr)
        raise RuntimeError("Cell count estimation failed")

    print(f"\n{'='*80}")
    print("✅ Cell count estimation completed successfully")
    print(f"{'='*80}\n")


def downgrade() -> None:
    """Clear the estimated cell counts."""
    # Set all cell counts back to NULL
    op.execute(
        "UPDATE regions_country SET "
        "land_cells_total_resolution6 = NULL, "
        "land_cells_total_resolution8 = NULL"
    )
    op.execute(
        "UPDATE regions_state SET "
        "land_cells_total_resolution6 = NULL, "
        "land_cells_total_resolution8 = NULL"
    )
    print("✅ Cell counts cleared (set to NULL)")
