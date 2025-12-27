"""Geospatial catalogs: countries, states, and H3 cell registry."""

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base, DATABASE_URL

# For SQLite without SpatiaLite, use Text columns instead of Geometry
# (SpatiaLite is often not available, especially on macOS)
_is_sqlite = DATABASE_URL.startswith("sqlite")


def _geom_column(geom_type: str, srid: int = 4326):
    """Return appropriate column type for geometry based on database."""
    if _is_sqlite:
        # Store as WKT text for SQLite without SpatiaLite
        return Text
    else:
        # Use proper PostGIS geometry for PostgreSQL
        return Geometry(geom_type, srid=srid)


class CountryRegion(Base):
    """Country catalog with geometry and estimated land cell totals.

    Cell counts are estimated using area-based calculation at multiple H3 resolutions:
    - Resolution 6 (~36 km² avg cell area): Coarse coverage tracking
    - Resolution 8 (~0.74 km² avg cell area): Fine-grained coverage tracking

    Estimation method: region_area / average_hexagon_area(resolution)
    """

    __tablename__ = "regions_country"
    __table_args__ = (
        UniqueConstraint("iso2", name="uq_regions_country_iso2"),
        UniqueConstraint("iso3", name="uq_regions_country_iso3"),
    )

    id = Column(Integer, primary_key=True)
    iso2 = Column(String(2), nullable=False, index=True)
    iso3 = Column(String(3), nullable=False, index=True)
    name = Column(String(128), nullable=False, index=True)
    geom = Column(_geom_column("MULTIPOLYGON"), nullable=True)
    land_cells_total_resolution6 = Column(Integer, nullable=True)
    land_cells_total_resolution8 = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    states = relationship("StateRegion", back_populates="country")


class StateRegion(Base):
    """State/province catalog linked to a country.

    Cell counts are estimated using area-based calculation at multiple H3 resolutions:
    - Resolution 6 (~36 km² avg cell area): Coarse coverage tracking
    - Resolution 8 (~0.74 km² avg cell area): Fine-grained coverage tracking

    Estimation method: region_area / average_hexagon_area(resolution)
    """

    __tablename__ = "regions_state"
    __table_args__ = (
        UniqueConstraint("country_id", "code", name="uq_regions_state_code"),
    )

    id = Column(Integer, primary_key=True)
    country_id = Column(
        Integer,
        ForeignKey("regions_country.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code = Column(String(10), nullable=True, index=True)
    name = Column(String(128), nullable=False, index=True)
    geom = Column(_geom_column("MULTIPOLYGON"), nullable=True)
    land_cells_total_resolution6 = Column(Integer, nullable=True)
    land_cells_total_resolution8 = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    country = relationship("CountryRegion", back_populates="states")
    h3_cells = relationship("H3Cell", back_populates="state")


class H3Cell(Base):
    """Global registry of visited H3 cells with region lookup."""

    __tablename__ = "h3_cells"
    __table_args__ = (
        Index("ix_h3_cells_res", "res"),
    )

    h3_index = Column(String(25), primary_key=True)
    res = Column(SmallInteger, nullable=False)  # Indexed via __table_args__
    country_id = Column(
        Integer,
        ForeignKey("regions_country.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    state_id = Column(
        Integer,
        ForeignKey("regions_state.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    centroid = Column(_geom_column("POINT"), nullable=True)
    first_visited_at = Column(DateTime, nullable=True)
    last_visited_at = Column(DateTime, nullable=True)
    visit_count = Column(Integer, default=1, nullable=False)

    country = relationship("CountryRegion")
    state = relationship("StateRegion", back_populates="h3_cells")
    user_visits = relationship("UserCellVisit", back_populates="cell")

