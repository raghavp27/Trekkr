# Location Processing Service Design

**Date:** 2025-12-26
**Status:** Approved

## Overview

A real-time location processing service that converts user coordinates into tracked H3 cells, countries, and regions. The service efficiently handles duplicate visits and provides discovery feedback to enable rich mobile UX.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Processing timing | Real-time | Immediate feedback as users explore |
| Update frequency | Smart adaptive (client-side H3 filtering) | Only send when moving to new cell; reduces API calls by 90%+ |
| Reverse geocoding | PostGIS spatial lookup | Accurate, fast with GIST indexes, no external dependencies |
| API response | Discovery summary | Enables celebratory UX for new discoveries |
| Resolution handling | Single endpoint, derive parent | Client sends res-8, server derives res-6 automatically |
| Edge cases | Record cells with null geography | Handles ocean, disputed territories gracefully |
| Duplicate handling | PostgreSQL UPSERT (ON CONFLICT) | Atomic, fast, no race conditions |
| Rate limiting | Application-level with slowapi | 120 requests/minute per user |

## API Endpoint

### POST /api/v1/location/ingest

**Request:**
```json
{
  "latitude": 48.8566,
  "longitude": 2.3522,
  "h3_res8": "881f1a4a9bfffff",
  "timestamp": "2025-12-26T10:30:00Z",
  "device_id": "uuid-here"
}
```

**Response:**
```json
{
  "discoveries": {
    "new_country": {"id": 1, "name": "France", "iso2": "FR"},
    "new_state": {"id": 42, "name": "Île-de-France"},
    "new_cells_res6": ["861f1a47fffffff"],
    "new_cells_res8": ["881f1a4a9bfffff"]
  },
  "revisits": {
    "cells_res6": [],
    "cells_res8": []
  },
  "visit_counts": {
    "res6_visit_count": 1,
    "res8_visit_count": 1
  }
}
```

## Processing Flow

1. **Derive Parent Cell** - Use H3 library: `h3.cell_to_parent(h3_res8, 6)`

2. **Reverse Geocoding (PostGIS)** - Single query with CTEs:
```sql
WITH point AS (
  SELECT ST_SetSRID(ST_MakePoint(lon, lat), 4326) AS geom
),
country_match AS (
  SELECT id FROM regions_country
  WHERE ST_Contains(geom, (SELECT geom FROM point))
  LIMIT 1
),
state_match AS (
  SELECT id FROM regions_state
  WHERE ST_Contains(geom, (SELECT geom FROM point))
  LIMIT 1
)
SELECT * FROM country_match, state_match;
```

3. **Process Both Resolutions in Transaction** - Upsert H3Cell and UserCellVisit for each resolution

4. **Build Discovery Response** - Aggregate new vs. revisited entities

## Database Operations

### H3Cell UPSERT
```sql
INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, first_visited_at, last_visited_at, visit_count)
VALUES (:h3_index, :res, :country_id, :state_id, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), NOW(), NOW(), 1)
ON CONFLICT (h3_index)
DO UPDATE SET
  last_visited_at = NOW(),
  visit_count = h3_cells.visit_count + 1,
  country_id = COALESCE(h3_cells.country_id, EXCLUDED.country_id),
  state_id = COALESCE(h3_cells.state_id, EXCLUDED.state_id)
RETURNING h3_index, (xmax = 0) AS was_inserted;
```

### UserCellVisit UPSERT
```sql
INSERT INTO user_cell_visits (user_id, device_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
VALUES (:user_id, :device_id, :h3_index, :res, NOW(), NOW(), 1)
ON CONFLICT (user_id, h3_index)
DO UPDATE SET
  last_visited_at = NOW(),
  visit_count = user_cell_visits.visit_count + 1,
  device_id = COALESCE(:device_id, user_cell_visits.device_id)
RETURNING h3_index, res, visit_count, (xmax = 0) AS was_inserted;
```

## Error Handling

| Error | HTTP Code | Response | Recovery |
|-------|-----------|----------|----------|
| Rate limit exceeded | 429 | `{"error": "rate_limit", "retry_after": 30}` | Client backs off |
| Invalid H3 index | 400 | `{"error": "invalid_h3", "detail": "..."}` | Client bug fix |
| H3 mismatch (lat/lon ≠ h3_res8) | 400 | `{"error": "h3_mismatch"}` | Client bug fix |
| Database timeout | 503 | `{"error": "service_unavailable"}` | Auto-retry |
| Auth failure | 401 | `{"error": "unauthorized"}` | Re-authenticate |

**Graceful Degradation:** If PostGIS lookup times out, still record cells with null geography.

## Performance Optimizations

### Required Indexes
```sql
CREATE INDEX IF NOT EXISTS ix_regions_country_geom ON regions_country USING GIST (geom);
CREATE INDEX IF NOT EXISTS ix_regions_state_geom ON regions_state USING GIST (geom);
```

### Expected Latency
- Reverse geocoding: ~5-10ms (with GIST index)
- UPSERT operations: ~2-5ms
- Total endpoint latency: <50ms under normal load

## File Structure

```
backend/
├── routers/
│   └── location.py          # POST /api/v1/location/ingest endpoint
├── services/
│   └── location_processor.py # Core processing logic
├── schemas/
│   └── location.py          # Pydantic request/response models
```

## Dependencies

- `h3` Python library for H3 cell operations
- `slowapi` for rate limiting

## Audit Logging

Each request logged to IngestBatch table:
- user_id, device_id
- received_at timestamp
- cells_count (2: res-6 + res-8)
- res_min (6), res_max (8)
