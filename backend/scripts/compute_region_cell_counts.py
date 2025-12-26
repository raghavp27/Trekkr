#!/usr/bin/env python3
"""Compute H3 cell counts at resolutions 6 and 8 for all regions."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import h3
from shapely import wkb
from shapely.geometry import mapping
from sqlalchemy.orm import joinedload

from database import SessionLocal
from models.geo import CountryRegion, StateRegion


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
        print(f"  Geometry type: {shapely_geom.geom_type}")
        print(f"  Geometry bounds: {shapely_geom.bounds}")
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

        # Periodic commits every 50 countries
        if i % 50 == 0:
            db.commit()
            print(f"  💾 Checkpoint: committed {i} countries")

    db.commit()
    print(f"\n✅ Updated {len(countries)} countries")


def compute_state_cells(db):
    """Compute and update cell counts for all states."""
    states = db.query(StateRegion).options(
        joinedload(StateRegion.country)
    ).filter(StateRegion.geom.isnot(None)).all()

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

        # Periodic commits every 50 states
        if i % 50 == 0:
            db.commit()
            print(f"  💾 Checkpoint: committed {i} states")

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
