# Location Ingestion Test Suite Design

**Date**: 2025-12-26
**Status**: Approved
**Scope**: Comprehensive test coverage for location ingestion endpoint and LocationProcessor service

---

## Overview

This test suite provides comprehensive coverage for the location ingestion functionality in `backend/routers/location.py` and `backend/services/location_processor.py`. The system accepts GPS coordinates and H3 cells, performs reverse geocoding, tracks visits, and detects discoveries (new countries/states/cells).

## Test Architecture

### Framework & Tools
- **pytest**: Modern Python testing framework with fixtures and parametrization
- **TestClient**: FastAPI's test client for endpoint integration tests
- **unittest.mock**: For mocking database interactions in unit tests
- **PostgreSQL/PostGIS**: Real test database for integration tests

### File Structure

```
backend/
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # Shared pytest fixtures
│   ├── test_location_processor.py       # Unit tests for LocationProcessor
│   ├── test_location_router.py          # Integration tests for /ingest endpoint
│   └── fixtures/
│       ├── __init__.py
│       └── test_data.py                 # Test data constants
└── pytest.ini                            # Pytest configuration
```

---

## Test Coverage

### Unit Tests (`test_location_processor.py`)

Tests the `LocationProcessor` service class with mocked database interactions.

**1. Basic Location Processing**
- Happy path: first visit to a new location
- H3 res-6 cell correctly derived from res-8
- Both resolution cells processed
- Timestamp handling (provided vs auto-generated)
- device_id passed through correctly

**2. Reverse Geocoding**
- Successfully finds country and state
- Finds country but no state
- Finds neither (international waters, poles)
- Handles NULL responses from PostGIS

**3. UPSERT Logic**
- First visit: creates new records (is_new=True, visit_count=1)
- Revisit: updates existing records (is_new=False, visit_count incremented)
- Preserves existing country_id/state_id when NULL (COALESCE logic)

**4. Discovery Detection**
- First visit to new country returns new_country
- First visit to new state returns new_state
- Revisit to known country does NOT return new_country
- User with other cells in country does NOT get new_country
- Only checks country/state discovery when res-8 cell is new

### Integration Tests (`test_location_router.py`)

Tests the `/ingest` POST endpoint end-to-end with real database.

**1. Request Validation**
- Valid requests return 200 with correct schema
- Invalid latitude/longitude returns 422
- Invalid H3 index returns 422
- Wrong H3 resolution returns 422
- Missing required fields returns 422

**2. H3 Coordinate Validation**
- Exact H3 match succeeds
- Neighbor cells (GPS jitter tolerance) succeed
- Non-matching, non-neighbor cells return 400
- Error includes expected vs received H3 indices

**3. Authentication & Authorization**
- No JWT token returns 401
- Invalid/expired token returns 401
- Valid token succeeds

**4. Rate Limiting**
- 120 requests/minute per user succeeds
- 121st request returns 429
- Different users have independent limits
- Rate limit resets after 1 minute

**5. Device Handling**
- Valid device_id belonging to user links device
- device_id for different user is ignored
- Non-existent device_id is ignored
- No device_id works fine (None)

**6. End-to-End Discovery Flow**
- First location in new country returns full discovery
- Second location in same country returns only new cells
- Revisit exact location returns empty discoveries

---

## Edge Cases & Error Scenarios

### Geographic Edge Cases
- International waters (no country/state)
- North/South poles
- Prime Meridian & Equator (0° crossings)
- Antimeridian (±180° longitude)
- Border regions
- Small countries (Monaco, Vatican, Liechtenstein)
- Island nations (Hawaii, Philippines)

### H3 Edge Cases
- Pentagon cells (12 per resolution)
- Cell boundaries
- All 6 neighbor validation
- Parent-child relationship verification

### Database Edge Cases
- First ever visit (empty database)
- Concurrent visits
- Missing geography data
- Orphaned cells (no country_id/state_id)

### Error Scenarios
- Database connection failure (503)
- PostGIS query timeout
- Transaction rollback on error
- SQL injection attempts (parameter escaping)

---

## Fixtures & Test Data

### Database Fixtures (`conftest.py`)
- `mock_db_session`: MagicMock for unit tests
- `test_database_url`: PostgreSQL test DB URL
- `db_session`: Real session for integration tests (auto-rollback)
- `seed_geography`: Populates test countries/states

### Test User & Device Fixtures
- `test_user`: Creates test user
- `test_device`: Creates test device linked to user
- `client`: FastAPI TestClient with overridden dependencies

### Mock Data Fixtures
- `mock_country`: Mock CountryRegion object
- `mock_state`: Mock StateRegion object

### Test Data Constants (`fixtures/test_data.py`)
```python
SAN_FRANCISCO = {
    "latitude": 37.7749, "longitude": -122.4194,
    "h3_res8": "8828308281fffff", "country": "United States", "state": "California"
}

TOKYO = {...}
INTERNATIONAL_WATERS = {...}
```

### Helper Functions
- `create_jwt_token(user_id)`: Generate valid JWT
- `create_test_country(db, name, iso2, geom)`: Insert test country
- `create_test_state(db, name, country_id, geom)`: Insert test state
- `assert_discovery_response(...)`: Validate response structure

---

## pytest Configuration (`pytest.ini`)

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -v --tb=short --strict-markers
markers =
    unit: Unit tests with mocked dependencies
    integration: Integration tests with real database
    slow: Tests that take >1 second
```

---

## Running Tests

```bash
# All tests
pytest

# Unit tests only (fast)
pytest -m unit

# Integration tests only
pytest -m integration

# Specific file
pytest tests/test_location_processor.py

# With coverage
pytest --cov=routers.location --cov=services.location_processor
```

---

## Success Criteria

- ✅ All unit tests pass in isolation with mocked dependencies
- ✅ All integration tests pass with real PostgreSQL/PostGIS
- ✅ Code coverage > 90% for location_processor.py and location.py
- ✅ Edge cases handled gracefully
- ✅ Tests run in < 30 seconds total
- ✅ No database state leakage between tests
