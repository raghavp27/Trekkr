# Resolution-Specific H3 Cell Counts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace generic `land_cells_total` with resolution-specific columns (`land_cells_total_resolution6` and `land_cells_total_resolution8`) for both country and state regions, then compute accurate cell counts.

**Architecture:** Two-phase migration approach - first modify schema structure, then populate data using PostGIS spatial functions combined with H3 polyfill calculations.

**Tech Stack:** Alembic (migrations), SQLAlchemy (ORM), PostGIS (spatial queries), h3-py (hexagonal indexing)

---

## Task 1: Add h3-py dependency

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Add h3-py to requirements**

Add to `backend/requirements.txt`:
```
h3==4.0.0b5
```

**Step 2: Install the dependency**

Run: `pip install h3==4.0.0b5`
Expected: Successfully installed h3 and dependencies

**Step 3: Verify installation**

Run: `python -c "import h3; print(h3.__version__)"`
Expected: Prints version (e.g., "4.0.0b5")

**Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "$(cat <<'EOF'
feat: add h3-py library for hexagonal indexing

Add h3-py 4.0.0b5 to support H3 cell count calculations
for resolution-specific land area metrics.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Update SQLAlchemy models

**Files:**
- Modify: `backend/models/geo.py:50`
- Modify: `backend/models/geo.py:80`

**Step 1: Update CountryRegion model**

In `backend/models/geo.py`, replace line 50:
```python
    land_cells_total = Column(Integer, nullable=True)
```

With:
```python
    land_cells_total_resolution6 = Column(Integer, nullable=True)
    land_cells_total_resolution8 = Column(Integer, nullable=True)
```

**Step 2: Update StateRegion model**

In `backend/models/geo.py`, replace line 80:
```python
    land_cells_total = Column(Integer, nullable=True)
```

With:
```python
    land_cells_total_resolution6 = Column(Integer, nullable=True)
    land_cells_total_resolution8 = Column(Integer, nullable=True)
```

**Step 3: Verify model syntax**

Run: `python -c "from backend.models.geo import CountryRegion, StateRegion; print('Models loaded successfully')"`
Expected: "Models loaded successfully" (no import errors)

**Step 4: Commit**

```bash
git add backend/models/geo.py
git commit -m "$(cat <<'EOF'
model: replace land_cells_total with resolution-specific columns

Replace single land_cells_total column with:
- land_cells_total_resolution6
- land_cells_total_resolution8

Applies to both CountryRegion and StateRegion models.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Create Alembic migration for schema changes

**Files:**
- Create: `backend/alembic/versions/20251226_0003_resolution_specific_cells.py`

**Step 1: Generate migration stub**

Run: `cd backend && alembic revision -m "replace land_cells_total with resolution specific columns"`
Expected: Creates new migration file in `backend/alembic/versions/`

**Step 2: Rename migration file**

Run: `cd backend/alembic/versions && mv $(ls -t | head -1) 20251226_0003_resolution_specific_cells.py`
Expected: File renamed to our naming convention

**Step 3: Write migration upgrade**

Edit `backend/alembic/versions/20251226_0003_resolution_specific_cells.py`:

```python
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
```

**Step 4: Verify migration syntax**

Run: `cd backend && alembic upgrade head --sql`
Expected: Prints SQL without errors (dry-run check)

**Step 5: Run migration**

Run: `cd backend && alembic upgrade head`
Expected: Migration applied successfully, prints "Running upgrade ... -> 20251226_0003"

**Step 6: Verify schema changes**

Run: `cd backend && psql $DATABASE_URL -c "\d regions_country" | grep land_cells`
Expected: Shows land_cells_total_resolution6 and land_cells_total_resolution8 columns

**Step 7: Commit**

```bash
git add backend/alembic/versions/20251226_0003_resolution_specific_cells.py
git commit -m "$(cat <<'EOF'
migration: add resolution-specific cell count columns

Replace single land_cells_total with:
- land_cells_total_resolution6
- land_cells_total_resolution8

Migration handles both regions_country and regions_state tables
with full upgrade/downgrade support.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Create script to compute H3 cell counts

**Files:**
- Create: `backend/scripts/compute_region_cell_counts.py`

**Step 1: Write cell count computation script**

Create `backend/scripts/compute_region_cell_counts.py`:

```python
#!/usr/bin/env python3
"""Compute H3 cell counts at resolutions 6 and 8 for all regions."""

import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import h3
from shapely import wkb, wkt
from shapely.geometry import shape, mapping
from geoalchemy2.shape import to_shape
from sqlalchemy import text

from database import SessionLocal
from models.geo import CountryRegion, StateRegion


def geometry_to_geojson(geom_wkb) -> Optional[dict]:
    """Convert PostGIS geometry to GeoJSON dict for h3.polygon_to_cells."""
    if geom_wkb is None:
        return None

    try:
        # Convert WKB to shapely geometry
        shapely_geom = wkb.loads(bytes(geom_wkb.data))

        # Convert to GeoJSON-like dict
        geojson = mapping(shapely_geom)
        return geojson
    except Exception as e:
        print(f"Error converting geometry: {e}")
        return None


def count_h3_cells_in_geometry(geom_wkb, resolution: int) -> int:
    """Count H3 cells at given resolution that intersect with geometry.

    Uses h3.polygon_to_cells which performs polyfill operation.
    For MultiPolygon, combines cell counts from all polygons.
    """
    if geom_wkb is None:
        return 0

    try:
        shapely_geom = wkb.loads(bytes(geom_wkb.data))

        # Handle MultiPolygon by processing each polygon
        if shapely_geom.geom_type == 'MultiPolygon':
            all_cells = set()
            for polygon in shapely_geom.geoms:
                geojson = mapping(polygon)
                cells = h3.polygon_to_cells(geojson, resolution)
                all_cells.update(cells)
            return len(all_cells)

        # Handle single Polygon
        elif shapely_geom.geom_type == 'Polygon':
            geojson = mapping(shapely_geom)
            cells = h3.polygon_to_cells(geojson, resolution)
            return len(cells)

        else:
            print(f"Unsupported geometry type: {shapely_geom.geom_type}")
            return 0

    except Exception as e:
        print(f"Error counting H3 cells: {e}")
        return 0


def compute_country_cells(db):
    """Compute and update cell counts for all countries."""
    countries = db.query(CountryRegion).filter(
        CountryRegion.geom.isnot(None)
    ).all()

    print(f"\nProcessing {len(countries)} countries...")

    for i, country in enumerate(countries, 1):
        print(f"[{i}/{len(countries)}] {country.name} ({country.iso3})")

        # Compute cell counts at both resolutions
        cells_r6 = count_h3_cells_in_geometry(country.geom, resolution=6)
        cells_r8 = count_h3_cells_in_geometry(country.geom, resolution=8)

        print(f"  Resolution 6: {cells_r6:,} cells")
        print(f"  Resolution 8: {cells_r8:,} cells")

        # Update database
        country.land_cells_total_resolution6 = cells_r6
        country.land_cells_total_resolution8 = cells_r8

    db.commit()
    print(f"\n✅ Updated {len(countries)} countries")


def compute_state_cells(db):
    """Compute and update cell counts for all states."""
    states = db.query(StateRegion).filter(
        StateRegion.geom.isnot(None)
    ).all()

    print(f"\nProcessing {len(states)} states/regions...")

    for i, state in enumerate(states, 1):
        country_name = state.country.name if state.country else "Unknown"
        print(f"[{i}/{len(states)}] {state.name}, {country_name}")

        # Compute cell counts at both resolutions
        cells_r6 = count_h3_cells_in_geometry(state.geom, resolution=6)
        cells_r8 = count_h3_cells_in_geometry(state.geom, resolution=8)

        print(f"  Resolution 6: {cells_r6:,} cells")
        print(f"  Resolution 8: {cells_r8:,} cells")

        # Update database
        state.land_cells_total_resolution6 = cells_r6
        state.land_cells_total_resolution8 = cells_r8

    db.commit()
    print(f"\n✅ Updated {len(states)} states/regions")


def main():
    """Main execution."""
    db = SessionLocal()

    try:
        print("=" * 80)
        print("H3 CELL COUNT COMPUTATION")
        print("=" * 80)

        # Compute for countries
        compute_country_cells(db)

        # Compute for states
        compute_state_cells(db)

        print("\n" + "=" * 80)
        print("✅ COMPUTATION COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

**Step 2: Make script executable**

Run: `chmod +x backend/scripts/compute_region_cell_counts.py`
Expected: File permissions updated

**Step 3: Test script on one country**

First, let's verify the script works by testing imports:
Run: `cd backend && python -c "from scripts.compute_region_cell_counts import count_h3_cells_in_geometry; print('Script imports successfully')"`
Expected: "Script imports successfully"

**Step 4: Commit**

```bash
git add backend/scripts/compute_region_cell_counts.py
git commit -m "$(cat <<'EOF'
script: add H3 cell count computation for regions

Compute H3 cell counts at resolutions 6 and 8 for:
- All countries with geometries
- All states/regions with geometries

