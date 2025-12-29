# Achievements System Design

## Overview

Implement a gamification system that rewards users for exploration milestones. Achievements are unlocked automatically when users meet criteria through location ingestion.

## Key Decisions

- **Continent classification**: Primary continent only (UN geoscheme) - each country assigned to one continent
- **Achievement tiers**: Progressive (3/5/7 continents, 10%/25%/50% coverage)
- **Coverage naming**: Country Explorer/Master/Conqueror, Region Explorer/Master

## Data Model

### Existing Tables (Already Created)

- `achievements` - Achievement catalog with flexible `criteria_json`
- `user_achievements` - Join table recording when user unlocked achievement

### New Column

Add `continent` column to `regions_country` table:

```sql
ALTER TABLE regions_country ADD COLUMN continent VARCHAR(32) NOT NULL;
```

Values: Africa, Antarctica, Asia, Europe, North America, Oceania, South America

### Criteria Types

| Type | Description | Example JSON |
|------|-------------|--------------|
| `cells_total` | Total res8 cells visited | `{"type": "cells_total", "threshold": 100}` |
| `countries` | Distinct countries visited | `{"type": "countries", "threshold": 10}` |
| `regions` | Distinct regions visited | `{"type": "regions", "threshold": 50}` |
| `regions_in_country` | Regions in single country | `{"type": "regions_in_country", "threshold": 5}` |
| `continents` | Distinct continents visited | `{"type": "continents", "threshold": 3}` |
| `hemispheres` | N/S hemispheres visited | `{"type": "hemispheres", "count": 2}` |
| `country_coverage_pct` | Coverage % of any country | `{"type": "country_coverage_pct", "threshold": 0.25}` |
| `region_coverage_pct` | Coverage % of any region | `{"type": "region_coverage_pct", "threshold": 0.50}` |
| `unique_days` | Distinct visit days | `{"type": "unique_days", "threshold": 30}` |

## Achievement Catalog (17 Total)

### Volume Milestones (3)

| Code | Name | Description | Criteria |
|------|------|-------------|----------|
| `first_steps` | First Steps | Visit your first location | `{"type": "cells_total", "threshold": 1}` |
| `explorer` | Explorer | Visit 100 unique cells | `{"type": "cells_total", "threshold": 100}` |
| `wanderer` | Wanderer | Visit 500 unique cells | `{"type": "cells_total", "threshold": 500}` |

### Geographic Breadth (6)

| Code | Name | Description | Criteria |
|------|------|-------------|----------|
| `globetrotter` | Globetrotter | Visit 10 countries | `{"type": "countries", "threshold": 10}` |
| `country_collector` | Country Collector | Visit 25 countries | `{"type": "countries", "threshold": 25}` |
| `state_hopper` | State Hopper | Visit 5 regions in one country | `{"type": "regions_in_country", "threshold": 5}` |
| `regional_master` | Regional Master | Visit 50 regions total | `{"type": "regions", "threshold": 50}` |
| `hemisphere_hopper` | Hemisphere Hopper | Visit both N/S hemispheres | `{"type": "hemispheres", "count": 2}` |
| `frequent_traveler` | Frequent Traveler | Visit on 30 unique days | `{"type": "unique_days", "threshold": 30}` |

### Continent Achievements (3)

| Code | Name | Description | Criteria |
|------|------|-------------|----------|
| `continental` | Continental | Visit 3 continents | `{"type": "continents", "threshold": 3}` |
| `intercontinental` | Intercontinental | Visit 5 continents | `{"type": "continents", "threshold": 5}` |
| `world_explorer` | World Explorer | Visit all 7 continents | `{"type": "continents", "threshold": 7}` |

### Coverage Depth (5)

| Code | Name | Description | Criteria |
|------|------|-------------|----------|
| `country_explorer` | Country Explorer | 10% coverage of any country | `{"type": "country_coverage_pct", "threshold": 0.10}` |
| `country_master` | Country Master | 25% coverage of any country | `{"type": "country_coverage_pct", "threshold": 0.25}` |
| `country_conqueror` | Country Conqueror | 50% coverage of any country | `{"type": "country_coverage_pct", "threshold": 0.50}` |
| `region_explorer` | Region Explorer | 25% coverage of any state/province | `{"type": "region_coverage_pct", "threshold": 0.25}` |
| `region_master` | Region Master | 50% coverage of any state/province | `{"type": "region_coverage_pct", "threshold": 0.50}` |

## Service Architecture

### AchievementService

```python
# backend/services/achievement_service.py

class AchievementService:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def check_and_unlock(self) -> List[Achievement]:
        """Check all achievements, unlock newly earned ones, return newly unlocked."""

    def get_user_stats(self) -> dict:
        """Gather all stats needed for achievement evaluation."""

    def evaluate_criteria(self, criteria: dict, stats: dict) -> bool:
        """Check if user stats satisfy achievement criteria."""

    def get_all_with_status(self) -> List[dict]:
        """All achievements with user's unlock status for API response."""
```

### Integration with LocationProcessor

In `process_location()`, after recording cell visit:

```python
from services.achievement_service import AchievementService

# Check achievements after cell visit recorded
achievement_service = AchievementService(self.db, self.user_id)
newly_unlocked = achievement_service.check_and_unlock()

return {
    "discoveries": discoveries,
    "revisits": revisits,
    "visit_counts": visit_counts,
    "achievements_unlocked": [
        {"code": a.code, "name": a.name, "description": a.description}
        for a in newly_unlocked
    ]
}
```

## API Endpoints

### New Achievements Router

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/v1/achievements` | All achievements with user's unlock status |
| GET | `/api/v1/achievements/unlocked` | Only user's unlocked achievements |

**Response for `/api/v1/achievements`:**

```json
{
  "achievements": [
    {
      "code": "first_steps",
      "name": "First Steps",
      "description": "Visit your first location",
      "unlocked": true,
      "unlocked_at": "2024-12-20T10:30:00Z"
    },
    {
      "code": "explorer",
      "name": "Explorer",
      "description": "Visit 100 unique cells",
      "unlocked": false,
      "unlocked_at": null
    }
  ],
  "total": 17,
  "unlocked_count": 5
}
```

### Updated Location Ingest Response

```python
class LocationIngestResponse(BaseModel):
    discoveries: DiscoveriesSchema
    revisits: RevisitsSchema
    visit_counts: VisitCountsSchema
    achievements_unlocked: List[AchievementUnlockedSchema]  # NEW

class AchievementUnlockedSchema(BaseModel):
    code: str
    name: str
    description: str
```

## Database Migrations

### Migration 1: Add Continent Column

```sql
ALTER TABLE regions_country ADD COLUMN continent VARCHAR(32);

-- Populate using UN geoscheme
UPDATE regions_country SET continent = 'Africa' WHERE iso2 IN (...);
UPDATE regions_country SET continent = 'Antarctica' WHERE iso2 IN ('AQ');
UPDATE regions_country SET continent = 'Asia' WHERE iso2 IN (...);
UPDATE regions_country SET continent = 'Europe' WHERE iso2 IN (...);
UPDATE regions_country SET continent = 'North America' WHERE iso2 IN (...);
UPDATE regions_country SET continent = 'Oceania' WHERE iso2 IN (...);
UPDATE regions_country SET continent = 'South America' WHERE iso2 IN (...);

ALTER TABLE regions_country ALTER COLUMN continent SET NOT NULL;
```

### Migration 2: Seed Achievements

Insert all 17 achievements into the `achievements` table.

## Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `backend/services/achievement_service.py` | Core achievement logic |
| `backend/routers/achievements.py` | API endpoints |
| `backend/schemas/achievements.py` | Pydantic request/response models |
| `backend/alembic/versions/YYYYMMDD_add_continent_to_countries.py` | Add continent column |
| `backend/alembic/versions/YYYYMMDD_seed_achievements.py` | Seed 17 achievements |
| `backend/tests/test_achievement_service.py` | Service unit tests |
| `backend/tests/test_achievements_router.py` | Endpoint integration tests |

### Modified Files

| File | Changes |
|------|---------|
| `backend/models/geo.py` | Add `continent` column to `CountryRegion` |
| `backend/services/location_processor.py` | Call `AchievementService.check_and_unlock()` |
| `backend/routers/location.py` | Update response schema |
| `backend/schemas/location.py` | Add `AchievementUnlockedSchema` |
| `backend/main.py` | Register achievements router |
| `backend/tests/test_location_processor.py` | Assert `achievements_unlocked` in response |
| `backend/tests/conftest.py` | Add achievement fixtures if needed |

## Test Strategy (TDD)

### Test Files

**1. `backend/tests/test_achievement_service.py`**

- `test_check_and_unlock_first_steps`
- `test_check_and_unlock_returns_only_new`
- `test_evaluate_cells_total_criteria`
- `test_evaluate_countries_criteria`
- `test_evaluate_continents_criteria`
- `test_evaluate_country_coverage_criteria`
- `test_evaluate_region_coverage_criteria`
- `test_evaluate_regions_in_country_criteria`
- `test_evaluate_hemispheres_criteria`
- `test_evaluate_unique_days_criteria`
- `test_get_all_with_status_unlocked`
- `test_get_all_with_status_locked`

**2. `backend/tests/test_achievements_router.py`**

- `test_get_all_achievements_authenticated`
- `test_get_all_achievements_unauthenticated`
- `test_get_unlocked_achievements_empty`
- `test_get_unlocked_achievements_with_data`

**3. `backend/tests/test_location_processor.py`** (updates)

- `test_process_location_returns_achievements_unlocked`
- `test_process_location_unlocks_first_steps`
- `test_process_location_no_duplicate_unlocks`

### TDD Order

1. Write tests first (red)
2. Implement to make them pass (green)
3. Refactor if needed
4. Run full test suite to ensure no regressions

### Validation

After implementation, run full test suite:

```bash
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/ -v
```

All existing tests must continue to pass.

## Implementation Order

1. Migration: Add continent column → Run existing tests
2. Migration: Seed achievements → Run existing tests
3. Write achievement service tests (red)
4. Implement AchievementService → New tests pass
5. Write achievements router tests (red)
6. Implement router + schemas + register in main.py → New tests pass
7. Write updated location processor tests (red)
8. Integrate into LocationProcessor → New tests pass
9. Run full test suite → All tests pass
