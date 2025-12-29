# Achievements System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a gamification system with 17 achievements that unlock automatically when users meet exploration criteria.

**Architecture:** Achievement criteria are stored as flexible JSON in the `achievements` table. The `AchievementService` evaluates user stats against criteria after each location ingestion, unlocking newly earned achievements. Results are returned in the location ingest response for immediate client feedback.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL/PostGIS, Pydantic v2, pytest

---

## Task 1: Migration - Add Continent Column to Countries

**Files:**
- Create: `backend/alembic/versions/20251229_0008_add_continent_to_countries.py`

**Step 1: Create the migration file**

```python
"""Add continent column to regions_country

Revision ID: 20251229_0008
Revises: 20251229_0007
Create Date: 2024-12-29

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251229_0008'
down_revision = '20251229_0007'
branch_labels = None
depends_on = None


# UN geoscheme continent assignments by ISO2 code
CONTINENT_MAPPING = {
    'Africa': [
        'DZ', 'AO', 'BJ', 'BW', 'BF', 'BI', 'CV', 'CM', 'CF', 'TD', 'KM', 'CG', 'CD', 'CI', 'DJ',
        'EG', 'GQ', 'ER', 'SZ', 'ET', 'GA', 'GM', 'GH', 'GN', 'GW', 'KE', 'LS', 'LR', 'LY', 'MG',
        'MW', 'ML', 'MR', 'MU', 'YT', 'MA', 'MZ', 'NA', 'NE', 'NG', 'RE', 'RW', 'ST', 'SN', 'SC',
        'SL', 'SO', 'ZA', 'SS', 'SD', 'TZ', 'TG', 'TN', 'UG', 'EH', 'ZM', 'ZW'
    ],
    'Antarctica': ['AQ'],
    'Asia': [
        'AF', 'AM', 'AZ', 'BH', 'BD', 'BT', 'BN', 'KH', 'CN', 'CY', 'GE', 'HK', 'IN', 'ID', 'IR',
        'IQ', 'IL', 'JP', 'JO', 'KZ', 'KW', 'KG', 'LA', 'LB', 'MO', 'MY', 'MV', 'MN', 'MM', 'NP',
        'KP', 'OM', 'PK', 'PS', 'PH', 'QA', 'SA', 'SG', 'KR', 'LK', 'SY', 'TW', 'TJ', 'TH', 'TL',
        'TR', 'TM', 'AE', 'UZ', 'VN', 'YE'
    ],
    'Europe': [
        'AL', 'AD', 'AT', 'BY', 'BE', 'BA', 'BG', 'HR', 'CZ', 'DK', 'EE', 'FO', 'FI', 'FR', 'DE',
        'GI', 'GR', 'GL', 'GG', 'HU', 'IS', 'IE', 'IM', 'IT', 'JE', 'XK', 'LV', 'LI', 'LT', 'LU',
        'MT', 'MD', 'MC', 'ME', 'NL', 'MK', 'NO', 'PL', 'PT', 'RO', 'RU', 'SM', 'RS', 'SK', 'SI',
        'ES', 'SJ', 'SE', 'CH', 'UA', 'GB', 'VA'
    ],
    'North America': [
        'AI', 'AG', 'AW', 'BS', 'BB', 'BZ', 'BM', 'BQ', 'VG', 'CA', 'KY', 'CR', 'CU', 'CW', 'DM',
        'DO', 'SV', 'GD', 'GP', 'GT', 'HT', 'HN', 'JM', 'MQ', 'MX', 'MS', 'NI', 'PA', 'PR', 'BL',
        'KN', 'LC', 'MF', 'PM', 'VC', 'SX', 'TT', 'TC', 'US', 'VI'
    ],
    'Oceania': [
        'AS', 'AU', 'CK', 'FJ', 'PF', 'GU', 'KI', 'MH', 'FM', 'NR', 'NC', 'NZ', 'NU', 'NF', 'MP',
        'PW', 'PG', 'PN', 'WS', 'SB', 'TK', 'TO', 'TV', 'UM', 'VU', 'WF'
    ],
    'South America': [
        'AR', 'BO', 'BR', 'CL', 'CO', 'EC', 'FK', 'GF', 'GY', 'PY', 'PE', 'SR', 'UY', 'VE'
    ],
}


def upgrade():
    """Add continent column and populate based on UN geoscheme."""
    # Add nullable column first
    op.add_column('regions_country', sa.Column('continent', sa.String(32), nullable=True))

    # Populate continent values
    for continent, iso2_codes in CONTINENT_MAPPING.items():
        if iso2_codes:
            placeholders = ', '.join(f"'{code}'" for code in iso2_codes)
            op.execute(f"""
                UPDATE regions_country
                SET continent = '{continent}'
                WHERE iso2 IN ({placeholders})
            """)

    # Set any remaining countries to 'Unknown' (shouldn't happen with complete mapping)
    op.execute("""
        UPDATE regions_country
        SET continent = 'Unknown'
        WHERE continent IS NULL
    """)

    # Make column non-nullable
    op.alter_column('regions_country', 'continent', nullable=False)


def downgrade():
    """Remove continent column."""
    op.drop_column('regions_country', 'continent')
```

**Step 2: Run the migration**

Run: `cd backend && alembic upgrade head`
Expected: Migration applies successfully

**Step 3: Verify migration**

Run: `cd backend && python -c "from sqlalchemy import create_engine, text; e = create_engine('postgresql+psycopg2://appuser:apppass@localhost:5433/appdb'); r = e.execute(text('SELECT continent, COUNT(*) FROM regions_country GROUP BY continent')); print(list(r))"`
Expected: Lists continents with country counts

**Step 4: Run existing tests to verify no regression**

Run: `cd backend && $env:TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test"; python -m pytest tests/ -v --tb=short`
Expected: All existing tests pass

**Step 5: Commit**

```bash
cd backend && git add alembic/versions/20251229_0008_add_continent_to_countries.py && git commit -m "migration: add continent column to regions_country"
```

---

## Task 2: Update CountryRegion Model

**Files:**
- Modify: `backend/models/geo.py:36-68` (CountryRegion class)

**Step 1: Add continent column to model**

In `backend/models/geo.py`, add after line 58 (`land_cells_total_resolution8`):

```python
    continent = Column(String(32), nullable=False)
```

**Step 2: Verify model matches database**

