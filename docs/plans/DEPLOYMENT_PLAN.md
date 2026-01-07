# Trekkr Backend Deployment Plan - Render

This document outlines the complete deployment process for the Trekkr backend on Render.

## Table of Contents
1. [Pre-Deployment Security Actions](#1-pre-deployment-security-actions)
2. [Render Project Setup](#2-render-project-setup)
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

You'll create a **new** SendGrid API key specifically for production use in Render's environment variables. Keep your local development key separate.

---

## 2. Render Project Setup

### Create Render Account

1. Go to [Render](https://render.com) and sign up/login
2. Connect your GitHub account for auto-deploy

### Project Structure

Render will need:
- **Web Service**: The FastAPI backend
- **PostgreSQL Database**: With PostGIS extension support

---

## 3. Database Configuration

### Add PostgreSQL Database

1. In Render Dashboard, click **"New +"** → **"PostgreSQL"**
2. Configure database:
   - **Name**: `trekkr-db` (or your preferred name)
   - **Database**: `trekkr`
   - **User**: `trekkr_user` (auto-generated)
   - **Region**: Choose closest to your users
   - **PostgreSQL Version**: 16 (matches local development)
   - **Plan**: Free tier for testing, or paid for production

3. Click **"Create Database"**

### PostGIS Extension

Render's PostgreSQL supports PostGIS. After the database is created:

**Via Render's PSQL Console:**
1. Click on your database in Render Dashboard
2. Go to "Shell" tab
3. Run:
```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

**Via External Tool (psql, pgAdmin, etc.):**
```bash
# Get connection string from Render dashboard (External Database URL)
psql <EXTERNAL_DATABASE_URL> -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

### Database URL Format

Render provides connection strings in both formats:
- **Internal Database URL**: For connecting from Render services (faster, free bandwidth)
- **External Database URL**: For external connections

Both use the format:
```
postgresql://user:password@host:port/database
```

**Important:** The backend expects `postgresql+psycopg2://...` format. See [Code Changes](#5-code-changes-required) for the fix.

---

## 4. Environment Variables

### Required Environment Variables

Set these in Render's Environment section for the web service:

| Variable | Value | Notes |
|----------|-------|-------|
| `ENV` | `production` | Enables strict validation |
| `SECRET_KEY` | `<generate-32+-char-secret>` | See generation command below |
| `DATABASE_URL` | (from database service) | Use Internal Database URL |
| `SENDGRID_API_KEY` | `SG.xxx...` | New API key from SendGrid |
| `SENDGRID_FROM_EMAIL` | `noreply@yourdomain.com` | Must be verified in SendGrid |
| `FRONTEND_URL` | `https://your-frontend.com` | Your production frontend URL |
| `CORS_ORIGINS` | `https://your-frontend.com` | Comma-separated if multiple |
| `PORT` | `10000` | Render's default port (auto-injected) |
| `PYTHON_VERSION` | `3.11.0` | Specify Python version |

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

### 5.1 Create requirements.txt (if not exists)

Ensure `backend/requirements.txt` includes all dependencies:

```txt
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.36
psycopg2-binary==2.9.10
pydantic==2.10.3
pydantic-settings==2.6.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.20
h3==4.1.2
slowapi==0.1.9
sendgrid==6.11.0
alembic==1.14.0
geoalchemy2==0.15.2
shapely==2.0.6
requests==2.32.3
```

### 5.2 Create render.yaml (Infrastructure as Code - Optional)

Create `render.yaml` in project root for reproducible deployments:

```yaml
services:
  # PostgreSQL Database
  - type: pserv
    name: trekkr-db
    env: docker
    region: oregon
    plan: free
    databaseName: trekkr
    databaseUser: trekkr_user
    ipAllowList: []

  # FastAPI Backend
  - type: web
    name: trekkr-backend
    env: python
    region: oregon
    plan: free
    branch: main
    rootDir: backend
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /api/health
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: trekkr-db
          property: connectionString
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: ENV
        value: production
      - key: SECRET_KEY
        generateValue: true
      - key: SENDGRID_API_KEY
        sync: false
      - key: SENDGRID_FROM_EMAIL
        sync: false
      - key: FRONTEND_URL
        sync: false
      - key: CORS_ORIGINS
        sync: false
```

### 5.3 Update Database URL Handling

Render provides `DATABASE_URL` without the `+psycopg2` driver suffix. Update `backend/database.py` to handle this:

**Current code (line 6):**
```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./trekkr.db")
```

**Change to:**
```python
def get_database_url() -> str:
    """Get database URL, ensuring correct driver for PostgreSQL."""
    url = os.getenv("DATABASE_URL", "sqlite:///./trekkr.db")

    # Render provides postgresql:// but SQLAlchemy needs postgresql+psycopg2://
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
Run this once after deploying to Render.
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

### 5.5 Create Build Script (Optional)

Create `backend/build.sh` for custom build steps:

```bash
#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Run database migrations (if using Alembic)
# alembic upgrade head
```

Make it executable:
```bash
chmod +x backend/build.sh
```

---

## 6. Deployment Configuration

### Option A: Deploy from GitHub (Recommended)

1. In Render Dashboard, click **"New +"** → **"Web Service"**
2. Connect your GitHub repository
3. Configure the service:
   - **Name**: `trekkr-backend`
   - **Region**: Choose closest to your users (same as database)
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt` (or use `build.sh`)
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free tier for testing, or paid for production

4. Click **"Advanced"** to configure:
   - **Auto-Deploy**: Yes (deploys on git push)
   - **Health Check Path**: `/api/health`

5. Add environment variables (see Section 4)

6. Click **"Create Web Service"**

### Option B: Deploy via render.yaml

1. Push `render.yaml` to your repository root
2. In Render Dashboard, click **"New +"** → **"Blueprint"**
3. Select your repository
4. Render will auto-detect `render.yaml` and create all services
5. Add secret environment variables manually (SENDGRID_API_KEY, etc.)

### Option C: Deploy via Render CLI (Advanced)

```bash
# Install Render CLI
brew install render  # macOS
# or download from https://render.com/docs/cli

# Login
render login

# Deploy
cd backend
render deploy
```

### Configure Service Settings

In Render dashboard for the web service:

1. **Settings** → **Environment**:
   - Add all environment variables from Section 4
   - Link `DATABASE_URL` by selecting "From Database" and choosing your Render PostgreSQL service

2. **Settings** → **Health & Alerts**:
   - Health Check Path: `/api/health`
   - Expected Status Code: `200`

3. **Settings** → **Disk**:
   - Not needed for this application (stateless)

---

## 7. Database Initialization

After the first deployment, initialize the database with seed data.

### Option A: Render Shell (Recommended)

1. Go to your web service in Render Dashboard
2. Click **"Shell"** tab in the top menu
3. Run:

```bash
python scripts/init_production_db.py
```

### Option B: Manual Database Connection

1. Get the **External Database URL** from your database service in Render
2. Connect using psql or your preferred client
3. Run the SQL files manually:

```bash
# Connect to database
psql <EXTERNAL_DATABASE_URL>

# In psql, run:
CREATE EXTENSION IF NOT EXISTS postgis;

# Then run seed SQL files (you'll need to copy/paste content)
```

### Option C: Add to Build Command (One-Time)

**Warning:** Only use this approach once, then remove it to avoid re-seeding on every deploy.

In Render web service settings:
- **Build Command**: `pip install -r requirements.txt && python scripts/init_production_db.py`

After successful first deploy, change back to:
- **Build Command**: `pip install -r requirements.txt`

### Manual SQL Initialization (Alternative)

If the script approach doesn't work, run these SQL files manually via Render's database shell:

1. `docker-init/00_extensions.sql` - PostGIS extension
2. `docker-init/01_schema.sql` - Table creation (optional if using SQLAlchemy)
3. `docker-init/02_seed_countries.sql` - 250 countries
4. `docker-init/03_seed_states.sql` - 5,096 states/provinces

---

## 8. Verification Checklist

### Pre-Deployment

- [ ] Generated new SendGrid API key for production
- [ ] Updated `backend/database.py` for Render's DATABASE_URL format
- [ ] Created `backend/scripts/init_production_db.py`
- [ ] Created `render.yaml` (optional but recommended)
- [ ] Committed and pushed all changes

### Render Configuration

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
  - [ ] `PYTHON_VERSION=3.11.0`
- [ ] Web service deployed successfully
- [ ] Health check configured and passing

### Post-Deployment Verification

- [ ] Health check passes: `GET https://your-backend.onrender.com/api/health`
- [ ] Database initialized with seed data (250 countries, 5,096 states)
- [ ] User registration works: `POST /api/auth/register`
- [ ] Login works: `POST /api/auth/login`
- [ ] Location ingestion works: `POST /api/v1/location/ingest`
- [ ] Password reset email sends successfully

### API Endpoint Tests

```bash
# Set your Render backend URL
export API_URL="https://your-backend.onrender.com"

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
| `backend/database.py` | **MODIFY** | Handle Render's DATABASE_URL format |
| `backend/scripts/init_production_db.py` | **CREATE** | Database initialization script |
| `render.yaml` | **CREATE** (optional) | Infrastructure as code configuration |
| `backend/build.sh` | **CREATE** (optional) | Custom build script |

---

## Troubleshooting

### "Connection refused" to database
- Ensure DATABASE_URL is set correctly (use Internal Database URL from Render)
- Check if the database service is running
- Verify the database and web service are in the same region (free tier restriction)

### "PostGIS extension not found"
- Run `CREATE EXTENSION IF NOT EXISTS postgis;` manually in Render's database shell
- Render's PostgreSQL supports PostGIS but extension must be enabled

### "SECRET_KEY validation failed"
- Ensure SECRET_KEY is at least 32 characters
- Check there are no extra spaces or quotes in environment variable

### Rate limiting returns 500 errors
- Known issue: Rate limiter uses IP fallback for auth endpoints
- See `docs/plans/RATE_LIMITING_FIX.md` for fix details

### CORS errors from frontend
- Verify CORS_ORIGINS matches your frontend URL exactly
- Include protocol (https://) and no trailing slash

### Build failures
- Check Render build logs in the "Events" tab
- Ensure all dependencies in requirements.txt are compatible with Python 3.11
- Verify `psycopg2-binary` is in requirements (not just `psycopg2`)

### Service won't start / Health check failing
- Check logs in Render dashboard "Logs" tab
- Verify `PORT` environment variable is being used correctly
- Ensure database migrations have run successfully
- Test health endpoint locally first

### Free tier limitations
- Free web services spin down after 15 minutes of inactivity (first request after will be slow)
- Free PostgreSQL databases have 1GB storage limit
- Free tier services in different regions cannot connect

---

## Cost Estimate

Render pricing (as of 2025):

### Free Tier
- **Web Services**:
  - 750 hours/month free (spins down after 15 min inactivity)
  - 0.1 CPU, 512MB RAM
  - Perfect for development/testing

- **PostgreSQL**:
  - Free tier available
  - 1GB storage
  - Expires after 90 days (must upgrade or recreate)

### Paid Plans

**Starter Plan** ($7/month per service):
- Always-on (no spin down)
- 0.5 CPU, 512MB RAM
- Good for small production apps

**Standard Plan** ($25/month per service):
- 1 CPU, 2GB RAM
- Better for production

**PostgreSQL** ($7/month):
- 1GB storage
- No expiration
- Additional storage: $0.25/GB/month

### Estimated Monthly Cost for Production
- Web Service (Starter): $7
- PostgreSQL (Starter): $7
- **Total**: ~$14/month

---

## Render vs Railway Comparison

| Feature | Render | Railway | Notes |
|---------|--------|---------|-------|
| **Free Tier** | 750 hrs/month, spins down | $5/month, 500 hours | Render more generous for dev |
| **Database** | Free tier available | Pay per use | Render free DB expires after 90 days |
| **Deploy Speed** | Medium | Fast | Railway generally faster builds |
| **Custom Domains** | Free on all tiers | Free on all tiers | Tie |
| **Health Checks** | Built-in | Built-in | Tie |
| **Shell Access** | Yes | Yes | Tie |
| **Logs** | 7 days free tier | Real-time, limited history | Railway better log retention |
| **Auto-deploy** | Yes (GitHub) | Yes (GitHub) | Tie |
| **Infrastructure as Code** | `render.yaml` | `railway.json` | Both supported |

**Why Render?**
- More generous free tier for testing
- Easier database management
- Better documentation
- Simpler pricing model
- Good community support

---

## Next Steps After Deployment

1. **Custom Domain Setup** (optional):
   - Go to web service → Settings → Custom Domain
   - Add your domain and configure DNS

2. **Monitoring & Alerts**:
   - Configure notification emails in Render dashboard
   - Set up health check alerts
   - Consider integrating with monitoring service (Sentry, Datadog, etc.)

3. **CI/CD Enhancements**:
   - Add GitHub Actions for automated testing before deploy
   - Set up preview environments for pull requests
   - Configure deploy notifications (Slack, Discord, etc.)

4. **Performance Optimization**:
   - Consider Redis for rate limiting (if scaling to multiple instances)
   - Enable connection pooling in SQLAlchemy
   - Set up CDN for static assets (if any)

5. **Security Hardening**:
   - Enable Render's DDoS protection
   - Set up rate limiting at the service level
   - Regular security audits and dependency updates

6. **Database Backups**:
   - Configure automated backups in Render database settings
   - Test restore procedure
   - Consider point-in-time recovery for production

7. **Frontend Deployment**:
   - Deploy React Native web build to Render Static Site or Vercel
   - Connect to this backend via FRONTEND_URL and CORS_ORIGINS

---

## Additional Resources

- [Render Documentation](https://render.com/docs)
- [Deploying FastAPI on Render](https://render.com/docs/deploy-fastapi)
- [Render PostgreSQL Docs](https://render.com/docs/databases)
- [Render Environment Variables](https://render.com/docs/environment-variables)
- [Render Shell Access](https://render.com/docs/shell-access)
