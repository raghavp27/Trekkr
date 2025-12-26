# Location Ingestion System Design

**Date:** 2025-12-26
**Status:** Approved for Implementation

## Overview

The location ingestion system enables users to upload GPS coordinates from their mobile devices, converting them into H3 hexagonal cells at multiple resolutions to power the "fog of war" map visualization.

## API Endpoint Design

**Endpoint:** `POST /api/visits/batch`
**Authentication:** JWT bearer token required

### Request Format

```json
{
  "locations": [
    {
      "latitude": 37.7749,
      "longitude": -122.4194,
      "timestamp": "2025-01-15T10:30:00Z",
      "accuracy": 10.5
    }
  ]
}
```

**Validation Rules:**
- `locations` array: 1-1000 items (prevents abuse, allows full day of tracking)
- `latitude`: -90 to 90
- `longitude`: -180 to 180
- `timestamp`: ISO 8601, not in future, not older than 1 year
- `accuracy`: optional float, 0-1000 meters

### Response Format

```json
{
  "processed": 247,
  "new_cells_unlocked": 15,
  "countries_visited": 3,
  "states_visited": 8,
  "errors": []
}
```

## H3 Processing Logic

### Resolutions

We track two H3 resolutions:
- **Resolution 6** (~3.2km cells): "Preset Cell" level for city/town coverage
- **Resolution 8** (~460m cells): "Fine Cell" level for neighborhood detail

### Processing Flow

For each location:

1. **Convert to H3 cells** at both resolutions:
   ```python
   fine_cell = h3.geo_to_h3(lat, lng, resolution=8)
   preset_cell = h3.geo_to_h3(lat, lng, resolution=6)
   ```

2. **Geographic lookup** via PostGIS:
   ```sql
   SELECT cr.id as country_id, sr.id as state_id
   FROM country_regions cr
   LEFT JOIN state_regions sr ON sr.country_id = cr.id
   WHERE ST_Contains(cr.geom, ST_Point(lng, lat))
     AND (sr.geom IS NULL OR ST_Contains(sr.geom, ST_Point(lng, lat)))
   ```

3. **Deduplication** within batch:
   - Multiple locations mapping to same H3 cell → keep earliest timestamp
   - Prevents redundant writes for lingering in one spot

### Edge Cases

- **International waters**: `country_id = NULL`, don't update country stats
- **State boundaries**: Use LEFT JOIN since not all countries have state data
- **Border cells**: Accept first matching country from PostGIS query

## Database Operations

All operations occur within a single transaction for data consistency.

### 1. Create Audit Trail

```python
batch = IngestBatch(
    user_id=current_user.id,
    location_count=len(locations),
    uploaded_at=datetime.utcnow()
)
```

### 2. Upsert Cell Visits

Process cells at BOTH resolutions (creates 2 records per location):

```sql
INSERT INTO user_cell_visits (user_id, h3_index, resolution, country_id, state_id,
                               first_visited_at, last_visited_at, visit_count)
VALUES (?, ?, ?, ?, ?, ?, ?, 1)
ON CONFLICT (user_id, h3_index)
DO UPDATE SET
    last_visited_at = EXCLUDED.last_visited_at,
    visit_count = user_cell_visits.visit_count + 1
RETURNING (xmax = 0) AS inserted
```

The `RETURNING (xmax = 0)` trick identifies new cells vs revisits for response metrics.

### 3. Update Country Statistics

Recalculate coverage at both resolutions:

```sql
UPDATE user_country_stats SET
    cells_res6_visited = (SELECT COUNT(*) FROM user_cell_visits
                          WHERE user_id = ? AND country_id = ? AND resolution = 6),
    cells_res8_visited = (SELECT COUNT(*) FROM user_cell_visits
                          WHERE user_id = ? AND country_id = ? AND resolution = 8),
    coverage_res6_pct = (cells_res6_visited::float / country.land_cells_res6_total) * 100,
    coverage_res8_pct = (cells_res8_visited::float / country.land_cells_res8_total) * 100,
    updated_at = NOW()
WHERE user_id = ? AND country_id IN (?)
```

### 4. Update State Statistics

Same pattern as countries, with resolution-specific coverage.