Run: `cd backend && python -c "from models.geo import CountryRegion; print(CountryRegion.__table__.columns.keys())"`
Expected: Output includes 'continent'

**Step 3: Commit**

```bash
cd backend && git add models/geo.py && git commit -m "model: add continent column to CountryRegion"
```

---

## Task 3: Migration - Seed Achievements

**Files:**
- Create: `backend/alembic/versions/20251229_0009_seed_achievements.py`

**Step 1: Create the migration file**

```python
"""Seed initial achievements

Revision ID: 20251229_0009
Revises: 20251229_0008
Create Date: 2024-12-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String, Integer, JSON
import json


# revision identifiers, used by Alembic.
revision = '20251229_0009'
down_revision = '20251229_0008'
branch_labels = None
depends_on = None


# Achievement definitions
ACHIEVEMENTS = [
    # Volume milestones
    {
        "code": "first_steps",
        "name": "First Steps",
        "description": "Visit your first location",
        "criteria_json": {"type": "cells_total", "threshold": 1},
    },
    {
        "code": "explorer",
        "name": "Explorer",
        "description": "Visit 100 unique cells",
        "criteria_json": {"type": "cells_total", "threshold": 100},
    },
    {
        "code": "wanderer",
        "name": "Wanderer",
        "description": "Visit 500 unique cells",
        "criteria_json": {"type": "cells_total", "threshold": 500},
    },
    # Geographic breadth
    {
        "code": "globetrotter",
        "name": "Globetrotter",
        "description": "Visit 10 countries",
        "criteria_json": {"type": "countries", "threshold": 10},
    },
    {
        "code": "country_collector",
        "name": "Country Collector",
        "description": "Visit 25 countries",
        "criteria_json": {"type": "countries", "threshold": 25},
    },
    {
        "code": "state_hopper",
        "name": "State Hopper",
        "description": "Visit 5 regions in one country",
        "criteria_json": {"type": "regions_in_country", "threshold": 5},
    },
    {
        "code": "regional_master",
        "name": "Regional Master",
        "description": "Visit 50 regions total",
        "criteria_json": {"type": "regions", "threshold": 50},
    },
    {
        "code": "hemisphere_hopper",
        "name": "Hemisphere Hopper",
        "description": "Visit both northern and southern hemispheres",
        "criteria_json": {"type": "hemispheres", "count": 2},
    },
    {
        "code": "frequent_traveler",
        "name": "Frequent Traveler",
        "description": "Visit locations on 30 different days",
        "criteria_json": {"type": "unique_days", "threshold": 30},
    },
    # Continent achievements
    {
        "code": "continental",
        "name": "Continental",
        "description": "Visit 3 continents",
        "criteria_json": {"type": "continents", "threshold": 3},
    },
    {
        "code": "intercontinental",
        "name": "Intercontinental",
        "description": "Visit 5 continents",
        "criteria_json": {"type": "continents", "threshold": 5},
    },
    {
        "code": "world_explorer",
        "name": "World Explorer",
        "description": "Visit all 7 continents",
        "criteria_json": {"type": "continents", "threshold": 7},
    },
    # Coverage depth
    {
        "code": "country_explorer",
        "name": "Country Explorer",
        "description": "Achieve 10% coverage of any country",
        "criteria_json": {"type": "country_coverage_pct", "threshold": 0.10},
    },
    {
        "code": "country_master",
        "name": "Country Master",
        "description": "Achieve 25% coverage of any country",
        "criteria_json": {"type": "country_coverage_pct", "threshold": 0.25},
    },
    {
        "code": "country_conqueror",
        "name": "Country Conqueror",
        "description": "Achieve 50% coverage of any country",
        "criteria_json": {"type": "country_coverage_pct", "threshold": 0.50},
    },
    {
        "code": "region_explorer",
        "name": "Region Explorer",
        "description": "Achieve 25% coverage of any state/province",
        "criteria_json": {"type": "region_coverage_pct", "threshold": 0.25},
    },
    {
        "code": "region_master",
        "name": "Region Master",
        "description": "Achieve 50% coverage of any state/province",
        "criteria_json": {"type": "region_coverage_pct", "threshold": 0.50},
    },
]


def upgrade():
    """Insert initial achievements."""
    achievements_table = table(
        'achievements',
        column('code', String),
        column('name', String),
        column('description', String),
        column('criteria_json', JSON),
    )

    op.bulk_insert(achievements_table, ACHIEVEMENTS)


def downgrade():
    """Remove seeded achievements."""
    codes = [a['code'] for a in ACHIEVEMENTS]
    placeholders = ', '.join(f"'{code}'" for code in codes)
    op.execute(f"DELETE FROM achievements WHERE code IN ({placeholders})")
```

**Step 2: Run the migration**

Run: `cd backend && alembic upgrade head`
Expected: Migration applies successfully, 17 achievements inserted

**Step 3: Verify achievements seeded**

Run: `cd backend && python -c "from sqlalchemy import create_engine, text; e = create_engine('postgresql+psycopg2://appuser:apppass@localhost:5433/appdb'); r = e.execute(text('SELECT code, name FROM achievements ORDER BY id')); print(list(r))"`
Expected: Lists all 17 achievements

**Step 4: Run existing tests**

Run: `cd backend && $env:TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test"; python -m pytest tests/ -v --tb=short`
Expected: All existing tests pass

**Step 5: Commit**

```bash
cd backend && git add alembic/versions/20251229_0009_seed_achievements.py && git commit -m "migration: seed 17 initial achievements"
```

---

## Task 4: Create Achievement Schemas

**Files:**
- Create: `backend/schemas/achievements.py`

**Step 1: Write the schemas file**

```python
"""Pydantic schemas for achievements endpoints."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class AchievementUnlockedSchema(BaseModel):
    """Achievement that was just unlocked (returned in location ingest response)."""

    code: str
    name: str
    description: Optional[str] = None


class AchievementSchema(BaseModel):
    """Achievement with user's unlock status."""

    code: str
    name: str
    description: Optional[str] = None
    unlocked: bool
    unlocked_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AchievementsListResponse(BaseModel):
    """Response for GET /achievements endpoint."""

    achievements: List[AchievementSchema]
    total: int
    unlocked_count: int


class UnlockedAchievementsResponse(BaseModel):
    """Response for GET /achievements/unlocked endpoint."""

    achievements: List[AchievementSchema]
    total: int
```

