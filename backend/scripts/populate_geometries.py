"""Populate region geometries from Natural Earth 1:10m data (standalone script)."""

import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import geopandas as gpd
from geoalchemy2.shape import from_shape
from sqlalchemy import text, create_engine

# Natural Earth 1:10m data URLs
NATURAL_EARTH_COUNTRIES_URL = (
    "https://naciscdn.org/naturalearth/10m/cultural/"
    "ne_10m_admin_0_countries.zip"
)
NATURAL_EARTH_STATES_URL = (
    "https://naciscdn.org/naturalearth/10m/cultural/"
    "ne_10m_admin_1_states_provinces.zip"
)


def normalize_name(name: str) -> str:
    """Normalize name for fuzzy matching."""
    if not name:
        return ""
    return name.lower().strip().replace(".", "").replace("-", " ")


def download_and_parse_shapefile(url: str, description: str) -> gpd.GeoDataFrame:
    """Download and parse a Natural Earth shapefile."""
    print(f"Downloading {description} from Natural Earth...")
    try:
        gdf = gpd.read_file(url)
        print(f"  Loaded {len(gdf)} {description} features")
        return gdf
    except Exception as e:
        raise RuntimeError(f"Failed to download {description} from {url}: {e}") from e


def populate_country_geometries(conn):
    """Populate country geometries from Natural Earth data."""
    gdf = download_and_parse_shapefile(NATURAL_EARTH_COUNTRIES_URL, "countries")

    # Get existing countries from database
    result = conn.execute(text("SELECT id, iso2, iso3, name FROM regions_country"))
    db_countries = {row.id: row for row in result}

    # Build lookup maps
    ne_by_iso2 = {}
    ne_by_iso3 = {}
    ne_by_name = {}

    for _, row in gdf.iterrows():
        iso2 = row.get("ISO_A2", "")
        iso3 = row.get("ISO_A3", "")
        name = row.get("NAME", "") or row.get("ADMIN", "")
        geometry = row.geometry

        if iso2 and iso2 != "-99":
            ne_by_iso2[iso2] = geometry
        if iso3 and iso3 != "-99":
            ne_by_iso3[iso3] = geometry
        if name:
            ne_by_name[normalize_name(name)] = geometry

    matched = 0
    print(f"Processing {len(db_countries)} database countries...")

    for country_id, country in db_countries.items():
        geometry = None

        # Try matching by ISO codes first, then by name
        if country.iso2 in ne_by_iso2:
            geometry = ne_by_iso2[country.iso2]
        elif country.iso3 in ne_by_iso3:
            geometry = ne_by_iso3[country.iso3]
        elif normalize_name(country.name) in ne_by_name:
            geometry = ne_by_name[normalize_name(country.name)]

        if geometry:
            geom_wkb = from_shape(geometry, srid=4326)
            conn.execute(
                text("UPDATE regions_country SET geom = :geom, updated_at = :updated_at WHERE id = :id"),
                {"geom": str(geom_wkb), "updated_at": datetime.utcnow(), "id": country_id}
            )
            matched += 1
            if matched % 50 == 0:
                print(f"  Updated {matched} countries...")

    print(f"  Countries matched: {matched}/{len(db_countries)}")
    return matched


def populate_state_geometries(conn):
    """Populate state/province geometries from Natural Earth data."""
    gdf = download_and_parse_shapefile(NATURAL_EARTH_STATES_URL, "states/provinces")

    # Get existing states with their country ISO codes
    result = conn.execute(text("""
        SELECT s.id, s.code, s.name, c.iso2 as country_iso2
        FROM regions_state s
        JOIN regions_country c ON s.country_id = c.id
    """))
    db_states = {row.id: row for row in result}

    # Build lookup map: (country_iso2, state_code or name) -> geometry
    ne_states = {}
    for _, row in gdf.iterrows():
        country_iso2 = row.get("iso_a2", "")
        state_code = row.get("iso_3166_2", "")  # e.g., "US-CA"
        state_name = row.get("name", "")
        geometry = row.geometry

        if country_iso2 and country_iso2 != "-99":
            # Store by full ISO code (e.g., "US-CA")
            if state_code:
                ne_states[(country_iso2, state_code)] = geometry
            # Also store by name for fallback
            if state_name:
                ne_states[(country_iso2, normalize_name(state_name))] = geometry

    matched = 0
    print(f"Processing {len(db_states)} database states...")

    for state_id, state in db_states.items():
        geometry = None
        full_code = f"{state.country_iso2}-{state.code}" if state.code else None

        # Try matching by ISO 3166-2 code first
        if full_code and (state.country_iso2, full_code) in ne_states:
            geometry = ne_states[(state.country_iso2, full_code)]
        # Try by name
        elif (state.country_iso2, normalize_name(state.name)) in ne_states:
            geometry = ne_states[(state.country_iso2, normalize_name(state.name))]

        if geometry:
            geom_wkb = from_shape(geometry, srid=4326)
            conn.execute(
                text("UPDATE regions_state SET geom = :geom, updated_at = :updated_at WHERE id = :id"),
                {"geom": str(geom_wkb), "updated_at": datetime.utcnow(), "id": state_id}
            )
            matched += 1
            if matched % 200 == 0:
                print(f"  Updated {matched} states...")

    print(f"  States matched: {matched}/{len(db_states)}")
    return matched


def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Set it with: $env:DATABASE_URL='postgresql+psycopg2://appuser:apppass@localhost:5433/appdb'")
        sys.exit(1)

    print("=" * 60)
    print("POPULATE REGION GEOMETRIES")
    print("=" * 60)
    print(f"Database: {database_url.split('@')[1] if '@' in database_url else database_url}")
    print()

    engine = create_engine(database_url)

    with engine.connect() as conn:
        countries_matched = populate_country_geometries(conn)
        print()
        states_matched = populate_state_geometries(conn)
        conn.commit()

    print()
    print("=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"Countries with geometries: {countries_matched}")
    print(f"States with geometries: {states_matched}")


if __name__ == "__main__":
    main()
