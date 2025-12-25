#!/usr/bin/env python3
"""Seed the regions_country table with country data from countries.json."""

import json
import sys
from pathlib import Path

# Add parent directory to path so we can import from backend modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models.geo import CountryRegion


def load_countries_json():
    """Load country data from the bundled JSON file."""
    data_dir = Path(__file__).parent.parent / "data"
    countries_file = data_dir / "countries.json"

    if not countries_file.exists():
        raise FileNotFoundError(f"Countries data file not found: {countries_file}")

    with open(countries_file, "r", encoding="utf-8") as f:
        return json.load(f)


def seed_countries():
    """Insert or update countries in the database."""
    db = SessionLocal()

    try:
        countries_data = load_countries_json()
        print(f"Loaded {len(countries_data)} countries from JSON")

        inserted = 0
        updated = 0

        for country_data in countries_data:
            iso2 = country_data["iso2"]
            iso3 = country_data["iso3"]
            name = country_data["name"]

            # Check if country already exists
            existing = db.query(CountryRegion).filter(
                CountryRegion.iso2 == iso2
            ).first()

            if existing:
                # Update existing country
                existing.iso3 = iso3
                existing.name = name
                updated += 1
            else:
                # Insert new country
                new_country = CountryRegion(
                    iso2=iso2,
                    iso3=iso3,
                    name=name,
                    geom=None,  # Frontend has its own map
                    land_cells_total=None,  # Calculate later when H3 data available
                )
                db.add(new_country)
                inserted += 1

        # Commit all changes
        db.commit()

        print(f"✓ Seeding complete!")
        print(f"  - Inserted: {inserted} countries")
        print(f"  - Updated: {updated} countries")
        print(f"  - Total in database: {inserted + updated}")

    except Exception as e:
        db.rollback()
        print(f"✗ Error seeding countries: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Starting country seed script...")
    seed_countries()