### 5. Update Streaks

```python
# Check if last_activity_date is yesterday → extend streak
# If gap > 1 day → reset current_streak to 1
# Update longest_streak if current > longest
```

## Error Handling

### Validation Strategy

Use Pydantic schemas:

```python
class LocationPoint(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timestamp: datetime
    accuracy: Optional[float] = Field(None, ge=0, le=1000)

    @validator('timestamp')
    def timestamp_must_be_valid(cls, v):
        if v > datetime.utcnow():
            raise ValueError('Timestamp cannot be in the future')
        if v < datetime.utcnow() - timedelta(days=365):
            raise ValueError('Timestamp too old (max 1 year)')
        return v
```

### Partial Success

Process all valid locations, skip invalid ones:

```json
{
  "processed": 97,
  "new_cells_unlocked": 15,
  "errors": [
    {"index": 12, "reason": "Invalid coordinates: lat out of range"},
    {"index": 45, "reason": "Timestamp in future"}
  ]
}
```

### Transaction Strategy

- Statistics update fails → rollback entire batch (data consistency)
- Single location fails lookup → skip that location, continue with others
- Use savepoints for partial rollback if needed

## Implementation Structure

### File Organization

```
backend/
├── routers/
│   └── visits.py          # POST /api/visits/batch endpoint
├── services/
│   └── location.py        # H3 processing, geographic lookup, stats
├── schemas/
│   └── visits.py          # Pydantic models
└── requirements.txt       # Add: h3==3.7.6
```

### Service Layer Design

**Router** (`routers/visits.py`):
- Handles HTTP concerns (auth, validation, response formatting)
- Delegates business logic to service layer

**Service** (`services/location.py`):
- `process_batch()`: Main orchestration
- `convert_to_h3_cells()`: H3 conversion
- `lookup_geographic_regions()`: PostGIS queries
- `upsert_cell_visits()`: Bulk database operations
- `update_user_statistics()`: Statistics recalculation

### Key Helper Functions

```python
def convert_to_h3_cells(locations: List[LocationPoint]) -> List[H3CellData]:
    """Convert lat/lng to H3 cells at res 6 & 8."""
    pass

def lookup_geographic_regions(db: Session, cells: List[H3CellData]) -> List[H3CellData]:
    """Determine country/state for each cell via PostGIS."""
    pass

def upsert_cell_visits(db: Session, user_id: int, cells: List[H3CellData]) -> int:
    """Bulk insert/update cell visits, return count of new cells."""
    pass

def update_user_statistics(db: Session, user_id: int, affected_regions: Set[int]):
    """Recalculate coverage percentages for affected countries/states."""
    pass
```

## Dependencies

```bash
pip install h3==3.7.6
```

## Testing Strategy

### Unit Tests
- H3 conversion with known coordinates → expected h3_index
- Geographic lookup with test polygons
- Statistics calculation logic

### Integration Tests
- Full batch upload with mock locations
- Database transaction rollback scenarios
- Concurrent batch uploads (race conditions)

### Edge Case Tests
- International waters (null country)
- Invalid coordinates (out of range)
- Duplicate cells in batch
- Future timestamps
- Old timestamps (>1 year)

## Storage Considerations

- Each location creates 2 `UserCellVisit` records (res 6 + res 8)
- 1 million locations = ~2 million cell visit records
- At ~100 bytes/row = ~200MB (manageable for PostgreSQL)

## Future Flexibility

Raw coordinates stored in `IngestBatch` enable:
- Reprocessing at different H3 resolutions
- Historical analysis
- Audit trail for data integrity

To change resolutions later:
1. Write migration script reading `IngestBatch`
2. Regenerate `UserCellVisit` at new resolutions
3. Rebuild statistics tables
4. One-time operation, no data loss

## Success Criteria

- [ ] API accepts batches of 1-1000 locations
- [ ] Locations converted to H3 cells at res 6 & 8
- [ ] Geographic regions identified via PostGIS
- [ ] Cell visits upserted with revisit tracking
- [ ] Statistics updated at both resolutions
- [ ] Partial success with error reporting
- [ ] Transaction safety (rollback on failure)
- [ ] Response includes unlock counts and errors
