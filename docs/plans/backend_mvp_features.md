---
name: Backend MVP Features
overview: "Implement remaining backend features needed for MVP launch: single device per user, profile summary, achievements system, password management, account deletion, batch location ingestion, visit history, and error handling improvements."
todos:
  - id: device-single-user
    content: Add unique constraint for one device per user, update LocationProcessor
    status: pending
  - id: profile-summary
    content: Create /stats/overview endpoint with user stats and recent visits
    status: pending
  - id: password-change
    content: Implement POST /auth/change-password endpoint
    status: pending
  - id: account-deletion
    content: Implement DELETE /auth/account with cascade validation
    status: pending
  - id: achievements-system
    content: Create achievement service, seed 10 achievements, add endpoints
    status: pending
  - id: batch-ingestion
    content: Create POST /location/ingest/batch endpoint with bulk SQL operations
    status: pending
  - id: visit-timeline
    content: Create /visits/timeline endpoint with discovery and milestone events
    status: pending
  - id: error-handling
    content: Implement standardized error responses with error codes
    status: pending
---

# Backend MVP Features Implementation Plan

## Overview

Complete the backend API to MVP-ready state with essential user features. This plan covers 8 major feature areas needed before frontend integration and launch.

**Key Simplification:** Users have exactly ONE device (1:1 relationship). Auto-create device on first location ingestion.

## Architecture Decisions

### Device Model Simplification

- **Current:** `Device` model supports multiple devices per user (1:many)
- **MVP Change:** One device per user (1:1 relationship)
- **Implementation:** 
  - Keep existing `devices` table structure for future flexibility
  - Add unique constraint: `(user_id)` in migration
  - Auto-create device record on first location ingestion (if not exists)
  - No device management endpoints needed (auto-managed)
  - Device updates via `PATCH /api/auth/device` (update device_name/platform)

### Tech Stack

- **Framework:** FastAPI 0.115.6
- **Database:** PostgreSQL 16 + PostGIS
- **ORM:** SQLAlchemy 2.0 (raw SQL with `text()` for complex queries)
- **Validation:** Pydantic v2
- **Testing:** pytest with 100% endpoint coverage target

---

## Feature 1: Single Device Per User (DONE)

### Changes Required

**Migration:** `backend/alembic/versions/20251228_XXXX_single_device_per_user.py`

```sql
-- Add unique constraint on user_id
ALTER TABLE devices ADD CONSTRAINT uq_devices_user_id UNIQUE (user_id);
```

**Service Layer:** Update `LocationProcessor._ensure_device()`

```python
def _ensure_device(self, device_uuid: Optional[str], device_name: Optional[str], 
                   platform: Optional[str]) -> int:
    """Get or create user's single device."""
    device = self.db.query(Device).filter(Device.user_id == self.user_id).first()
    
    if not device:
        # Create first device
        device = Device(
            user_id=self.user_id,
            device_uuid=device_uuid,
            device_name=device_name or "My Phone",
            platform=platform or "unknown"
        )
        self.db.add(device)
        self.db.flush()
    else:
        # Update metadata if provided
        if device_uuid and device.device_uuid != device_uuid:
            device.device_uuid = device_uuid
        if device_name:
            device.device_name = device_name
        if platform:
            device.platform = platform
    
    return device.id
```

**Endpoint:** `PATCH /api/auth/device` (update device metadata)

**Schemas:** [`backend/schemas/auth.py`](backend/schemas/auth.py)

```python
class DeviceUpdateRequest(BaseModel):
    device_name: Optional[str] = None
    platform: Optional[str] = None  # "ios", "android", "web"
    app_version: Optional[str] = None

class DeviceResponse(BaseModel):
    id: int
    device_uuid: Optional[str]
    device_name: Optional[str]
    platform: Optional[str]
    app_version: Optional[str]
    created_at: datetime
    updated_at: datetime
```

**Tests:**

- `test_device_auto_creation_on_first_ingestion()`
- `test_device_metadata_update()`
- `test_duplicate_device_constraint()`

---

## Feature 2: Profile Summary Endpoint

### Endpoint Design

**Route:** `GET /api/v1/stats/overview`

**Response:**

