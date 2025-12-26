# Backend Setup Guide

Follow these steps to get your Trekkr backend server running:

## Prerequisites
- Python 3.8 or higher installed
- pip (Python package manager)

## Step 1: Navigate to the Backend Directory
```powershell
cd backend
```

## Step 2: Create a Virtual Environment
```powershell
python -m venv venv
```

## Step 3: Activate the Virtual Environment
On Windows PowerShell:
```powershell
.\venv\Scripts\Activate.ps1
```

If you get an execution policy error, run this first:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Alternatively, on Windows Command Prompt:
```cmd
venv\Scripts\activate.bat
```

## Step 4: Install Dependencies
```powershell
pip install -r requirements.txt
```

## Step 5: Run the Server
```powershell
uvicorn main:app --reload
```

The server will start on `http://127.0.0.1:8000` by default.

## Optional: Environment Variables
The backend uses environment variables with defaults:
- `DATABASE_URL`: Defaults to `sqlite:///./trekkr.db` (SQLite database)
- `SECRET_KEY`: Defaults to a dev key (change in production)

You can create a `.env` file in the `backend` directory if you want to customize these values.

## Initialize the Docker Postgres/PostGIS Database
The project ships with a PostGIS-enabled database in `docker-compose.yml`. This creates a Postgres container named `app-postgres` listening on host port `5433`.

### Quick Start (Fresh Database)
On first run, Docker automatically initializes the database with:
- PostGIS extension enabled
- All tables created (users, regions, H3 cells, etc.)
- 250 countries pre-seeded
- 5,096 states/provinces pre-seeded (ISO 3166-2)

```bash
# Start the database (auto-initializes on first run)
docker compose up -d db

# Wait ~15 seconds for initialization scripts to complete
sleep 15

# Verify tables and seed data
docker compose exec db psql -U appuser -d appdb -c "\dt"
docker compose exec db psql -U appuser -d appdb -c "SELECT COUNT(*) FROM regions_country;"  # 250
docker compose exec db psql -U appuser -d appdb -c "SELECT COUNT(*) FROM regions_state;"    # 5096
```

### Docker Init Scripts
The `docker-init/` folder contains SQL scripts that run automatically in alphabetical order:
| File | Purpose |
|------|---------|
| `00_extensions.sql` | Enables PostGIS extension |
| `01_schema.sql` | Creates all database tables |
| `02_seed_countries.sql` | Seeds 250 countries (ISO 3166-1) |
| `03_seed_states.sql` | Seeds 5,096 states/provinces (ISO 3166-2) |

### Common Commands
```bash
# Start database
docker compose up -d db

# Set DATABASE_URL for Python scripts
export DATABASE_URL=postgresql+psycopg2://appuser:apppass@localhost:5433/appdb

# List all tables
docker compose exec db psql -U appuser -d appdb -c "\dt"

# Inspect a table schema
docker compose exec db psql -U appuser -d appdb -c "\d regions_state"

# Query data
docker compose exec db psql -U appuser -d appdb -c "SELECT code, name FROM regions_state WHERE code LIKE 'US-%' LIMIT 10;"

# Stop database (preserves data)
docker compose down

# Reset database completely (deletes all data)
docker compose down -v
```

### Manual Seeding (Development)
If you need to re-seed data without resetting the container:
```bash
export DATABASE_URL=postgresql+psycopg2://appuser:apppass@localhost:5433/appdb
python scripts/seed_countries.py
python scripts/seed_states.py
```

## Populate Region Geometries (Geographic Boundaries)

After initializing the database with countries and states, you need to populate their geographic boundary data (geometries) for map visualization and spatial queries.

### Prerequisites
- PostgreSQL/PostGIS database running (see above)
- Countries and states already seeded (250 countries, 5,096 states)
- Internet connection (downloads ~30MB from Natural Earth)

### Step 1: Set Database URL
```bash
export DATABASE_URL=postgresql+psycopg2://appuser:apppass@localhost:5433/appdb
```

### Step 2: Run Alembic Migrations
```bash
# Apply all pending migrations (includes geometry population)
alembic upgrade head
```

**Expected Output:**
```
INFO  [alembic.runtime.migration] Running upgrade 20251224_0001 -> 20251225_0002

============================================================
MIGRATION: Populate Region Geometries
============================================================

Downloading countries from Natural Earth...
✓ Loaded 258 countries features
Processing 258 Natural Earth countries...
  Updated 10 countries...
  Updated 20 countries...
  ... (continues)

✓ Country Summary:
  Matched: 236
  Unmatched: 22

Downloading states/provinces from Natural Earth...
✓ Loaded 4596 states/provinces features
Processing 4596 Natural Earth states/provinces...
  Updated 50 states...
  Updated 100 states...
  ... (continues)

✓ State Summary:
  Matched: 4102
  Unmatched: 494

============================================================
MIGRATION COMPLETE
============================================================
Countries: 236/258 matched
States: 4102/4596 matched
Total unmatched: 516
============================================================
```

**Migration Time:** ~5-8 minutes (depends on internet speed)

### Step 3: Verify Geometries Populated
```bash
# Check countries with geometries
docker compose exec db psql -U appuser -d appdb -c \
  "SELECT COUNT(*) FROM regions_country WHERE geom IS NOT NULL;"
# Expected: 236

# Check states with geometries
docker compose exec db psql -U appuser -d appdb -c \
  "SELECT COUNT(*) FROM regions_state WHERE geom IS NOT NULL;"
# Expected: 4025

# Test a spatial query (which country contains Los Angeles?)
docker compose exec db psql -U appuser -d appdb -c \
  "SELECT name FROM regions_country WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(-118.2437, 34.0522), 4326));"
# Expected: United States
```

### Coverage Statistics
After running the migration:
- **Countries**: 236 out of 250 (94.4% coverage)
- **States/Provinces**: 4,025 out of 5,096 (79.0% coverage)

Unmatched regions are typically:
- Disputed territories (Gaza Strip, West Bank, Somaliland)
- Military zones (UNDOF, Dhekelia)
- Entities with invalid ISO codes in Natural Earth data
- Historical administrative divisions that have been reorganized

### Rollback (if needed)
To remove all geometries and revert to the previous state:
```bash
alembic downgrade -1
```

This sets all `geom` columns to NULL without deleting country/state metadata.

## Verify Installation
Once the API server is running, you can:
- Visit `http://127.0.0.1:8000` - Root endpoint
- Visit `http://127.0.0.1:8000/docs` - Interactive API documentation (Swagger UI)
- Visit `http://127.0.0.1:8000/api/health` - Health check endpoint
