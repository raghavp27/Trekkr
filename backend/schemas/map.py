"""Pydantic schemas for map endpoints."""

from pydantic import BaseModel, model_validator


class CountryVisited(BaseModel):
    """Country the user has visited."""

    code: str  # ISO 3166-1 alpha-2 (e.g., "US")
    name: str


class RegionVisited(BaseModel):
    """Region/state the user has visited."""

    code: str  # ISO 3166-2 (e.g., "US-CA")
    name: str


class MapSummaryResponse(BaseModel):
    """Response for /map/summary endpoint."""

    countries: list[CountryVisited]
    regions: list[RegionVisited]


class BoundingBox(BaseModel):
    """Geographic bounding box for viewport queries."""

    min_lng: float
    min_lat: float
    max_lng: float
    max_lat: float

    @model_validator(mode="after")
    def validate_bounds(self) -> "BoundingBox":
        """Validate bounding box constraints."""
        # Validate coordinate ranges
        for lat_field, lat_value in [("min_lat", self.min_lat), ("max_lat", self.max_lat)]:
            if lat_value < -90 or lat_value > 90:
                raise ValueError(f"{lat_field}: latitude must be in range [-90, 90]")
        for lng_field, lng_value in [("min_lng", self.min_lng), ("max_lng", self.max_lng)]:
            if lng_value < -180 or lng_value > 180:
                raise ValueError(f"{lng_field}: longitude must be in range [-180, 180]")

        # Validate min < max constraints
        if self.min_lng >= self.max_lng:
            raise ValueError("min_lng must be less than max_lng")
        if self.min_lat >= self.max_lat:
            raise ValueError("min_lat must be less than max_lat")
        if self.max_lng - self.min_lng > 180:
            raise ValueError("Bounding box too large: max 180 degrees longitude span")
        if self.max_lat - self.min_lat > 90:
            raise ValueError("Bounding box too large: max 90 degrees latitude span")
        return self


class MapCellsResponse(BaseModel):
    """Response for /map/cells endpoint."""

    res6: list[str]  # H3 indexes at resolution 6
    res8: list[str]  # H3 indexes at resolution 8