**Step 2: Verify import works**

Run: `cd backend && python -c "from schemas.achievements import AchievementsListResponse; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
cd backend && git add schemas/achievements.py && git commit -m "schemas: add achievement pydantic models"
```

---

## Task 5: Write Achievement Service Tests (TDD - Red Phase)

**Files:**
- Create: `backend/tests/test_achievement_service.py`

**Step 1: Write the failing tests**

```python
"""Tests for AchievementService.

Tests achievement evaluation logic and unlock functionality.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

from models.achievements import Achievement, UserAchievement
from models.user import User
from services.achievement_service import AchievementService
from tests.fixtures.test_data import SAN_FRANCISCO, SYDNEY


@pytest.fixture
def seed_achievements(db_session: Session) -> list[Achievement]:
    """Seed test achievements into the database."""
    achievements_data = [
        {"code": "first_steps", "name": "First Steps", "description": "Visit your first location",
         "criteria_json": {"type": "cells_total", "threshold": 1}},
        {"code": "explorer", "name": "Explorer", "description": "Visit 100 unique cells",
         "criteria_json": {"type": "cells_total", "threshold": 100}},
        {"code": "globetrotter", "name": "Globetrotter", "description": "Visit 10 countries",
         "criteria_json": {"type": "countries", "threshold": 10}},
        {"code": "continental", "name": "Continental", "description": "Visit 3 continents",
         "criteria_json": {"type": "continents", "threshold": 3}},
        {"code": "hemisphere_hopper", "name": "Hemisphere Hopper", "description": "Visit both hemispheres",
         "criteria_json": {"type": "hemispheres", "count": 2}},
        {"code": "state_hopper", "name": "State Hopper", "description": "Visit 5 regions in one country",
         "criteria_json": {"type": "regions_in_country", "threshold": 5}},
        {"code": "regional_master", "name": "Regional Master", "description": "Visit 50 regions",
         "criteria_json": {"type": "regions", "threshold": 50}},
        {"code": "country_explorer", "name": "Country Explorer", "description": "10% coverage of any country",
         "criteria_json": {"type": "country_coverage_pct", "threshold": 0.10}},
        {"code": "region_explorer", "name": "Region Explorer", "description": "25% coverage of any region",
         "criteria_json": {"type": "region_coverage_pct", "threshold": 0.25}},
        {"code": "frequent_traveler", "name": "Frequent Traveler", "description": "Visit on 30 unique days",
         "criteria_json": {"type": "unique_days", "threshold": 30}},
    ]

    achievements = []
    for data in achievements_data:
        achievement = Achievement(**data)
        db_session.add(achievement)
        achievements.append(achievement)

    db_session.commit()
    for a in achievements:
        db_session.refresh(a)

    return achievements


@pytest.fixture
def test_country_with_continent(db_session: Session):
    """Create USA with continent for testing."""
    db_session.execute(text("""
        INSERT INTO regions_country (name, iso2, iso3, continent, geom, land_cells_total_resolution8, created_at, updated_at)
        VALUES (
            'United States', 'US', 'USA', 'North America',
            ST_GeomFromText('POLYGON((-125 30, -125 50, -115 50, -115 30, -125 30))', 4326),
            1000,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
    """))
    db_session.commit()
    result = db_session.execute(text("SELECT id FROM regions_country WHERE iso2 = 'US'")).fetchone()
    return result.id


@pytest.fixture
def test_country_australia(db_session: Session):
    """Create Australia (southern hemisphere) for testing."""
    db_session.execute(text("""
        INSERT INTO regions_country (name, iso2, iso3, continent, geom, land_cells_total_resolution8, created_at, updated_at)
        VALUES (
            'Australia', 'AU', 'AUS', 'Oceania',
            ST_GeomFromText('POLYGON((140 -40, 140 -10, 155 -10, 155 -40, 140 -40))', 4326),
            5000,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
    """))
    db_session.commit()
    result = db_session.execute(text("SELECT id FROM regions_country WHERE iso2 = 'AU'")).fetchone()
    return result.id


class TestCheckAndUnlock:
    """Test the check_and_unlock method."""

    def test_unlocks_first_steps_on_first_cell(
        self, db_session: Session, test_user: User, seed_achievements: list, test_country_with_continent: int
    ):
        """First cell visit should unlock 'first_steps' achievement."""
        # Create one cell visit for user
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, first_visited_at, last_visited_at, visit_count)
            VALUES (:h3, 8, :country_id, NOW(), NOW(), 1)
        """), {"h3": SAN_FRANCISCO["h3_res8"], "country_id": test_country_with_continent})

        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3": SAN_FRANCISCO["h3_res8"]})
        db_session.commit()

        service = AchievementService(db_session, test_user.id)
        newly_unlocked = service.check_and_unlock()

        assert len(newly_unlocked) >= 1
        codes = [a.code for a in newly_unlocked]
        assert "first_steps" in codes

    def test_returns_only_newly_unlocked(
        self, db_session: Session, test_user: User, seed_achievements: list, test_country_with_continent: int
    ):
        """Already unlocked achievements should not be returned again."""
        # Create cell visit
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, first_visited_at, last_visited_at, visit_count)
            VALUES (:h3, 8, :country_id, NOW(), NOW(), 1)
        """), {"h3": SAN_FRANCISCO["h3_res8"], "country_id": test_country_with_continent})

        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3": SAN_FRANCISCO["h3_res8"]})
        db_session.commit()

        service = AchievementService(db_session, test_user.id)

        # First call unlocks first_steps
        first_unlocked = service.check_and_unlock()
        assert any(a.code == "first_steps" for a in first_unlocked)

        # Second call should not return first_steps again
        second_unlocked = service.check_and_unlock()
        assert not any(a.code == "first_steps" for a in second_unlocked)

    def test_no_unlock_when_threshold_not_met(
        self, db_session: Session, test_user: User, seed_achievements: list
    ):
        """No achievements should unlock when user has no cells."""
        service = AchievementService(db_session, test_user.id)
        newly_unlocked = service.check_and_unlock()

        assert len(newly_unlocked) == 0


class TestEvaluateCriteria:
    """Test individual criteria evaluation."""

    def test_cells_total_criteria(
        self, db_session: Session, test_user: User, seed_achievements: list, test_country_with_continent: int
    ):
        """Test cells_total criteria type."""
        # Add exactly 100 cells
        for i in range(100):
            h3_index = f"88283082{i:07d}"  # Generate unique h3 indexes
            db_session.execute(text("""
                INSERT INTO h3_cells (h3_index, res, country_id, first_visited_at, last_visited_at, visit_count)
                VALUES (:h3, 8, :country_id, NOW(), NOW(), 1)
                ON CONFLICT (h3_index) DO NOTHING
            """), {"h3": h3_index, "country_id": test_country_with_continent})

            db_session.execute(text("""
                INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
                VALUES (:user_id, :h3, 8, NOW(), NOW(), 1)
            """), {"user_id": test_user.id, "h3": h3_index})

        db_session.commit()

        service = AchievementService(db_session, test_user.id)
        newly_unlocked = service.check_and_unlock()

        codes = [a.code for a in newly_unlocked]
        assert "first_steps" in codes  # threshold: 1
        assert "explorer" in codes     # threshold: 100

    def test_hemispheres_criteria(
        self, db_session: Session, test_user: User, seed_achievements: list,
        test_country_with_continent: int, test_country_australia: int
    ):
        """Test hemispheres criteria (N/S detection based on latitude)."""
        # Add cell in northern hemisphere (USA)
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, centroid, first_visited_at, last_visited_at, visit_count)
            VALUES (:h3, 8, :country_id, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), NOW(), NOW(), 1)
        """), {
            "h3": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_with_continent,
            "lat": SAN_FRANCISCO["latitude"],
            "lon": SAN_FRANCISCO["longitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3": SAN_FRANCISCO["h3_res8"]})

        # Add cell in southern hemisphere (Australia)
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, centroid, first_visited_at, last_visited_at, visit_count)
            VALUES (:h3, 8, :country_id, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), NOW(), NOW(), 1)
        """), {
            "h3": SYDNEY["h3_res8"],
            "country_id": test_country_australia,
            "lat": SYDNEY["latitude"],
            "lon": SYDNEY["longitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3": SYDNEY["h3_res8"]})

        db_session.commit()

        service = AchievementService(db_session, test_user.id)
        newly_unlocked = service.check_and_unlock()

        codes = [a.code for a in newly_unlocked]
        assert "hemisphere_hopper" in codes


class TestGetAllWithStatus:
    """Test the get_all_with_status method."""

    def test_returns_all_achievements_with_unlock_status(
        self, db_session: Session, test_user: User, seed_achievements: list, test_country_with_continent: int
    ):
        """Should return all achievements with correct unlock status."""
        # Create one cell to unlock first_steps
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, first_visited_at, last_visited_at, visit_count)
            VALUES (:h3, 8, :country_id, NOW(), NOW(), 1)
        """), {"h3": SAN_FRANCISCO["h3_res8"], "country_id": test_country_with_continent})

        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3": SAN_FRANCISCO["h3_res8"]})
        db_session.commit()

        service = AchievementService(db_session, test_user.id)
        service.check_and_unlock()  # Unlock first_steps

        all_achievements = service.get_all_with_status()

        assert len(all_achievements) == 10  # All seeded achievements

        first_steps = next(a for a in all_achievements if a["code"] == "first_steps")
        assert first_steps["unlocked"] is True
        assert first_steps["unlocked_at"] is not None

        explorer = next(a for a in all_achievements if a["code"] == "explorer")
        assert explorer["unlocked"] is False
        assert explorer["unlocked_at"] is None

    def test_returns_empty_for_new_user(
        self, db_session: Session, test_user: User, seed_achievements: list
    ):
        """New user should have all achievements locked."""
        service = AchievementService(db_session, test_user.id)
        all_achievements = service.get_all_with_status()

        assert all(a["unlocked"] is False for a in all_achievements)
        assert all(a["unlocked_at"] is None for a in all_achievements)
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && $env:TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test"; python -m pytest tests/test_achievement_service.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'services.achievement_service'"

**Step 3: Commit test file**

```bash
cd backend && git add tests/test_achievement_service.py && git commit -m "test: add achievement service tests (red phase)"
```

---

## Task 6: Implement AchievementService (TDD - Green Phase)

**Files:**
- Create: `backend/services/achievement_service.py`

**Step 1: Implement the service**

```python
"""Achievement service for checking and unlocking achievements."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from models.achievements import Achievement, UserAchievement


class AchievementService:
    """Service for evaluating and unlocking user achievements."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def check_and_unlock(self) -> List[Achievement]:
        """Check all achievements and unlock newly earned ones.

        Returns list of newly unlocked achievements.
        """
        # Get user stats
        stats = self._get_user_stats()

        # Get all achievements
        all_achievements = self.db.query(Achievement).all()

        # Get already unlocked achievement IDs
        unlocked_ids = set(
            row[0] for row in self.db.query(UserAchievement.achievement_id)
            .filter(UserAchievement.user_id == self.user_id)
            .all()
        )

        newly_unlocked = []

        for achievement in all_achievements:
            if achievement.id in unlocked_ids:
                continue

            if self._evaluate_criteria(achievement.criteria_json, stats):
                # Unlock the achievement
                user_achievement = UserAchievement(
                    user_id=self.user_id,
                    achievement_id=achievement.id,
                    unlocked_at=datetime.utcnow(),
                )
                self.db.add(user_achievement)
                newly_unlocked.append(achievement)

        if newly_unlocked:
            self.db.commit()

        return newly_unlocked

    def _get_user_stats(self) -> dict:
        """Gather all stats needed for achievement evaluation."""
        stats = {}

        # Total cells (res8)
        result = self.db.execute(text("""
            SELECT COUNT(*) as total
            FROM user_cell_visits
            WHERE user_id = :user_id AND res = 8
        """), {"user_id": self.user_id}).fetchone()
        stats["cells_total"] = result.total if result else 0

        # Distinct countries
        result = self.db.execute(text("""
            SELECT COUNT(DISTINCT hc.country_id) as total
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            WHERE ucv.user_id = :user_id AND ucv.res = 8 AND hc.country_id IS NOT NULL
        """), {"user_id": self.user_id}).fetchone()
        stats["countries"] = result.total if result else 0

        # Distinct regions
        result = self.db.execute(text("""
            SELECT COUNT(DISTINCT hc.state_id) as total
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            WHERE ucv.user_id = :user_id AND ucv.res = 8 AND hc.state_id IS NOT NULL
        """), {"user_id": self.user_id}).fetchone()
        stats["regions"] = result.total if result else 0

        # Distinct continents
        result = self.db.execute(text("""
            SELECT COUNT(DISTINCT rc.continent) as total
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            JOIN regions_country rc ON hc.country_id = rc.id
            WHERE ucv.user_id = :user_id AND ucv.res = 8
        """), {"user_id": self.user_id}).fetchone()
        stats["continents"] = result.total if result else 0

        # Max regions in single country
        result = self.db.execute(text("""
            SELECT MAX(region_count) as max_regions
            FROM (
                SELECT hc.country_id, COUNT(DISTINCT hc.state_id) as region_count
                FROM user_cell_visits ucv
                JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                WHERE ucv.user_id = :user_id AND ucv.res = 8
                  AND hc.country_id IS NOT NULL AND hc.state_id IS NOT NULL
                GROUP BY hc.country_id
            ) sub
        """), {"user_id": self.user_id}).fetchone()
        stats["max_regions_in_country"] = result.max_regions if result and result.max_regions else 0

        # Hemispheres visited (based on cell centroid latitude)
        result = self.db.execute(text("""
            SELECT
                CASE WHEN EXISTS (
                    SELECT 1 FROM user_cell_visits ucv
                    JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                    WHERE ucv.user_id = :user_id AND ucv.res = 8
                      AND ST_Y(hc.centroid) >= 0
                ) THEN 1 ELSE 0 END as northern,
                CASE WHEN EXISTS (
                    SELECT 1 FROM user_cell_visits ucv
                    JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                    WHERE ucv.user_id = :user_id AND ucv.res = 8
                      AND ST_Y(hc.centroid) < 0
                ) THEN 1 ELSE 0 END as southern
        """), {"user_id": self.user_id}).fetchone()
        stats["hemispheres"] = (result.northern if result else 0) + (result.southern if result else 0)

        # Unique days visited
        result = self.db.execute(text("""
            SELECT COUNT(DISTINCT DATE(first_visited_at)) as unique_days
            FROM user_cell_visits
            WHERE user_id = :user_id AND res = 8
        """), {"user_id": self.user_id}).fetchone()
        stats["unique_days"] = result.unique_days if result else 0

        # Max country coverage percentage
        result = self.db.execute(text("""
            SELECT MAX(coverage) as max_coverage
            FROM (
                SELECT
                    hc.country_id,
                    COUNT(DISTINCT ucv.h3_index)::float / NULLIF(rc.land_cells_total_resolution8, 0) as coverage
                FROM user_cell_visits ucv
                JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                JOIN regions_country rc ON hc.country_id = rc.id
                WHERE ucv.user_id = :user_id AND ucv.res = 8
                  AND hc.country_id IS NOT NULL
                  AND rc.land_cells_total_resolution8 > 0
                GROUP BY hc.country_id, rc.land_cells_total_resolution8
            ) sub
        """), {"user_id": self.user_id}).fetchone()
        stats["max_country_coverage"] = result.max_coverage if result and result.max_coverage else 0.0

        # Max region coverage percentage
        result = self.db.execute(text("""
            SELECT MAX(coverage) as max_coverage
            FROM (
                SELECT
                    hc.state_id,
                    COUNT(DISTINCT ucv.h3_index)::float / NULLIF(rs.land_cells_total_resolution8, 0) as coverage
                FROM user_cell_visits ucv
                JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                JOIN regions_state rs ON hc.state_id = rs.id
                WHERE ucv.user_id = :user_id AND ucv.res = 8
                  AND hc.state_id IS NOT NULL
                  AND rs.land_cells_total_resolution8 > 0
                GROUP BY hc.state_id, rs.land_cells_total_resolution8
            ) sub
        """), {"user_id": self.user_id}).fetchone()
        stats["max_region_coverage"] = result.max_coverage if result and result.max_coverage else 0.0

        return stats

    def _evaluate_criteria(self, criteria: dict, stats: dict) -> bool:
        """Check if user stats satisfy achievement criteria."""
        if not criteria:
            return False

        criteria_type = criteria.get("type")

        if criteria_type == "cells_total":
            return stats.get("cells_total", 0) >= criteria.get("threshold", 0)

        elif criteria_type == "countries":
            return stats.get("countries", 0) >= criteria.get("threshold", 0)

        elif criteria_type == "regions":
            return stats.get("regions", 0) >= criteria.get("threshold", 0)

        elif criteria_type == "continents":
            return stats.get("continents", 0) >= criteria.get("threshold", 0)

        elif criteria_type == "regions_in_country":
            return stats.get("max_regions_in_country", 0) >= criteria.get("threshold", 0)

        elif criteria_type == "hemispheres":
            return stats.get("hemispheres", 0) >= criteria.get("count", 0)

        elif criteria_type == "unique_days":
            return stats.get("unique_days", 0) >= criteria.get("threshold", 0)

        elif criteria_type == "country_coverage_pct":
            return stats.get("max_country_coverage", 0) >= criteria.get("threshold", 0)

        elif criteria_type == "region_coverage_pct":
            return stats.get("max_region_coverage", 0) >= criteria.get("threshold", 0)

        return False

    def get_all_with_status(self) -> List[dict]:
        """Get all achievements with user's unlock status."""
        result = self.db.execute(text("""
            SELECT
                a.code,
                a.name,
                a.description,
                CASE WHEN ua.id IS NOT NULL THEN TRUE ELSE FALSE END as unlocked,
                ua.unlocked_at
            FROM achievements a
            LEFT JOIN user_achievements ua
                ON a.id = ua.achievement_id AND ua.user_id = :user_id
            ORDER BY a.id
        """), {"user_id": self.user_id}).fetchall()

        return [
            {
                "code": row.code,
                "name": row.name,
                "description": row.description,
                "unlocked": row.unlocked,
                "unlocked_at": row.unlocked_at,
            }
            for row in result
        ]

    def get_unlocked(self) -> List[dict]:
        """Get only user's unlocked achievements."""
        return [a for a in self.get_all_with_status() if a["unlocked"]]