```json
{
  "user": {
    "id": 1,
    "username": "traveler",
    "created_at": "2024-01-15T10:00:00Z"
  },
  "stats": {
    "countries_visited": 12,
    "regions_visited": 45,
    "cells_visited_res6": 234,
    "cells_visited_res8": 1523,
    "first_visit_at": "2024-01-20T08:30:00Z",
    "last_visit_at": "2024-12-28T14:22:00Z",
    "total_visit_count": 2847
  },
  "recent": {
    "last_country": {
      "code": "US",
      "name": "United States",
      "visited_at": "2024-12-28T14:22:00Z"
    },
    "last_region": {
      "code": "US-CA",
      "name": "California",
      "visited_at": "2024-12-28T14:22:00Z"
    }
  }
}
```

**Implementation:**

Service: [`backend/services/stats_service.py`](backend/services/stats_service.py) - add `get_overview()` method

Router: [`backend/routers/stats.py`](backend/routers/stats.py) - add `/overview` endpoint

Schema: [`backend/schemas/stats.py`](backend/schemas/stats.py) - add response models

**SQL Query Strategy:**

```sql
-- Single query with CTEs for efficiency
WITH user_stats AS (
  SELECT 
    COUNT(DISTINCT CASE WHEN res = 6 THEN h3_index END) as cells_res6,
    COUNT(DISTINCT CASE WHEN res = 8 THEN h3_index END) as cells_res8,
    MIN(first_visited_at) as first_visit,
    MAX(last_visited_at) as last_visit,
    SUM(visit_count) as total_visits
  FROM user_cell_visits
  WHERE user_id = :user_id
),
country_stats AS (
  SELECT COUNT(DISTINCT hc.country_id) as countries
  FROM user_cell_visits ucv
  JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
  WHERE ucv.user_id = :user_id AND ucv.res = 8
),
region_stats AS (
  SELECT COUNT(DISTINCT hc.state_id) as regions
  FROM user_cell_visits ucv
  JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
  WHERE ucv.user_id = :user_id AND ucv.res = 8 AND hc.state_id IS NOT NULL
),
recent_country AS (
  SELECT rc.iso2 as code, rc.name, ucv.last_visited_at
  FROM user_cell_visits ucv
  JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
  JOIN regions_country rc ON hc.country_id = rc.id
  WHERE ucv.user_id = :user_id
  ORDER BY ucv.last_visited_at DESC
  LIMIT 1
)
SELECT * FROM user_stats, country_stats, region_stats, recent_country;
```

**Tests:**

- `test_overview_for_new_user_returns_zeros()`
- `test_overview_returns_correct_stats()`
- `test_overview_requires_authentication()`

---

## Feature 3: Achievements System

### Database & Models

**Models Already Exist:** [`backend/models/achievements.py`](backend/models/achievements.py) ✅

**Migration:** `20251228_XXXX_seed_initial_achievements.py`

Seed 10 initial achievements:

```python
achievements = [
    {"code": "first_steps", "name": "First Steps", "description": "Visit your first location", 
     "criteria_json": {"type": "cells_total", "threshold": 1}},
    {"code": "explorer", "name": "Explorer", "description": "Visit 100 unique cells",
     "criteria_json": {"type": "cells_total", "threshold": 100}},
    {"code": "wanderer", "name": "Wanderer", "description": "Visit 500 unique cells",
     "criteria_json": {"type": "cells_total", "threshold": 500}},
    {"code": "globetrotter", "name": "Globetrotter", "description": "Visit 10 countries",
     "criteria_json": {"type": "countries", "threshold": 10}},
    {"code": "country_collector", "name": "Country Collector", "description": "Visit 25 countries",
     "criteria_json": {"type": "countries", "threshold": 25}},
    {"code": "state_hopper", "name": "State Hopper", "description": "Visit 5 regions in one country",
     "criteria_json": {"type": "regions_in_country", "threshold": 5}},
    {"code": "regional_master", "name": "Regional Master", "description": "Visit 50 regions total",
     "criteria_json": {"type": "regions", "threshold": 50}},
    {"code": "hemisphere_hopper", "name": "Hemisphere Hopper", "description": "Visit both northern and southern hemispheres",
     "criteria_json": {"type": "hemispheres", "count": 2}},
    {"code": "coverage_bronze", "name": "Bronze Coverage", "description": "Achieve 10% coverage of any country",
     "criteria_json": {"type": "country_coverage_pct", "threshold": 0.10}},
    {"code": "frequent_traveler", "name": "Frequent Traveler", "description": "Visit locations on 30 different days",
     "criteria_json": {"type": "unique_days", "threshold": 30}},
]
```

