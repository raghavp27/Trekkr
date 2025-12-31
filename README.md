# Trekkr

A mobile travel journal app that transforms real-world exploration into a visual "fog of war" experience. As you travel, Trekkr reveals an interactive map showing everywhere you've been, using hexagonal H3 cells to track coverage at multiple zoom levels.

## Concept

Trekkr creates a personal exploration map where:
- **Unexplored areas** appear grayed out (fog of war)
- **Visited areas** are revealed as you physically travel there
- **Coverage statistics** show how much of each country/region you've explored
- **H3 hexagonal grid** provides precise, multi-resolution tracking

## Tech Stack

**Backend:** FastAPI + PostgreSQL/PostGIS + H3 geospatial indexing  
**Frontend:** React Native (Expo) + Mapbox GL  
**Database:** PostgreSQL 16 with PostGIS extension  
**Geospatial:** H3 hexagonal grid system for coverage tracking

## Project Structure

```
Trekkr/
├── backend/          # FastAPI backend
│   ├── alembic/      # Database migrations
│   ├── data/         # Static data files (e.g., countries.json)
│   ├── models/       # SQLAlchemy database models
│   ├── routers/      # API route handlers
│   ├── schemas/      # Pydantic request/response schemas
│   ├── scripts/      # Utility scripts (e.g., seed_countries.py)
│   ├── services/     # Business logic and utilities
│   └── main.py       # FastAPI application entry point
│
└── frontend/         # React Native (Expo) frontend
    ├── app/          # Expo Router file-based routing
    ├── components/   # Reusable React components
    ├── contexts/     # React context providers
    ├── services/     # API and storage services
    ├── config/       # Configuration files
    └── hooks/        # Custom React hooks
```

## Features

### Core Functionality
- 🔐 **Advanced Auth** - JWT with access/refresh tokens, password reset, and device management
- 📍 **Location Ingestion** - GPS tracking with H3 hexagonal cell resolution
- 🗺️ **Multi-Level Coverage** - Track exploration at country, region, and cell levels
- 📊 **Statistics** - Coverage percentages, visit counts, and timestamps
- 🏆 **Achievements** - Unlockable badges for exploration milestones (e.g., "First Discovery")
- 🌍 **Global Support** - Country, state/region, and continent data for worldwide tracking
- 🔄 **Real-time Sync** - Single-device tracking with cloud synchronization

### Technical Features
- **H3 Geospatial Indexing** - Hierarchical hexagonal grid (res 6 & 8)
- **PostGIS Integration** - Spatial queries with optimized GIST indexes
- **Rate Limiting** - Per-user limits for location ingestion and auth actions
- **Comprehensive Testing** - 150+ integration tests with high coverage
- 📱 **Cross-platform** - iOS, Android, Web (Expo framework)

## Getting Started

### Prerequisites

- **Python 3.12+** (for backend)
- **Node.js 18+** (for frontend)
- **Docker & Docker Compose** (for PostgreSQL/PostGIS database)
- **npm or yarn**

### Backend Setup

#### 1. Start the Database

Using Docker Compose (recommended):

```bash
cd backend
docker compose up -d db
```

This starts PostgreSQL 16 with PostGIS extension on port **5433**.

#### 2. Set Up Python Environment

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# OR: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

#### 3. Configure Environment

Create a `.env` file in `backend/` directory:

```env
DATABASE_URL=postgresql+psycopg2://appuser:apppass@localhost:5433/appdb
SECRET_KEY=your-secret-key-change-in-production
```

#### 4. Run Database Migrations

```bash
# Database tables are created automatically on first run
# Or manually with:
alembic upgrade head
```

#### 5. Start the API Server

```bash
uvicorn main:app --reload --env-file .env
```

