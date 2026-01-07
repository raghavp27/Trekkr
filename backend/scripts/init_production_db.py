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
