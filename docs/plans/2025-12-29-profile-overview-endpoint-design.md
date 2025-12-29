# Profile Overview Endpoint Design

**Feature:** Profile Summary Endpoint (Feature 2 from Backend MVP)
**Date:** 2025-12-29
**Status:** Design Approved

---

## Overview

Implement `GET /api/v1/stats/overview` endpoint to power the Profile Page. Returns comprehensive user statistics, cell counts at multiple resolutions, and recent travel activity in a single optimized query.

### Key Decisions

- **Usage:** Profile page load only (not a dashboard widget)
- **Recent Data:** Last 3 countries + last 3 regions visited
- **Cell Resolutions:** Both res6 (preset cells) and res8 (fine cells)
- **Query Strategy:** Single CTE mega-query for optimal performance
- **Caching:** No caching for MVP (direct query each time)

---

## API Contract

### Endpoint

```
GET /api/v1/stats/overview
```

**Authentication:** Required (JWT Bearer token)

### Response Schema

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
    "total_visit_count": 2847,
    "first_visit_at": "2024-01-20T08:30:00Z",
    "last_visit_at": "2024-12-28T14:22:00Z"
  },
  "recent_countries": [
    {
      "code": "US",
      "name": "United States",
      "visited_at": "2024-12-28T14:22:00Z"
    },
    {
      "code": "MX",
      "name": "Mexico",
      "visited_at": "2024-12-20T09:15:00Z"
    },
    {
      "code": "CA",
      "name": "Canada",
      "visited_at": "2024-12-01T11:00:00Z"
    }
  ],
  "recent_regions": [
    {
      "code": "US-CA",
      "name": "California",
      "country_name": "United States",
      "visited_at": "2024-12-28T14:22:00Z"
    },
    {
      "code": "MX-BCN",
      "name": "Baja California",
      "country_name": "Mexico",
      "visited_at": "2024-12-20T09:15:00Z"
    },
    {
      "code": "CA-BC",
      "name": "British Columbia",
      "country_name": "Canada",
      "visited_at": "2024-12-01T11:00:00Z"
    }
  ]
}
```

### Field Descriptions

**User Section:**
- `id`: User's database ID
- `username`: Display name
- `created_at`: Account creation timestamp (when they started using the app)

**Stats Section:**
- `countries_visited`: Count of unique countries with at least one res8 cell
- `regions_visited`: Count of unique states/provinces with at least one res8 cell
- `cells_visited_res6`: Count of unique H3 resolution 6 cells (preset/medium cells)
- `cells_visited_res8`: Count of unique H3 resolution 8 cells (fine/detailed cells)
- `total_visit_count`: Sum of all `visit_count` fields (includes revisits)
- `first_visit_at`: Timestamp of user's very first location visit (null if no visits)
- `last_visit_at`: Timestamp of user's most recent location visit (null if no visits)

**Recent Countries:**
- Array of up to 3 most recently visited countries
- `visited_at` is `MAX(last_visited_at)` grouped by country
- Ordered by `visited_at DESC`

**Recent Regions:**
- Array of up to 3 most recently visited regions/states
- `visited_at` is `MAX(last_visited_at)` grouped by region
- Ordered by `visited_at DESC`

---

## SQL Query Strategy

### Single CTE Mega-Query

Use PostgreSQL Common Table Expressions to compute all sections in one database round-trip:

```sql
WITH
-- Aggregate statistics from user_cell_visits
user_stats AS (
  SELECT
    COUNT(DISTINCT CASE WHEN res = 6 THEN h3_index END) as cells_res6,
    COUNT(DISTINCT CASE WHEN res = 8 THEN h3_index END) as cells_res8,
    MIN(first_visited_at) as first_visit,
    MAX(last_visited_at) as last_visit,
    SUM(visit_count) as total_visits
  FROM user_cell_visits
  WHERE user_id = :user_id
),

-- Count unique countries via h3_cells join
country_stats AS (
  SELECT COUNT(DISTINCT hc.country_id) as countries
  FROM user_cell_visits ucv
  JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
  WHERE ucv.user_id = :user_id AND ucv.res = 8
),

-- Count unique regions via h3_cells join
region_stats AS (
  SELECT COUNT(DISTINCT hc.state_id) as regions
  FROM user_cell_visits ucv
  JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
  WHERE ucv.user_id = :user_id AND ucv.res = 8 AND hc.state_id IS NOT NULL
),

-- Recent 3 countries with max(last_visited_at) grouped by country
recent_countries AS (
  SELECT
    rc.iso2 as code,
    rc.name,
    MAX(ucv.last_visited_at) as visited_at,
    ROW_NUMBER() OVER (ORDER BY MAX(ucv.last_visited_at) DESC) as rn
  FROM user_cell_visits ucv
  JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
  JOIN regions_country rc ON hc.country_id = rc.id
  WHERE ucv.user_id = :user_id
  GROUP BY rc.id, rc.iso2, rc.name
  ORDER BY visited_at DESC
  LIMIT 3
),

