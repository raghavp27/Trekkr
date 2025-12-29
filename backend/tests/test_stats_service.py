"""Integration tests for StatsService."""

from datetime import datetime

import pytest
from sqlalchemy import text

from models.user import User
from models.geo import CountryRegion, StateRegion
from services.stats_service import StatsService
from tests.fixtures.test_data import SAN_FRANCISCO, LOS_ANGELES, TOKYO


@pytest.mark.integration
class TestStatsServiceCountries:
    """Test StatsService.get_countries() method."""

    def test_user_with_no_visits_returns_empty(
        self, db_session, test_user: User
    ):
        """Test that user with no visits returns zero total and empty list."""
        service = StatsService(db_session, test_user.id)
        result = service.get_countries()

        assert result["total_countries_visited"] == 0
        assert result["countries"] == []

    def test_user_with_visits_returns_country_stats(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that user with visits returns country with coverage."""
        # Set up cell count for coverage calculation
        db_session.execute(text("""
            UPDATE regions_country
            SET land_cells_total_resolution8 = 1000
            WHERE id = :country_id
        """), {"country_id": test_country_usa.id})

        # Create a cell visit
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
            VALUES (:user_id, :h3_index, 8, :first_visited, :last_visited, 1)
        """), {
            "user_id": test_user.id,
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "first_visited": datetime(2024, 3, 15, 10, 30),
            "last_visited": datetime(2024, 3, 15, 10, 30),
        })
        db_session.commit()

        service = StatsService(db_session, test_user.id)
        result = service.get_countries()

        assert result["total_countries_visited"] == 1
        assert len(result["countries"]) == 1

        country = result["countries"][0]
        assert country["code"] == "US"
        assert country["name"] == "United States"
        assert country["coverage_pct"] == 0.001  # 1/1000
        assert country["first_visited_at"] == datetime(2024, 3, 15, 10, 30)

    def test_only_counts_user_cells(
        self,
        db_session,
        test_user: User,
        test_user2: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that only the requesting user's cells are counted."""
        db_session.execute(text("""
            UPDATE regions_country SET land_cells_total_resolution8 = 1000 WHERE id = :id
        """), {"id": test_country_usa.id})

        # User 1 has SF cell
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

        # User 2 has LA cell
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
        """), {
            "h3_index": LOS_ANGELES["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": LOS_ANGELES["longitude"],
            "lat": LOS_ANGELES["latitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user2.id, "h3_index": LOS_ANGELES["h3_res8"]})
        db_session.commit()

        # User 1 should only see 1 cell (0.1% coverage)
        service = StatsService(db_session, test_user.id)
        result = service.get_countries()
        assert result["countries"][0]["coverage_pct"] == 0.001  # 1/1000

    def test_sorting_by_coverage(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_country_japan: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test sorting by coverage percentage."""
        # USA: 2 cells / 1000 total = 0.2%
        db_session.execute(text("""
            UPDATE regions_country SET land_cells_total_resolution8 = 1000 WHERE id = :id
        """), {"id": test_country_usa.id})

        # Japan: 1 cell / 100 total = 1%
        db_session.execute(text("""
            UPDATE regions_country SET land_cells_total_resolution8 = 100 WHERE id = :id
        """), {"id": test_country_japan.id})

        # Two cells in USA
        for loc in [SAN_FRANCISCO, LOS_ANGELES]:
            db_session.execute(text("""
                INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
                VALUES (:h3_index, 8, :country_id, :state_id,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
                ON CONFLICT DO NOTHING
            """), {
                "h3_index": loc["h3_res8"],
                "country_id": test_country_usa.id,
                "state_id": test_state_california.id,
                "lon": loc["longitude"],
                "lat": loc["latitude"],
            })
            db_session.execute(text("""
                INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
                VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
                ON CONFLICT DO NOTHING
            """), {"user_id": test_user.id, "h3_index": loc["h3_res8"]})

        # One cell in Japan
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
        """), {
            "h3_index": TOKYO["h3_res8"],
            "country_id": test_country_japan.id,
            "lon": TOKYO["longitude"],
            "lat": TOKYO["latitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": TOKYO["h3_res8"]})

        db_session.commit()

        service = StatsService(db_session, test_user.id)

        # Sort by coverage descending - Japan (1%) should be first
        result = service.get_countries(sort_by="coverage_pct", order="desc")
        assert result["countries"][0]["code"] == "JP"
        assert result["countries"][1]["code"] == "US"

        # Sort by coverage ascending - USA (0.2%) should be first
        result = service.get_countries(sort_by="coverage_pct", order="asc")
        assert result["countries"][0]["code"] == "US"


@pytest.mark.integration
class TestStatsServiceRegions:
    """Test StatsService.get_regions() method."""

    def test_user_with_no_visits_returns_empty(
        self, db_session, test_user: User
    ):
        """Test that user with no visits returns zero total and empty list."""
        service = StatsService(db_session, test_user.id)
        result = service.get_regions()

        assert result["total_regions_visited"] == 0
        assert result["regions"] == []

    def test_user_with_visits_returns_region_stats(
        self,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that user with visits returns region with coverage."""
        # Set up cell count for coverage calculation
        db_session.execute(text("""
            UPDATE regions_state
            SET land_cells_total_resolution8 = 500
            WHERE id = :state_id
        """), {"state_id": test_state_california.id})

        # Create a cell visit
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
            VALUES (:user_id, :h3_index, 8, :first_visited, :last_visited, 1)
        """), {
            "user_id": test_user.id,
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "first_visited": datetime(2024, 3, 15, 10, 30),
            "last_visited": datetime(2024, 3, 15, 10, 30),
        })
        db_session.commit()

        service = StatsService(db_session, test_user.id)
        result = service.get_regions()

        assert result["total_regions_visited"] == 1
        assert len(result["regions"]) == 1

        region = result["regions"][0]
        assert region["code"] == "US-CA"
        assert region["name"] == "California"
        assert region["country_code"] == "US"
        assert region["country_name"] == "United States"
        assert region["coverage_pct"] == 0.002  # 1/500
        assert region["first_visited_at"] == datetime(2024, 3, 15, 10, 30)