### Service Layer

**File:** `backend/services/achievement_service.py` (new)

**Key Methods:**

```python
class AchievementService:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
    
    def check_and_unlock(self) -> List[Achievement]:
        """Check all achievements and unlock newly earned ones."""
        # Get user stats
        # Get already unlocked achievements
        # Check each unearned achievement
        # Unlock newly earned ones
        # Return list of newly unlocked achievements
        
    def get_all_achievements(self) -> List[dict]:
        """Get all achievements with user's unlock status."""
        
    def get_unlocked_achievements(self) -> List[dict]:
        """Get only user's unlocked achievements."""
```

### Integration with Location Ingestion

**Update:** [`backend/services/location_processor.py`](backend/services/location_processor.py)

Add to `process_location()` return value:

```python
def process_location(...) -> dict:
    # ... existing processing ...
    
    # Check achievements after cell visit recorded
    from services.achievement_service import AchievementService
    achievement_service = AchievementService(self.db, self.user_id)
    newly_unlocked = achievement_service.check_and_unlock()
    
    return {
        "discoveries": discoveries,
        "revisits": revisits,
        "visit_counts": visit_counts,
        "achievements_unlocked": [
            {"code": a.code, "name": a.name} for a in newly_unlocked
        ]
    }
```

### Endpoints

**Router:** `backend/routers/achievements.py` (new)

Routes:

- `GET /api/v1/achievements` - All achievements with unlock status
- `GET /api/v1/achievements/unlocked` - User's unlocked achievements only

**Schemas:** `backend/schemas/achievements.py` (new)

**Tests:** `backend/tests/test_achievement_service.py`, `test_achievement_router.py`

---

## Feature 4: Password Management

### Endpoints

**Change Password:** `POST /api/auth/change-password` (authenticated)

Request:

```json
{
  "current_password": "OldPass123",
  "new_password": "NewPass456"
}
```

**Forgot Password:** `POST /api/auth/forgot-password`

Request:

```json
{
  "email": "user@example.com"
}
```

Response: `{"message": "Password reset email sent"}` (always success to prevent email enumeration)

**Reset Password:** `POST /api/auth/reset-password`

Request:

```json
{
  "token": "reset_token_here",
  "new_password": "NewPass789"
}
```

### Implementation Notes

**For MVP (without email infrastructure):**

- Implement change-password endpoint only
- Document forgot-password/reset-password schemas (implement in Phase 2)
- Return 501 Not Implemented for forgot/reset endpoints with helpful message:
  ```json
  {
    "detail": "Password reset via email is not yet available. Please contact support."
  }
  ```


**Change Password Logic:**

1. Verify current password matches
2. Validate new password (reuse validation from registration)
3. Hash new password
4. Update `hashed_password` in database
5. Invalidate all existing tokens (optional: add token versioning)

**Files:**

- Router: [`backend/routers/auth.py`](backend/routers/auth.py)
- Schemas: [`backend/schemas/auth.py`](backend/schemas/auth.py)
- Service: [`backend/services/auth.py`](backend/services/auth.py)

**Tests:**

- `test_change_password_success()`
- `test_change_password_wrong_current()`
- `test_change_password_invalid_new()`
- `test_change_password_unauthenticated()`

---

## Feature 5: Account Deletion

### Endpoint Design

**Route:** `DELETE /api/auth/account`

**Request:**

```json
{
  "password": "MyPassword123",
  "confirmation": "DELETE"
}
```

**Response:** 204 No Content

### Implementation

**Validation:**

1. Verify password matches
2. Require exact string "DELETE" in confirmation field (prevent accidents)
3. Authenticate user (must have valid token)

**Deletion Strategy:**

