"""Pydantic schemas for stats endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StatsQueryParams(BaseModel):
    """Query parameters for stats endpoints."""

    sort_by: Literal["coverage_pct", "first_visited_at", "last_visited_at", "name"] = "last_visited_at"
    order: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class CountryStatResponse(BaseModel):
    """Statistics for a single country."""

    code: str  # ISO 3166-1 alpha-2 (e.g., "US")
    name: str
    coverage_pct: float
    first_visited_at: datetime
    last_visited_at: datetime


class CountriesStatsResponse(BaseModel):
    """Response for /stats/countries endpoint."""

    total_countries_visited: int
    countries: list[CountryStatResponse]


class RegionStatResponse(BaseModel):
    """Statistics for a single region/state."""

    code: str  # ISO 3166-2 (e.g., "US-CA")
    name: str
    country_code: str  # ISO 3166-1 alpha-2 (e.g., "US")
    country_name: str
    coverage_pct: float
    first_visited_at: datetime
    last_visited_at: datetime


class RegionsStatsResponse(BaseModel):
    """Response for /stats/regions endpoint."""

    total_regions_visited: int
    regions: list[RegionStatResponse]


class UserInfoResponse(BaseModel):
    """User information for profile display."""
    id: int
    username: str
    created_at: datetime


class StatsResponse(BaseModel):
    """Aggregate travel statistics."""
    countries_visited: int
    regions_visited: int
    cells_visited_res6: int
    cells_visited_res8: int
    total_visit_count: int
    first_visit_at: datetime | None
    last_visit_at: datetime | None


class RecentCountryResponse(BaseModel):
    """Recently visited country."""
    code: str  # ISO 3166-1 alpha-2
    name: str
    visited_at: datetime


class RecentRegionResponse(BaseModel):
    """Recently visited region/state."""
    code: str  # ISO 3166-2 format (e.g., "US-CA")
    name: str
    country_name: str
    visited_at: datetime


class OverviewResponse(BaseModel):
    """Complete profile overview response."""
    user: UserInfoResponse
    stats: StatsResponse
    recent_countries: list[RecentCountryResponse]
    recent_regions: list[RecentRegionResponse]
