# Trekkr Backend Deployment Plan - Railway

This document outlines the complete deployment process for the Trekkr backend on Railway.

## Table of Contents
1. [Pre-Deployment Security Actions](#1-pre-deployment-security-actions)
2. [Railway Project Setup](#2-railway-project-setup)
3. [Database Configuration](#3-database-configuration)
4. [Environment Variables](#4-environment-variables)
5. [Code Changes Required](#5-code-changes-required)
6. [Deployment Configuration](#6-deployment-configuration)
7. [Database Initialization](#7-database-initialization)
8. [Verification Checklist](#8-verification-checklist)

---

## 1. Pre-Deployment Security Actions

### Verify `.env` is Not in Git

Your `.env` file is properly excluded from version control:
- Listed in `.gitignore` (line 21)
- Listed in `backend/.gitignore` (line 20)
- Never committed to git history

**No action required** - your local secrets are safe.

### For Production

You'll create a **new** SendGrid API key specifically for production use in Railway's environment variables. Keep your local development key separate.

---

## 2. Railway Project Setup

### Create Railway Project

1. Go to [Railway](https://railway.app) and create a new project
2. Choose "Empty Project"
3. Connect your GitHub repository (optional, for auto-deploy)

### Project Structure

Railway will need:
- **Service**: The FastAPI backend
- **Database**: PostgreSQL with PostGIS extension

---

## 3. Database Configuration

### Add PostgreSQL Database

1. In Railway project, click **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Railway automatically provisions the database and sets `DATABASE_URL`

### PostGIS Extension

Railway's PostgreSQL supports PostGIS. After the database is created, connect and run:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

**Option A: Via Railway's Query Tab**
- Click on the PostgreSQL service
- Go to "Data" tab
- Run the SQL command above

**Option B: Via psql connection**
```bash
# Get connection string from Railway dashboard
psql $DATABASE_URL -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

### Database URL Format

Railway provides `DATABASE_URL` in this format:
```
postgresql://user:password@host:port/database
```

**Important:** The backend expects `postgresql+psycopg2://...` format. See [Code Changes](#5-code-changes-required) for the fix.

---

## 4. Environment Variables

### Required Environment Variables

Set these in Railway's Variables tab for the backend service:

| Variable | Value | Notes |
|----------|-------|-------|
| `ENV` | `production` | Enables strict validation |
| `SECRET_KEY` | `<generate-32+-char-secret>` | See generation command below |
| `DATABASE_URL` | (auto-set by Railway) | Link to PostgreSQL service |
| `SENDGRID_API_KEY` | `SG.xxx...` | New API key from SendGrid |
| `SENDGRID_FROM_EMAIL` | `noreply@yourdomain.com` | Must be verified in SendGrid |
| `FRONTEND_URL` | `https://your-frontend.com` | Your production frontend URL |
| `CORS_ORIGINS` | `https://your-frontend.com` | Comma-separated if multiple |
| `PORT` | (auto-set by Railway) | Railway injects this |

### Generate a Secure SECRET_KEY

```bash
# Option 1: Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Option 2: OpenSSL
openssl rand -base64 32
```

Example output: `Abc123XyzRandomSecureKeyHere456789012`

### Optional Environment Variables

| Variable | Default | Notes |
|----------|---------|-------|
| `LOG_LEVEL` | `INFO` | Set to `DEBUG` for troubleshooting |

---

## 5. Code Changes Required

### 5.1 Create Dockerfile

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for psycopg2 and geospatial libraries
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libgeos-dev \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Railway sets PORT env var)
EXPOSE 8000

# Run the application
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

### 5.2 Create railway.json (Optional)

Create `backend/railway.json` for build configuration:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "healthcheckPath": "/api/health",
    "healthcheckTimeout": 30,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

### 5.3 Update Database URL Handling

Railway provides `DATABASE_URL` without the `+psycopg2` driver suffix. Update `backend/database.py` to handle this:

**Current code (line 6):**
```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./trekkr.db")
```

**Change to:**
```python
def get_database_url() -> str:
    """Get database URL, ensuring correct driver for PostgreSQL."""
    url = os.getenv("DATABASE_URL", "sqlite:///./trekkr.db")

    # Railway provides postgresql:// but SQLAlchemy needs postgresql+psycopg2://
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return url

DATABASE_URL = get_database_url()
```

### 5.4 Create Database Initialization Script

Create `backend/scripts/init_production_db.py`:

```python
#!/usr/bin/env python
"""
Initialize production database with required extensions and seed data.
Run this once after deploying to Railway.
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import engine, Base
from models import user, geo, visits, stats, achievements


def init_database():
    """Initialize database with extensions, tables, and seed data."""
    print("Starting database initialization...")

    with engine.connect() as conn:
        # 1. Create PostGIS extension
        print("Creating PostGIS extension...")
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()
        print("PostGIS extension ready.")

    # 2. Create all tables
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")

    # 3. Seed countries and states
    print("Seeding geographic data...")
    from scripts.seed_countries import seed_countries
    from scripts.seed_states import seed_states

    seed_countries()
    seed_states()

    print("Database initialization complete!")


if __name__ == "__main__":
    init_database()
```

### 5.5 Ensure .dockerignore Exists

Create `backend/.dockerignore`:

```
# Development files
.env
.env.*
.venv/
venv/
__pycache__/
*.pyc
*.pyo

# Testing
.pytest_cache/
.coverage
htmlcov/
tests/

# IDE
.vscode/
.idea/

# Docker dev files
docker-compose.yml
docker-init/

# Documentation
*.md
docs/

# Git
.git/
.gitignore
```

---

## 6. Deployment Configuration

### Option A: Deploy from GitHub (Recommended)

1. In Railway, click **"+ New"** → **"GitHub Repo"**
2. Select your repository
3. Set **Root Directory** to `backend`
4. Railway auto-detects Dockerfile and builds

### Option B: Deploy via Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Deploy
cd backend
railway up
```

### Configure Service Settings

In Railway dashboard for the backend service:

1. **Settings** → **Networking**:
   - Enable "Public Networking" to get a public URL
   - Or use Railway's internal networking for frontend-only access

2. **Settings** → **Health Check**:
   - Path: `/api/health`
   - Timeout: 30 seconds

3. **Variables**:
   - Link `DATABASE_URL` to your PostgreSQL service
   - Add all other environment variables from Section 4

---

## 7. Database Initialization

After the first deployment, initialize the database with seed data.

### Option A: Railway Shell (Recommended)

1. Go to your backend service in Railway
2. Click **"Shell"** or use CLI: `railway run bash`
3. Run:

```bash
python scripts/init_production_db.py
```

### Option B: One-Time Deploy Command

Add to `railway.json`:

```json
{
  "deploy": {
    "startCommand": "python scripts/init_production_db.py && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"
  }
}
```

**Note:** Remove the init script from startCommand after first successful run to avoid re-seeding on every deploy.

### Manual SQL Initialization (Alternative)

If the script approach doesn't work, run these SQL files manually via Railway's database query tab:

1. `docker-init/00_extensions.sql` - PostGIS extension
2. `docker-init/01_schema.sql` - Table creation (optional if using SQLAlchemy)
3. `docker-init/02_seed_countries.sql` - 250 countries
4. `docker-init/03_seed_states.sql` - 5,096 states/provinces

---

## 8. Verification Checklist

### Pre-Deployment

- [ ] Generated new SendGrid API key for production
- [ ] Created `backend/Dockerfile`
- [ ] Created `backend/.dockerignore`
- [ ] Updated `backend/database.py` for Railway's DATABASE_URL format
- [ ] Committed and pushed all changes

### Railway Configuration

- [ ] PostgreSQL database provisioned
- [ ] PostGIS extension enabled
- [ ] All environment variables set:
  - [ ] `ENV=production`
  - [ ] `SECRET_KEY` (32+ characters)
  - [ ] `DATABASE_URL` (linked to PostgreSQL)
  - [ ] `SENDGRID_API_KEY`
  - [ ] `SENDGRID_FROM_EMAIL`
  - [ ] `FRONTEND_URL`
  - [ ] `CORS_ORIGINS`
- [ ] Backend service deployed successfully

### Post-Deployment Verification

- [ ] Health check passes: `GET https://your-backend.railway.app/api/health`
- [ ] Database initialized with seed data (250 countries, 5,096 states)
- [ ] User registration works: `POST /api/auth/register`
- [ ] Login works: `POST /api/auth/login`
- [ ] Location ingestion works: `POST /api/v1/location/ingest`
- [ ] Password reset email sends successfully

### API Endpoint Tests

```bash
# Set your Railway backend URL
export API_URL="https://your-backend.railway.app"

# Health check
curl $API_URL/api/health

# Register (should succeed)
curl -X POST $API_URL/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"SecurePass123!","username":"testuser"}'

# Login (should return tokens)
curl -X POST $API_URL/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"SecurePass123!"}'
```

---

## Summary of Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `backend/Dockerfile` | **CREATE** | Production container definition |
| `backend/.dockerignore` | **CREATE** | Exclude dev files from image |
| `backend/railway.json` | **CREATE** | Railway build/deploy config |
| `backend/database.py` | **MODIFY** | Handle Railway's DATABASE_URL format |
| `backend/scripts/init_production_db.py` | **CREATE** | Database initialization script |

---

## Troubleshooting

### "Connection refused" to database
- Ensure DATABASE_URL is linked to the PostgreSQL service
- Check if the database service is running

### "PostGIS extension not found"
- Run `CREATE EXTENSION IF NOT EXISTS postgis;` manually
- Railway's PostgreSQL supports PostGIS but extension must be enabled

### "SECRET_KEY validation failed"
- Ensure SECRET_KEY is at least 32 characters
- Check there are no extra spaces or quotes

### Rate limiting returns 500 errors
- Known issue: Rate limiter uses IP fallback for auth endpoints
- See `docs/plans/RATE_LIMITING_FIX.md` for fix details

### CORS errors from frontend
- Verify CORS_ORIGINS matches your frontend URL exactly
- Include protocol (https://) and no trailing slash

---

## Cost Estimate

Railway pricing (as of 2024):
- **Hobby Plan**: $5/month, includes:
  - 500 hours of execution
  - Shared resources
  - Good for development/testing

- **Pro Plan**: $20/month, includes:
  - Unlimited execution hours
  - More resources
  - Better for production

PostgreSQL database usage is billed separately based on storage and compute.

---

## Next Steps After Deployment

1. Set up custom domain (optional)
2. Configure monitoring/alerting
3. Set up CI/CD for automatic deployments
4. Implement Redis for rate limiting (if scaling to multiple instances)
5. Deploy the React Native frontend to connect to this backend
