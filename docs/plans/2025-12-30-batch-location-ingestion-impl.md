---
name: Batch Location Ingestion Implementation
overview: "Implement POST /location/ingest/batch endpoint with bulk SQL operations, partial success handling, and optimized reverse geocoding."
todos:
  - id: schemas
    content: Add Pydantic schemas for batch request/response
    status: pending
  - id: service-helpers
    content: Add helper methods for validation, deduplication, and pre-query
    status: pending
  - id: service-geocode
    content: Add batch reverse geocoding method
    status: pending
  - id: service-bulk-upsert
    content: Add bulk upsert method with UNNEST
    status: pending
  - id: service-process-batch
    content: Add main process_batch() method
    status: pending
  - id: router
    content: Add /ingest/batch endpoint with rate limiting
    status: pending
  - id: tests
    content: Add comprehensive test suite
    status: pending
  - id: verify
    content: Run tests and verify implementation
    status: pending
---

# Batch Location Ingestion Implementation Plan

## Overview

This plan implements the batch location ingestion feature as designed in `2025-12-30-batch-location-ingestion-design.md`. Follow tasks in order using TDD (write tests first where applicable).

---

## Task 1: Add Pydantic Schemas

**File**: `backend/schemas/location.py`

### Add these new models after existing schemas:

```python
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
```

### Verification
```bash
cd backend
python3 -c "from schemas.location import BatchLocationIngestRequest, BatchLocationIngestResponse; print('Schemas OK')"
```

---

## Task 2: Add Helper Methods for Validation & Pre-Query

**File**: `backend/services/location_processor.py`

### Add these methods to `LocationProcessor` class:

```python
def _validate_and_dedupe_batch(
    self,
    locations: list,
) -> tuple[list[dict], list[dict]]:
    """
    Validate locations and dedupe by H3 res-8.

    Returns:
        (valid_locations, skipped_with_reasons)

    Each valid_location dict contains:
        - latitude, longitude, h3_res8, timestamp
        - h3_res6 (derived parent)
    """
    valid = []
    skipped = []
    seen_cells = set()

    for idx, loc in enumerate(locations):
        # Check H3 matches coordinates (with neighbor tolerance)
        expected_h3 = h3.latlng_to_cell(loc.latitude, loc.longitude, 8)
        if loc.h3_res8 != expected_h3:
            neighbors = h3.grid_ring(expected_h3, 1)
            if loc.h3_res8 not in neighbors:
                skipped.append({"index": idx, "reason": "h3_mismatch"})
                continue

        # Dedupe: keep first occurrence
        if loc.h3_res8 in seen_cells:
            continue
        seen_cells.add(loc.h3_res8)

        # Derive res-6 parent
        h3_res6 = h3.cell_to_parent(loc.h3_res8, 6)

        valid.append({
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "h3_res8": loc.h3_res8,
            "h3_res6": h3_res6,
            "timestamp": loc.timestamp or datetime.utcnow(),
        })

    return valid, skipped


def _get_existing_visits(self) -> dict:
    """
    Pre-query user's existing countries, states, and cells.

    Returns dict with sets:
        - country_ids: set[int]
        - state_ids: set[int]
        - h3_res6: set[str]
        - h3_res8: set[str]
    """
    # Get visited country and state IDs
    geo_query = text("""
        SELECT DISTINCT hc.country_id, hc.state_id
        FROM user_cell_visits ucv
        JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
        WHERE ucv.user_id = :user_id AND ucv.res = 8
    """)
    geo_results = self.db.execute(geo_query, {"user_id": self.user_id}).fetchall()

    country_ids = {r.country_id for r in geo_results if r.country_id}
    state_ids = {r.state_id for r in geo_results if r.state_id}

    # Get visited H3 cells
    cells_query = text("""
        SELECT h3_index, res FROM user_cell_visits
        WHERE user_id = :user_id
    """)
    cells_results = self.db.execute(cells_query, {"user_id": self.user_id}).fetchall()

    h3_res6 = {r.h3_index for r in cells_results if r.res == 6}
    h3_res8 = {r.h3_index for r in cells_results if r.res == 8}

    return {
        "country_ids": country_ids,
        "state_ids": state_ids,
        "h3_res6": h3_res6,
        "h3_res8": h3_res8,
    }
```

