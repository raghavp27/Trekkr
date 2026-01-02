"""Pydantic schemas for location ingestion endpoint."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator
import h3

from schemas.achievements import AchievementUnlockedSchema


class LocationIngestRequest(BaseModel):
    """Request schema for location ingestion (requires H3 from client)."""

    latitude: float
    longitude: float
    h3_res8: str
    timestamp: Optional[datetime] = None
    device_uuid: Optional[str] = None
    device_name: Optional[str] = None
    platform: Optional[str] = None

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        return v

    @field_validator("h3_res8")
    @classmethod
    def validate_h3_index(cls, v: str) -> str:
        if not h3.is_valid_cell(v):
            raise ValueError("Invalid H3 cell index")
        if h3.get_resolution(v) != 8:
            raise ValueError("H3 index must be resolution 8")
        return v


class SimpleLocationIngestRequest(BaseModel):
    """Simplified request schema - backend computes H3 index."""

    latitude: float
    longitude: float
    timestamp: Optional[datetime] = None
    device_uuid: Optional[str] = None
    device_name: Optional[str] = None
    platform: Optional[str] = None

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        return v


class CountryDiscovery(BaseModel):
    """Country discovery information."""

    id: int
    name: str
    iso2: str


class StateDiscovery(BaseModel):
    """State/region discovery information."""

    id: int
    name: str
    code: Optional[str] = None


class DiscoveriesResponse(BaseModel):
    """Discovered entities in this location update."""

    new_country: Optional[CountryDiscovery] = None
    new_state: Optional[StateDiscovery] = None
    new_cells_res6: list[str] = []
    new_cells_res8: list[str] = []


class RevisitsResponse(BaseModel):
    """Revisited entities in this location update."""

    cells_res6: list[str] = []
    cells_res8: list[str] = []


class VisitCountsResponse(BaseModel):
    """Visit counts for the processed cells."""

    res6_visit_count: int = 0
    res8_visit_count: int = 0


class LocationIngestResponse(BaseModel):
    """Response schema for location ingestion."""

    discoveries: DiscoveriesResponse
    revisits: RevisitsResponse
    visit_counts: VisitCountsResponse
    achievements_unlocked: list[AchievementUnlockedSchema] = Field(default_factory=list)


class BatchLocationItem(BaseModel):
    """Single location within a batch."""

    latitude: float
    longitude: float
    h3_res8: str
    timestamp: Optional[datetime] = None

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        return v

    @field_validator("h3_res8")
    @classmethod
    def validate_h3_index(cls, v: str) -> str:
        if not h3.is_valid_cell(v):
            raise ValueError("Invalid H3 cell index")
        if h3.get_resolution(v) != 8:
            raise ValueError("H3 index must be resolution 8")
        return v


class BatchLocationIngestRequest(BaseModel):
    """Request schema for batch location ingestion."""

    locations: list[BatchLocationItem] = Field(..., min_length=1, max_length=100)
    device_uuid: Optional[str] = None
    device_name: Optional[str] = None
    platform: Optional[str] = None


class SkippedLocation(BaseModel):
    """Info about a skipped location in batch processing."""

    index: int
    reason: str  # "h3_mismatch", "invalid_coordinates", "invalid_h3"


class BatchDiscoveries(BaseModel):
    """Aggregated discoveries from batch processing."""

    new_countries: list[CountryDiscovery] = Field(default_factory=list)
    new_regions: list[StateDiscovery] = Field(default_factory=list)
    new_cells_res6: int = 0
    new_cells_res8: int = 0


class BatchLocationIngestResponse(BaseModel):
    """Response schema for batch location ingestion."""

    processed: int
    skipped: int
    skipped_reasons: list[SkippedLocation] = Field(default_factory=list)
    discoveries: BatchDiscoveries
    achievements_unlocked: list[AchievementUnlockedSchema] = Field(default_factory=list)
