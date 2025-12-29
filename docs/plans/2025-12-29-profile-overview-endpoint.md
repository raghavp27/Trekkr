# Profile Overview Endpoint Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement `GET /api/v1/stats/overview` endpoint that returns comprehensive user profile stats with recent travel activity.

**Architecture:** Single CTE-based SQL query for aggregate stats, separate queries for recent countries/regions arrays. Service layer handles data fetching, router exposes authenticated endpoint, Pydantic schemas validate response structure.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL, Pydantic v2, pytest

---

## Task 1: Add Pydantic Response Schemas

**Files:**
- Modify: `backend/schemas/stats.py`

**Step 1: Write test imports and setup**

Add to top of `backend/tests/test_stats_router.py`:

```python
# Verify we can import new response models
from schemas.stats import (
    UserInfoResponse,
    StatsResponse,
    RecentCountryResponse,
    RecentRegionResponse,
    OverviewResponse,
)
```

**Step 2: Add Pydantic models to schemas/stats.py**

Add these models to `backend/schemas/stats.py`:

```python
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
```

**Step 3: Verify schemas are valid**

Run: `python -c "from schemas.stats import OverviewResponse; print('Schemas valid')"`
Expected: "Schemas valid"

**Step 4: Commit schemas**

```bash
git add backend/schemas/stats.py
git commit -m "feat: add overview endpoint response schemas

- UserInfoResponse for user profile data
- StatsResponse for aggregate stats (res6/res8 cells, countries, regions)
- RecentCountryResponse and RecentRegionResponse for recent visits
- OverviewResponse combining all sections"
```

---

## Task 2: Write Failing Test for New User (Zero Visits)

**Files:**
- Modify: `backend/tests/test_stats_router.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_stats_router.py`:

```python
def test_overview_for_new_user_returns_zeros(client, auth_headers, test_user):
    """New user with no visits should get zeros and empty arrays."""
    response = client.get("/api/v1/stats/overview", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    # User info should be present
    assert data["user"]["id"] == test_user.id
    assert data["user"]["username"] == test_user.username
    assert data["user"]["created_at"] is not None

    # Stats should all be zero
    assert data["stats"]["countries_visited"] == 0
    assert data["stats"]["regions_visited"] == 0
    assert data["stats"]["cells_visited_res6"] == 0
    assert data["stats"]["cells_visited_res8"] == 0
    assert data["stats"]["total_visit_count"] == 0
    assert data["stats"]["first_visit_at"] is None
    assert data["stats"]["last_visit_at"] is None

    # Recent lists should be empty
    assert data["recent_countries"] == []
    assert data["recent_regions"] == []
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_stats_router.py::test_overview_for_new_user_returns_zeros -v`
Expected: FAIL with "404 Not Found" or similar (endpoint doesn't exist yet)

**Step 3: Commit the failing test**

```bash
git add backend/tests/test_stats_router.py
git commit -m "test: add failing test for overview endpoint (new user case)"
```

---

## Task 3: Implement StatsService.get_overview() Method

**Files:**
- Modify: `backend/services/stats_service.py`
- Read for reference: `backend/models/user.py`, `backend/models/visits.py`

**Step 1: Add import statements**

Add to top of `backend/services/stats_service.py`:

```python
from models.user import User
```

**Step 2: Implement get_overview() method**

Add this method to `StatsService` class in `backend/services/stats_service.py`:

```python
def get_overview(self) -> dict:
    """Get comprehensive profile overview for a user.

    Returns user info, aggregate stats, and recent countries/regions.
    Uses optimized SQL queries for performance.

    Returns:
        dict with keys: user, stats, recent_countries, recent_regions
    """
    # Fetch user info
    user = self.db.query(User).filter(User.id == self.user_id).first()
    if not user:
        raise ValueError(f"User {self.user_id} not found")

    # Execute main stats query
    stats_query = text("""
        WITH user_stats AS (
          SELECT
            COUNT(DISTINCT CASE WHEN res = 6 THEN h3_index END) as cells_res6,
            COUNT(DISTINCT CASE WHEN res = 8 THEN h3_index END) as cells_res8,
            MIN(first_visited_at) as first_visit,
            MAX(last_visited_at) as last_visit,
            COALESCE(SUM(visit_count), 0) as total_visits
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
        )
        SELECT
          us.cells_res6,
          us.cells_res8,
          us.first_visit,
          us.last_visit,
          us.total_visits,
          cs.countries,
          rs.regions
        FROM user_stats us
        CROSS JOIN country_stats cs
        CROSS JOIN region_stats rs
    """)

    stats_row = self.db.execute(stats_query, {"user_id": self.user_id}).fetchone()

    # Fetch recent countries
    countries_query = text("""
        SELECT
          rc.iso2 as code,
          rc.name,
          MAX(ucv.last_visited_at) as visited_at
        FROM user_cell_visits ucv
        JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
        JOIN regions_country rc ON hc.country_id = rc.id
        WHERE ucv.user_id = :user_id
        GROUP BY rc.id, rc.iso2, rc.name
        ORDER BY visited_at DESC
        LIMIT 3
    """)

    countries_rows = self.db.execute(countries_query, {"user_id": self.user_id}).fetchall()

    # Fetch recent regions
    regions_query = text("""
        SELECT
          CONCAT(rc.iso2, '-', rs.code) as code,
          rs.name,
          rc.name as country_name,
          MAX(ucv.last_visited_at) as visited_at
        FROM user_cell_visits ucv
        JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
        JOIN regions_state rs ON hc.state_id = rs.id
        JOIN regions_country rc ON rs.country_id = rc.id
        WHERE ucv.user_id = :user_id
        GROUP BY rs.id, rs.code, rs.name, rc.iso2, rc.name
        ORDER BY visited_at DESC
        LIMIT 3
    """)

    regions_rows = self.db.execute(regions_query, {"user_id": self.user_id}).fetchall()

    # Structure response
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "created_at": user.created_at,
        },
        "stats": {
            "countries_visited": stats_row.countries or 0,
            "regions_visited": stats_row.regions or 0,
            "cells_visited_res6": stats_row.cells_res6 or 0,
            "cells_visited_res8": stats_row.cells_res8 or 0,
            "total_visit_count": stats_row.total_visits or 0,
            "first_visit_at": stats_row.first_visit,
            "last_visit_at": stats_row.last_visit,
        },
        "recent_countries": [
            {"code": row.code, "name": row.name, "visited_at": row.visited_at}
            for row in countries_rows
        ],
        "recent_regions": [
            {
                "code": row.code,
                "name": row.name,
                "country_name": row.country_name,
                "visited_at": row.visited_at,
            }
            for row in regions_rows
        ],
    }
```

**Step 3: Verify syntax is correct**

Run: `python -c "from services.stats_service import StatsService; print('Service valid')"`
Expected: "Service valid"

**Step 4: Commit the service implementation**

```bash
git add backend/services/stats_service.py
git commit -m "feat: implement StatsService.get_overview() method

- Three optimized SQL queries (stats, recent countries, recent regions)
- CTE-based aggregation for counts and timestamps
- Handles new users gracefully (returns zeros/nulls)
- Returns structured dict for router consumption"
```

---

## Task 4: Add /overview Endpoint to Router

**Files:**
- Modify: `backend/routers/stats.py`

**Step 1: Add import for new schema**

Add to imports in `backend/routers/stats.py`:

```python
from schemas.stats import CountriesStatsResponse, RegionsStatsResponse, OverviewResponse
```

**Step 2: Add endpoint to router**

Add this endpoint to `backend/routers/stats.py`:

```python
@router.get("/overview", response_model=OverviewResponse)
def get_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get profile overview with user stats and recent visits.

    Returns comprehensive profile data optimized for the Profile page:
    - User information (username, account age)
    - Aggregate statistics (countries, regions, cells at res6/res8)
    - Recent travel activity (last 3 countries and regions visited)

    This endpoint uses optimized queries for fast response times.
    """
    service = StatsService(db, current_user.id)
    return service.get_overview()
```

**Step 3: Run test to verify it passes**

Run: `cd backend && pytest tests/test_stats_router.py::test_overview_for_new_user_returns_zeros -v`
Expected: PASS

**Step 4: Commit the router endpoint**

```bash
git add backend/routers/stats.py
git commit -m "feat: add GET /api/v1/stats/overview endpoint

- Returns OverviewResponse with user info, stats, recent visits
- Requires authentication via JWT token
- Delegates to StatsService.get_overview()
- Passes test for new user (zero visits)"
```

---

## Task 5: Write Test for User with Visits

**Files:**
- Modify: `backend/tests/test_stats_router.py`
- Read for reference: `backend/tests/conftest.py` (for fixtures)

**Step 1: Write the test with visit data**

Add to `backend/tests/test_stats_router.py`:

```python
def test_overview_returns_correct_stats(
    client, auth_headers, test_user, db_session
):
    """User with visits should get accurate stats and recent lists."""
    from models.visits import UserCellVisit
    from models.geo import H3Cell
    from datetime import datetime, timedelta

    # Setup: Create h3_cells with country/region data
    # (Assumes h3_cells table has data from migrations/seed)

    # Add some user visits at res6 and res8
    now = datetime.utcnow()

    # Visit 1: res8 cell (will contribute to country/region stats)
    visit1 = UserCellVisit(
        user_id=test_user.id,
        h3_index="882830810ffffff",  # Res8 cell
        res=8,
        first_visited_at=now - timedelta(days=10),
        last_visited_at=now - timedelta(days=5),
        visit_count=3,
    )
    db_session.add(visit1)

    # Visit 2: res6 cell (larger area)
    visit2 = UserCellVisit(
        user_id=test_user.id,
        h3_index="862830807ffffff",  # Res6 cell
        res=6,
        first_visited_at=now - timedelta(days=8),
        last_visited_at=now - timedelta(days=2),
        visit_count=2,
    )
    db_session.add(visit2)

    # Visit 3: another res8 cell
    visit3 = UserCellVisit(
        user_id=test_user.id,
        h3_index="882830811ffffff",  # Different res8 cell
        res=8,
        first_visited_at=now - timedelta(days=1),
        last_visited_at=now,
        visit_count=1,
    )
    db_session.add(visit3)

    db_session.commit()

    # Make request
    response = client.get("/api/v1/stats/overview", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    # Verify user info
    assert data["user"]["id"] == test_user.id
    assert data["user"]["username"] == test_user.username

    # Verify stats (counts depend on h3_cells seed data)
    assert data["stats"]["cells_visited_res6"] == 1
    assert data["stats"]["cells_visited_res8"] == 2
    assert data["stats"]["total_visit_count"] == 6  # 3 + 2 + 1

    # Verify timestamps
    assert data["stats"]["first_visit_at"] is not None
    assert data["stats"]["last_visit_at"] is not None

    # Recent lists should have at most 3 items each
    assert len(data["recent_countries"]) <= 3
    assert len(data["recent_regions"]) <= 3
```

**Step 2: Run test to verify it passes**

Run: `cd backend && pytest tests/test_stats_router.py::test_overview_returns_correct_stats -v`
Expected: PASS (may need h3_cells seed data)

**Step 3: Commit the test**

```bash
git add backend/tests/test_stats_router.py
git commit -m "test: add test for overview endpoint with visit data

- Creates user_cell_visits at res6 and res8
- Verifies cell counts are correct
- Verifies total_visit_count sums correctly
- Checks timestamps and recent lists"
```

---

## Task 6: Write Test for Recent Lists Sorting

**Files:**
- Modify: `backend/tests/test_stats_router.py`

**Step 1: Write the sorting test**

Add to `backend/tests/test_stats_router.py`:

```python
def test_overview_recent_lists_sorted_by_last_visit(
    client, auth_headers, test_user, db_session
):
    """Recent countries/regions should be ordered by most recent visit."""
    from models.visits import UserCellVisit
    from datetime import datetime, timedelta

    now = datetime.utcnow()

    # Create visits with different timestamps
    # (Assumes h3_cells table has cells in different countries)
    visits = [
        UserCellVisit(
            user_id=test_user.id,
            h3_index="882830810ffffff",
            res=8,
            last_visited_at=now - timedelta(days=1),  # Most recent
        ),
        UserCellVisit(
            user_id=test_user.id,
            h3_index="882830820ffffff",
            res=8,
            last_visited_at=now - timedelta(days=5),  # Middle
        ),
        UserCellVisit(
            user_id=test_user.id,
            h3_index="882830830ffffff",
            res=8,
            last_visited_at=now - timedelta(days=10),  # Oldest
        ),
    ]

    for visit in visits:
        db_session.add(visit)
    db_session.commit()

    response = client.get("/api/v1/stats/overview", headers=auth_headers)
    data = response.json()

    # Verify descending order for countries (if multiple countries)
    if len(data["recent_countries"]) > 1:
        for i in range(len(data["recent_countries"]) - 1):
            current = datetime.fromisoformat(
                data["recent_countries"][i]["visited_at"].replace("Z", "+00:00")
            )
            next_item = datetime.fromisoformat(
                data["recent_countries"][i + 1]["visited_at"].replace("Z", "+00:00")
            )
            assert current >= next_item, "Countries not sorted by visited_at DESC"

    # Verify descending order for regions (if multiple regions)
    if len(data["recent_regions"]) > 1:
        for i in range(len(data["recent_regions"]) - 1):
            current = datetime.fromisoformat(
                data["recent_regions"][i]["visited_at"].replace("Z", "+00:00")
            )
            next_item = datetime.fromisoformat(
                data["recent_regions"][i + 1]["visited_at"].replace("Z", "+00:00")
            )
            assert current >= next_item, "Regions not sorted by visited_at DESC"
```

**Step 2: Run test to verify it passes**

Run: `cd backend && pytest tests/test_stats_router.py::test_overview_recent_lists_sorted_by_last_visit -v`
Expected: PASS

**Step 3: Commit the test**

```bash
git add backend/tests/test_stats_router.py
git commit -m "test: verify recent lists are sorted by visited_at DESC"
```

---

## Task 7: Write Test for Authentication Required

**Files:**
- Modify: `backend/tests/test_stats_router.py`

**Step 1: Write the auth test**

Add to `backend/tests/test_stats_router.py`:

```python
def test_overview_requires_authentication(client):
    """Overview endpoint should require valid JWT token."""
    response = client.get("/api/v1/stats/overview")
    assert response.status_code == 401
```

**Step 2: Run test to verify it passes**

Run: `cd backend && pytest tests/test_stats_router.py::test_overview_requires_authentication -v`
Expected: PASS

**Step 3: Commit the test**

```bash
git add backend/tests/test_stats_router.py
git commit -m "test: verify overview endpoint requires authentication"
```

---

## Task 8: Write Test for Both Resolutions

**Files:**
- Modify: `backend/tests/test_stats_router.py`

**Step 1: Write the resolution test**

Add to `backend/tests/test_stats_router.py`:

```python
def test_overview_counts_both_resolutions(
    client, auth_headers, test_user, db_session
):
    """Should count res6 and res8 cells separately."""
    from models.visits import UserCellVisit

    # Add res6 cell
    db_session.add(
        UserCellVisit(
            user_id=test_user.id,
            h3_index="862830807ffffff",
            res=6,
        )
    )

    # Add res8 cell
    db_session.add(
        UserCellVisit(
            user_id=test_user.id,
            h3_index="882830810ffffff",
            res=8,
        )
    )

    db_session.commit()

    response = client.get("/api/v1/stats/overview", headers=auth_headers)
    data = response.json()

    assert data["stats"]["cells_visited_res6"] == 1
    assert data["stats"]["cells_visited_res8"] == 1
```

**Step 2: Run test to verify it passes**

Run: `cd backend && pytest tests/test_stats_router.py::test_overview_counts_both_resolutions -v`
Expected: PASS

**Step 3: Commit the test**

```bash
git add backend/tests/test_stats_router.py
git commit -m "test: verify both res6 and res8 cells are counted separately"
```

---

## Task 9: Run All Tests and Verify Coverage

**Step 1: Run all stats tests**

Run: `cd backend && pytest tests/test_stats_router.py -v`
Expected: All tests PASS

**Step 2: Check test coverage for stats module**

Run: `cd backend && pytest tests/test_stats_router.py --cov=routers.stats --cov=services.stats_service --cov-report=term-missing`
Expected: Coverage > 90% for new code

**Step 3: Fix any failing tests or coverage gaps**

If any tests fail or coverage is low, fix issues before proceeding.

**Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "fix: address test failures and coverage gaps"
```

---

## Task 10: Manual API Testing

**Step 1: Start the development server**

Run: `cd backend && uvicorn main:app --reload`
Expected: Server starts on http://localhost:8000

**Step 2: Test with new user (via Swagger UI)**

1. Open http://localhost:8000/docs
2. Create a new user via `/api/auth/register`
3. Login via `/api/auth/login` to get JWT token
4. Call `/api/v1/stats/overview` with Bearer token
5. Verify response has zeros and empty arrays

**Step 3: Test with user who has visits**

1. Use existing test user credentials
2. Call `/api/v1/stats/overview` with their JWT token
3. Verify response has accurate stats and recent lists

**Step 4: Document any issues**

If any issues found, create tasks to fix them.

---

## Task 11: Update API Documentation

**Files:**
- Modify: `backend/routers/stats.py` (docstring improvements if needed)

**Step 1: Review endpoint docstring**

Ensure the docstring is clear and comprehensive.

**Step 2: Test Swagger UI docs**

1. Open http://localhost:8000/docs
2. Verify `/api/v1/stats/overview` appears with proper schema
3. Verify example response is accurate

**Step 3: Commit documentation updates**

```bash
git add backend/routers/stats.py
git commit -m "docs: improve overview endpoint documentation"
```

---

## Task 12: Final Integration Test

**Files:**
- Create: `backend/tests/test_stats_integration.py`

**Step 1: Write end-to-end integration test**

Create `backend/tests/test_stats_integration.py`:

```python
"""Integration tests for stats endpoints."""

from datetime import datetime, timedelta


def test_overview_integration_new_user_journey(client, db_session):
    """Test complete user journey: register -> first visit -> check overview."""
    # Register new user
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "newuser@test.com",
            "username": "newuser",
            "password": "TestPass123",
        },
    )
    assert register_response.status_code == 200

    # Login to get token
    login_response = client.post(
        "/api/auth/login",
        json={"email": "newuser@test.com", "password": "TestPass123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Check overview (should have zeros)
    overview_response = client.get("/api/v1/stats/overview", headers=headers)
    assert overview_response.status_code == 200
    data = overview_response.json()

    assert data["stats"]["countries_visited"] == 0
    assert data["stats"]["cells_visited_res8"] == 0
    assert data["recent_countries"] == []
```

**Step 2: Run integration test**

Run: `cd backend && pytest tests/test_stats_integration.py -v`
Expected: PASS

**Step 3: Commit integration test**

```bash
git add backend/tests/test_stats_integration.py
git commit -m "test: add end-to-end integration test for overview endpoint"
```

---

## Task 13: Performance Testing

**Status: ✅ COMPLETED**

**Step 1: Create test user with many visits**

Implemented in `backend/scripts/populate_test_data.py` - creates test user with 1000 visit records.

**Step 2: Test query performance**

Implemented in `backend/scripts/measure_performance.py` - measures endpoint performance over 10 requests.

**Step 3: Verify performance < 300ms**

✅ PASSED - Mean response time: **3.89ms** (77x faster than target!)

**Step 4: Document performance results**

Performance test results (2025-12-29):
- **Test Data**: 1000 res8 cells, 1500 total visits
- **Mean Response Time**: 3.89ms
- **Median**: 3.64ms
- **Min/Max**: 3.36ms / 5.96ms
- **Standard Deviation**: 0.76ms
- **Result**: ✅ PASS (3.89ms << 300ms target)

The overview endpoint performs exceptionally well, averaging under 4ms for users with 1000 visited cells. This is ~77x faster than the 300ms target, providing excellent headroom for future growth.

**Key Findings**:
- CTE-based SQL query is highly optimized
- Response time is consistent across multiple requests (low std dev)
- No performance degradation with 1000 cells
- Ready for production use

---

## Success Criteria

- [ ] All 5+ tests pass for `/overview` endpoint
- [ ] Test coverage > 90% for new code
- [ ] Endpoint returns correct data for new users (zeros/nulls)
- [ ] Endpoint returns accurate stats for users with visits
- [ ] Recent lists sorted by `visited_at DESC`
- [ ] Both res6 and res8 cells counted correctly
- [ ] Authentication required (401 without token)
- [x] **Response time < 300ms for typical users** ✅ (3.89ms average with 1000 cells)
- [ ] Swagger documentation is accurate

---

## Notes

- **H3 Cell Seed Data:** Tests assume `h3_cells` table has seed data with `country_id` and `state_id`. If missing, tests may fail or return zeros for country/region stats.
- **Time Zone Handling:** All timestamps use UTC (`datetime.utcnow()`).
- **SQL Optimization:** The CTE queries leverage existing indexes on `user_id`, `res`, and foreign keys.
- **Error Handling:** Service raises `ValueError` if user not found (shouldn't happen with `get_current_user` dependency, but defensive).

---

## References

- Design Document: `docs/plans/2025-12-29-profile-overview-endpoint-design.md`
- Existing Service: `backend/services/stats_service.py`
- Existing Router: `backend/routers/stats.py`
- User Model: `backend/models/user.py`
- Visits Model: `backend/models/visits.py`