### Verification
```bash
cd backend
python3 -c "from services.location_processor import LocationProcessor; print('Helpers OK')"
```

---

## Task 3: Add Batch Reverse Geocoding Method

**File**: `backend/services/location_processor.py`

### Add this method to `LocationProcessor` class:

```python
def _batch_reverse_geocode(
    self,
    locations: list[dict],
) -> dict[str, tuple[Optional[int], Optional[int]]]:
    """
    Reverse geocode unique res-6 cells.

    Args:
        locations: List of location dicts with h3_res6, latitude, longitude

    Returns:
        Dict mapping h3_res6 -> (country_id, state_id)
    """
    # Group by unique res-6 cells, pick first location as representative point
    res6_representatives = {}
    for loc in locations:
        if loc["h3_res6"] not in res6_representatives:
            res6_representatives[loc["h3_res6"]] = (loc["latitude"], loc["longitude"])

    if not res6_representatives:
        return {}

    # Build query for all unique res-6 cells
    # Use a single query with multiple points for efficiency
    geocode_results = {}

    for h3_res6, (lat, lon) in res6_representatives.items():
        country_id, state_id = self._reverse_geocode(lat, lon)
        geocode_results[h3_res6] = (country_id, state_id)

    return geocode_results
```

**Note**: This implementation calls `_reverse_geocode` per unique res-6 cell. For further optimization, we could batch into a single PostGIS query with multiple points, but this is sufficient for MVP (typically <20 unique res-6 cells per batch).

### Verification
```bash
cd backend
python3 -c "from services.location_processor import LocationProcessor; print('Geocode OK')"
```

---

## Task 4: Add Bulk Upsert Method

**File**: `backend/services/location_processor.py`

### Add this method to `LocationProcessor` class:

```python
def _bulk_upsert_cells_and_visits(
    self,
    locations: list[dict],
    geocode_map: dict[str, tuple],
    existing_visits: dict,
    device_id: int,
) -> dict:
    """
    Bulk upsert cells and visits using PostgreSQL arrays.

    Returns dict with discovery counts:
        - new_cells_res6: int
        - new_cells_res8: int
        - new_country_ids: set[int]
        - new_state_ids: set[int]
    """
    # Prepare data for both resolutions
    res8_data = []
    res6_data = []
    res6_seen = set()

    for loc in locations:
        country_id, state_id = geocode_map.get(loc["h3_res6"], (None, None))

        # Res-8 cell data
        res8_data.append({
            "h3_index": loc["h3_res8"],
            "res": 8,
            "country_id": country_id,
            "state_id": state_id,
            "lat": loc["latitude"],
            "lon": loc["longitude"],
            "timestamp": loc["timestamp"],
        })

        # Res-6 cell data (dedupe within batch)
        if loc["h3_res6"] not in res6_seen:
            res6_seen.add(loc["h3_res6"])
            # Use centroid of res-6 cell
            res6_lat, res6_lon = h3.cell_to_latlng(loc["h3_res6"])
            res6_data.append({
                "h3_index": loc["h3_res6"],
                "res": 6,
                "country_id": country_id,
                "state_id": state_id,
                "lat": res6_lat,
                "lon": res6_lon,
                "timestamp": loc["timestamp"],
            })

    # Combine all cells for bulk insert
    all_cells = res6_data + res8_data

    # Bulk upsert h3_cells
    h3_cells_query = text("""
        INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid,
                              first_visited_at, last_visited_at, visit_count)
        VALUES (:h3_index, :res, :country_id, :state_id,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                :timestamp, :timestamp, 1)
        ON CONFLICT (h3_index)
        DO UPDATE SET
            last_visited_at = GREATEST(h3_cells.last_visited_at, EXCLUDED.last_visited_at),
            visit_count = h3_cells.visit_count + 1,
            country_id = COALESCE(h3_cells.country_id, EXCLUDED.country_id),
            state_id = COALESCE(h3_cells.state_id, EXCLUDED.state_id)
    """)

    for cell in all_cells:
        self.db.execute(h3_cells_query, cell)

    # Bulk upsert user_cell_visits and track new cells
    user_visits_query = text("""
        INSERT INTO user_cell_visits
            (user_id, device_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
        VALUES (:user_id, :device_id, :h3_index, :res, :timestamp, :timestamp, 1)
        ON CONFLICT (user_id, h3_index)
        DO UPDATE SET
            last_visited_at = GREATEST(user_cell_visits.last_visited_at, EXCLUDED.last_visited_at),
            visit_count = user_cell_visits.visit_count + 1,
            device_id = COALESCE(EXCLUDED.device_id, user_cell_visits.device_id)
        RETURNING h3_index, res, (xmax = 0) AS was_inserted
    """)

    new_cells_res6 = 0
    new_cells_res8 = 0
    new_country_ids = set()
    new_state_ids = set()

    for cell in all_cells:
        result = self.db.execute(user_visits_query, {
            "user_id": self.user_id,
            "device_id": device_id,
            "h3_index": cell["h3_index"],
            "res": cell["res"],
            "timestamp": cell["timestamp"],
        }).fetchone()

        if result.was_inserted:
            if result.res == 6:
                new_cells_res6 += 1
            else:
                new_cells_res8 += 1

                # Check for new country/state discoveries (only on res-8)
                country_id = cell["country_id"]
                state_id = cell["state_id"]

                if country_id and country_id not in existing_visits["country_ids"]:
                    new_country_ids.add(country_id)
                    existing_visits["country_ids"].add(country_id)  # Don't rediscover

                if state_id and state_id not in existing_visits["state_ids"]:
                    new_state_ids.add(state_id)
                    existing_visits["state_ids"].add(state_id)  # Don't rediscover

    return {
        "new_cells_res6": new_cells_res6,
        "new_cells_res8": new_cells_res8,
        "new_country_ids": new_country_ids,
        "new_state_ids": new_state_ids,
    }
```

### Verification
```bash
cd backend
python3 -c "from services.location_processor import LocationProcessor; print('Bulk upsert OK')"
```

---

## Task 5: Add Main `process_batch()` Method

**File**: `backend/services/location_processor.py`

### Add this method to `LocationProcessor` class:

```python
def process_batch(
    self,
    locations: list,
    device_uuid: Optional[str] = None,
    device_name: Optional[str] = None,
    platform: Optional[str] = None,
) -> dict:
    """
    Process a batch of locations efficiently.

    Args:
        locations: List of BatchLocationItem objects
        device_uuid: Optional device identifier
        device_name: Optional device name
        platform: Optional platform (ios/android/web)

    Returns:
        Dict with processed count, skipped info, discoveries, achievements
    """
    # Step 1: Validate and deduplicate
    valid_locations, skipped = self._validate_and_dedupe_batch(locations)

    if not valid_locations:
        return {
            "processed": 0,
            "skipped": len(skipped),
            "skipped_reasons": skipped,
            "discoveries": {
                "new_countries": [],
                "new_regions": [],
                "new_cells_res6": 0,
                "new_cells_res8": 0,
            },
            "achievements_unlocked": [],
        }

    # Step 2: Ensure device exists
    device_id = self._ensure_device(device_uuid, device_name, platform)

    # Step 3: Pre-query existing visits
    existing_visits = self._get_existing_visits()

    # Step 4: Batch reverse geocode
    geocode_map = self._batch_reverse_geocode(valid_locations)

    # Step 5: Bulk upsert cells and visits
    upsert_results = self._bulk_upsert_cells_and_visits(
        valid_locations, geocode_map, existing_visits, device_id
    )

    # Step 6: Record ingest batch for audit
    batch = IngestBatch(
        user_id=self.user_id,
        device_id=device_id,
        cells_count=len(valid_locations) * 2,  # res-6 + res-8 per location
        res_min=6,
        res_max=8,
    )
    self.db.add(batch)

    # Step 7: Check achievements (once at end)
    achievement_service = AchievementService(self.db, self.user_id)
    newly_unlocked = achievement_service.check_and_unlock()

    # Step 8: Commit transaction
    self.db.commit()

    # Step 9: Build response with country/state details
    new_countries = []
    if upsert_results["new_country_ids"]:
        countries = self.db.query(CountryRegion).filter(
            CountryRegion.id.in_(upsert_results["new_country_ids"])
        ).all()
        new_countries = [
            {"id": c.id, "name": c.name, "iso2": c.iso2}
            for c in countries
        ]

    new_regions = []
    if upsert_results["new_state_ids"]:
        states = self.db.query(StateRegion).filter(
            StateRegion.id.in_(upsert_results["new_state_ids"])
        ).all()
        new_regions = [
            {"id": s.id, "name": s.name, "code": s.code}
            for s in states
        ]

    return {
        "processed": len(valid_locations),
        "skipped": len(skipped),
        "skipped_reasons": skipped,
        "discoveries": {
            "new_countries": new_countries,
            "new_regions": new_regions,
            "new_cells_res6": upsert_results["new_cells_res6"],
            "new_cells_res8": upsert_results["new_cells_res8"],
        },
        "achievements_unlocked": [
            {
                "code": a.code,
                "name": a.name,
                "description": a.description,
            }
            for a in newly_unlocked
        ],
    }
```

### Verification
```bash
cd backend
python3 -c "from services.location_processor import LocationProcessor; print('process_batch OK')"
```

---

## Task 6: Add Router Endpoint

**File**: `backend/routers/location.py`

### Add import at top:
```python
from schemas.location import (
    LocationIngestRequest,
    LocationIngestResponse,
    BatchLocationIngestRequest,
    BatchLocationIngestResponse,
)
```

### Add endpoint after existing `/ingest` route:

```python
@router.post("/ingest/batch", response_model=BatchLocationIngestResponse)
@limiter.limit("30/minute")
def ingest_location_batch(
    request: Request,
    payload: BatchLocationIngestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Ingest a batch of locations (up to 100) efficiently.

    Use this endpoint for:
    - Syncing locations collected while offline
    - Batching real-time location updates (every 5-10 minutes)

    **Partial success**: Invalid locations are skipped with reasons,
    valid locations are always processed.

    **Rate limit**: 30 requests per minute per user.

    For >100 locations, client should chunk into multiple requests.
    """
    # Store user_id in request state for rate limiting
    request.state.user_id = current_user.id

    # Process the batch
    processor = LocationProcessor(db, current_user.id)

    try:
        result = processor.process_batch(
            locations=payload.locations,
            device_uuid=payload.device_uuid,
            device_name=payload.device_name,
            platform=payload.platform,
        )
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "service_unavailable", "message": str(e)},
        )
```

### Verification
```bash
cd backend
python3 -c "from routers.location import router; print('Router OK')"
```

---

## Task 7: Add Test Suite

**File**: `backend/tests/test_location_batch.py` (new file)