- Leverage existing CASCADE constraints in database
- Single `db.delete(user)` will cascade to:
  - `devices` (ondelete="CASCADE")
  - `user_cell_visits` (ondelete="CASCADE")
  - `ingest_batches` (ondelete="CASCADE")
  - `user_achievements` (ondelete="CASCADE")
- Do NOT delete `h3_cells` (global registry, other users may have visited)

**Endpoint Logic:**

```python
@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    request: AccountDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify password
    if not verify_password(request.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # Require explicit confirmation
    if request.confirmation != "DELETE":
        raise HTTPException(
            status_code=400, 
            detail="Confirmation must be exactly 'DELETE'"
        )
    
    # Delete user (cascades to all related records)
    db.delete(current_user)
    db.commit()
    
    return Response(status_code=204)
```

**Files:**

- Router: [`backend/routers/auth.py`](backend/routers/auth.py)
- Schema: [`backend/schemas/auth.py`](backend/schemas/auth.py) - add `AccountDeleteRequest`

**Tests:**

- `test_delete_account_success()`
- `test_delete_account_wrong_password()`
- `test_delete_account_wrong_confirmation()`
- `test_delete_account_cascades_data()`
- `test_delete_account_preserves_global_h3_cells()`

---

## Feature 6: Batch Location Ingestion

### Motivation

Mobile apps collect locations while offline or in background. Sending locations one-by-one is inefficient (slow, high API call count). Batch ingestion reduces:

- API calls by 10-50x
- Network usage
- Client battery drain
- Server load

### Endpoint Design

**Route:** `POST /api/v1/location/ingest/batch`

**Rate Limit:** `30/minute` (vs 120/min for single ingestion)

**Request:**

```json
{
  "locations": [
    {
      "latitude": 37.7749,
      "longitude": -122.4194,
      "h3_res8": "882830810ffffff",
      "timestamp": "2024-12-28T10:30:00Z"
    },
    {
      "latitude": 37.7750,
      "longitude": -122.4195,
      "h3_res8": "882830811ffffff",
      "timestamp": "2024-12-28T10:35:00Z"
    }
    // ... up to 100 locations
  ],
  "device_id": "optional-uuid"
}
```

**Constraints:**

- Max 100 locations per batch
- Timestamps must be chronologically ordered
- Duplicate h3_res8 cells within batch are deduplicated

**Response:**

```json
{
  "processed": 98,
  "skipped": 2,
  "discoveries": {
    "new_countries": [{"code": "US", "name": "United States"}],
    "new_regions": [{"code": "US-CA", "name": "California"}],
    "new_cells_res6": 12,
    "new_cells_res8": 45
  },
  "achievements_unlocked": [
    {"code": "explorer", "name": "Explorer"}
  ]
}
```

### Implementation Strategy

**Optimize with Bulk Operations:**

1. **Deduplicate cells** within batch (client-side should already do this)
2. **Reverse geocode once per unique country/region** (not per cell)
3. **Bulk upsert cells** using single SQL statement with `VALUES` clause
4. **Single achievement check** at end (not per cell)

**SQL Optimization:**

```sql
-- Bulk insert cells (PostgreSQL UNNEST)
INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, ...)
SELECT * FROM UNNEST(
  :h3_indexes, :resolutions, :country_ids, :state_ids, :centroids, ...
) AS t(h3_index, res, country_id, state_id, centroid, ...)
ON CONFLICT (h3_index) DO UPDATE SET ...;

-- Bulk insert user visits
INSERT INTO user_cell_visits (user_id, h3_index, res, ...)
SELECT :user_id, * FROM UNNEST(:h3_indexes, :resolutions, ...)
ON CONFLICT (user_id, h3_index) DO UPDATE SET ...;
```

**Files:**

- Router: [`backend/routers/location.py`](backend/routers/location.py)
- Schema: [`backend/schemas/location.py`](backend/schemas/location.py) - add `BatchLocationIngestRequest/Response`
- Service: [`backend/services/location_processor.py`](backend/services/location_processor.py) - add `process_batch()`

**Tests:**

- `test_batch_ingest_success()`
- `test_batch_ingest_max_100_locations()`
- `test_batch_ingest_deduplicates_cells()`
- `test_batch_ingest_discoveries()`
- `test_batch_ingest_rate_limit()`

