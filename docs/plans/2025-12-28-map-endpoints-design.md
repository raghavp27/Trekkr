# Map Endpoints Design

**Date:** 2025-12-28
**Status:** Approved
**Goal:** Create backend endpoints that return user's visited cells/regions for frontend map rendering

---

## Overview

The frontend needs data to render the "fog of war" map showing visited areas. This design covers two endpoints:

1. **Map Summary** — Returns all visited countries and regions (called once on app load)
2. **Map Cells** — Returns H3 cell indexes within a viewport bounding box (called on pan/zoom)

---

## Design Decisions

### Data Fetching Strategy: Hybrid Approach
- **Countries/Regions:** Fetch once, cache on frontend (small dataset)
- **H3 Cells:** Fetch by viewport (potentially large dataset)

**Rationale:** A user might have thousands of H3 cells but rarely more than 100 countries or 500 regions. Fetching cells by viewport scales better.

### Cell Response Format: H3 Indexes Only
- Return raw H3 index strings (e.g., `"861f05a37ffffff"`)
- Frontend uses `h3-js` library to compute polygon boundaries
- Smallest payload, distributed computation

### Country/Region Boundaries: Mapbox Built-in
- Backend returns ISO codes only
- Frontend uses Mapbox's `admin-0-boundary` and `admin-1-boundary` layers
- No geometry data in API responses

### Pagination: Deferred
- No pagination for MVP
- Code structured to add `limit`/`cursor` params later if needed
- Service accepts optional limit param (defaults to None)

---

## API Endpoints

### GET /api/v1/map/summary

Returns all countries and regions the user has visited.

**Request:**
```
GET /api/v1/map/summary
Authorization: Bearer <token>
```

**Response 200:**
```json
{
  "countries": [
    { "code": "US", "name": "United States" },
    { "code": "JP", "name": "Japan" }
  ],
  "regions": [
    { "code": "US-CA", "name": "California" },
    { "code": "JP-13", "name": "Tokyo" }
  ]
}
```

**Notes:**
- `code` for countries = ISO 3166-1 alpha-2
- `code` for regions = ISO 3166-2 (e.g., "US-CA")
- Returns empty arrays if user has no visits

---

### GET /api/v1/map/cells

Returns H3 cell indexes within a bounding box at both resolutions.

**Request:**
```
GET /api/v1/map/cells?min_lng=-122.5&min_lat=37.7&max_lng=-122.4&max_lat=37.8
Authorization: Bearer <token>
```

**Query Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| min_lng | float | Yes | Western longitude bound |
| min_lat | float | Yes | Southern latitude bound |
| max_lng | float | Yes | Eastern longitude bound |
| max_lat | float | Yes | Northern latitude bound |

**Response 200:**
```json
{
  "res6": ["861f05a37ffffff", "861f05a3fffffff"],
  "res8": ["881f05a37ffffff", "881f05a39ffffff", "881f05a3bffffff"]
}
```

**Validation:**
- `min_lng < max_lng` and `min_lat < max_lat` required
- Maximum bbox span: 180° longitude, 90° latitude
- Invalid bbox returns `400 Bad Request`

---

## Database Queries

### Summary Query
```sql
-- Countries
SELECT DISTINCT cr.iso_code, cr.name
FROM user_cell_visits ucv
JOIN h3_cells hc ON ucv.h3_cell_id = hc.id
JOIN country_regions cr ON hc.country_id = cr.id
WHERE ucv.user_id = :user_id;

-- Regions (similar with state_regions table)
```

### Cells Query
```sql
SELECT hc.h3_index, hc.resolution
FROM user_cell_visits ucv
JOIN h3_cells hc ON ucv.h3_cell_id = hc.id
WHERE ucv.user_id = :user_id
  AND hc.resolution IN (6, 8)
  AND ST_Intersects(
      hc.center,
      ST_MakeEnvelope(:min_lng, :min_lat, :max_lng, :max_lat, 4326)
  );
```

Uses GIST index on `h3_cells.center` for efficient spatial lookup.

---

## File Structure

```
backend/
├── routers/
│   └── map.py              # New router
├── services/
│   └── map_service.py      # New service
├── schemas/
│   └── map.py              # New schemas
```

---

## Schemas

```python
# schemas/map.py

class CountryVisited(BaseModel):
    code: str          # ISO 3166-1 alpha-2
    name: str

class RegionVisited(BaseModel):
    code: str          # ISO 3166-2
    name: str

class MapSummaryResponse(BaseModel):
    countries: list[CountryVisited]
    regions: list[RegionVisited]

class MapCellsResponse(BaseModel):
    res6: list[str]
    res8: list[str]
```

---

## Error Handling

| Scenario | Response |
|----------|----------|
| Invalid bbox (min >= max) | 400 Bad Request |
| Bbox too large (> 180° lng or > 90° lat) | 400 Bad Request |
| User has no visits | 200 OK with empty arrays |
| Unauthenticated | 401 Unauthorized |

---

## Not In Scope (YAGNI)

- Caching layer
- Pagination
- Rate limiting (location ingest already rate-limited)
- WebSocket real-time updates
- Geometry data in responses

---

## Implementation Tasks

1. Create Pydantic schemas (`schemas/map.py`)
2. Create MapService with summary and cells queries (`services/map_service.py`)
3. Create map router with both endpoints (`routers/map.py`)
4. Register router in main.py
5. Write tests for MapService
6. Write integration tests for endpoints
