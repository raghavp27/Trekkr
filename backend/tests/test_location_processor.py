"""Unit tests for LocationProcessor service.

Tests the business logic of location processing with mocked database interactions.
These tests are fast and isolated, focusing on the correctness of the service layer.
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, call, patch
from typing import Any

import h3
import pytest
from sqlalchemy import text

from models.geo import CountryRegion, StateRegion
from models.visits import IngestBatch
from services.location_processor import LocationProcessor
from tests.fixtures.test_data import (
    SAN_FRANCISCO,
    TOKYO,
    INTERNATIONAL_WATERS,
    LOS_ANGELES,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def processor(mock_db_session) -> LocationProcessor:
    """Create LocationProcessor with mocked database session."""
    return LocationProcessor(db=mock_db_session, user_id=1)


# ============================================================================
# Basic Location Processing Tests
# ============================================================================

@pytest.mark.unit
class TestProcessLocation:
    """Test the main process_location method."""

    def test_process_location_first_visit(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test processing a location for the first time."""
        # Mock reverse geocoding to return country and state
        mock_db_session.execute.side_effect = [
            # Reverse geocode query
            Mock(
                fetchone=Mock(
                    return_value=Mock(country_id=1, state_id=5)
                )
            ),
            # First UPSERT (res-6)
            Mock(
                fetchone=Mock(
                    return_value=Mock(
                        h3_index=SAN_FRANCISCO["h3_res6"],
                        res=6,
                        visit_count=1,
                        was_inserted=True,
                    )
                )
            ),
            # Second UPSERT (res-8)
            Mock(
                fetchone=Mock(
                    return_value=Mock(
                        h3_index=SAN_FRANCISCO["h3_res8"],
                        res=8,
                        visit_count=1,
                        was_inserted=True,
                    )
                )
            ),
            # Query for other cells in country
            Mock(fetchone=Mock(return_value=None)),
            # Query for other cells in state
            Mock(fetchone=Mock(return_value=None)),
        ]

        # Mock country and state objects
        mock_country = Mock(spec=CountryRegion, id=1, name="United States", iso2="US")
        mock_state = Mock(spec=StateRegion, id=5, name="California", code="CA")

        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_country,
            mock_state,
        ]

        # Execute
        result = processor.process_location(
            latitude=SAN_FRANCISCO["latitude"],
            longitude=SAN_FRANCISCO["longitude"],
            h3_res8=SAN_FRANCISCO["h3_res8"],
            device_id=1,
        )

        # Verify commit was called
        mock_db_session.commit.assert_called_once()

        # Verify IngestBatch was added
        assert mock_db_session.add.called

        # Verify response structure
        assert "discoveries" in result
        assert "revisits" in result
        assert "visit_counts" in result

        # Verify discoveries
        assert result["discoveries"]["new_country"]["name"] == "United States"
        assert result["discoveries"]["new_state"]["name"] == "California"
        assert len(result["discoveries"]["new_cells_res6"]) == 1
        assert len(result["discoveries"]["new_cells_res8"]) == 1

        # Verify no revisits
        assert len(result["revisits"]["cells_res6"]) == 0
        assert len(result["revisits"]["cells_res8"]) == 0

    def test_process_location_derives_res6_from_res8(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test that res-6 cell is correctly derived from res-8."""
        expected_res6 = h3.cell_to_parent(SAN_FRANCISCO["h3_res8"], 6)

        # Mock minimal responses
        mock_db_session.execute.side_effect = [
            Mock(fetchone=Mock(return_value=Mock(country_id=None, state_id=None))),
            Mock(fetchone=Mock(return_value=Mock(
                h3_index=expected_res6, res=6, visit_count=1, was_inserted=True
            ))),
            Mock(fetchone=Mock(return_value=Mock(
                h3_index=SAN_FRANCISCO["h3_res8"], res=8, visit_count=1, was_inserted=True
            ))),
        ]

        result = processor.process_location(
            latitude=SAN_FRANCISCO["latitude"],
            longitude=SAN_FRANCISCO["longitude"],
            h3_res8=SAN_FRANCISCO["h3_res8"],
        )

        # Verify res-6 cell in discoveries
        assert result["discoveries"]["new_cells_res6"][0] == expected_res6

    def test_process_location_with_custom_timestamp(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test that custom timestamp is used when provided."""
        custom_timestamp = datetime(2024, 1, 15, 12, 30, 0)

        mock_db_session.execute.side_effect = [
            Mock(fetchone=Mock(return_value=Mock(country_id=None, state_id=None))),
            Mock(fetchone=Mock(return_value=Mock(
                h3_index=SAN_FRANCISCO["h3_res6"], res=6, visit_count=1, was_inserted=True
            ))),
            Mock(fetchone=Mock(return_value=Mock(
                h3_index=SAN_FRANCISCO["h3_res8"], res=8, visit_count=1, was_inserted=True
            ))),
        ]

        # Should not raise an error (timestamp is used internally but not returned)
        result = processor.process_location(
            latitude=SAN_FRANCISCO["latitude"],
            longitude=SAN_FRANCISCO["longitude"],
            h3_res8=SAN_FRANCISCO["h3_res8"],
            timestamp=custom_timestamp,
        )

        assert result is not None

    def test_process_location_without_device_id(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test processing location without device_id."""
        mock_db_session.execute.side_effect = [
            Mock(fetchone=Mock(return_value=Mock(country_id=None, state_id=None))),
            Mock(fetchone=Mock(return_value=Mock(
                h3_index=SAN_FRANCISCO["h3_res6"], res=6, visit_count=1, was_inserted=True
            ))),
            Mock(fetchone=Mock(return_value=Mock(
                h3_index=SAN_FRANCISCO["h3_res8"], res=8, visit_count=1, was_inserted=True
            ))),
        ]

        result = processor.process_location(
            latitude=SAN_FRANCISCO["latitude"],
            longitude=SAN_FRANCISCO["longitude"],
            h3_res8=SAN_FRANCISCO["h3_res8"],
            device_id=None,
        )

        assert result is not None


# ============================================================================
# Reverse Geocoding Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.geo
class TestReverseGeocode:
    """Test the _reverse_geocode method."""

    def test_reverse_geocode_finds_country_and_state(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test reverse geocoding successfully finds both country and state."""
        mock_db_session.execute.return_value.fetchone.return_value = Mock(
            country_id=1, state_id=5
        )

        country_id, state_id = processor._reverse_geocode(
            SAN_FRANCISCO["latitude"], SAN_FRANCISCO["longitude"]
        )

        assert country_id == 1
        assert state_id == 5

        # Verify PostGIS query was called with correct params
        mock_db_session.execute.assert_called_once()
        call_args = mock_db_session.execute.call_args
        assert "lat" in call_args[0][1]
        assert "lon" in call_args[0][1]

    def test_reverse_geocode_finds_country_only(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test reverse geocoding finds country but no state (e.g., small countries)."""
        mock_db_session.execute.return_value.fetchone.return_value = Mock(
            country_id=1, state_id=None
        )

        country_id, state_id = processor._reverse_geocode(43.7384, 7.4246)  # Monaco

        assert country_id == 1
        assert state_id is None

    def test_reverse_geocode_finds_nothing(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test reverse geocoding in international waters returns None."""
        mock_db_session.execute.return_value.fetchone.return_value = Mock(
            country_id=None, state_id=None
        )

        country_id, state_id = processor._reverse_geocode(
            INTERNATIONAL_WATERS["latitude"], INTERNATIONAL_WATERS["longitude"]
        )

        assert country_id is None
        assert state_id is None

    def test_reverse_geocode_handles_no_result(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test reverse geocoding when query returns no rows."""
        mock_db_session.execute.return_value.fetchone.return_value = None

        country_id, state_id = processor._reverse_geocode(0.0, 0.0)

        assert country_id is None
        assert state_id is None


# ============================================================================
# UPSERT Cell Visit Tests
# ============================================================================

@pytest.mark.unit
class TestUpsertCellVisit:
    """Test the _upsert_cell_visit method."""

    def test_upsert_first_visit(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test UPSERT for first visit creates new record."""
        mock_db_session.execute.return_value.fetchone.return_value = Mock(
            h3_index=SAN_FRANCISCO["h3_res8"],
            res=8,
            visit_count=1,
            was_inserted=True,
        )

        result = processor._upsert_cell_visit(
            h3_index=SAN_FRANCISCO["h3_res8"],
            res=8,
            latitude=SAN_FRANCISCO["latitude"],
            longitude=SAN_FRANCISCO["longitude"],
            country_id=1,
            state_id=5,
            device_id=1,
        )

        assert result["h3_index"] == SAN_FRANCISCO["h3_res8"]
        assert result["res"] == 8
        assert result["visit_count"] == 1
        assert result["is_new"] is True

    def test_upsert_revisit(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test UPSERT for revisit updates existing record."""
        mock_db_session.execute.return_value.fetchone.return_value = Mock(
            h3_index=SAN_FRANCISCO["h3_res8"],
            res=8,
            visit_count=2,  # Incremented
            was_inserted=False,
        )

        result = processor._upsert_cell_visit(
            h3_index=SAN_FRANCISCO["h3_res8"],
            res=8,
            latitude=SAN_FRANCISCO["latitude"],
            longitude=SAN_FRANCISCO["longitude"],
            country_id=1,
            state_id=5,
            device_id=1,
        )

        assert result["visit_count"] == 2
        assert result["is_new"] is False

    def test_upsert_without_geography(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test UPSERT works with NULL country_id and state_id."""
        mock_db_session.execute.return_value.fetchone.return_value = Mock(
            h3_index=INTERNATIONAL_WATERS["h3_res8"],
            res=8,
            visit_count=1,
            was_inserted=True,
        )

        result = processor._upsert_cell_visit(
            h3_index=INTERNATIONAL_WATERS["h3_res8"],
            res=8,
            latitude=INTERNATIONAL_WATERS["latitude"],
            longitude=INTERNATIONAL_WATERS["longitude"],
            country_id=None,
            state_id=None,
            device_id=None,
        )

        assert result["is_new"] is True


# ============================================================================
# Discovery Detection Tests
# ============================================================================

@pytest.mark.unit
class TestBuildResponse:
    """Test the _build_response method for discovery detection."""

    def test_first_visit_to_new_country(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test that first visit to a country returns new_country discovery."""
        res6_result = {
            "h3_index": SAN_FRANCISCO["h3_res6"],
            "res": 6,
            "visit_count": 1,
            "is_new": True,
        }
        res8_result = {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "res": 8,
            "visit_count": 1,
            "is_new": True,
        }

        # Mock country/state queries
        mock_country = Mock(spec=CountryRegion, id=1, name="United States", iso2="US")
        mock_state = Mock(spec=StateRegion, id=5, name="California", code="CA")

        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_country,
            mock_state,
        ]

        # Mock "no other cells" queries
        mock_db_session.execute.side_effect = [
            Mock(fetchone=Mock(return_value=None)),  # No other cells in country
            Mock(fetchone=Mock(return_value=None)),  # No other cells in state
        ]

        result = processor._build_response(
            res6_result=res6_result,
            res8_result=res8_result,
            country_id=1,
            state_id=5,
        )

        # Should discover country and state
        assert result["discoveries"]["new_country"]["name"] == "United States"
        assert result["discoveries"]["new_state"]["name"] == "California"

    def test_revisit_does_not_discover_country(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test that revisiting a cell does not trigger country discovery."""
        res6_result = {
            "h3_index": SAN_FRANCISCO["h3_res6"],
            "res": 6,
            "visit_count": 2,
            "is_new": False,  # Revisit
        }
        res8_result = {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "res": 8,
            "visit_count": 2,
            "is_new": False,  # Revisit
        }

        result = processor._build_response(
            res6_result=res6_result,
            res8_result=res8_result,
            country_id=1,
            state_id=5,
        )

        # Should NOT discover country (res-8 is not new)
        assert result["discoveries"]["new_country"] is None
        assert result["discoveries"]["new_state"] is None

        # Cells should be in revisits
        assert SAN_FRANCISCO["h3_res6"] in result["revisits"]["cells_res6"]
        assert SAN_FRANCISCO["h3_res8"] in result["revisits"]["cells_res8"]

    def test_second_cell_in_country_does_not_discover(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test that visiting a second cell in the same country doesn't rediscover country."""
        res6_result = {
            "h3_index": LOS_ANGELES["h3_res6"],
            "res": 6,
            "visit_count": 1,
            "is_new": True,
        }
        res8_result = {
            "h3_index": LOS_ANGELES["h3_res8"],
            "res": 8,
            "visit_count": 1,
            "is_new": True,
        }

        mock_country = Mock(spec=CountryRegion, id=1, name="United States", iso2="US")
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_country

        # Mock "other cells exist" query
        mock_db_session.execute.return_value.fetchone.return_value = Mock(
            h3_index=SAN_FRANCISCO["h3_res8"]  # User has other cells in USA
        )

        result = processor._build_response(
            res6_result=res6_result,
            res8_result=res8_result,
            country_id=1,
            state_id=None,
        )

        # Should NOT discover country (user already has cells there)
        assert result["discoveries"]["new_country"] is None

    def test_no_geography_no_discovery(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test that locations without geography don't trigger discoveries."""
        res6_result = {
            "h3_index": INTERNATIONAL_WATERS["h3_res6"],
            "res": 6,
            "visit_count": 1,
            "is_new": True,
        }
        res8_result = {
            "h3_index": INTERNATIONAL_WATERS["h3_res8"],
            "res": 8,
            "visit_count": 1,
            "is_new": True,
        }

        result = processor._build_response(
            res6_result=res6_result,
            res8_result=res8_result,
            country_id=None,
            state_id=None,
        )

        # No country or state discovery
        assert result["discoveries"]["new_country"] is None
        assert result["discoveries"]["new_state"] is None

        # But cells should still be discovered
        assert len(result["discoveries"]["new_cells_res6"]) == 1
        assert len(result["discoveries"]["new_cells_res8"]) == 1


# ============================================================================
# Audit Batch Tests
# ============================================================================

@pytest.mark.unit
class TestRecordIngestBatch:
    """Test the _record_ingest_batch method."""

    def test_records_batch_with_device(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test that IngestBatch is created with device_id."""
        processor._record_ingest_batch(device_id=1)

        # Verify IngestBatch was added
        mock_db_session.add.assert_called_once()
        batch = mock_db_session.add.call_args[0][0]

        assert isinstance(batch, IngestBatch)
        assert batch.user_id == 1
        assert batch.device_id == 1
        assert batch.cells_count == 2  # res-6 + res-8
        assert batch.res_min == 6
        assert batch.res_max == 8

    def test_records_batch_without_device(
        self, processor: LocationProcessor, mock_db_session: MagicMock
    ):
        """Test that IngestBatch is created without device_id."""
        processor._record_ingest_batch(device_id=None)

        mock_db_session.add.assert_called_once()
        batch = mock_db_session.add.call_args[0][0]

        assert batch.device_id is None
