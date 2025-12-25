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
        print(f"✓ Loaded {len(gdf)} {description} features")
        return gdf
    except Exception as e:
        raise RuntimeError(
            f"Failed to download {description} from {url}: {e}"
        ) from e


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

