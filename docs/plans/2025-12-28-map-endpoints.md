# Map Endpoints Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create two authenticated endpoints that return user's visited cells/regions for frontend map rendering.

**Architecture:** MapService queries PostGIS to find visited countries, regions, and H3 cells. Map router exposes `/summary` (all visited countries/regions) and `/cells` (H3 indexes within viewport bounding box).

**Tech Stack:** FastAPI, SQLAlchemy, PostGIS (ST_Intersects), Pydantic v2, pytest

---

## Task 1: Create Map Schemas

**Files:**
- Create: `backend/schemas/map.py`
- Modify: `backend/schemas/__init__.py`

**Step 1: Write the failing test**

Create test file `backend/tests/test_map_schemas.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_map_schemas.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'schemas.map'"

**Step 3: Write minimal implementation**

Create `backend/schemas/map.py`:

```python
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
```

**Step 4: Update schemas/__init__.py**

Add to `backend/schemas/__init__.py`:

```python
from .map import (
    CountryVisited,
    RegionVisited,
    MapSummaryResponse,
    BoundingBox,
    MapCellsResponse,
)
```

**Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_map_schemas.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add backend/schemas/map.py backend/schemas/__init__.py backend/tests/test_map_schemas.py
git commit -m "feat(schemas): add map endpoint schemas with bbox validation"
```

---

## Task 2: Create MapService - Summary Query

**Files:**
- Create: `backend/services/map_service.py`
- Create: `backend/tests/test_map_service.py`

**Step 1: Write the failing test**

Create `backend/tests/test_map_service.py`:

```python
"""Integration tests for MapService."""

import pytest
from sqlalchemy import text

from models.user import User
from models.geo import CountryRegion, StateRegion
from services.map_service import MapService
from tests.fixtures.test_data import SAN_FRANCISCO, TOKYO, LOS_ANGELES


@pytest.mark.integration
class TestMapServiceSummary:
    """Test MapService.get_summary() method."""

    def test_user_with_no_visits_returns_empty(
        self, db_session, test_user: User
    ):
        """Test that user with no visits returns empty arrays."""
        service = MapService(db_session, test_user.id)
        result = service.get_summary()

        assert result["countries"] == []
        assert result["regions"] == []

    def test_user_with_one_visit_returns_country_and_region(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that user with one visit returns that country and region."""
        # Create a cell visit for the user
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
        """), {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": SAN_FRANCISCO["longitude"],
            "lat": SAN_FRANCISCO["latitude"],
        })

        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {
            "user_id": test_user.id,
            "h3_index": SAN_FRANCISCO["h3_res8"],
        })
        db_session.commit()

        service = MapService(db_session, test_user.id)
        result = service.get_summary()

        assert len(result["countries"]) == 1
        assert result["countries"][0]["code"] == "US"
        assert result["countries"][0]["name"] == "United States"

        assert len(result["regions"]) == 1
        assert result["regions"][0]["code"] == "US-CA"
        assert result["regions"][0]["name"] == "California"

    def test_multiple_visits_same_country_returns_one_country(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that multiple visits to same country return one entry."""
        # Create two cell visits in the same country
        for loc in [SAN_FRANCISCO, LOS_ANGELES]:
            db_session.execute(text("""
                INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid)
                VALUES (:h3_index, 8, :country_id, :state_id,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                ON CONFLICT (h3_index) DO NOTHING
            """), {
                "h3_index": loc["h3_res8"],
                "country_id": test_country_usa.id,
                "state_id": test_state_california.id,
                "lon": loc["longitude"],
                "lat": loc["latitude"],
            })

            db_session.execute(text("""
                INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
                VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
                ON CONFLICT (user_id, h3_index) DO NOTHING
            """), {
                "user_id": test_user.id,
                "h3_index": loc["h3_res8"],
            })
        db_session.commit()

        service = MapService(db_session, test_user.id)
        result = service.get_summary()

        # Should have only one country entry (deduplicated)
        assert len(result["countries"]) == 1
        assert result["countries"][0]["code"] == "US"

    def test_visits_in_multiple_countries(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
        test_country_japan: CountryRegion,
    ):
        """Test visits in multiple countries returns all."""
        # Visit in USA
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
        """), {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": SAN_FRANCISCO["longitude"],
            "lat": SAN_FRANCISCO["latitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": SAN_FRANCISCO["h3_res8"]})

        # Visit in Japan
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, centroid)
            VALUES (:h3_index, 8, :country_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
        """), {
            "h3_index": TOKYO["h3_res8"],
            "country_id": test_country_japan.id,
            "lon": TOKYO["longitude"],
            "lat": TOKYO["latitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": TOKYO["h3_res8"]})

        db_session.commit()

        service = MapService(db_session, test_user.id)
        result = service.get_summary()

        assert len(result["countries"]) == 2
        country_codes = {c["code"] for c in result["countries"]}
        assert country_codes == {"US", "JP"}
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_map_service.py::TestMapServiceSummary -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'services.map_service'"

**Step 3: Write minimal implementation**

Create `backend/services/map_service.py`:

```python
"""Map service for retrieving user's visited areas."""

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


