from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from config import validate_config
from database import init_db
from routers import auth, health, location, map, stats, achievements
from routers.location import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup: Initialize the database
    validate_config()
    init_db()
    yield
    # Shutdown: Cleanup if needed


app = FastAPI(
    title="Trekkr API",
    description="Backend API for Trekkr",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware configuration
# In production, set CORS_ORIGINS environment variable to comma-separated list of allowed origins
# Example: CORS_ORIGINS="https://app.trekkr.com,https://www.trekkr.com"
import os

CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
)
origins = [origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(location.router, prefix="/api/v1/location", tags=["location"])
app.include_router(map.router, prefix="/api/v1/map", tags=["map"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["stats"])
app.include_router(achievements.router, prefix="/api/v1/achievements", tags=["achievements"])


@app.get("/")
async def root():
    return {"message": "Welcome to Trekkr API"}