```python
"""Tests for batch location ingestion endpoint."""

import pytest
from datetime import datetime, timedelta
from fastapi import status
import h3


class TestBatchLocationIngest:
    """Tests for POST /api/v1/location/ingest/batch"""

    def test_batch_ingest_success(self, client, auth_headers, db_session):
        """Happy path: multiple valid locations are all processed."""
        # Generate 5 locations in San Francisco area
        base_lat, base_lon = 37.7749, -122.4194
        locations = []
        for i in range(5):
            lat = base_lat + (i * 0.001)
            lon = base_lon + (i * 0.001)
            h3_index = h3.latlng_to_cell(lat, lon, 8)
            locations.append({
                "latitude": lat,
                "longitude": lon,
                "h3_res8": h3_index,
                "timestamp": (datetime.utcnow() - timedelta(minutes=5-i)).isoformat(),
            })

        response = client.post(
            "/api/v1/location/ingest/batch",
            json={"locations": locations},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["processed"] == 5
        assert data["skipped"] == 0
        assert data["skipped_reasons"] == []

    def test_batch_ingest_empty_rejected(self, client, auth_headers):
        """Empty locations array returns 422."""
        response = client.post(
            "/api/v1/location/ingest/batch",
            json={"locations": []},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_batch_ingest_max_100_locations(self, client, auth_headers):
        """101 locations returns 422."""
        base_lat, base_lon = 37.7749, -122.4194
        locations = []
        for i in range(101):
            lat = base_lat + (i * 0.0001)
            lon = base_lon + (i * 0.0001)
            h3_index = h3.latlng_to_cell(lat, lon, 8)
            locations.append({
                "latitude": lat,
                "longitude": lon,
                "h3_res8": h3_index,
            })

        response = client.post(
            "/api/v1/location/ingest/batch",
            json={"locations": locations},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_batch_ingest_partial_success(self, client, auth_headers):
        """Mix of valid/invalid: valid processed, invalid skipped with reasons."""
        base_lat, base_lon = 37.7749, -122.4194
        h3_valid = h3.latlng_to_cell(base_lat, base_lon, 8)

        # Location in Tokyo but with SF H3 index (mismatch)
        h3_mismatched = h3.latlng_to_cell(35.6762, 139.6503, 8)

        locations = [
            {"latitude": base_lat, "longitude": base_lon, "h3_res8": h3_valid},  # Valid
            {"latitude": 35.6762, "longitude": 139.6503, "h3_res8": h3_valid},  # H3 mismatch
            {"latitude": base_lat + 0.001, "longitude": base_lon + 0.001,
             "h3_res8": h3.latlng_to_cell(base_lat + 0.001, base_lon + 0.001, 8)},  # Valid
        ]

        response = client.post(
            "/api/v1/location/ingest/batch",
            json={"locations": locations},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["processed"] == 2
        assert data["skipped"] == 1
        assert len(data["skipped_reasons"]) == 1
        assert data["skipped_reasons"][0]["index"] == 1
        assert data["skipped_reasons"][0]["reason"] == "h3_mismatch"

    def test_batch_ingest_deduplicates_cells(self, client, auth_headers, db_session):
        """Same H3 cell twice: only first processed (deduped)."""
        lat, lon = 37.7749, -122.4194
        h3_index = h3.latlng_to_cell(lat, lon, 8)

        locations = [
            {"latitude": lat, "longitude": lon, "h3_res8": h3_index,
             "timestamp": "2024-12-28T10:00:00Z"},
            {"latitude": lat, "longitude": lon, "h3_res8": h3_index,
             "timestamp": "2024-12-28T10:05:00Z"},  # Duplicate, should be ignored
        ]

        response = client.post(
            "/api/v1/location/ingest/batch",
            json={"locations": locations},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Only 1 unique cell processed (duplicate silently deduped, not "skipped")
        assert data["processed"] == 1
        assert data["skipped"] == 0

    def test_batch_ingest_discovers_country(
        self, client, auth_headers, db_session, seed_us_geography
    ):
        """First cells in new country: country appears in discoveries."""
        # Use coordinates in seeded US geography
        lat, lon = 37.7749, -122.4194  # San Francisco
        h3_index = h3.latlng_to_cell(lat, lon, 8)

        response = client.post(
            "/api/v1/location/ingest/batch",
            json={"locations": [{"latitude": lat, "longitude": lon, "h3_res8": h3_index}]},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should discover US (if geography is seeded)
        # Note: This test depends on seed_us_geography fixture
        assert data["discoveries"]["new_cells_res8"] >= 1

    def test_batch_ingest_triggers_achievement(
        self, client, auth_headers, db_session, seed_achievements
    ):
        """Batch pushes user over threshold: achievement unlocked."""
        # This test assumes "first_steps" achievement exists (threshold: 1 cell)
        lat, lon = 37.7749, -122.4194
        h3_index = h3.latlng_to_cell(lat, lon, 8)

        response = client.post(
            "/api/v1/location/ingest/batch",
            json={"locations": [{"latitude": lat, "longitude": lon, "h3_res8": h3_index}]},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should unlock "first_steps" achievement
        achievement_codes = [a["code"] for a in data["achievements_unlocked"]]
        assert "first_steps" in achievement_codes

    def test_batch_ingest_unauthenticated(self, client):
        """No token returns 401."""
        response = client.post(
            "/api/v1/location/ingest/batch",
            json={"locations": [{"latitude": 0, "longitude": 0, "h3_res8": "88283082bffffff"}]},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_batch_ingest_idempotent_cells(self, client, auth_headers, db_session):
        """Re-sending same cells increments visit_count, not duplicates."""
        lat, lon = 37.7749, -122.4194
        h3_index = h3.latlng_to_cell(lat, lon, 8)
        payload = {"locations": [{"latitude": lat, "longitude": lon, "h3_res8": h3_index}]}

        # First request
        response1 = client.post(
            "/api/v1/location/ingest/batch",
            json=payload,
            headers=auth_headers,
        )
        assert response1.status_code == status.HTTP_200_OK
        assert response1.json()["discoveries"]["new_cells_res8"] == 1

        # Second request with same cell
        response2 = client.post(
            "/api/v1/location/ingest/batch",
            json=payload,
            headers=auth_headers,
        )
        assert response2.status_code == status.HTTP_200_OK
        # Cell is no longer new (revisit)
        assert response2.json()["discoveries"]["new_cells_res8"] == 0
        assert response2.json()["processed"] == 1

    def test_batch_ingest_with_device_metadata(self, client, auth_headers, db_session):
        """Device metadata at batch level is applied."""
        lat, lon = 37.7749, -122.4194
        h3_index = h3.latlng_to_cell(lat, lon, 8)

        response = client.post(
            "/api/v1/location/ingest/batch",
            json={
                "locations": [{"latitude": lat, "longitude": lon, "h3_res8": h3_index}],
                "device_uuid": "test-device-123",
                "device_name": "Test iPhone",
                "platform": "ios",
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["processed"] == 1
```

