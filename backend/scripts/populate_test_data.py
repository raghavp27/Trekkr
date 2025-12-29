#!/usr/bin/env python3
"""Populate test database with visit data for performance testing.

This script creates a test user (if needed) and populates it with 1000
UserCellVisit records to test the performance of the overview endpoint.

Usage:
    cd backend
    python scripts/populate_test_data.py

Environment Variables:
    DATABASE_URL: Connection string for the database (defaults to development DB)
"""

import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path so we can import from backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import SessionLocal
from models.user import User
from models.visits import UserCellVisit
from models.geo import H3Cell


def create_test_user(db) -> User:
    """Create or retrieve the test user."""
    test_email = "test@test.com"

    # Check if user already exists
    user = db.query(User).filter(User.email == test_email).first()

    if user:
        print(f"Found existing test user: {user.username} (ID: {user.id})")
        return user

    # Create new test user
    user = User(
        username="test_perf_user",
        email=test_email,
        hashed_password="$2b$12$hashedpasswordfortesting123456",  # bcrypt hash
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    print(f"Created new test user: {user.username} (ID: {user.id})")
    return user


def cleanup_existing_visits(db, user_id: int):
    """Remove existing visits for the test user."""
    deleted_count = db.query(UserCellVisit).filter(
        UserCellVisit.user_id == user_id
    ).delete()

    db.commit()

    if deleted_count > 0:
        print(f"Cleaned up {deleted_count} existing visits for user {user_id}")


def ensure_h3_cells_exist(db, h3_indices: list[str]):
    """Ensure H3Cell records exist for all indices we'll use.

    Creates placeholder cells if they don't exist in the database.
    """
    existing_cells = db.query(H3Cell.h3_index).filter(
        H3Cell.h3_index.in_(h3_indices)
    ).all()
    existing_indices = {cell.h3_index for cell in existing_cells}

    missing_indices = set(h3_indices) - existing_indices

    if missing_indices:
        print(f"Creating {len(missing_indices)} missing H3Cell records...")

        # Create H3Cell records for missing indices
        for h3_index in missing_indices:
            # Create cell with minimal required fields
            cell = H3Cell(
                h3_index=h3_index,
                res=8,
                country_id=None,
                state_id=None,
                centroid=None,  # Would be computed in real system
            )
            db.add(cell)

        db.commit()
        print(f"Created {len(missing_indices)} H3Cell records")


def populate_visits(db, user_id: int, count: int = 1000):
    """Create visit records for the test user.

    Args:
        db: Database session
        user_id: ID of the test user
        count: Number of visits to create (default: 1000)
    """
    print(f"Populating {count} visits for user {user_id}...")

    # Generate unique H3 indices
    # Using format: 88283081{i:07x} where i is 0-999
    # This creates valid 15-character hex strings
    h3_indices = [f"88283081{i:07x}" for i in range(count)]

    # Ensure H3Cell records exist
    ensure_h3_cells_exist(db, h3_indices)

    # Create visits with staggered timestamps
    visits = []
    base_time = datetime.utcnow()

    for i, h3_index in enumerate(h3_indices):
        # Spread visits over the past 1000 days
        first_visited = base_time - timedelta(days=1000-i)
        last_visited = base_time - timedelta(days=500-i) if i < 500 else first_visited

        visit = UserCellVisit(
            user_id=user_id,
            h3_index=h3_index,
            res=8,
            first_visited_at=first_visited,
            last_visited_at=last_visited,
            visit_count=1 if first_visited == last_visited else 2,
        )
        visits.append(visit)

        # Batch insert every 100 records to avoid memory issues
        if len(visits) >= 100:
            db.bulk_save_objects(visits)
            db.commit()
            print(f"  Inserted {i+1}/{count} visits...")
            visits = []

    # Insert remaining visits
    if visits:
        db.bulk_save_objects(visits)
        db.commit()

    print(f"Successfully populated {count} visits")


def verify_data(db, user_id: int):
    """Verify the populated data."""
    visit_count = db.query(UserCellVisit).filter(
        UserCellVisit.user_id == user_id
    ).count()

    print(f"\nVerification:")
    print(f"  Total visits: {visit_count}")

    # Check resolution distribution
    res8_count = db.query(UserCellVisit).filter(
        UserCellVisit.user_id == user_id,
        UserCellVisit.res == 8
    ).count()

    print(f"  Resolution 8 visits: {res8_count}")

    # Get date range
    result = db.execute(text("""
        SELECT
            MIN(first_visited_at) as earliest,
            MAX(last_visited_at) as latest
        FROM user_cell_visits
        WHERE user_id = :user_id
    """), {"user_id": user_id}).fetchone()

    if result.earliest and result.latest:
        print(f"  Date range: {result.earliest} to {result.latest}")

    return visit_count == 1000


def main():
    """Main entry point."""
    print("=" * 60)
    print("Performance Test Data Population Script")
    print("=" * 60)
    print()

    # Check database URL
    db_url = os.getenv("DATABASE_URL", "Not set - will use default")
    print(f"Database URL: {db_url}")
    print()

    # Create database session
    db = SessionLocal()

    try:
        # Step 1: Create or get test user
        user = create_test_user(db)

        # Step 2: Clean up existing visits
        cleanup_existing_visits(db, user.id)

        # Step 3: Populate visits
        populate_visits(db, user.id, count=1000)

        # Step 4: Verify data
        success = verify_data(db, user.id)

        print()
        if success:
            print("SUCCESS: Test data populated successfully!")
            print()
            print("Next steps:")
            print("  1. Run: python scripts/measure_performance.py")
            print("  2. Or manually test: curl http://localhost:8000/api/v1/stats/overview")
            return 0
        else:
            print("ERROR: Data verification failed")
            return 1

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