```

**Step 2: Run tests to verify they pass**

Run: `cd backend && $env:TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test"; python -m pytest tests/test_achievement_service.py -v`
Expected: All tests PASS

**Step 3: Run full test suite to check for regressions**

Run: `cd backend && $env:TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test"; python -m pytest tests/ -v --tb=short`
Expected: All existing tests pass

**Step 4: Commit**

```bash
cd backend && git add services/achievement_service.py && git commit -m "feat: implement AchievementService"
```

---

## Task 7: Write Achievements Router Tests (TDD - Red Phase)

**Files:**
- Create: `backend/tests/test_achievements_router.py`

**Step 1: Write the failing tests**

```python
"""Tests for achievements router endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from models.achievements import Achievement
from models.user import User
from tests.conftest import create_jwt_token
from tests.fixtures.test_data import SAN_FRANCISCO


@pytest.fixture
def seed_achievements_for_router(db_session: Session) -> list[Achievement]:
    """Seed achievements for router tests."""
    achievements_data = [
        {"code": "first_steps", "name": "First Steps", "description": "Visit your first location",
         "criteria_json": {"type": "cells_total", "threshold": 1}},
        {"code": "explorer", "name": "Explorer", "description": "Visit 100 unique cells",
         "criteria_json": {"type": "cells_total", "threshold": 100}},
    ]

    achievements = []
    for data in achievements_data:
        achievement = Achievement(**data)
        db_session.add(achievement)
        achievements.append(achievement)

    db_session.commit()
    for a in achievements:
        db_session.refresh(a)

    return achievements


class TestGetAllAchievements:
    """Test GET /api/v1/achievements endpoint."""

    def test_returns_all_achievements_authenticated(
        self, client: TestClient, test_user: User, valid_jwt_token: str,
        seed_achievements_for_router: list
    ):
        """Authenticated user should get all achievements with status."""
        response = client.get(
            "/api/v1/achievements",
            headers={"Authorization": f"Bearer {valid_jwt_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert "achievements" in data
        assert "total" in data
        assert "unlocked_count" in data
        assert data["total"] == 2
        assert data["unlocked_count"] == 0

        # All should be locked for new user
        for achievement in data["achievements"]:
            assert achievement["unlocked"] is False
            assert achievement["unlocked_at"] is None

    def test_returns_401_unauthenticated(self, client: TestClient):
        """Unauthenticated request should return 401."""
        response = client.get("/api/v1/achievements")

        assert response.status_code == 401


class TestGetUnlockedAchievements:
    """Test GET /api/v1/achievements/unlocked endpoint."""

    def test_returns_empty_for_new_user(
        self, client: TestClient, test_user: User, valid_jwt_token: str,
        seed_achievements_for_router: list
    ):
        """New user should have no unlocked achievements."""
        response = client.get(
            "/api/v1/achievements/unlocked",
            headers={"Authorization": f"Bearer {valid_jwt_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["achievements"] == []
        assert data["total"] == 0

    def test_returns_unlocked_achievements(
        self, client: TestClient, db_session: Session, test_user: User,
        valid_jwt_token: str, seed_achievements_for_router: list
    ):
        """Should return achievements that user has unlocked."""
        # Create country for cell
        db_session.execute(text("""
            INSERT INTO regions_country (name, iso2, iso3, continent, geom, created_at, updated_at)
            VALUES ('United States', 'US', 'USA', 'North America',
                    ST_GeomFromText('POLYGON((-125 30, -125 50, -115 50, -115 30, -125 30))', 4326),
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """))
        country_id = db_session.execute(text("SELECT id FROM regions_country WHERE iso2 = 'US'")).fetchone().id

        # Create cell visit to trigger first_steps
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, first_visited_at, last_visited_at, visit_count)
            VALUES (:h3, 8, :country_id, NOW(), NOW(), 1)
        """), {"h3": SAN_FRANCISCO["h3_res8"], "country_id": country_id})

        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3": SAN_FRANCISCO["h3_res8"]})

        # Manually unlock first_steps
        first_steps = db_session.execute(
            text("SELECT id FROM achievements WHERE code = 'first_steps'")
        ).fetchone()
        db_session.execute(text("""
            INSERT INTO user_achievements (user_id, achievement_id, unlocked_at)
            VALUES (:user_id, :achievement_id, NOW())
        """), {"user_id": test_user.id, "achievement_id": first_steps.id})

        db_session.commit()

        response = client.get(
            "/api/v1/achievements/unlocked",
            headers={"Authorization": f"Bearer {valid_jwt_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert len(data["achievements"]) == 1
        assert data["achievements"][0]["code"] == "first_steps"
        assert data["achievements"][0]["unlocked"] is True

    def test_returns_401_unauthenticated(self, client: TestClient):
        """Unauthenticated request should return 401."""
        response = client.get("/api/v1/achievements/unlocked")

        assert response.status_code == 401
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && $env:TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test"; python -m pytest tests/test_achievements_router.py -v`
Expected: FAIL with 404 (router not registered)