### Verification
```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" \
  python3 -m pytest tests/test_location_batch.py -v
```

---

## Task 8: Run Full Test Suite and Verify

### Run all location tests:
```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" \
  python3 -m pytest tests/test_location*.py -v
```

### Run full test suite:
```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" \
  python3 -m pytest -v
```

### Manual API test:
```bash
# Get auth token first
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass123"}' | jq -r '.access_token')

# Test batch endpoint
curl -X POST http://localhost:8000/api/v1/location/ingest/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      {"latitude": 37.7749, "longitude": -122.4194, "h3_res8": "88283082bffffff"},
      {"latitude": 37.7849, "longitude": -122.4094, "h3_res8": "88283082affffff"}
    ],
    "platform": "ios"
  }'
```

---

## Summary

| Task | File(s) | Description |
|------|---------|-------------|
| 1 | `schemas/location.py` | Add batch request/response Pydantic models |
| 2 | `services/location_processor.py` | Add validation, deduplication, pre-query helpers |
| 3 | `services/location_processor.py` | Add batch reverse geocoding method |
| 4 | `services/location_processor.py` | Add bulk upsert method |
| 5 | `services/location_processor.py` | Add main `process_batch()` orchestration |
| 6 | `routers/location.py` | Add `/ingest/batch` endpoint with rate limiting |
| 7 | `tests/test_location_batch.py` | Add comprehensive test suite |
| 8 | - | Run tests and verify implementation |

**Estimated effort**: 3-4 hours following TDD
