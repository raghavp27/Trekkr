#!/usr/bin/env python3
"""Seed the regions_state table with state/province data from states.json."""

import json
import sys
from pathlib import Path

# Add parent directory to path so we can import from backend modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models.geo import CountryRegion, StateRegion


def load_states_json():
    """Load state data from the bundled JSON file."""
    data_dir = Path(__file__).parent.parent / "data"
    states_file = data_dir / "states.json"

    if not states_file.exists():
        raise FileNotFoundError(f"States data file not found: {states_file}")

    with open(states_file, "r", encoding="utf-8") as f:
        return json.load(f)


def seed_states():
    """Insert or update states in the database."""
    db = SessionLocal()

    try:
        states_data = load_states_json()
        print(f"Loaded {len(states_data)} states from JSON")

        # Build country lookup map: iso2 -> id
        countries = db.query(CountryRegion.id, CountryRegion.iso2).all()
        country_map = {c.iso2: c.id for c in countries}
        print(f"Found {len(country_map)} countries in database")

        if not country_map:
            print("No countries found! Please run seed_countries.py first.")
            return

        inserted = 0
        updated = 0
        skipped = 0

        for state_data in states_data:
            country_iso2 = state_data["country_iso2"]
            code = state_data["code"]
            name = state_data["name"]

            # Look up country_id
            country_id = country_map.get(country_iso2)
            if not country_id:
                print(f"  Warning: Country '{country_iso2}' not found, skipping {code}")
                skipped += 1
                continue

            # Check if state already exists (by country_id + code)
            existing = db.query(StateRegion).filter(
                StateRegion.country_id == country_id,
                StateRegion.code == code
            ).first()

            if existing:
                # Update existing state
                existing.name = name
                updated += 1
            else:
                # Insert new state
                new_state = StateRegion(
                    country_id=country_id,
                    code=code,
                    name=name,
                    geom=None,  # Geometry can be added later
                    land_cells_total_resolution6=None,  # Calculate later when H3 data available
                    land_cells_total_resolution8=None,
                )
                db.add(new_state)
                inserted += 1

        # Commit all changes
        db.commit()

        print("Seeding complete!")
        print(f"  - Inserted: {inserted} states")
        print(f"  - Updated: {updated} states")
        print(f"  - Skipped: {skipped} states (country not found)")
        print(f"  - Total in database: {inserted + updated}")

    except Exception as e:
        db.rollback()
        print(f"Error seeding states: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Starting state seed script...")
    seed_states()
