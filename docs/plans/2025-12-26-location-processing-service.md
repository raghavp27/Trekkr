# Location Processing Service Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a real-time location ingestion endpoint that converts user coordinates into tracked H3 cells at resolutions 6 and 8, with country/region reverse geocoding and discovery feedback.

**Architecture:** Single POST endpoint receives lat/lon + client-calculated H3 res-8 cell. Service derives res-6 parent, performs PostGIS reverse geocoding for country/state, and upserts both H3Cell and UserCellVisit records. Returns discovery summary distinguishing new vs. revisited entities.

**Tech Stack:** FastAPI router, SQLAlchemy ORM with raw SQL for UPSERTs, PostGIS for spatial queries, h3 library (already installed), slowapi for rate limiting.

---

## Task 1: Add slowapi dependency

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Add slowapi to requirements**

Add after line 17 in `backend/requirements.txt`:

```
slowapi==0.1.9
```

**Step 2: Install the dependency**

Run: `pip install slowapi==0.1.9`
Expected: Successfully installed slowapi-0.1.9

**Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add slowapi for rate limiting"
```

---

## Task 2: Create Pydantic schemas for location ingestion

**Files:**
- Create: `backend/schemas/location.py`
- Modify: `backend/schemas/__init__.py`

**Step 1: Create the location schemas file**

Create `backend/schemas/location.py`:

```python
"""Pydantic schemas for location ingestion endpoint."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator
import h3


class LocationIngestRequest(BaseModel):
    """Request schema for location ingestion."""

    latitude: float
    longitude: float
    h3_res8: str
    timestamp: Optional[datetime] = None
    device_id: Optional[str] = None

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
```

**Step 2: Export from schemas package**

Add to `backend/schemas/__init__.py`:

```python
from .location import (
    LocationIngestRequest,
    LocationIngestResponse,
    DiscoveriesResponse,
    RevisitsResponse,
    VisitCountsResponse,
    CountryDiscovery,
    StateDiscovery,
)
```

**Step 3: Verify schema imports work**

Run: `cd backend && python -c "from schemas.location import LocationIngestRequest; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add backend/schemas/location.py backend/schemas/__init__.py
git commit -m "feat(schemas): add location ingestion request/response schemas"
```

---

## Task 3: Create location processor service

**Files:**
- Create: `backend/services/location_processor.py`
- Modify: `backend/services/__init__.py`

**Step 1: Create the location processor service**

Create `backend/services/location_processor.py`:

```python
"""Location processing service for H3 cell tracking."""

from datetime import datetime
from typing import Optional, Tuple

import h3
from sqlalchemy import text
from sqlalchemy.orm import Session

from models.geo import CountryRegion, H3Cell, StateRegion
from models.visits import IngestBatch, UserCellVisit


class LocationProcessor:
    """Processes location updates and tracks cell visits."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def process_location(
        self,
        latitude: float,
        longitude: float,
        h3_res8: str,
        device_id: Optional[int] = None,
        timestamp: Optional[datetime] = None,
    ) -> dict:
        """
        Process a location update and record cell visits.

        Returns discovery summary with new vs. revisited entities.
        """
        timestamp = timestamp or datetime.utcnow()

        # Derive parent res-6 cell from res-8
        h3_res6 = h3.cell_to_parent(h3_res8, 6)

        # Reverse geocode to find country/state
        country_id, state_id = self._reverse_geocode(latitude, longitude)

        # Process both resolutions
        res6_result = self._upsert_cell_visit(
            h3_index=h3_res6,
            res=6,
            latitude=latitude,
            longitude=longitude,
            country_id=country_id,
            state_id=state_id,
            device_id=device_id,
        )

        res8_result = self._upsert_cell_visit(
            h3_index=h3_res8,
            res=8,
            latitude=latitude,
            longitude=longitude,
            country_id=country_id,
            state_id=state_id,
            device_id=device_id,
        )

        # Record audit batch
        self._record_ingest_batch(device_id)

        # Commit transaction
        self.db.commit()

        # Build response
        return self._build_response(
            res6_result=res6_result,
            res8_result=res8_result,
            country_id=country_id,
            state_id=state_id,
        )

    def _reverse_geocode(
        self, latitude: float, longitude: float
    ) -> Tuple[Optional[int], Optional[int]]:
        """Find country and state containing the given point using PostGIS."""
        query = text("""
            WITH point AS (
                SELECT ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) AS geom
            )
            SELECT
                (SELECT id FROM regions_country
                 WHERE ST_Contains(geom, (SELECT geom FROM point))
                 LIMIT 1) AS country_id,
                (SELECT id FROM regions_state
                 WHERE ST_Contains(geom, (SELECT geom FROM point))
                 LIMIT 1) AS state_id
        """)

        result = self.db.execute(
            query, {"lat": latitude, "lon": longitude}
        ).fetchone()

        if result:
            return result.country_id, result.state_id
        return None, None

    def _upsert_cell_visit(
        self,
        h3_index: str,
        res: int,
        latitude: float,
        longitude: float,
        country_id: Optional[int],
        state_id: Optional[int],
        device_id: Optional[int],
    ) -> dict:
        """Upsert H3Cell and UserCellVisit records, return insert/update status."""

        # Upsert H3Cell (global registry)
        h3_cell_query = text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid,
                                  first_visited_at, last_visited_at, visit_count)
            VALUES (:h3_index, :res, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                    NOW(), NOW(), 1)
            ON CONFLICT (h3_index)
            DO UPDATE SET
                last_visited_at = NOW(),
                visit_count = h3_cells.visit_count + 1,
                country_id = COALESCE(h3_cells.country_id, EXCLUDED.country_id),
                state_id = COALESCE(h3_cells.state_id, EXCLUDED.state_id)
            RETURNING h3_index, (xmax = 0) AS was_inserted
        """)

        self.db.execute(h3_cell_query, {
            "h3_index": h3_index,
            "res": res,
            "country_id": country_id,
            "state_id": state_id,
            "lat": latitude,
            "lon": longitude,
        })

        # Upsert UserCellVisit (per-user tracking)
        user_visit_query = text("""
            INSERT INTO user_cell_visits
                (user_id, device_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :device_id, :h3_index, :res, NOW(), NOW(), 1)
            ON CONFLICT (user_id, h3_index)
            DO UPDATE SET
                last_visited_at = NOW(),
                visit_count = user_cell_visits.visit_count + 1,
                device_id = COALESCE(EXCLUDED.device_id, user_cell_visits.device_id)
            RETURNING h3_index, res, visit_count, (xmax = 0) AS was_inserted
        """)

        result = self.db.execute(user_visit_query, {
            "user_id": self.user_id,
            "device_id": device_id,
            "h3_index": h3_index,
            "res": res,
        }).fetchone()

        return {
            "h3_index": result.h3_index,
            "res": result.res,
            "visit_count": result.visit_count,
            "is_new": result.was_inserted,
        }

    def _record_ingest_batch(self, device_id: Optional[int]) -> None:
        """Record audit entry for this ingestion."""
        batch = IngestBatch(
            user_id=self.user_id,
            device_id=device_id,
            cells_count=2,  # res-6 + res-8
            res_min=6,
            res_max=8,
        )
        self.db.add(batch)

    def _build_response(
        self,
        res6_result: dict,
        res8_result: dict,
        country_id: Optional[int],
        state_id: Optional[int],
    ) -> dict:
        """Build the discovery/revisit response."""
        discoveries = {
            "new_country": None,
            "new_state": None,
            "new_cells_res6": [],
            "new_cells_res8": [],
        }
        revisits = {
            "cells_res6": [],
            "cells_res8": [],
        }

        # Categorize res-6 cell
        if res6_result["is_new"]:
            discoveries["new_cells_res6"].append(res6_result["h3_index"])
        else:
            revisits["cells_res6"].append(res6_result["h3_index"])

        # Categorize res-8 cell
        if res8_result["is_new"]:
            discoveries["new_cells_res8"].append(res8_result["h3_index"])
        else:
            revisits["cells_res8"].append(res8_result["h3_index"])

        # Check if this is user's first visit to country/state
        # (Only if res-8 cell is new - indicates potential new region)
        if res8_result["is_new"]:
            if country_id:
                country = self.db.query(CountryRegion).filter(
                    CountryRegion.id == country_id
                ).first()
                if country:
                    # Check if user has any other cells in this country
                    other_cells = self.db.execute(text("""
                        SELECT 1 FROM user_cell_visits ucv
                        JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                        WHERE ucv.user_id = :user_id
                          AND hc.country_id = :country_id
                          AND ucv.h3_index != :current_h3
                        LIMIT 1
                    """), {
                        "user_id": self.user_id,
                        "country_id": country_id,
                        "current_h3": res8_result["h3_index"],
                    }).fetchone()

                    if not other_cells:
                        discoveries["new_country"] = {
                            "id": country.id,
                            "name": country.name,
                            "iso2": country.iso2,
                        }

            if state_id:
                state = self.db.query(StateRegion).filter(
                    StateRegion.id == state_id
                ).first()
                if state:
                    other_cells = self.db.execute(text("""
                        SELECT 1 FROM user_cell_visits ucv
                        JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                        WHERE ucv.user_id = :user_id
                          AND hc.state_id = :state_id
                          AND ucv.h3_index != :current_h3
                        LIMIT 1
                    """), {
                        "user_id": self.user_id,
                        "state_id": state_id,
                        "current_h3": res8_result["h3_index"],
                    }).fetchone()

                    if not other_cells:
                        discoveries["new_state"] = {
                            "id": state.id,
                            "name": state.name,
                            "code": state.code,
                        }

        return {
            "discoveries": discoveries,
            "revisits": revisits,
            "visit_counts": {
                "res6_visit_count": res6_result["visit_count"],
                "res8_visit_count": res8_result["visit_count"],
            },
        }
```

**Step 2: Export from services package**

Update `backend/services/__init__.py`:

```python
from .location_processor import LocationProcessor
```

**Step 3: Verify service imports work**

Run: `cd backend && python -c "from services.location_processor import LocationProcessor; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add backend/services/location_processor.py backend/services/__init__.py
git commit -m "feat(services): add LocationProcessor for cell visit tracking"
```

---

## Task 4: Create location router with rate limiting

**Files:**
- Create: `backend/routers/location.py`

**Step 1: Create the location router**

Create `backend/routers/location.py`:

```python
"""Location ingestion API endpoint."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
import h3

