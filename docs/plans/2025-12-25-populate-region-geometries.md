# Populate Region Geometries Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fill the `geom` columns in `regions_country` and `regions_state` tables with Natural Earth 1:10m boundary data via Alembic migration.

**Architecture:** Download Natural Earth shapefiles during migration, parse with geopandas, match to existing DB rows by ISO codes/names, update geom columns using GeoAlchemy2, with comprehensive error handling and logging.

**Tech Stack:** Alembic, SQLAlchemy, GeoAlchemy2, geopandas, shapely, Natural Earth Data

---

## Task 1: Add Geospatial Dependencies

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Add geopandas and dependencies**

Add these lines to `backend/requirements.txt`:

```
geopandas>=0.14.0
shapely>=2.0.0
pyproj>=3.6.0
```

**Step 2: Install dependencies**

Run from `backend/` directory:
```bash
pip install -r requirements.txt
```

Expected output: Successfully installed geopandas-X.X.X shapely-X.X.X pyproj-X.X.X and their dependencies

**Step 3: Verify installation**

Run:
```bash
python -c "import geopandas; print(geopandas.__version__)"
```

Expected output: Version number (e.g., `0.14.3`)

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "deps: add geopandas for Natural Earth data loading"
```

---

## Task 2: Generate Migration File

**Files:**
- Create: `backend/alembic/versions/20251225_0002_populate_region_geometries.py`

**Step 1: Generate migration skeleton**

Run from `backend/` directory:
```bash
alembic revision -m "populate region geometries from natural earth"
```

Expected output: `Generating /path/to/alembic/versions/<hash>_populate_region_geometries_from_natural_earth.py`

**Step 2: Rename migration file**

Rename the generated file to follow the naming convention:
```bash
mv alembic/versions/*_populate_region_geometries*.py alembic/versions/20251225_0002_populate_region_geometries.py
```

**Step 3: Update revision ID**

Edit the file and change:
- `revision = "<hash>"` → `revision = "20251225_0002"`
- `down_revision = "20251224_0001"` (link to previous migration)

**Step 4: Commit**

```bash
git add alembic/versions/20251225_0002_populate_region_geometries.py
git commit -m "migration: add skeleton for region geometry population"
```

---

## Task 3: Implement Helper Functions

**Files:**
- Modify: `backend/alembic/versions/20251225_0002_populate_region_geometries.py`

**Step 1: Add imports**

Add at the top of the migration file:

```python
"""Populate region geometries from Natural Earth 1:10m data."""

from alembic import op
import sqlalchemy as sa
from datetime import datetime
from typing import Optional
import geopandas as gpd
from geoalchemy2.shape import from_shape
from sqlalchemy import text

revision = "20251225_0002"
down_revision = "20251224_0001"
branch_labels = None
depends_on = None


# Natural Earth 1:10m data URLs
NATURAL_EARTH_COUNTRIES_URL = (
    "https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/"
    "10m/cultural/ne_10m_admin_0_countries.zip"
)
NATURAL_EARTH_STATES_URL = (
    "https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/"
    "10m/cultural/ne_10m_admin_1_states_provinces.zip"
)
```

**Step 2: Add name normalization helper**

Add this function before `upgrade()`:

```python
def normalize_name(name: str) -> str:
    """Normalize name for fuzzy matching."""
    if not name:
        return ""
    return name.lower().strip().replace(".", "").replace("-", " ")
```

**Step 3: Add download and parse function**

Add this function:

```python
def download_and_parse_shapefile(url: str, description: str) -> gpd.GeoDataFrame:
    """Download and parse a Natural Earth shapefile."""
    print(f"Downloading {description} from Natural Earth...")
    try:
        gdf = gpd.read_file(url)
        print(f"✓ Loaded {len(gdf)} {description} features")
        return gdf
    except Exception as e:
        raise RuntimeError(
            f"Failed to download {description} from {url}: {e}"
        ) from e
```

**Step 4: Commit**

```bash
git add alembic/versions/20251225_0002_populate_region_geometries.py
git commit -m "migration: add helper functions for shapefile loading"
```

---

## Task 4: Implement Country Geometry Population

**Files:**
- Modify: `backend/alembic/versions/20251225_0002_populate_region_geometries.py`

**Step 1: Add country population function**

Add this function before `upgrade()`:

```python
def populate_country_geometries(conn) -> tuple[int, int, list]:
    """Populate country geometries from Natural Earth data.

    Returns: (matched_count, total_count, unmatched_list)
    """
    print("\n=== Populating Country Geometries ===")

    # Download and parse Natural Earth countries
    countries_gdf = download_and_parse_shapefile(
        NATURAL_EARTH_COUNTRIES_URL,
        "countries"
    )

    # Get existing countries from database
    result = conn.execute(text("SELECT id, iso2, iso3, name FROM regions_country"))
    db_countries = {row[0]: {"iso2": row[1], "iso3": row[2], "name": row[3]}
                    for row in result}

    matched_count = 0
    unmatched = []

    print(f"Processing {len(countries_gdf)} Natural Earth countries...")

    for idx, row in countries_gdf.iterrows():
        ne_iso2 = str(row.get("ISO_A2", "")).upper().strip()
        ne_iso3 = str(row.get("ISO_A3", "")).upper().strip()
        ne_name = str(row.get("NAME", "")).strip()
        geometry = row.geometry

        # Skip invalid ISO codes
        if ne_iso2 in ["-99", ""] or ne_iso3 in ["-99", ""]:
            unmatched.append(f"{ne_name} (invalid ISO codes)")
            continue

        # Find matching database country
        matched_id = None
        for db_id, db_data in db_countries.items():
            if db_data["iso2"].upper() == ne_iso2 or db_data["iso3"].upper() == ne_iso3:
                matched_id = db_id
                break

        if matched_id:
            # Convert geometry to WKB
            geom_wkb = from_shape(geometry, srid=4326)

            # Update database
            conn.execute(
                text("""
                    UPDATE regions_country
                    SET geom = :geom, updated_at = :updated_at
                    WHERE id = :id
                """),
                {"geom": str(geom_wkb), "updated_at": datetime.utcnow(), "id": matched_id}
            )
            matched_count += 1

            if matched_count % 10 == 0:
                print(f"  Updated {matched_count} countries...")
        else:
            unmatched.append(f"{ne_name} ({ne_iso2}/{ne_iso3})")

    print(f"\n✓ Country Summary:")
    print(f"  Matched: {matched_count}")
    print(f"  Unmatched: {len(unmatched)}")

    if unmatched and len(unmatched) <= 20:
        print(f"  Unmatched countries: {', '.join(unmatched[:20])}")

    return matched_count, len(countries_gdf), unmatched
```

**Step 2: Commit**

```bash
git add alembic/versions/20251225_0002_populate_region_geometries.py
git commit -m "migration: implement country geometry population logic"
```

---

## Task 5: Implement State Geometry Population

**Files:**
- Modify: `backend/alembic/versions/20251225_0002_populate_region_geometries.py`

**Step 1: Add state population function**

Add this function before `upgrade()`:

```python
def populate_state_geometries(conn) -> tuple[int, int, list]:
    """Populate state/province geometries from Natural Earth data.

    Returns: (matched_count, total_count, unmatched_list)
    """
    print("\n=== Populating State/Province Geometries ===")

    # Download and parse Natural Earth states
    states_gdf = download_and_parse_shapefile(
        NATURAL_EARTH_STATES_URL,
        "states/provinces"
    )

    # Get existing states with country info
    result = conn.execute(text("""
        SELECT s.id, s.country_id, s.code, s.name, c.iso2 as country_iso2
        FROM regions_state s
        JOIN regions_country c ON s.country_id = c.id
    """))
    db_states = {
        row[0]: {
            "country_id": row[1],
            "code": row[2],
            "name": row[3],
            "country_iso2": row[4]
        }
        for row in result
    }

    matched_count = 0
    unmatched = []

    print(f"Processing {len(states_gdf)} Natural Earth states/provinces...")

    for idx, row in states_gdf.iterrows():
        ne_iso_3166_2 = str(row.get("iso_3166_2", "")).strip()
        ne_name = str(row.get("name", "")).strip()
        ne_country_iso2 = str(row.get("iso_a2", "")).upper().strip()
        geometry = row.geometry

        # Find matching database state
        matched_id = None

        # Strategy 1: Try exact ISO 3166-2 code match
        for db_id, db_data in db_states.items():
            if db_data["code"] and db_data["code"].strip() == ne_iso_3166_2:
                matched_id = db_id
                break

        # Strategy 2: Fuzzy name match within same country
        if not matched_id:
            ne_name_norm = normalize_name(ne_name)
            for db_id, db_data in db_states.items():
                db_name_norm = normalize_name(db_data["name"])
                if (db_name_norm == ne_name_norm and
                    db_data["country_iso2"].upper() == ne_country_iso2):
                    matched_id = db_id
                    break

        if matched_id:
            # Convert geometry to WKB
            geom_wkb = from_shape(geometry, srid=4326)

            # Update database
            conn.execute(
                text("""
                    UPDATE regions_state
                    SET geom = :geom, updated_at = :updated_at
                    WHERE id = :id
                """),
                {"geom": str(geom_wkb), "updated_at": datetime.utcnow(), "id": matched_id}
            )
            matched_count += 1

            if matched_count % 50 == 0:
                print(f"  Updated {matched_count} states...")
        else:
            unmatched.append(f"{ne_name} ({ne_country_iso2})")

    print(f"\n✓ State Summary:")
    print(f"  Matched: {matched_count}")
    print(f"  Unmatched: {len(unmatched)}")

    if unmatched and len(unmatched) <= 30:
        print(f"  Sample unmatched: {', '.join(unmatched[:30])}")

    return matched_count, len(states_gdf), unmatched
```

**Step 2: Commit**

```bash
git add alembic/versions/20251225_0002_populate_region_geometries.py
git commit -m "migration: implement state geometry population logic"
```

---

## Task 6: Implement Upgrade and Downgrade Functions

**Files:**
- Modify: `backend/alembic/versions/20251225_0002_populate_region_geometries.py`

**Step 1: Implement upgrade function**

Replace the empty `upgrade()` function with:

```python
def upgrade() -> None:
    """Populate region geometries from Natural Earth 1:10m data."""
    print("\n" + "=" * 60)
    print("MIGRATION: Populate Region Geometries")
    print("=" * 60)

    # Get database connection
    conn = op.get_bind()

    try:
        # Populate countries
        country_matched, country_total, country_unmatched = populate_country_geometries(conn)

        # Populate states
        state_matched, state_total, state_unmatched = populate_state_geometries(conn)

        # Final summary
        print("\n" + "=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)
        print(f"Countries: {country_matched}/{country_total} matched")
        print(f"States: {state_matched}/{state_total} matched")
        print(f"Total unmatched: {len(country_unmatched) + len(state_unmatched)}")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise
```

**Step 2: Implement downgrade function**

Replace the empty `downgrade()` function with:

```python
def downgrade() -> None:
    """Remove all region geometries (set to NULL)."""
    print("\nDowngrading: Setting region geometries to NULL...")

    conn = op.get_bind()

    # Clear country geometries
    result = conn.execute(text("UPDATE regions_country SET geom = NULL"))
    print(f"✓ Cleared {result.rowcount} country geometries")

    # Clear state geometries
    result = conn.execute(text("UPDATE regions_state SET geom = NULL"))
    print(f"✓ Cleared {result.rowcount} state geometries")

    print("✓ Downgrade complete\n")
```

**Step 3: Commit**

```bash
git add alembic/versions/20251225_0002_populate_region_geometries.py
git commit -m "migration: implement upgrade and downgrade functions"
```

---

## Task 7: Test Migration Upgrade

**Files:**
- Test: `backend/alembic/versions/20251225_0002_populate_region_geometries.py`

**Step 1: Check current migration state**

Run from `backend/` directory:
```bash
alembic current
```

Expected output: Shows current revision (should be `20251224_0001` or similar)

**Step 2: Run the migration**

Run:
```bash
alembic upgrade head
```

Expected output:
- "Downloading countries from Natural Earth..."
- "✓ Loaded XXX countries features"
- Progress updates every 10 countries
- "Downloading states/provinces from Natural Earth..."
- "✓ Loaded XXXX states/provinces features"
- Progress updates every 50 states
- Final summary with match counts
- "Running upgrade 20251224_0001 -> 20251225_0002"

**Step 3: Verify country geometries**

Connect to PostgreSQL and run:
```sql
SELECT COUNT(*) FROM regions_country WHERE geom IS NOT NULL;
SELECT name, ST_GeometryType(geom), ST_SRID(geom)
FROM regions_country
WHERE iso2 = 'US'
LIMIT 1;
```

Expected output:
- Count > 0 (number of matched countries)
- USA should show: `MULTIPOLYGON`, SRID `4326`

**Step 4: Verify state geometries**

Run:
```sql
SELECT COUNT(*) FROM regions_state WHERE geom IS NOT NULL;
SELECT name, ST_GeometryType(geom), ST_SRID(geom)
FROM regions_state
WHERE code LIKE 'US-%'
LIMIT 3;
```

Expected output:
- Count > 0 (number of matched states)
- US states should show: `MULTIPOLYGON`, SRID `4326`

**Step 5: Visual check (optional)**

Export a geometry to GeoJSON for visual inspection:
```sql
SELECT name, ST_AsGeoJSON(geom)
FROM regions_country
WHERE iso2 = 'US';
```

Paste the GeoJSON into http://geojson.io to visualize - should show USA shape

---

## Task 8: Test Migration Downgrade

**Files:**
- Test: `backend/alembic/versions/20251225_0002_populate_region_geometries.py`

**Step 1: Run downgrade**

Run from `backend/` directory:
```bash
alembic downgrade -1
```

Expected output:
- "Downgrading: Setting region geometries to NULL..."
- "✓ Cleared XXX country geometries"
- "✓ Cleared XXX state geometries"
- "✓ Downgrade complete"
- "Running downgrade 20251225_0002 -> 20251224_0001"

**Step 2: Verify geometries cleared**

Connect to PostgreSQL and run:
```sql
SELECT COUNT(*) FROM regions_country WHERE geom IS NOT NULL;
SELECT COUNT(*) FROM regions_state WHERE geom IS NOT NULL;
```

Expected output: Both counts should be `0`

**Step 3: Re-run upgrade to restore**

Run:
```bash
alembic upgrade head
```

Expected output: Same as Task 7 Step 2 (migration runs successfully again)

**Step 4: Verify geometries restored**

Run:
```sql
SELECT COUNT(*) FROM regions_country WHERE geom IS NOT NULL;
SELECT COUNT(*) FROM regions_state WHERE geom IS NOT NULL;
```

Expected output: Both counts should be > 0 (geometries restored)

---

## Task 9: Final Verification and Commit

**Files:**
- Modify: `backend/alembic/versions/20251225_0002_populate_region_geometries.py`

**Step 1: Test spatial queries**

Verify PostGIS can use the geometries:
```sql
-- Check if a point is in USA
SELECT name FROM regions_country
WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(-118.2437, 34.0522), 4326))
LIMIT 1;
```

Expected output: `United States` (or similar) - Los Angeles coordinates

**Step 2: Check migration performance**

Review the console output from the last upgrade run:
- Download time should be 2-5 minutes
- Processing time should be 1-3 minutes
- Total time should be < 10 minutes

If significantly slower, may need optimization (but acceptable for a one-time migration)

**Step 3: Document any unmatched records**

Review the console output for unmatched countries/states. If the numbers are reasonable (< 10% unmatched), this is expected. Natural Earth may have territories your DB doesn't include.

Create a note in the migration docstring if needed:
```python
"""Populate region geometries from Natural Earth 1:10m data.

Note: Some Natural Earth features may not match database records. This is expected
for territories, disputed regions, or entities not in your catalog.
"""
```

**Step 4: Final commit**

```bash
git add alembic/versions/20251225_0002_populate_region_geometries.py
git commit -m "migration: finalize and verify region geometry population"
```

---

## Success Criteria

✅ All tasks completed without errors
✅ Migration runs in < 10 minutes
✅ Countries have geometries (geom IS NOT NULL)
✅ States have geometries (geom IS NOT NULL)
✅ Geometries are MULTIPOLYGON type with SRID 4326
✅ Spatial queries work (ST_Contains, etc.)
✅ Downgrade successfully clears geometries
✅ Re-upgrade successfully restores geometries
✅ No data loss (id, name, ISO codes preserved)

## Notes

- Migration downloads ~30MB of data - ensure stable network connection
- First run takes longest (5-6 minutes) - subsequent runs can be faster if data is cached
- Unmatched records are logged but don't fail the migration
- Invalid geometries are skipped with warnings
- The migration is idempotent - safe to run multiple times (will update existing geom values)
