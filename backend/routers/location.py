"""Location ingestion API endpoint."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
import h3

from database import get_db
from models.user import User
from schemas.location import LocationIngestRequest, LocationIngestResponse, BatchLocationIngestRequest, BatchLocationIngestResponse, SimpleLocationIngestRequest
from services.auth import get_current_user
from services.location_processor import LocationProcessor


logger = logging.getLogger(__name__)


def get_user_id_from_request(request: Request) -> str:
    """Extract user ID for rate limiting key."""
    # During rate limit check, user may not be authenticated yet
    # Fall back to IP address if no user context
    if hasattr(request.state, "user_id"):
        return str(request.state.user_id)
    return get_remote_address(request)


limiter = Limiter(key_func=get_user_id_from_request)
router = APIRouter()


@router.post("/ingest", response_model=LocationIngestResponse)
@limiter.limit("120/minute")
def ingest_location(
    request: Request,
    payload: LocationIngestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Ingest a location update and record H3 cell visits.

    The client should send this request when the user moves to a new H3 res-8 cell.
    The server will:
    1. Derive the parent res-6 cell
    2. Perform reverse geocoding to find country/state
    3. Record visits for both resolutions
    4. Return discovery summary (new vs. revisited entities)

    Rate limit: 120 requests per minute per user.
    """
    # Store user_id in request state for rate limiting
    request.state.user_id = current_user.id

    # Validate H3 index matches coordinates (with neighbor tolerance for GPS jitter)
    expected_h3 = h3.latlng_to_cell(payload.latitude, payload.longitude, 8)
    if payload.h3_res8 != expected_h3:
        # Check if it's a neighbor (handles GPS jitter at cell boundaries)
        neighbors = h3.grid_ring(expected_h3, 1)
        if payload.h3_res8 not in neighbors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "h3_mismatch",
                    "message": "H3 index does not match coordinates",
                    "expected": expected_h3,
                    "received": payload.h3_res8,
                },
            )

    # Process the location
    processor = LocationProcessor(db, current_user.id)

    try:
        result = processor.process_location(
            latitude=payload.latitude,
            longitude=payload.longitude,
            h3_res8=payload.h3_res8,
            device_uuid=payload.device_uuid,
            device_name=payload.device_name,
            platform=payload.platform,
            timestamp=payload.timestamp,
        )
        return result
    except Exception as e:
        db.rollback()
        logger.exception("Location processing failed for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        )


@router.post("/ingest/batch", response_model=BatchLocationIngestResponse)
@limiter.limit("30/minute")
def ingest_location_batch(
    request: Request,
    payload: BatchLocationIngestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Ingest a batch of locations (up to 100) efficiently.

    Use this endpoint for:
    - Syncing locations collected while offline
    - Batching real-time location updates (every 5-10 minutes)

    **Partial success**: Invalid locations are skipped with reasons,
    valid locations are always processed.

    **Rate limit**: 30 requests per minute per user.

    For >100 locations, client should chunk into multiple requests.
    """
    # Store user_id in request state for rate limiting
    request.state.user_id = current_user.id

    # Process the batch
    processor = LocationProcessor(db, current_user.id)

    try:
        result = processor.process_batch(
            locations=payload.locations,
            device_uuid=payload.device_uuid,
            device_name=payload.device_name,
            platform=payload.platform,
        )
        return result
    except Exception as e:
        db.rollback()
        logger.exception("Batch location processing failed for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        )


@router.post("/ingest/simple", response_model=LocationIngestResponse)
@limiter.limit("120/minute")
def ingest_location_simple(
    request: Request,
    payload: SimpleLocationIngestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Simplified location ingestion - backend computes H3 index.

    Use this endpoint when the client cannot compute H3 indexes
    (e.g., React Native without h3-js support).

    Rate limit: 120 requests per minute per user.
    """
    # Store user_id in request state for rate limiting
    request.state.user_id = current_user.id

    # Compute H3 index on the server
    h3_res8 = h3.latlng_to_cell(payload.latitude, payload.longitude, 8)

    # Process the location
    processor = LocationProcessor(db, current_user.id)

    try:
        result = processor.process_location(
            latitude=payload.latitude,
            longitude=payload.longitude,
            h3_res8=h3_res8,
            device_uuid=payload.device_uuid,
            device_name=payload.device_name,
            platform=payload.platform,
            timestamp=payload.timestamp,
        )
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "service_unavailable", "message": str(e)},
        )