**Step 3: Commit test file**

```bash
cd backend && git add tests/test_achievements_router.py && git commit -m "test: add achievements router tests (red phase)"
```

---

## Task 8: Implement Achievements Router (TDD - Green Phase)

**Files:**
- Create: `backend/routers/achievements.py`
- Modify: `backend/main.py:9` (add import)
- Modify: `backend/main.py:55` (add router)

**Step 1: Create the router**

```python
"""Achievements API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from schemas.achievements import AchievementsListResponse, UnlockedAchievementsResponse, AchievementSchema
from services.achievement_service import AchievementService
from services.auth import get_current_user


router = APIRouter()


@router.get("", response_model=AchievementsListResponse)
def get_all_achievements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all achievements with user's unlock status.

    Returns the complete list of achievements in the system,
    with each achievement showing whether the current user has unlocked it.
    """
    service = AchievementService(db, current_user.id)
    all_achievements = service.get_all_with_status()

    unlocked_count = sum(1 for a in all_achievements if a["unlocked"])

    return AchievementsListResponse(
        achievements=[AchievementSchema(**a) for a in all_achievements],
        total=len(all_achievements),
        unlocked_count=unlocked_count,
    )


@router.get("/unlocked", response_model=UnlockedAchievementsResponse)
def get_unlocked_achievements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get only user's unlocked achievements.

    Returns achievements the current user has earned, sorted by unlock date.
    """
    service = AchievementService(db, current_user.id)
    unlocked = service.get_unlocked()

    return UnlockedAchievementsResponse(
        achievements=[AchievementSchema(**a) for a in unlocked],
        total=len(unlocked),
    )
```