Uses h3.polygon_to_cells for accurate polyfill calculations,
handles both Polygon and MultiPolygon geometries.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Run cell count computation

**Files:**
- Modify: `backend/alembic/versions/20251226_0004_populate_cell_counts.py` (new data migration)

**Step 1: Create data migration**

Run: `cd backend && alembic revision -m "populate resolution specific cell counts"`
Expected: Creates new migration file

**Step 2: Rename migration file**

Run: `cd backend/alembic/versions && mv $(ls -t | head -1) 20251226_0004_populate_cell_counts.py`
Expected: File renamed

**Step 3: Write data migration**

Edit `backend/alembic/versions/20251226_0004_populate_cell_counts.py`:

```python
"""Populate resolution-specific cell counts for existing regions."""

from alembic import op
import sqlalchemy as sa


revision = "20251226_0004"
down_revision = "20251226_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the cell count computation script."""
    import subprocess
    import sys
    from pathlib import Path

    # Get path to computation script
    backend_dir = Path(__file__).parent.parent.parent
    script_path = backend_dir / "scripts" / "compute_region_cell_counts.py"

    print(f"\nRunning H3 cell count computation: {script_path}")

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
        print(f"ERROR: Script failed with return code {result.returncode}")
        if result.stderr:
            print("STDERR:", result.stderr)
        raise RuntimeError("Cell count computation failed")

    print("✅ Cell count computation completed successfully")


def downgrade() -> None:
    """Clear the computed cell counts."""
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
```

**Step 4: Run the data migration**

Run: `cd backend && alembic upgrade head`
Expected: Migration runs, shows cell count computation progress, completes successfully

**Step 5: Verify cell counts were populated**

Run: `cd backend && psql $DATABASE_URL -c "SELECT name, land_cells_total_resolution6, land_cells_total_resolution8 FROM regions_country WHERE iso3 = 'USA' LIMIT 1;"`
Expected: Shows USA with non-null cell counts at both resolutions

**Step 6: Verify state cell counts**

Run: `cd backend && psql $DATABASE_URL -c "SELECT name, land_cells_total_resolution6, land_cells_total_resolution8 FROM regions_state WHERE name = 'California' LIMIT 1;"`
Expected: Shows California with non-null cell counts

**Step 7: Commit**