from database import get_db
from models.user import User
from models.device import Device
from schemas.location import LocationIngestRequest, LocationIngestResponse
from services.auth import get_current_user
from services.location_processor import LocationProcessor


def get_user_id_from_request(request: Request) -> str:
    """Extract user ID for rate limiting key."""
    # During rate limit check, user may not be authenticated yet
    # Fall back to IP address if no user context
    if hasattr(request.state, "user_id"):
        return str(request.state.user_id)
    return get_remote_address(request)


limiter = Limiter(key_func=get_user_id_from_request)
router = APIRouter()


@router.post("/ingest", response_model=LocationIngestResponse)
@limiter.limit("120/minute")
def ingest_location(
    request: Request,
    payload: LocationIngestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Ingest a location update and record H3 cell visits.

    The client should send this request when the user moves to a new H3 res-8 cell.
    The server will:
    1. Derive the parent res-6 cell
    2. Perform reverse geocoding to find country/state
    3. Record visits for both resolutions
    4. Return discovery summary (new vs. revisited entities)

    Rate limit: 120 requests per minute per user.
    """
    # Store user_id in request state for rate limiting
    request.state.user_id = current_user.id

    # Validate H3 index matches coordinates (with neighbor tolerance for GPS jitter)
    expected_h3 = h3.latlng_to_cell(payload.latitude, payload.longitude, 8)
    if payload.h3_res8 != expected_h3:
        # Check if it's a neighbor (handles GPS jitter at cell boundaries)
        neighbors = h3.grid_ring(expected_h3, 1)
        if payload.h3_res8 not in neighbors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "h3_mismatch",
                    "message": "H3 index does not match coordinates",
                    "expected": expected_h3,
                    "received": payload.h3_res8,
                },
            )

    # Resolve device_id if provided
    device_id = None
    if payload.device_id:
        device = db.query(Device).filter(
            Device.device_uuid == payload.device_id,
            Device.user_id == current_user.id,
        ).first()
        if device:
            device_id = device.id

    # Process the location
    processor = LocationProcessor(db, current_user.id)

    try:
        result = processor.process_location(
            latitude=payload.latitude,
            longitude=payload.longitude,
            h3_res8=payload.h3_res8,
            device_id=device_id,
            timestamp=payload.timestamp,
        )
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "service_unavailable", "message": str(e)},
        )
```

**Step 2: Verify router imports work**

Run: `cd backend && python -c "from routers.location import router; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add backend/routers/location.py
git commit -m "feat(routers): add location ingestion endpoint with rate limiting"
```

---

## Task 5: Register router and configure rate limiter in main.py

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/routers/__init__.py`

**Step 1: Update routers __init__.py to export location**

Update `backend/routers/__init__.py`:

```python
from . import auth, health, location
```

**Step 2: Update main.py to register location router and rate limiter**

Replace entire `backend/main.py` with:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from database import init_db
from routers import auth, health, location
from routers.location import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup: Initialize the database
    init_db()
    yield
    # Shutdown: Cleanup if needed


app = FastAPI(
    title="Trekkr API",
    description="Backend API for Trekkr",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware configuration
# Update origins list when frontend is available
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(location.router, prefix="/api/v1/location", tags=["location"])


@app.get("/")
async def root():
    return {"message": "Welcome to Trekkr API"}
```

**Step 3: Verify app starts without errors**

Run: `cd backend && python -c "from main import app; print('App loaded OK')"`
Expected: App loaded OK

**Step 4: Commit**

```bash
git add backend/main.py backend/routers/__init__.py
git commit -m "feat: register location router with rate limiting in main app"
```

---

## Task 6: Add PostGIS spatial indexes migration

**Files:**
- Create: `backend/alembic/versions/YYYYMMDD_XXXX_add_spatial_indexes.py`

**Step 1: Create alembic migration for spatial indexes**

Run: `cd backend && alembic revision -m "add_spatial_indexes_for_reverse_geocoding"`

This will create a migration file. Edit it to contain:

```python
"""add_spatial_indexes_for_reverse_geocoding

Revision ID: <auto-generated>
Revises: <previous-revision>
Create Date: <auto-generated>
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers
revision: str = "<auto-generated>"
down_revision: Union[str, None] = "<previous-revision>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create GIST indexes on geometry columns for fast spatial queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_regions_country_geom
        ON regions_country USING GIST (geom)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_regions_state_geom
        ON regions_state USING GIST (geom)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_regions_country_geom")
    op.execute("DROP INDEX IF EXISTS ix_regions_state_geom")
```

**Step 2: Apply the migration**

Run: `cd backend && alembic upgrade head`
Expected: INFO  [alembic.runtime.migration] Running upgrade ... -> ..., add_spatial_indexes_for_reverse_geocoding

**Step 3: Commit**

```bash
git add backend/alembic/versions/*add_spatial_indexes*.py
git commit -m "migration: add PostGIS GIST indexes for reverse geocoding"
```

---

## Task 7: Manual integration test

**Step 1: Start the backend server**

Run: `cd backend && uvicorn main:app --reload`
Expected: Uvicorn running on http://127.0.0.1:8000

**Step 2: Create test user and get token (in another terminal)**

```bash
# Register
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "username": "testuser", "password": "TestPass123"}'

# Save the access_token from response
```

**Step 3: Test location ingestion**

```bash
# Use the access_token from step 2
curl -X POST http://127.0.0.1:8000/api/v1/location/ingest \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -d '{
    "latitude": 37.7749,
    "longitude": -122.4194,
    "h3_res8": "'$(python3 -c "import h3; print(h3.latlng_to_cell(37.7749, -122.4194, 8))")'"
  }'
```

Expected: JSON response with discoveries and visit_counts

**Step 4: Test duplicate handling (send same location again)**

Run the same curl command from Step 3 again.
Expected: cells should now be in "revisits" instead of "discoveries", visit_count should be 2

**Step 5: Final commit with any fixes**

```bash
git add -A
git commit -m "feat: complete location processing service implementation"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add slowapi dependency | requirements.txt |
| 2 | Create Pydantic schemas | schemas/location.py |
| 3 | Create LocationProcessor service | services/location_processor.py |
| 4 | Create location router | routers/location.py |
| 5 | Register router in main.py | main.py, routers/__init__.py |
| 6 | Add PostGIS spatial indexes | alembic migration |
| 7 | Manual integration test | - |

Total estimated commits: 7