**Step 2: Update main.py to register router**

In `backend/main.py`, add import at line 9 (after other router imports):

```python
from routers import auth, health, location, map, stats, achievements
```

Add router registration at line 56 (after stats router):

```python
app.include_router(achievements.router, prefix="/api/v1/achievements", tags=["achievements"])
```

**Step 3: Run tests to verify they pass**

Run: `cd backend && $env:TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test"; python -m pytest tests/test_achievements_router.py -v`
Expected: All tests PASS

**Step 4: Run full test suite**

Run: `cd backend && $env:TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test"; python -m pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 5: Commit**

```bash
cd backend && git add routers/achievements.py main.py && git commit -m "feat: add achievements router with GET endpoints"
```

---

## Task 9: Update Location Schema for Achievements

**Files:**
- Modify: `backend/schemas/location.py:84-89`

**Step 1: Add AchievementUnlockedSchema import and update response**

Add import at top of file (after existing imports):

```python
from schemas.achievements import AchievementUnlockedSchema
```

Update `LocationIngestResponse` class (line 84-89):

```python
class LocationIngestResponse(BaseModel):
    """Response schema for location ingestion."""

    discoveries: DiscoveriesResponse
    revisits: RevisitsResponse
    visit_counts: VisitCountsResponse
    achievements_unlocked: list[AchievementUnlockedSchema] = []