-- Recent 3 regions with max(last_visited_at) grouped by region
recent_regions AS (
  SELECT
    CONCAT(rc.iso2, '-', rs.code) as code,
    rs.name,
    rc.name as country_name,
    MAX(ucv.last_visited_at) as visited_at,
    ROW_NUMBER() OVER (ORDER BY MAX(ucv.last_visited_at) DESC) as rn
  FROM user_cell_visits ucv
  JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
  JOIN regions_state rs ON hc.state_id = rs.id
  JOIN regions_country rc ON rs.country_id = rc.id
  WHERE ucv.user_id = :user_id
  GROUP BY rs.id, rs.code, rs.name, rc.iso2, rc.name
  ORDER BY visited_at DESC
  LIMIT 3
)

-- Final SELECT combines all CTEs
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
CROSS JOIN region_stats rs;
```

**Note:** The recent countries/regions will be fetched separately since they return multiple rows (arrays). The main stats query returns a single row.

### Query Optimizations

- **CASE WHEN filtering:** Counts res6 and res8 in a single table scan
- **GROUP BY with MAX():** Efficiently finds most recent visit per country/region
- **Existing indexes:** Leverages `user_id`, `res`, and foreign key indexes
- **LIMIT 3:** Restricts recent lists to exactly 3 items
- **NULL safety:** `COUNT()` returns 0 for empty sets, `MIN/MAX` return NULL

### Expected Performance

- **Typical users (< 1000 cells):** 100-200ms
- **Power users (10K+ cells):** < 500ms
- **New users (0 visits):** < 50ms

---

## Code Structure

### Files to Modify/Create

#### 1. Service Layer: `backend/services/stats_service.py`

Add new method to existing `StatsService` class:

```python
def get_overview(self) -> dict:
    """Get comprehensive profile overview for a user.

    Returns user info, aggregate stats, and recent countries/regions.
    Uses single CTE query for optimal performance.

    Returns:
        dict with keys: user, stats, recent_countries, recent_regions
    """
    # Fetch user info (simple ORM query)
    user = self.db.query(User).filter(User.id == self.user_id).first()
    if not user:
        raise ValueError(f"User {self.user_id} not found")

    # Execute main stats CTE query
    stats_query = text("""
        WITH user_stats AS (...),
             country_stats AS (...),
             region_stats AS (...)
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

    # Fetch recent countries (separate query for array result)
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

    # Fetch recent regions (separate query for array result)
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

#### 2. Router: `backend/routers/stats.py`

Add new endpoint to existing router:

```python
from schemas.stats import OverviewResponse

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

    This endpoint uses a single optimized query for fast response times.
    """
    service = StatsService(db, current_user.id)
    return service.get_overview()
```

#### 3. Schemas: `backend/schemas/stats.py`

Add response models to existing file:

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

---

## Error Handling & Edge Cases

### Edge Case: New User (No Visits)

**Scenario:** User has registered but never ingested a location.

**Behavior:**
```json
{
  "user": {
    "id": 1,
    "username": "newuser",
    "created_at": "2025-12-29T10:00:00Z"
  },
  "stats": {
    "countries_visited": 0,
    "regions_visited": 0,
    "cells_visited_res6": 0,
    "cells_visited_res8": 0,
    "total_visit_count": 0,
    "first_visit_at": null,
    "last_visit_at": null
  },
  "recent_countries": [],
  "recent_regions": []
}
```

**Implementation:** Use `COALESCE()` and `or 0` in Python to handle NULL values gracefully.

### Edge Case: Countries Without Regions

**Scenario:** Some countries (e.g., small island nations) may not have `state_id` populated in `h3_cells`.

**Behavior:** `WHERE hc.state_id IS NOT NULL` filter ensures accurate region counts. These countries will appear in `recent_countries` but won't contribute to region stats.

### Edge Case: Mixed Resolutions

**Scenario:** User has visited cells at both res6 and res8 for the same geographic area.

**Behavior:** Each resolution is counted separately using `CASE WHEN res = X`. No double-counting occurs.

### Edge Case: Recent Lists with < 3 Items

**Scenario:** User has only visited 1-2 countries/regions.

**Behavior:** `LIMIT 3` returns actual number of rows (1, 2, or 3). Frontend receives array with actual count.

### Error Responses

- **401 Unauthorized:** Missing or invalid JWT token (handled by `get_current_user` dependency)
- **500 Internal Server Error:** Database connection issues (FastAPI default error handler)

No 404 needed - endpoint always returns data for the authenticated user (even if zeros).

---

## Testing Strategy

### Test File

`backend/tests/test_stats_router.py` (add to existing file)

### Test Cases

#### 1. New User Returns Zeros

```python
def test_overview_for_new_user_returns_zeros(client, auth_headers):
    """New user with no visits should get zeros and empty arrays."""
    response = client.get("/api/v1/stats/overview", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["user"]["username"] is not None
    assert data["stats"]["countries_visited"] == 0
    assert data["stats"]["cells_visited_res6"] == 0
    assert data["stats"]["cells_visited_res8"] == 0
    assert data["stats"]["first_visit_at"] is None
    assert data["stats"]["last_visit_at"] is None
    assert data["recent_countries"] == []
    assert data["recent_regions"] == []
```

#### 2. User with Visits Returns Correct Stats

```python
def test_overview_returns_correct_stats(client, auth_headers, db_session):
    """User with visits should get accurate stats and recent lists."""
    # Setup: Create user_cell_visits for multiple countries/regions
    # (Reuse existing fixtures from test_stats_service.py)

    response = client.get("/api/v1/stats/overview", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["stats"]["countries_visited"] > 0
    assert data["stats"]["regions_visited"] >= 0
    assert data["stats"]["total_visit_count"] > 0
    assert data["stats"]["first_visit_at"] is not None
    assert data["stats"]["last_visit_at"] is not None
    assert data["stats"]["first_visit_at"] <= data["stats"]["last_visit_at"]
    assert len(data["recent_countries"]) <= 3
    assert len(data["recent_regions"]) <= 3
```

#### 3. Recent Lists Are Sorted

```python
def test_overview_recent_lists_sorted_by_last_visit(client, auth_headers):
    """Recent countries/regions should be ordered by most recent visit."""
    response = client.get("/api/v1/stats/overview", headers=auth_headers)
    data = response.json()

    # Verify descending order for countries
    for i in range(len(data["recent_countries"]) - 1):
        assert data["recent_countries"][i]["visited_at"] >= \
               data["recent_countries"][i + 1]["visited_at"]

    # Verify descending order for regions
    for i in range(len(data["recent_regions"]) - 1):
        assert data["recent_regions"][i]["visited_at"] >= \
               data["recent_regions"][i + 1]["visited_at"]
```

#### 4. Authentication Required

```python
def test_overview_requires_authentication(client):
    """Overview endpoint should require valid JWT token."""
    response = client.get("/api/v1/stats/overview")
    assert response.status_code == 401
```

#### 5. Both Resolutions Counted

```python
def test_overview_counts_both_resolutions(client, auth_headers, db_session, test_user):
    """Should count res6 and res8 cells separately."""
    # Setup: Create visits with both res=6 and res=8
    from models.visits import UserCellVisit

    # Add res6 cell
    db_session.add(UserCellVisit(
        user_id=test_user.id,
        h3_index="862830807ffffff",
        res=6,
    ))

    # Add res8 cell
    db_session.add(UserCellVisit(
        user_id=test_user.id,
        h3_index="882830810ffffff",
        res=8,
    ))
    db_session.commit()

    response = client.get("/api/v1/stats/overview", headers=auth_headers)
    data = response.json()

    assert data["stats"]["cells_visited_res6"] > 0
    assert data["stats"]["cells_visited_res8"] > 0
```

### Coverage Goal

**Target:** 100% coverage for `get_overview()` method and `/overview` endpoint.

---

## Implementation Checklist

- [ ] Add Pydantic response models to `schemas/stats.py`
- [ ] Implement `get_overview()` method in `StatsService`
- [ ] Add `/overview` endpoint to stats router
- [ ] Write unit tests for service method
- [ ] Write integration tests for endpoint
- [ ] Test edge cases (new user, < 3 recent items)
- [ ] Verify SQL query performance with EXPLAIN ANALYZE
- [ ] Update API documentation (Swagger)

---

## Performance Considerations

### Database Indexes (Already Exist)

- `user_cell_visits(user_id)` - Index for WHERE clause
- `user_cell_visits(res)` - Index for resolution filtering
- `h3_cells(h3_index)` - Index for JOIN operations
- Foreign key indexes on `country_id`, `state_id`

### Query Optimization

- Single CTE query reduces network round-trips
- `LIMIT 3` on recent lists minimizes data transfer
- `COUNT(DISTINCT ...)` leverages indexes
- `MAX()` aggregation is efficient with sorted data

### No Caching (MVP Decision)

For MVP, no caching layer is needed:
- Profile page loads infrequently
- Query is fast enough (< 300ms typical)
- Always shows accurate, up-to-date data
- Can add Redis caching in v2 if monitoring shows need

---

## Future Enhancements (Post-MVP)

1. **Caching:** Add Redis with 5-minute TTL if P95 latency > 500ms
2. **Pagination:** Add query params for recent lists (currently fixed at 3)
3. **Date Range Filtering:** Allow filtering stats by date range
4. **Coverage Percentages:** Include country/region coverage % in overview
5. **Streaks:** Add "days traveled" or "consecutive visit days" metric

---

## Success Criteria

- [ ] Endpoint returns correct data for new users (zeros/nulls)
- [ ] Endpoint returns accurate stats for users with visits
- [ ] Recent lists are sorted by `visited_at DESC`
- [ ] Both res6 and res8 cells are counted correctly
- [ ] Response time < 300ms for typical users (< 1000 cells)
- [ ] All tests pass with 100% coverage
- [ ] Frontend can successfully integrate without backend changes
