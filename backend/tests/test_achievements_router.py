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
