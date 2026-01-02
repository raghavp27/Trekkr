#!/usr/bin/env python3
"""Seed the regions_country table with country data from countries.json."""

import json
import sys
from pathlib import Path

# Add parent directory to path so we can import from backend modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models.geo import CountryRegion

# ISO2 to continent mapping
CONTINENT_MAP = {
    # Africa
    "DZ": "Africa", "AO": "Africa", "BJ": "Africa", "BW": "Africa", "BF": "Africa",
    "BI": "Africa", "CV": "Africa", "CM": "Africa", "CF": "Africa", "TD": "Africa",
    "KM": "Africa", "CG": "Africa", "CD": "Africa", "CI": "Africa", "DJ": "Africa",
    "EG": "Africa", "GQ": "Africa", "ER": "Africa", "SZ": "Africa", "ET": "Africa",
    "GA": "Africa", "GM": "Africa", "GH": "Africa", "GN": "Africa", "GW": "Africa",
    "KE": "Africa", "LS": "Africa", "LR": "Africa", "LY": "Africa", "MG": "Africa",
    "MW": "Africa", "ML": "Africa", "MR": "Africa", "MU": "Africa", "MA": "Africa",
    "MZ": "Africa", "NA": "Africa", "NE": "Africa", "NG": "Africa", "RW": "Africa",
    "ST": "Africa", "SN": "Africa", "SC": "Africa", "SL": "Africa", "SO": "Africa",
    "ZA": "Africa", "SS": "Africa", "SD": "Africa", "TZ": "Africa", "TG": "Africa",
    "TN": "Africa", "UG": "Africa", "ZM": "Africa", "ZW": "Africa", "EH": "Africa",
    "RE": "Africa", "YT": "Africa",
    # Asia
    "AF": "Asia", "AM": "Asia", "AZ": "Asia", "BH": "Asia", "BD": "Asia",
    "BT": "Asia", "BN": "Asia", "KH": "Asia", "CN": "Asia", "CY": "Asia",
    "GE": "Asia", "HK": "Asia", "IN": "Asia", "ID": "Asia", "IR": "Asia",
    "IQ": "Asia", "IL": "Asia", "JP": "Asia", "JO": "Asia", "KZ": "Asia",
    "KW": "Asia", "KG": "Asia", "LA": "Asia", "LB": "Asia", "MO": "Asia",
    "MY": "Asia", "MV": "Asia", "MN": "Asia", "MM": "Asia", "NP": "Asia",
    "KP": "Asia", "OM": "Asia", "PK": "Asia", "PS": "Asia", "PH": "Asia",
    "QA": "Asia", "SA": "Asia", "SG": "Asia", "KR": "Asia", "LK": "Asia",
    "SY": "Asia", "TW": "Asia", "TJ": "Asia", "TH": "Asia", "TL": "Asia",
    "TR": "Asia", "TM": "Asia", "AE": "Asia", "UZ": "Asia", "VN": "Asia",
    "YE": "Asia",
    # Europe
    "AL": "Europe", "AD": "Europe", "AT": "Europe", "BY": "Europe", "BE": "Europe",
    "BA": "Europe", "BG": "Europe", "HR": "Europe", "CZ": "Europe", "DK": "Europe",
    "EE": "Europe", "FO": "Europe", "FI": "Europe", "FR": "Europe", "DE": "Europe",
    "GI": "Europe", "GR": "Europe", "GL": "Europe", "GG": "Europe", "HU": "Europe",
    "IS": "Europe", "IE": "Europe", "IM": "Europe", "IT": "Europe", "JE": "Europe",
    "XK": "Europe", "LV": "Europe", "LI": "Europe", "LT": "Europe", "LU": "Europe",
    "MT": "Europe", "MD": "Europe", "MC": "Europe", "ME": "Europe", "NL": "Europe",
    "MK": "Europe", "NO": "Europe", "PL": "Europe", "PT": "Europe", "RO": "Europe",
    "RU": "Europe", "SM": "Europe", "RS": "Europe", "SK": "Europe", "SI": "Europe",
    "ES": "Europe", "SJ": "Europe", "SE": "Europe", "CH": "Europe", "UA": "Europe",
    "GB": "Europe", "VA": "Europe", "AX": "Europe",
    # North America
    "AI": "North America", "AG": "North America", "AW": "North America", "BS": "North America",
    "BB": "North America", "BZ": "North America", "BM": "North America", "BQ": "North America",
    "VG": "North America", "CA": "North America", "KY": "North America", "CR": "North America",
    "CU": "North America", "CW": "North America", "DM": "North America", "DO": "North America",
    "SV": "North America", "GD": "North America", "GP": "North America", "GT": "North America",
    "HT": "North America", "HN": "North America", "JM": "North America", "MQ": "North America",
    "MX": "North America", "MS": "North America", "NI": "North America", "PA": "North America",
    "PR": "North America", "BL": "North America", "KN": "North America", "LC": "North America",
    "MF": "North America", "PM": "North America", "VC": "North America", "SX": "North America",
    "TT": "North America", "TC": "North America", "US": "North America", "VI": "North America",
    # South America
    "AR": "South America", "BO": "South America", "BR": "South America", "CL": "South America",
    "CO": "South America", "EC": "South America", "FK": "South America", "GF": "South America",
    "GY": "South America", "PY": "South America", "PE": "South America", "SR": "South America",
    "UY": "South America", "VE": "South America",
    # Oceania
    "AS": "Oceania", "AU": "Oceania", "CK": "Oceania", "FJ": "Oceania", "PF": "Oceania",
    "GU": "Oceania", "KI": "Oceania", "MH": "Oceania", "FM": "Oceania", "NR": "Oceania",
    "NC": "Oceania", "NZ": "Oceania", "NU": "Oceania", "NF": "Oceania", "MP": "Oceania",
    "PW": "Oceania", "PG": "Oceania", "PN": "Oceania", "WS": "Oceania", "SB": "Oceania",
    "TK": "Oceania", "TO": "Oceania", "TV": "Oceania", "VU": "Oceania", "WF": "Oceania",
    # Antarctica
    "AQ": "Antarctica", "BV": "Antarctica", "TF": "Antarctica", "HM": "Antarctica",
    "GS": "Antarctica",
}


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
                continent = CONTINENT_MAP.get(iso2, "Unknown")
                new_country = CountryRegion(
                    iso2=iso2,
                    iso3=iso3,
                    name=name,
                    continent=continent,
                    geom=None,  # Frontend has its own map
                    land_cells_total_resolution6=None,  # Calculate later when H3 data available
                    land_cells_total_resolution8=None,
                )
                db.add(new_country)
                inserted += 1

        # Commit all changes
        db.commit()

        print("Seeding complete!")
        print(f"  - Inserted: {inserted} countries")
        print(f"  - Updated: {updated} countries")
        print(f"  - Total in database: {inserted + updated}")

    except Exception as e:
        db.rollback()
        print(f"Error seeding countries: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Starting country seed script...")
    seed_countries()