---

## Feature 7: Visit History Timeline

### Endpoint Design

**Route:** `GET /api/v1/visits/timeline`

**Query Params:**

- `limit` (default: 50, max: 100)
- `offset` (default: 0)
- `type` (optional filter: "country" | "region" | "milestone")

**Response:**

```json
{
  "total_events": 156,
  "events": [
    {
      "type": "country_discovered",
      "timestamp": "2024-12-28T14:22:00Z",
      "data": {
        "code": "US",
        "name": "United States",
        "cell_h3": "882830810ffffff"
      }
    },
    {
      "type": "region_discovered",
      "timestamp": "2024-12-28T14:22:00Z",
      "data": {
        "code": "US-CA",
        "name": "California",
        "country_name": "United States"
      }
    },
    {
      "type": "milestone_reached",
      "timestamp": "2024-12-25T09:15:00Z",
      "data": {
        "milestone": "100_cells",
        "count": 100
      }
    }
  ]
}
```

### Event Types

1. **country_discovered** - First cell in a country
2. **region_discovered** - First cell in a region/state
3. **milestone_reached** - Cell count milestones (100, 500, 1000, 5000)

### Implementation

**SQL Query:**

```sql
-- Get first visits to countries
SELECT 
  'country_discovered' as type,
  MIN(ucv.first_visited_at) as timestamp,
  json_build_object(
    'code', rc.iso2,
    'name', rc.name
  ) as data
FROM user_cell_visits ucv
JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
JOIN regions_country rc ON hc.country_id = rc.id
WHERE ucv.user_id = :user_id AND ucv.res = 8
GROUP BY rc.id, rc.iso2, rc.name

UNION ALL

-- Get first visits to regions
SELECT 
  'region_discovered' as type,
  MIN(ucv.first_visited_at) as timestamp,
  json_build_object(
    'code', CONCAT(rc.iso2, '-', rs.code),
    'name', rs.name,
    'country_name', rc.name
  ) as data
FROM user_cell_visits ucv
JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
JOIN regions_state rs ON hc.state_id = rs.id
JOIN regions_country rc ON rs.country_id = rc.id
WHERE ucv.user_id = :user_id AND ucv.res = 8
GROUP BY rs.id, rs.code, rs.name, rc.iso2, rc.name

ORDER BY timestamp DESC
LIMIT :limit OFFSET :offset;
```

**Milestone Detection:**

- Calculate dynamically from `COUNT(DISTINCT h3_index)` in `user_cell_visits`
- Check thresholds: [100, 500, 1000, 2500, 5000, 10000]
- Use `ROW_NUMBER() OVER (ORDER BY first_visited_at)` to find exact milestone cells

**Files:**

- Router: `backend/routers/visits.py` (new)
- Schema: `backend/schemas/visits.py` (new)
- Service: `backend/services/visits_service.py` (new)

**Tests:**

- `test_timeline_empty_for_new_user()`
- `test_timeline_country_discovery_events()`
- `test_timeline_milestone_events()`
- `test_timeline_pagination()`
- `test_timeline_filter_by_type()`

---

## Feature 8: Error Handling Improvements

### Current State Issues

- Some endpoints return generic 500 errors
- Inconsistent error response formats
- Missing field-level validation errors
- No error codes for client-side handling

### Standardized Error Response

**Format:**

```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid request data",
    "details": {
      "field": "latitude",
      "reason": "Must be between -90 and 90"
    }
  },
  "request_id": "uuid-for-logging"
}
```

### Error Codes to Add

**Authentication Errors:**

- `invalid_credentials` (401)
- `token_expired` (401)
- `token_invalid` (401)
- `unauthorized` (403)

**Validation Errors:**

- `validation_error` (400)
- `missing_field` (400)
- `invalid_format` (400)
- `h3_mismatch` (400) - already exists ✅

**Resource Errors:**

- `user_not_found` (404)
- `country_not_found` (404)
- `duplicate_email` (409)
- `duplicate_username` (409)

**Rate Limiting:**

- `rate_limit_exceeded` (429) - already handled by SlowAPI ✅

**Server Errors:**