class MapService:
    """Service for map-related queries."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def get_summary(self) -> dict:
        """Get all countries and regions the user has visited.

        Returns:
            dict with 'countries' and 'regions' lists
        """
        # Query distinct countries
        countries_query = text("""
            SELECT DISTINCT rc.iso2 AS code, rc.name
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            JOIN regions_country rc ON hc.country_id = rc.id
            WHERE ucv.user_id = :user_id
            ORDER BY rc.name
        """)
        countries_result = self.db.execute(
            countries_query, {"user_id": self.user_id}
        ).fetchall()

        countries = [
            {"code": row.code, "name": row.name}
            for row in countries_result
        ]

        # Query distinct regions
        regions_query = text("""
            SELECT DISTINCT
                CONCAT(rc.iso2, '-', rs.code) AS code,
                rs.name
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            JOIN regions_state rs ON hc.state_id = rs.id
            JOIN regions_country rc ON rs.country_id = rc.id
            WHERE ucv.user_id = :user_id
            ORDER BY rs.name
        """)
        regions_result = self.db.execute(
            regions_query, {"user_id": self.user_id}
        ).fetchall()

        regions = [
            {"code": row.code, "name": row.name}
            for row in regions_result
        ]

        return {"countries": countries, "regions": regions}
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_map_service.py::TestMapServiceSummary -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/services/map_service.py backend/tests/test_map_service.py
git commit -m "feat(service): add MapService.get_summary() for visited countries/regions"
```

---

## Task 3: Create MapService - Cells Query

**Files:**
- Modify: `backend/services/map_service.py`
- Modify: `backend/tests/test_map_service.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_map_service.py`:

```python
@pytest.mark.integration
class TestMapServiceCells:
    """Test MapService.get_cells_in_viewport() method."""

    def test_no_cells_in_viewport_returns_empty(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that empty viewport returns empty arrays."""
        # Create cell in San Francisco
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
        """), {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": SAN_FRANCISCO["longitude"],
            "lat": SAN_FRANCISCO["latitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": SAN_FRANCISCO["h3_res8"]})
        db_session.commit()

        service = MapService(db_session, test_user.id)

        # Query viewport in Tokyo (no cells there)
        result = service.get_cells_in_viewport(
            min_lng=139.0, min_lat=35.0, max_lng=140.0, max_lat=36.0
        )

        assert result["res6"] == []
        assert result["res8"] == []

    def test_cells_in_viewport_returned(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that cells within viewport are returned."""
        # Create res-6 and res-8 cells in San Francisco
        for h3_index, res in [
            (SAN_FRANCISCO["h3_res6"], 6),
            (SAN_FRANCISCO["h3_res8"], 8),
        ]:
            db_session.execute(text("""
                INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid)
                VALUES (:h3_index, :res, :country_id, :state_id,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                ON CONFLICT (h3_index) DO NOTHING
            """), {
                "h3_index": h3_index,
                "res": res,
                "country_id": test_country_usa.id,
                "state_id": test_state_california.id,
                "lon": SAN_FRANCISCO["longitude"],
                "lat": SAN_FRANCISCO["latitude"],
            })
            db_session.execute(text("""
                INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
                VALUES (:user_id, :h3_index, :res, NOW(), NOW(), 1)
                ON CONFLICT (user_id, h3_index) DO NOTHING
            """), {"user_id": test_user.id, "h3_index": h3_index, "res": res})

        db_session.commit()

        service = MapService(db_session, test_user.id)

        # Query viewport around San Francisco
        result = service.get_cells_in_viewport(
            min_lng=-123.0, min_lat=37.0, max_lng=-122.0, max_lat=38.0
        )

        assert len(result["res6"]) == 1
        assert result["res6"][0] == SAN_FRANCISCO["h3_res6"]
        assert len(result["res8"]) == 1
        assert result["res8"][0] == SAN_FRANCISCO["h3_res8"]

    def test_only_user_cells_returned(
        self,
        db_session,
        test_user: User,
        test_user2: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that only the requesting user's cells are returned."""
        # User 1 has SF cell
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
        """), {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": SAN_FRANCISCO["longitude"],
            "lat": SAN_FRANCISCO["latitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": SAN_FRANCISCO["h3_res8"]})

        # User 2 has LA cell
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
        """), {
            "h3_index": LOS_ANGELES["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": LOS_ANGELES["longitude"],
            "lat": LOS_ANGELES["latitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user2.id, "h3_index": LOS_ANGELES["h3_res8"]})

        db_session.commit()

        # Query as user 1 with viewport covering both SF and LA
        service = MapService(db_session, test_user.id)
        result = service.get_cells_in_viewport(
            min_lng=-125.0, min_lat=32.0, max_lng=-115.0, max_lat=40.0
        )

        # Should only see user 1's SF cell, not user 2's LA cell
        assert len(result["res8"]) == 1
        assert result["res8"][0] == SAN_FRANCISCO["h3_res8"]
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_map_service.py::TestMapServiceCells -v`
Expected: FAIL with "AttributeError: 'MapService' object has no attribute 'get_cells_in_viewport'"

**Step 3: Write minimal implementation**

Add to `backend/services/map_service.py`:

```python
    def get_cells_in_viewport(
        self,
        min_lng: float,
        min_lat: float,
        max_lng: float,
        max_lat: float,
        limit: Optional[int] = None,
    ) -> dict:
        """Get H3 cell indexes within the bounding box.

        Args:
            min_lng: Western longitude bound
            min_lat: Southern latitude bound
            max_lng: Eastern longitude bound
            max_lat: Northern latitude bound
            limit: Optional maximum number of cells to return (for future use)

        Returns:
            dict with 'res6' and 'res8' lists of H3 index strings
        """
        query = text("""
            SELECT hc.h3_index, hc.res
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            WHERE ucv.user_id = :user_id
              AND hc.res IN (6, 8)
              AND ST_Intersects(
                  hc.centroid,
                  ST_MakeEnvelope(:min_lng, :min_lat, :max_lng, :max_lat, 4326)
              )
            ORDER BY hc.h3_index
        """)

        result = self.db.execute(query, {
            "user_id": self.user_id,
            "min_lng": min_lng,
            "min_lat": min_lat,
            "max_lng": max_lng,
            "max_lat": max_lat,
        }).fetchall()

        res6 = [row.h3_index for row in result if row.res == 6]
        res8 = [row.h3_index for row in result if row.res == 8]

        return {"res6": res6, "res8": res8}
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_map_service.py::TestMapServiceCells -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/services/map_service.py backend/tests/test_map_service.py
git commit -m "feat(service): add MapService.get_cells_in_viewport() with PostGIS query"
```

---

## Task 4: Create Map Router

**Files:**
- Create: `backend/routers/map.py`
- Modify: `backend/routers/__init__.py`
- Modify: `backend/main.py`

**Step 1: Write the failing test**

Create `backend/tests/test_map_router.py`:

```python
"""Integration tests for map endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from models.user import User
from models.geo import CountryRegion, StateRegion
from tests.conftest import create_jwt_token
from tests.fixtures.test_data import SAN_FRANCISCO


@pytest.mark.integration
class TestMapSummaryEndpoint:
    """Test GET /api/v1/map/summary endpoint."""

    def test_unauthenticated_returns_401(self, client: TestClient):
        """Test that unauthenticated request returns 401."""
        response = client.get("/api/v1/map/summary")
        assert response.status_code == 401

    def test_authenticated_empty_user_returns_200(
        self, client: TestClient, test_user: User
    ):
        """Test that authenticated user with no visits gets empty response."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/summary",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["countries"] == []
        assert data["regions"] == []

    def test_authenticated_with_visits_returns_data(
        self,
        client: TestClient,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that user with visits gets their data."""
        # Create visit
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
        """), {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": SAN_FRANCISCO["longitude"],
            "lat": SAN_FRANCISCO["latitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": SAN_FRANCISCO["h3_res8"]})
        db_session.commit()

        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/summary",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["countries"]) == 1
        assert data["countries"][0]["code"] == "US"
        assert len(data["regions"]) == 1
        assert data["regions"][0]["code"] == "US-CA"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_map_router.py::TestMapSummaryEndpoint -v`
Expected: FAIL with 404 (endpoint doesn't exist)

**Step 3: Write minimal implementation**

Create `backend/routers/map.py`:

```python
"""Map endpoints for retrieving user's visited areas."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from schemas.map import MapSummaryResponse, MapCellsResponse
from services.auth import get_current_user
from services.map_service import MapService


router = APIRouter()


@router.get("/summary", response_model=MapSummaryResponse)
def get_map_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all countries and regions the user has visited.

    Returns a summary of visited locations for fog of war rendering.
    Frontend uses Mapbox's built-in boundary layers with these codes.
    """
    service = MapService(db, current_user.id)
    result = service.get_summary()

    return MapSummaryResponse(
        countries=[
            {"code": c["code"], "name": c["name"]}
            for c in result["countries"]
        ],
        regions=[
            {"code": r["code"], "name": r["name"]}
            for r in result["regions"]
        ],
    )
```

**Step 4: Update routers/__init__.py**

Add to `backend/routers/__init__.py`:

```python
from . import map
```

**Step 5: Register router in main.py**

Add to `backend/main.py` imports:

```python
from routers import auth, health, location, map
```

Add router registration:

```python
app.include_router(map.router, prefix="/api/v1/map", tags=["map"])
```

**Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_map_router.py::TestMapSummaryEndpoint -v`
Expected: All tests PASS

**Step 7: Commit**

```bash
git add backend/routers/map.py backend/routers/__init__.py backend/main.py backend/tests/test_map_router.py
git commit -m "feat(router): add GET /api/v1/map/summary endpoint"
```

---

## Task 5: Add Cells Endpoint to Router

**Files:**
- Modify: `backend/routers/map.py`
- Modify: `backend/tests/test_map_router.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_map_router.py`:

```python
@pytest.mark.integration
class TestMapCellsEndpoint:
    """Test GET /api/v1/map/cells endpoint."""

    def test_unauthenticated_returns_401(self, client: TestClient):
        """Test that unauthenticated request returns 401."""
        response = client.get(
            "/api/v1/map/cells",
            params={"min_lng": -123, "min_lat": 37, "max_lng": -122, "max_lat": 38},
        )
        assert response.status_code == 401

    def test_missing_params_returns_422(self, client: TestClient, test_user: User):
        """Test that missing bbox params returns 422."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/cells",
            params={"min_lng": -123},  # Missing other params
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    def test_invalid_bbox_returns_400(self, client: TestClient, test_user: User):
        """Test that invalid bbox (min > max) returns 400."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/cells",
            params={
                "min_lng": -122,  # min > max
                "min_lat": 37,
                "max_lng": -123,
                "max_lat": 38,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    def test_bbox_too_large_returns_400(self, client: TestClient, test_user: User):
        """Test that bbox spanning > 180 degrees returns 400."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/cells",
            params={
                "min_lng": -180,
                "min_lat": 0,
                "max_lng": 90,  # 270 degree span
                "max_lat": 10,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    def test_valid_request_returns_cells(
        self,
        client: TestClient,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test valid request returns cells in viewport."""
        # Create visits
        for h3_index, res in [
            (SAN_FRANCISCO["h3_res6"], 6),
            (SAN_FRANCISCO["h3_res8"], 8),
        ]:
            db_session.execute(text("""
                INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid)
                VALUES (:h3_index, :res, :country_id, :state_id,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                ON CONFLICT (h3_index) DO NOTHING
            """), {
                "h3_index": h3_index,
                "res": res,
                "country_id": test_country_usa.id,
                "state_id": test_state_california.id,
                "lon": SAN_FRANCISCO["longitude"],
                "lat": SAN_FRANCISCO["latitude"],
            })
            db_session.execute(text("""
                INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
                VALUES (:user_id, :h3_index, :res, NOW(), NOW(), 1)
                ON CONFLICT (user_id, h3_index) DO NOTHING
            """), {"user_id": test_user.id, "h3_index": h3_index, "res": res})
        db_session.commit()

        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/cells",
            params={
                "min_lng": -123,
                "min_lat": 37,
                "max_lng": -122,
                "max_lat": 38,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["res6"]) == 1
        assert len(data["res8"]) == 1

    def test_empty_viewport_returns_empty_arrays(
        self, client: TestClient, test_user: User
    ):
        """Test that viewport with no cells returns empty arrays."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/cells",
            params={
                "min_lng": 0,
                "min_lat": 0,
                "max_lng": 1,
                "max_lat": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["res6"] == []
        assert data["res8"] == []
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_map_router.py::TestMapCellsEndpoint -v`
Expected: FAIL with 404 or missing endpoint

**Step 3: Write minimal implementation**

Add to `backend/routers/map.py`:

```python
from fastapi import HTTPException, status
from pydantic import ValidationError
from schemas.map import BoundingBox


@router.get("/cells", response_model=MapCellsResponse)
def get_map_cells(
    min_lng: float,
    min_lat: float,
    max_lng: float,
    max_lat: float,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get H3 cells within the bounding box.

    Returns H3 cell indexes at resolutions 6 and 8 that the user
    has visited within the specified viewport.
    """
    # Validate bounding box
    try:
        bbox = BoundingBox(
            min_lng=min_lng,
            min_lat=min_lat,
            max_lng=max_lng,
            max_lat=max_lat,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.errors()[0]["msg"]),
        )

    service = MapService(db, current_user.id)
    result = service.get_cells_in_viewport(
        min_lng=bbox.min_lng,
        min_lat=bbox.min_lat,
        max_lng=bbox.max_lng,
        max_lat=bbox.max_lat,
    )

    return MapCellsResponse(res6=result["res6"], res8=result["res8"])
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_map_router.py::TestMapCellsEndpoint -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/routers/map.py backend/tests/test_map_router.py
git commit -m "feat(router): add GET /api/v1/map/cells endpoint with bbox validation"
```

---

## Task 6: Run Full Test Suite & Final Verification

**Step 1: Run all map-related tests**

Run: `cd backend && python -m pytest tests/test_map_*.py -v`
Expected: All tests PASS

**Step 2: Run full test suite to ensure no regressions**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS (including existing location tests)

**Step 3: Manual verification with curl (optional)**

Start server: `cd backend && uvicorn main:app --reload`

Test endpoints:
```bash
# Get token (adjust credentials)
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}' | jq -r '.access_token')

# Test summary endpoint
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/map/summary

# Test cells endpoint
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/map/cells?min_lng=-123&min_lat=37&max_lng=-122&max_lat=38"
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete map endpoints implementation

- GET /api/v1/map/summary - returns visited countries/regions
- GET /api/v1/map/cells - returns H3 cells in viewport

Implements design from docs/plans/2025-12-28-map-endpoints-design.md"
```

---

## Summary

| Task | Description | Tests |
|------|-------------|-------|
| 1 | Map schemas with bbox validation | 7 unit tests |
| 2 | MapService.get_summary() | 4 integration tests |
| 3 | MapService.get_cells_in_viewport() | 3 integration tests |
| 4 | Map router /summary endpoint | 3 integration tests |
| 5 | Map router /cells endpoint | 6 integration tests |
| 6 | Full test suite verification | All tests |

**Total: 23 new tests across 6 tasks**
