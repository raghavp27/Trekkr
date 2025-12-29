"""Integration tests for stats router endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from models.user import User
from models.geo import CountryRegion, StateRegion
from tests.conftest import create_jwt_token
from tests.fixtures.test_data import SAN_FRANCISCO
# Verify we can import new response models
from schemas.stats import (
    UserInfoResponse,
    StatsResponse,
    RecentCountryResponse,
    RecentRegionResponse,
    OverviewResponse,
)


@pytest.mark.integration
class TestStatsCountriesEndpoint:
    """Test GET /api/v1/stats/countries endpoint."""

    def test_unauthenticated_returns_401(self, client: TestClient):
        """Test that unauthenticated request returns 401."""
        response = client.get("/api/v1/stats/countries")
        assert response.status_code == 401

    def test_returns_empty_for_new_user(
        self, client: TestClient, test_user: User
    ):
        """Test that new user with no visits gets empty response."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/stats/countries",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_countries_visited"] == 0
        assert data["countries"] == []

    def test_returns_country_stats(
        self,
        client: TestClient,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that endpoint returns country statistics."""
        # Set up test data
        db_session.execute(text("""
            UPDATE regions_country SET land_cells_total_resolution8 = 1000 WHERE id = :id
        """), {"id": test_country_usa.id})

        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
        """), {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": SAN_FRANCISCO["longitude"],
            "lat": SAN_FRANCISCO["latitude"],
        })

        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": SAN_FRANCISCO["h3_res8"]})
        db_session.commit()

        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/stats/countries",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_countries_visited"] == 1
        assert len(data["countries"]) == 1
        assert data["countries"][0]["code"] == "US"
        assert data["countries"][0]["coverage_pct"] == 0.001

    def test_query_params_work(
        self, client: TestClient, test_user: User
    ):
        """Test that query parameters are accepted."""
        token = create_jwt_token(test_user.id, test_user.username)
        
        response = client.get(
            "/api/v1/stats/countries?sort_by=name&order=asc&limit=10&offset=0",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    def test_invalid_sort_by_returns_422(
        self, client: TestClient, test_user: User
    ):
        """Test that invalid sort_by returns validation error."""
        token = create_jwt_token(test_user.id, test_user.username)
        
        response = client.get(
            "/api/v1/stats/countries?sort_by=invalid",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    def test_limit_over_100_returns_422(
        self, client: TestClient, test_user: User
    ):
        """Test that limit > 100 returns validation error."""
        token = create_jwt_token(test_user.id, test_user.username)
        
        response = client.get(
            "/api/v1/stats/countries?limit=101",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422


@pytest.mark.integration
class TestStatsRegionsEndpoint:
    """Test GET /api/v1/stats/regions endpoint."""

    def test_unauthenticated_returns_401(self, client: TestClient):
        """Test that unauthenticated request returns 401."""
        response = client.get("/api/v1/stats/regions")
        assert response.status_code == 401

    def test_returns_empty_for_new_user(
        self, client: TestClient, test_user: User
    ):
        """Test that new user with no visits gets empty response."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/stats/regions",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_regions_visited"] == 0
        assert data["regions"] == []

    def test_returns_region_stats(
        self,
        client: TestClient,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that endpoint returns region statistics."""
        # Set up test data
        db_session.execute(text("""
            UPDATE regions_state SET land_cells_total_resolution8 = 500 WHERE id = :id
        """), {"id": test_state_california.id})

        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
        """), {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": SAN_FRANCISCO["longitude"],
            "lat": SAN_FRANCISCO["latitude"],
        })

        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": SAN_FRANCISCO["h3_res8"]})
        db_session.commit()

        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/stats/regions",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_regions_visited"] == 1
        assert len(data["regions"]) == 1
        assert data["regions"][0]["code"] == "US-CA"
        assert data["regions"][0]["name"] == "California"
        assert data["regions"][0]["country_code"] == "US"
        assert data["regions"][0]["coverage_pct"] == 0.002


@pytest.mark.integration
class TestStatsOverviewEndpoint:
    """Test GET /api/v1/stats/overview endpoint."""

    def test_overview_requires_authentication(self, client: TestClient):
        """Overview endpoint should require valid JWT token."""
        response = client.get("/api/v1/stats/overview")
        assert response.status_code == 401

    def test_overview_for_new_user_returns_zeros(
        self, client: TestClient, test_user: User
    ):
        """New user with no visits should get zeros and empty arrays."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/stats/overview",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()

        # User info should be present
        assert data["user"]["id"] == test_user.id
        assert data["user"]["username"] == test_user.username
        assert data["user"]["created_at"] is not None

        # Stats should all be zero
        assert data["stats"]["countries_visited"] == 0
        assert data["stats"]["regions_visited"] == 0
        assert data["stats"]["cells_visited_res6"] == 0
        assert data["stats"]["cells_visited_res8"] == 0
        assert data["stats"]["total_visit_count"] == 0
        assert data["stats"]["first_visit_at"] is None
        assert data["stats"]["last_visit_at"] is None

        # Recent lists should be empty
        assert data["recent_countries"] == []
        assert data["recent_regions"] == []

    def test_overview_returns_correct_stats(
        self,
        client,
        test_user,
        db_session,
        test_country_usa,
        test_state_california,
    ):
        """User with visits should get accurate stats and recent lists."""
        from datetime import datetime, timedelta

        # Add some user visits at res6 and res8
        now = datetime.utcnow()

        # First, create h3_cells that we'll visit
        # Visit 1: res8 cell
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 0)
        """), {
            "h3_index": "882830810ffffff",
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": -122.4,
            "lat": 37.8,
        })

        # Visit 2: res6 cell
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 6, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 0)
        """), {
            "h3_index": "862830807ffffff",
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": -122.4,
            "lat": 37.8,
        })

        # Visit 3: another res8 cell
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 0)
        """), {
            "h3_index": "882830811ffffff",
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": -122.4,
            "lat": 37.8,
        })

        # Now create the user visits
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, :first_visited, :last_visited, 3)
        """), {
            "user_id": test_user.id,
            "h3_index": "882830810ffffff",
            "first_visited": now - timedelta(days=10),
            "last_visited": now - timedelta(days=5),
        })

        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 6, :first_visited, :last_visited, 2)
        """), {
            "user_id": test_user.id,
            "h3_index": "862830807ffffff",
            "first_visited": now - timedelta(days=8),
            "last_visited": now - timedelta(days=2),
        })

        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, :first_visited, :last_visited, 1)
        """), {
            "user_id": test_user.id,
            "h3_index": "882830811ffffff",
            "first_visited": now - timedelta(days=1),
            "last_visited": now,
        })

        db_session.commit()

        # Make request
        token = create_jwt_token(test_user.id, test_user.username)
        response = client.get(
            "/api/v1/stats/overview",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify user info
        assert data["user"]["id"] == test_user.id
        assert data["user"]["username"] == test_user.username

        # Verify stats (counts depend on h3_cells seed data)
        assert data["stats"]["cells_visited_res6"] == 1
        assert data["stats"]["cells_visited_res8"] == 2
        assert data["stats"]["total_visit_count"] == 6  # 3 + 2 + 1

        # Verify timestamps
        assert data["stats"]["first_visit_at"] is not None
        assert data["stats"]["last_visit_at"] is not None

        # Recent lists should have at most 3 items each
        assert len(data["recent_countries"]) <= 3
        assert len(data["recent_regions"]) <= 3

    def test_overview_recent_lists_sorted_by_last_visit(
        self, client, test_user, db_session, test_country_usa, test_state_california
    ):
        """Recent countries/regions should be ordered by most recent visit."""
        from models.visits import UserCellVisit
        from datetime import datetime, timedelta

        now = datetime.utcnow()

        # Create Mexico country and state
        country_mexico = db_session.execute(text("""
            INSERT INTO regions_country (name, iso2, iso3, geom, created_at, updated_at)
            VALUES (
                'Mexico',
                'MX',
                'MEX',
                ST_GeomFromText('POLYGON((-115 15, -115 30, -90 30, -90 15, -115 15))', 4326),
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            RETURNING id
        """)).fetchone()

        state_mexico = db_session.execute(text("""
            INSERT INTO regions_state (name, code, country_id, geom, created_at, updated_at)
            VALUES (
                'Jalisco',
                'JAL',
                :country_id,
                ST_GeomFromText('POLYGON((-105 19, -105 21, -103 21, -103 19, -105 19))', 4326),
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            RETURNING id
        """), {"country_id": country_mexico.id}).fetchone()

        # Create Canada country and state
        country_canada = db_session.execute(text("""
            INSERT INTO regions_country (name, iso2, iso3, geom, created_at, updated_at)
            VALUES (
                'Canada',
                'CA',
                'CAN',
                ST_GeomFromText('POLYGON((-140 45, -140 70, -60 70, -60 45, -140 45))', 4326),
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            RETURNING id
        """)).fetchone()

        state_canada = db_session.execute(text("""
            INSERT INTO regions_state (name, code, country_id, geom, created_at, updated_at)
            VALUES (
                'Ontario',
                'ON',
                :country_id,
                ST_GeomFromText('POLYGON((-85 42, -85 48, -75 48, -75 42, -85 42))', 4326),
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            RETURNING id
        """), {"country_id": country_canada.id}).fetchone()

        db_session.commit()

        # Create h3_cells in different countries with different timestamps
        # USA - 10 days ago (oldest)
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 0)
        """), {
            "h3_index": "882830810ffffff",
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": -122.4,
            "lat": 37.8,
        })

        # Mexico - 5 days ago (middle)
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 0)
        """), {
            "h3_index": "882830820ffffff",
            "country_id": country_mexico.id,
            "state_id": state_mexico.id,
            "lon": -103.5,
            "lat": 20.5,
        })

        # Canada - 1 day ago (most recent)
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 0)
        """), {
            "h3_index": "882830830ffffff",
            "country_id": country_canada.id,
            "state_id": state_canada.id,
            "lon": -79.4,
            "lat": 43.7,
        })

        # Create visits with different timestamps
        visits = [
            UserCellVisit(
                user_id=test_user.id,
                h3_index="882830810ffffff",
                res=8,
                first_visited_at=now - timedelta(days=10),
                last_visited_at=now - timedelta(days=10),  # USA - Oldest
                visit_count=1,
            ),
            UserCellVisit(
                user_id=test_user.id,
                h3_index="882830820ffffff",
                res=8,
                first_visited_at=now - timedelta(days=5),
                last_visited_at=now - timedelta(days=5),  # Mexico - Middle
                visit_count=1,
            ),
            UserCellVisit(
                user_id=test_user.id,
                h3_index="882830830ffffff",
                res=8,
                first_visited_at=now - timedelta(days=1),
                last_visited_at=now - timedelta(days=1),  # Canada - Most recent
                visit_count=1,
            ),
        ]

        for visit in visits:
            db_session.add(visit)
        db_session.commit()

        token = create_jwt_token(test_user.id, test_user.username)
        response = client.get(
            "/api/v1/stats/overview",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()

        # CRITICAL: Ensure we have multiple countries/regions to test sorting
        assert len(data["recent_countries"]) >= 2, "Test requires at least 2 countries to verify sorting"
        assert len(data["recent_regions"]) >= 2, "Test requires at least 2 regions to verify sorting"

        # Verify countries are sorted by most recent visit (DESC)
        # Should be: Canada (1 day ago), Mexico (5 days ago), USA (10 days ago)
        assert data["recent_countries"][0]["code"] == "CA", "Most recent country should be Canada"
        assert data["recent_countries"][1]["code"] == "MX", "Second most recent should be Mexico"
        assert data["recent_countries"][2]["code"] == "US", "Oldest country should be USA"

        # Verify regions are sorted by most recent visit (DESC)
        # Should be: Ontario (1 day ago), Jalisco (5 days ago), California (10 days ago)
        assert data["recent_regions"][0]["code"] == "CA-ON", "Most recent region should be Ontario"
        assert data["recent_regions"][1]["code"] == "MX-JAL", "Second most recent should be Jalisco"
        assert data["recent_regions"][2]["code"] == "US-CA", "Oldest region should be California"

        # Verify general descending order for timestamps
        for i in range(len(data["recent_countries"]) - 1):
            current = datetime.fromisoformat(
                data["recent_countries"][i]["visited_at"].replace("Z", "+00:00")
            )
            next_item = datetime.fromisoformat(
                data["recent_countries"][i + 1]["visited_at"].replace("Z", "+00:00")
            )
            assert current >= next_item, "Countries not sorted by visited_at DESC"

        for i in range(len(data["recent_regions"]) - 1):
            current = datetime.fromisoformat(
                data["recent_regions"][i]["visited_at"].replace("Z", "+00:00")
            )
            next_item = datetime.fromisoformat(
                data["recent_regions"][i + 1]["visited_at"].replace("Z", "+00:00")
            )
            assert current >= next_item, "Regions not sorted by visited_at DESC"