- `database_error` (503)
- `service_unavailable` (503)

### Implementation

**File:** `backend/services/error_handler.py` (new)

```python
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, OperationalError
import uuid

class AppError(Exception):
    """Base application error."""
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}

async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
            "request_id": str(uuid.uuid4()),
        }
    )

async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "validation_error",
                "message": "Invalid request data",
                "details": exc.errors(),
            },
            "request_id": str(uuid.uuid4()),
        }
    )

async def integrity_error_handler(request: Request, exc: IntegrityError):
    # Parse constraint name to provide helpful message
    if "uq_users_email" in str(exc):
        code = "duplicate_email"
        message = "Email already registered"
    elif "uq_users_username" in str(exc):
        code = "duplicate_username"
        message = "Username already taken"
    else:
        code = "integrity_error"
        message = "Database constraint violation"
    
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": code,
                "message": message,
            },
            "request_id": str(uuid.uuid4()),
        }
    )
```

**Register in [`backend/main.py`](backend/main.py):**

```python
from services.error_handler import (
    AppError, app_error_handler, validation_error_handler, 
    integrity_error_handler
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
```

**Update Existing Endpoints:**

- Replace generic `HTTPException` with `AppError` where appropriate
- Add try/except blocks for database operations
- Return consistent error codes

**Tests:**

- `test_validation_error_format()`
- `test_duplicate_email_error_code()`
- `test_database_error_handling()`
- `test_request_id_in_errors()`

---

## Implementation Order

### Phase 1: Core User Features (1-2 days)

1. Single device per user (migration + service updates)
2. Profile summary endpoint
3. Password change endpoint
4. Account deletion endpoint

### Phase 2: Gamification (1-2 days)

5. Achievements system (migration + service + endpoints)
6. Integrate achievements into location ingestion

### Phase 3: UX Improvements (1-2 days)

7. Batch location ingestion
8. Visit history timeline

### Phase 4: Polish (1 day)

9. Error handling improvements
10. Update all endpoint docstrings with examples
11. Integration testing across features

---

## Testing Strategy

### Coverage Goals

- **Unit tests:** 100% for new services
- **Integration tests:** All new endpoints
- **Edge cases:** Error conditions, rate limits, auth failures

### Test Database

Use existing test database setup from [`backend/tests/conftest.py`](backend/tests/conftest.py).

### Key Test Scenarios

1. **New user journey:** Register → first location → first achievement → view profile
2. **Batch ingestion:** Offline collection → bulk sync → discoveries
3. **Account lifecycle:** Register → change password → delete account → verify cascade
4. **Error handling:** Invalid data → correct error code → helpful message

---

## Documentation Updates

### Update [`README.md`](README.md)

- Add new endpoints to API section
- Update feature list with achievements
- Add batch ingestion example

### Update API Docs (Swagger)

- Add examples to all endpoint docstrings
- Document error codes per endpoint
- Add authentication flow diagram

### Create Migration Docs

- Document single-device constraint change
- Explain achievement criteria JSON format

---

## Success Criteria

**Backend is MVP-ready when:**

- ✅ All 8 features implemented and tested
- ✅ Test coverage > 90%
- ✅ All endpoints documented with examples
- ✅ Error responses are consistent
- ✅ Database migrations run cleanly
- ✅ Frontend can integrate without backend changes

**Performance Targets:**

- Profile summary: < 200ms
- Batch ingestion (100 cells): < 500ms
- Achievement check: < 100ms
- Timeline query: < 300ms

---

## Open Questions

1. **Achievement notification strategy:** Return in response vs. separate endpoint poll?

   - **Recommendation:** Return in location ingestion response (immediate feedback)

2. **Visit history pagination:** Offset-based vs. cursor-based?

   - **Recommendation:** Offset-based for MVP (simpler), cursor-based in v2

3. **Device metadata fields:** What platform values? ("ios", "android", "web")?

   - **Recommendation:** Free-form string, validate on frontend

4. **Batch ingestion transaction:** All-or-nothing vs. partial success?

   - **Recommendation:** Partial success (skip invalid, process valid)

5. **Error logging:** Sentry integration?

   - **Recommendation:** Add in Phase 2, use Python logging for MVP