```

**Step 2: Verify import works**

Run: `cd backend && python -c "from schemas.location import LocationIngestResponse; print(LocationIngestResponse.model_fields.keys())"`
Expected: Output includes 'achievements_unlocked'

**Step 3: Commit**

```bash
cd backend && git add schemas/location.py && git commit -m "schema: add achievements_unlocked to LocationIngestResponse"
```

---

## Task 10: Write Location Processor Integration Tests (TDD - Red Phase)

**Files:**
- Modify: `backend/tests/test_location_processor.py` (add new test class at end)

**Step 1: Add achievement integration tests at end of file**

```python
# ============================================================================
# Achievement Integration Tests
# ============================================================================

@pytest.mark.integration
class TestAchievementIntegration:
    """Test achievement unlocking through location processor."""

    def test_process_location_returns_achievements_unlocked_key(
        self, db_session: Session, test_user: User, test_country_usa: CountryRegion,
        test_state_california: StateRegion
    ):
        """Response should include achievements_unlocked field."""
        # Seed first_steps achievement
        from models.achievements import Achievement
        achievement = Achievement(
            code="first_steps",
            name="First Steps",
            description="Visit your first location",
            criteria_json={"type": "cells_total", "threshold": 1},
        )
        db_session.add(achievement)
        db_session.commit()

        processor = LocationProcessor(db_session, test_user.id)
        result = processor.process_location(
            latitude=SAN_FRANCISCO["latitude"],
            longitude=SAN_FRANCISCO["longitude"],
            h3_res8=SAN_FRANCISCO["h3_res8"],
        )

        assert "achievements_unlocked" in result

    def test_process_location_unlocks_first_steps(
        self, db_session: Session, test_user: User, test_country_usa: CountryRegion,
        test_state_california: StateRegion
    ):
        """First location should unlock first_steps achievement."""
        from models.achievements import Achievement
        achievement = Achievement(
            code="first_steps",
            name="First Steps",
            description="Visit your first location",
            criteria_json={"type": "cells_total", "threshold": 1},
        )
        db_session.add(achievement)
        db_session.commit()

        processor = LocationProcessor(db_session, test_user.id)
        result = processor.process_location(
            latitude=SAN_FRANCISCO["latitude"],
            longitude=SAN_FRANCISCO["longitude"],
            h3_res8=SAN_FRANCISCO["h3_res8"],
        )

        assert len(result["achievements_unlocked"]) >= 1
        codes = [a["code"] for a in result["achievements_unlocked"]]
        assert "first_steps" in codes

    def test_process_location_no_duplicate_unlocks(
        self, db_session: Session, test_user: User, test_country_usa: CountryRegion,
        test_state_california: StateRegion
    ):
        """Revisiting should not re-unlock achievements."""
        from models.achievements import Achievement
        achievement = Achievement(
            code="first_steps",
            name="First Steps",
            description="Visit your first location",
            criteria_json={"type": "cells_total", "threshold": 1},
        )
        db_session.add(achievement)
        db_session.commit()

        processor = LocationProcessor(db_session, test_user.id)

        # First visit unlocks
        result1 = processor.process_location(
            latitude=SAN_FRANCISCO["latitude"],
            longitude=SAN_FRANCISCO["longitude"],
            h3_res8=SAN_FRANCISCO["h3_res8"],
        )
        assert any(a["code"] == "first_steps" for a in result1["achievements_unlocked"])

        # Second visit should not re-unlock
        result2 = processor.process_location(
            latitude=SAN_FRANCISCO["latitude"],
            longitude=SAN_FRANCISCO["longitude"],
            h3_res8=SAN_FRANCISCO["h3_res8"],
        )
        assert not any(a["code"] == "first_steps" for a in result2["achievements_unlocked"])
```

**Step 2: Run new tests to verify they fail**

Run: `cd backend && $env:TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test"; python -m pytest tests/test_location_processor.py::TestAchievementIntegration -v`
Expected: FAIL with KeyError: 'achievements_unlocked'

**Step 3: Commit test additions**

```bash
cd backend && git add tests/test_location_processor.py && git commit -m "test: add achievement integration tests for location processor (red phase)"
```

---

## Task 11: Integrate Achievements into LocationProcessor (TDD - Green Phase)

**Files:**
- Modify: `backend/services/location_processor.py:1-15` (add import)
- Modify: `backend/services/location_processor.py:100-111` (add achievement check)

**Step 1: Add import at top of file**

After line 12 (`from models.visits import IngestBatch, UserCellVisit`), add:

```python
from services.achievement_service import AchievementService
```

**Step 2: Update process_location to check achievements**

Replace lines 99-111 (the return section) with:

```python
        # Record audit batch
        self._record_ingest_batch(device_id)

        # Check and unlock achievements
        achievement_service = AchievementService(self.db, self.user_id)
        newly_unlocked = achievement_service.check_and_unlock()

        # Commit transaction
        self.db.commit()

        # Build response
        response = self._build_response(
            res6_result=res6_result,
            res8_result=res8_result,
            country_id=country_id,
            state_id=state_id,
        )

        # Add achievements to response
        response["achievements_unlocked"] = [
            {
                "code": a.code,
                "name": a.name,
                "description": a.description,
            }
            for a in newly_unlocked
        ]

        return response
```