The API will be available at:
- **API:** `http://127.0.0.1:8000`
- **Interactive Docs:** `http://127.0.0.1:8000/docs`
- **Health Check:** `http://127.0.0.1:8000/api/health`

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm start
   ```

4. Update API configuration:
   - Edit `frontend/config/api.ts` to set the correct API base URL
   - For iOS physical devices, update the IP address
   - Android emulator automatically uses `10.0.2.2`

5. Configure Mapbox (if using maps):
   - Update `app.json` with your Mapbox secret token

## Development

### Backend Architecture

- **FastAPI** - Modern async web framework with automatic OpenAPI docs
- **SQLAlchemy 2.0** - ORM with raw SQL support for complex spatial queries
- **PostgreSQL + PostGIS** - Geospatial database for point-in-polygon queries
- **JWT Authentication** - Secure access/refresh token system
- **H3 Geospatial Library** - Hierarchical hexagonal grid indexing
- **Pydantic v2** - Request/response validation and serialization
- **SlowAPI** - Rate limiting for location ingestion and auth endpoints
- **Alembic** - Database migrations
- **SendGrid** - Transactional email service for password management

### Frontend Stack

- **Expo SDK 54** - React Native framework
- **Expo Router** - File-based routing system
- **Mapbox GL** - Interactive map rendering
- **H3-js** - Client-side hexagonal grid calculations
- **Expo Location** - GPS tracking and background location
- **Expo Secure Store** - Encrypted token storage
- **TypeScript** - Full type safety

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register a new user
- `POST /api/auth/login` - Login and receive JWT tokens
- `POST /api/auth/logout` - Invalidate refresh token
- `POST /api/auth/refresh` - Get new access token
- `GET /api/auth/me` - Get current user profile
- `POST /api/auth/change-password` - Change password (rate limited)
- `POST /api/auth/forgot-password` - Request password reset email
- `POST /api/auth/reset-password` - Reset password with email token
- `PATCH /api/auth/device` - Update device metadata (single device per user)

### Location Tracking
- `POST /api/v1/location/ingest` - Upload visited H3 cells (rate limited: 120/min)
  - Validates H3 cell matches GPS coordinates
  - Performs reverse geocoding to country/region
  - Returns newly discovered countries/regions

### Map Data
- `GET /api/v1/map/summary` - Get all visited countries and regions
  - Returns ISO codes and names
  - Used for fog-of-war rendering
  
- `GET /api/v1/map/cells` - Get H3 cells within viewport bounding box
  - Query params: `min_lng`, `min_lat`, `max_lng`, `max_lat`
  - Returns cells at resolution 6 and 8
  - Bbox validation (max 180° longitude, 90° latitude span)

### Achievements
- `GET /api/v1/achievements` - List all achievements with user unlock status
- `GET /api/v1/achievements/unlocked` - List only user's earned badges

### Statistics
- `GET /api/v1/stats/countries` - Get country coverage statistics
  - Coverage percentage (cells visited / total land cells)
  - First and last visit timestamps
  - Supports sorting, pagination
  
- `GET /api/v1/stats/regions` - Get state/province coverage statistics
  - Coverage percentage per region
  - Parent country information
  - Supports sorting, pagination

### Health
- `GET /api/health` - Health check endpoint

## Environment Variables

### Backend
- `DATABASE_URL` - PostgreSQL connection string (default: `postgresql+psycopg2://appuser:apppass@localhost:5433/appdb`)
- `SECRET_KEY` - JWT secret key for token signing (required, change in production!)
- `TEST_DATABASE_URL` - Test database URL (default: port 5434)

### Frontend
- API base URL configured in `frontend/config/api.ts`
- Mapbox token in `app.json`

## Testing

### Backend Tests

The backend has comprehensive test coverage with 150+ integration tests:

```bash
cd backend

# Start test database
docker compose up -d db-test

# Run all tests
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" \
  python -m pytest tests/ -v

# Run specific test file
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" \
  python -m pytest tests/test_stats_service.py -v

# Run with coverage
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" \
  python -m pytest tests/ --cov=. --cov-report=html
```

**Test Coverage:**
- ✅ Location ingestion and processing
- ✅ Map endpoints and services
- ✅ Statistics endpoints and services
- ✅ Authentication and authorization
- ✅ Rate limiting
- ✅ H3 coordinate validation
- ✅ Reverse geocoding
- ✅ Discovery flow (first visits)

## Database Schema

### Core Tables
- `users` - User accounts
- `devices` - User devices (single device per user)
- `regions_country` - Country geometries and metadata (includes continent)
- `regions_state` - State/province geometries
- `h3_cells` - Registry of visited H3 cells with geographic references
- `user_cell_visits` - Per-user cell ownership and visit metadata
- `ingest_batches` - Audit log of location uploads
- `achievements` - Registry of available exploration badges
- `user_achievements` - Track unlocked badges for each user
- `password_resets` - Secure tokens for password recovery

### Spatial Queries
The app uses PostGIS for efficient spatial operations:
- Point-in-polygon queries for reverse geocoding
- Bounding box queries for viewport filtering
- ST_Intersects for geographic containment

## Docker Services

The `docker-compose.yml` provides two PostgreSQL instances:

```bash
# Development database (port 5433)
docker compose up -d db

# Test database (port 5434)
docker compose up -d db-test

# View logs
docker compose logs -f db

# Stop services
docker compose down
```

## License

MIT

