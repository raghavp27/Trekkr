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
The project ships with a PostGIS-enabled database in `docker-compose.yml`. This will create a Postgres container named `app-postgres` listening on host port `5433`.

### Exact commands based on this repo’s config
- Start DB: `docker compose up -d db`
- (Optional) set/override DB URL: `export DATABASE_URL=postgresql+psycopg2://appuser:apppass@localhost:5433/appdb`
- Create tables: `alembic upgrade head`
- List tables: `docker compose exec db psql -U appuser -d appdb -c "\dt"`
- Inspect table: `docker compose exec db psql -U appuser -d appdb -c "\d users"` (replace `users` as needed; quit pager with `q`, exit psql with `\q`)
- Stop DB: `docker compose down`

## Verify Installation
Once the API server is running, you can:
- Visit `http://127.0.0.1:8000` - Root endpoint
- Visit `http://127.0.0.1:8000/docs` - Interactive API documentation (Swagger UI)
- Visit `http://127.0.0.1:8000/api/health` - Health check endpoint
