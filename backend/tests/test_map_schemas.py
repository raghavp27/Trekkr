"""Unit tests for map schemas."""

import pytest
from pydantic import ValidationError

from schemas.map import (
    CountryVisited,
    RegionVisited,
    MapSummaryResponse,
    BoundingBox,
    MapCellsResponse,
)


class TestBoundingBox:
    """Test BoundingBox validation."""

    def test_valid_bbox_succeeds(self):
        """Test that valid bounding box is accepted."""
        bbox = BoundingBox(
            min_lng=-122.5,
            min_lat=37.7,
            max_lng=-122.4,
            max_lat=37.8,
        )
        assert bbox.min_lng == -122.5
        assert bbox.max_lat == 37.8

    def test_min_greater_than_max_fails(self):
        """Test that min > max raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            BoundingBox(
                min_lng=-122.4,  # min > max
                min_lat=37.7,
                max_lng=-122.5,
                max_lat=37.8,
            )
        assert "min_lng must be less than max_lng" in str(exc_info.value)

    def test_bbox_too_large_fails(self):
        """Test that bbox > 180 degrees longitude span fails."""
        with pytest.raises(ValidationError) as exc_info:
            BoundingBox(
                min_lng=-180.0,
                min_lat=0.0,
                max_lng=90.0,  # 270 degree span
                max_lat=10.0,
            )
        assert "too large" in str(exc_info.value).lower()

    def test_latitude_bbox_too_large_fails(self):
        """Test that bbox > 90 degrees latitude span fails."""
        with pytest.raises(ValidationError) as exc_info:
            BoundingBox(
                min_lng=0.0,
                min_lat=-80.0,
                max_lng=10.0,
                max_lat=20.0,  # 100 degree span
            )
        assert "too large" in str(exc_info.value).lower()

    def test_min_lat_greater_than_max_lat_fails(self):
        """Test that min_lat >= max_lat raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            BoundingBox(
                min_lng=-122.5,
                min_lat=38.0,  # min > max
                max_lng=-122.4,
                max_lat=37.0,
            )
        assert "min_lat must be less than max_lat" in str(exc_info.value)

    def test_invalid_latitude_range_fails(self):
        """Test that latitude outside [-90, 90] fails."""
        with pytest.raises(ValidationError) as exc_info:
            BoundingBox(
                min_lng=-122.5,
                min_lat=-100.0,  # Invalid: < -90
                max_lng=-122.4,
                max_lat=37.0,
            )
        assert "latitude" in str(exc_info.value).lower()

    def test_invalid_longitude_range_fails(self):
        """Test that longitude outside [-180, 180] fails."""
        with pytest.raises(ValidationError) as exc_info:
            BoundingBox(
                min_lng=-200.0,  # Invalid: < -180
                min_lat=37.0,
                max_lng=-122.4,
                max_lat=38.0,
            )
        assert "longitude" in str(exc_info.value).lower()


class TestMapSummaryResponse:
    """Test MapSummaryResponse schema."""

    def test_empty_response(self):
        """Test empty response is valid."""
        response = MapSummaryResponse(countries=[], regions=[])
        assert response.countries == []
        assert response.regions == []

    def test_populated_response(self):
        """Test populated response."""
        response = MapSummaryResponse(
            countries=[
                CountryVisited(code="US", name="United States"),
                CountryVisited(code="JP", name="Japan"),
            ],
            regions=[
                RegionVisited(code="US-CA", name="California"),
            ],
        )
        assert len(response.countries) == 2
        assert response.countries[0].code == "US"


class TestMapCellsResponse:
    """Test MapCellsResponse schema."""

    def test_empty_response(self):
        """Test empty cells response."""
        response = MapCellsResponse(res6=[], res8=[])
        assert response.res6 == []
        assert response.res8 == []

    def test_populated_response(self):
        """Test populated cells response."""
        response = MapCellsResponse(
            res6=["861f05a37ffffff"],
            res8=["881f05a37ffffff", "881f05a39ffffff"],
        )
        assert len(response.res6) == 1
        assert len(response.res8) == 2