**Step 3: Run integration tests to verify they pass**

Run: `cd backend && $env:TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test"; python -m pytest tests/test_location_processor.py::TestAchievementIntegration -v`
Expected: All tests PASS

**Step 4: Run full test suite**

Run: `cd backend && $env:TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test"; python -m pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 5: Commit**

```bash
cd backend && git add services/location_processor.py && git commit -m "feat: integrate achievement unlocking into location processor"
```

---

## Task 12: Update conftest.py for Achievement Fixtures

**Files:**
- Modify: `backend/tests/conftest.py` (add fixture at end)

**Step 1: Add country fixture with continent**

Add after line 257 (after `mock_state_california` fixture):

```python
@pytest.fixture
def test_country_usa_with_continent(db_session: Session) -> CountryRegion:
    """Create USA country with continent for achievement tests."""
    country = db_session.execute(text("""
        INSERT INTO regions_country (name, iso2, iso3, continent, geom, land_cells_total_resolution8, created_at, updated_at)
        VALUES (
            'United States',
            'US',
            'USA',
            'North America',
            ST_GeomFromText('POLYGON((-125 30, -125 50, -115 50, -115 30, -125 30))', 4326),
            1000,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
        RETURNING id, name, iso2, iso3
    """)).fetchone()

    db_session.commit()

    result = CountryRegion()
    result.id = country.id
    result.name = country.name
    result.iso2 = country.iso2
    result.iso3 = country.iso3
    return result
```

**Step 2: Verify fixture works**

Run: `cd backend && $env:TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test"; python -m pytest tests/test_achievement_service.py::TestCheckAndUnlock::test_unlocks_first_steps_on_first_cell -v`
Expected: Test passes

**Step 3: Commit**

```bash
cd backend && git add tests/conftest.py && git commit -m "test: add continent-aware country fixture"
```

---

## Task 13: Update assert_discovery_response Helper

**Files:**
- Modify: `backend/tests/conftest.py:336-376`

**Step 1: Update helper to check achievements_unlocked**

Replace the `assert_discovery_response` function:

```python
def assert_discovery_response(
    response_data: dict,
    expected_new_country: Optional[str] = None,
    expected_new_state: Optional[str] = None,
    expected_new_cells_res6: int = 0,
    expected_new_cells_res8: int = 0,
    expected_revisit_cells_res6: int = 0,
    expected_revisit_cells_res8: int = 0,
    expected_achievements_unlocked: Optional[list[str]] = None,
):
    """Helper to validate LocationIngestResponse structure and values."""
    assert "discoveries" in response_data
    assert "revisits" in response_data
    assert "visit_counts" in response_data
    assert "achievements_unlocked" in response_data

    discoveries = response_data["discoveries"]
    revisits = response_data["revisits"]
    visit_counts = response_data["visit_counts"]

    # Check country discovery
    if expected_new_country:
        assert discoveries["new_country"] is not None
        assert discoveries["new_country"]["name"] == expected_new_country
    else:
        assert discoveries["new_country"] is None

    # Check state discovery
    if expected_new_state:
        assert discoveries["new_state"] is not None
        assert discoveries["new_state"]["name"] == expected_new_state
    else:
        assert discoveries["new_state"] is None

    # Check cell counts
    assert len(discoveries["new_cells_res6"]) == expected_new_cells_res6
    assert len(discoveries["new_cells_res8"]) == expected_new_cells_res8
    assert len(revisits["cells_res6"]) == expected_revisit_cells_res6
    assert len(revisits["cells_res8"]) == expected_revisit_cells_res8

    # Check visit counts exist
    assert "res6_visit_count" in visit_counts
    assert "res8_visit_count" in visit_counts

    # Check achievements if specified
    if expected_achievements_unlocked is not None:
        unlocked_codes = [a["code"] for a in response_data["achievements_unlocked"]]
        for code in expected_achievements_unlocked:
            assert code in unlocked_codes, f"Expected achievement {code} not found"
```

**Step 2: Run tests using the helper**

Run: `cd backend && $env:TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test"; python -m pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 3: Commit**

```bash
cd backend && git add tests/conftest.py && git commit -m "test: update assert_discovery_response for achievements"
```

---

## Task 14: Final Verification

**Files:** None (verification only)

**Step 1: Run full test suite**

Run: `cd backend && $env:TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test"; python -m pytest tests/ -v`
Expected: All tests pass (should be 50+ tests)

**Step 2: Run migrations on dev database**

Run: `cd backend && alembic upgrade head`
Expected: Both migrations apply successfully

**Step 3: Verify API endpoints work**

Run: `cd backend && uvicorn main:app --reload`
Then in another terminal:
```bash
# Get token (adjust credentials as needed)
curl -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"test","password":"test"}'

# Get achievements
curl http://localhost:8000/api/v1/achievements -H "Authorization: Bearer <token>"
```
Expected: Returns list of 17 achievements

**Step 4: Create final commit with all changes**

```bash
cd backend && git add -A && git status
```
Verify only expected files are staged.

```bash
git commit -m "feat: complete achievements system implementation

- Add continent column to regions_country table
- Seed 17 initial achievements (volume, geographic, coverage)
- Implement AchievementService with criteria evaluation
- Add /api/v1/achievements endpoints
- Integrate achievement unlocking into location ingestion
- Add comprehensive test coverage

Closes #achievements-system"
```

---

## Summary

This plan implements the full achievements system in 14 tasks following TDD:

1. **Migrations** (Tasks 1, 3): Add continent column, seed 17 achievements
2. **Model updates** (Task 2): Add continent to CountryRegion
3. **Schemas** (Tasks 4, 9): Achievement response models
4. **Service** (Tasks 5-6): AchievementService with TDD
5. **Router** (Tasks 7-8): GET endpoints with TDD
6. **Integration** (Tasks 10-11): LocationProcessor integration with TDD
7. **Test fixtures** (Tasks 12-13): Updated helpers and fixtures
8. **Verification** (Task 14): Full test suite and manual verification

Each task is atomic and includes verification steps. The full test suite must pass after each task.