```bash
git add backend/alembic/versions/20251226_0004_populate_cell_counts.py
git commit -m "$(cat <<'EOF'
migration: populate resolution-specific cell counts

Run computation script to populate:
- land_cells_total_resolution6
- land_cells_total_resolution8

For all existing countries and states with geometries.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Verify and test the changes

**Files:**
- Create: `backend/scripts/verify_cell_counts.py`

**Step 1: Write verification script**

Create `backend/scripts/verify_cell_counts.py`:

```python
#!/usr/bin/env python3
"""Verify that cell counts were computed correctly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func
from database import SessionLocal
from models.geo import CountryRegion, StateRegion


def verify_countries(db):
    """Verify country cell counts."""
    total = db.query(func.count(CountryRegion.id)).scalar()
    with_geom = db.query(func.count(CountryRegion.id)).filter(
        CountryRegion.geom.isnot(None)
    ).scalar()
    with_r6 = db.query(func.count(CountryRegion.id)).filter(
        CountryRegion.land_cells_total_resolution6.isnot(None)
    ).scalar()
    with_r8 = db.query(func.count(CountryRegion.id)).filter(
        CountryRegion.land_cells_total_resolution8.isnot(None)
    ).scalar()

    print("COUNTRIES:")
    print(f"  Total countries: {total}")
    print(f"  With geometries: {with_geom}")
    print(f"  With resolution 6 counts: {with_r6}")
    print(f"  With resolution 8 counts: {with_r8}")

    # Sample a few countries
    samples = db.query(CountryRegion).filter(
        CountryRegion.land_cells_total_resolution6.isnot(None)
    ).limit(5).all()

    print("\n  Sample countries:")
    for country in samples:
        print(f"    {country.name}: R6={country.land_cells_total_resolution6:,}, "
              f"R8={country.land_cells_total_resolution8:,}")

    return with_geom == with_r6 == with_r8


def verify_states(db):
    """Verify state cell counts."""
    total = db.query(func.count(StateRegion.id)).scalar()
    with_geom = db.query(func.count(StateRegion.id)).filter(
        StateRegion.geom.isnot(None)
    ).scalar()
    with_r6 = db.query(func.count(StateRegion.id)).filter(
        StateRegion.land_cells_total_resolution6.isnot(None)
    ).scalar()
    with_r8 = db.query(func.count(StateRegion.id)).filter(
        StateRegion.land_cells_total_resolution8.isnot(None)
    ).scalar()

    print("\nSTATES/REGIONS:")
    print(f"  Total states: {total}")
    print(f"  With geometries: {with_geom}")
    print(f"  With resolution 6 counts: {with_r6}")
    print(f"  With resolution 8 counts: {with_r8}")

    # Sample a few states
    samples = db.query(StateRegion).filter(
        StateRegion.land_cells_total_resolution6.isnot(None)
    ).limit(5).all()

    print("\n  Sample states:")
    for state in samples:
        print(f"    {state.name}: R6={state.land_cells_total_resolution6:,}, "
              f"R8={state.land_cells_total_resolution8:,}")

    return with_geom == with_r6 == with_r8


def main():
    """Main verification."""
    db = SessionLocal()

    try:
        print("=" * 80)
        print("CELL COUNT VERIFICATION")
        print("=" * 80)
        print()

        countries_ok = verify_countries(db)
        states_ok = verify_states(db)

        print("\n" + "=" * 80)
        if countries_ok and states_ok:
            print("✅ VERIFICATION PASSED")
            print("All regions with geometries have cell counts populated.")
            sys.exit(0)
        else:
            print("❌ VERIFICATION FAILED")
            print("Some regions are missing cell counts.")
            sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
```

**Step 2: Make verification script executable**

Run: `chmod +x backend/scripts/verify_cell_counts.py`
Expected: Permissions updated

**Step 3: Run verification**

Run: `cd backend && python scripts/verify_cell_counts.py`
Expected: Shows counts for countries and states, prints "✅ VERIFICATION PASSED"

**Step 4: Commit**

```bash
git add backend/scripts/verify_cell_counts.py
git commit -m "$(cat <<'EOF'
test: add cell count verification script

Verify that resolution-specific cell counts were computed
correctly for all regions with geometries.

Checks:
- All countries with geometries have cell counts
- All states with geometries have cell counts
- Sample data looks reasonable

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Update documentation

**Files:**
- Modify: `backend/models/geo.py:36-60` (add docstring details)
- Modify: `backend/models/geo.py:62-91` (add docstring details)

**Step 1: Update CountryRegion docstring**

In `backend/models/geo.py`, update the class docstring around line 36:

```python
class CountryRegion(Base):
    """Country catalog with geometry and precomputed land cell totals.

    Cell counts are precomputed at multiple H3 resolutions:
    - Resolution 6 (~36 km² avg cell area): Coarse coverage tracking
    - Resolution 8 (~0.74 km² avg cell area): Fine-grained coverage tracking
    """
```

**Step 2: Update StateRegion docstring**

In `backend/models/geo.py`, update the class docstring around line 62:

```python
class StateRegion(Base):
    """State/province catalog linked to a country.

    Cell counts are precomputed at multiple H3 resolutions:
    - Resolution 6 (~36 km² avg cell area): Coarse coverage tracking
    - Resolution 8 (~0.74 km² avg cell area): Fine-grained coverage tracking
    """
```

**Step 3: Verify documentation**

Run: `python -c "from backend.models.geo import CountryRegion, StateRegion; print(CountryRegion.__doc__); print(StateRegion.__doc__)"`
Expected: Prints updated docstrings

**Step 4: Commit**

```bash
git add backend/models/geo.py
git commit -m "$(cat <<'EOF'
docs: update model docstrings for resolution-specific cells

Document H3 resolution levels and their approximate cell areas
in CountryRegion and StateRegion model docstrings.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Summary

This plan implements resolution-specific H3 cell counting through:

1. **Dependency**: Add h3-py library
2. **Models**: Update SQLAlchemy models with new columns
3. **Schema Migration**: Alembic migration to add columns and drop old one
4. **Computation Script**: Python script using h3.polygon_to_cells for accurate counts
5. **Data Migration**: Alembic migration to run computation and populate data
6. **Verification**: Script to verify all regions have cell counts
7. **Documentation**: Update model docstrings

**Key Design Decisions:**
- Two separate migrations (schema + data) for clarity and rollback safety
- Uses h3-py's `polygon_to_cells` function for accurate polyfill
- Handles both Polygon and MultiPolygon geometries
- Computes at resolutions 6 and 8 as requested
- Maintains data integrity with nullable columns during migration

**Testing Strategy:**
- Verify imports and syntax before running
- Test script on sample data first
- Verify database state after each migration
- Run comprehensive verification script at the end
