"""Map endpoints for retrieving user's visited areas."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from schemas.map import (
    MapSummaryResponse,
    MapCellsResponse,
    MapPolygonsResponse,
    BoundingBox,
    LargeBoundingBox,
)
from services.auth import get_current_user
from services.map_service import MapService


router = APIRouter()


@router.get("/summary", response_model=MapSummaryResponse)
def get_map_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all countries and regions the user has visited.

    Returns a summary of visited locations for fog of war rendering.
    Frontend uses Mapbox's built-in boundary layers with these codes.
    """
    service = MapService(db, current_user.id)
    result = service.get_summary()

    return MapSummaryResponse(
        countries=[
            {"code": c["code"], "name": c["name"]}
            for c in result["countries"]
        ],
        regions=[
            {"code": r["code"], "name": r["name"]}
            for r in result["regions"]
        ],
    )


@router.get("/cells", response_model=MapCellsResponse)
def get_map_cells(
    min_lng: float,
    min_lat: float,
    max_lng: float,
    max_lat: float,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get H3 cells within the bounding box.

    Returns H3 cell indexes at resolutions 6 and 8 that the user
    has visited within the specified viewport.
    """
    # Validate bounding box
    try:
        bbox = BoundingBox(
            min_lng=min_lng,
            min_lat=min_lat,
            max_lng=max_lng,
            max_lat=max_lat,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.errors()[0]["msg"]),
        )

    service = MapService(db, current_user.id)
    result = service.get_cells_in_viewport(
        min_lng=bbox.min_lng,
        min_lat=bbox.min_lat,
        max_lng=bbox.max_lng,
        max_lat=bbox.max_lat,
    )

    return MapCellsResponse(res6=result["res6"], res8=result["res8"])


@router.get("/polygons", response_model=MapPolygonsResponse)
def get_map_polygons(
    min_lng: float,
    min_lat: float,
    max_lng: float,
    max_lat: float,
    zoom: Optional[float] = Query(
        None,
        description="Current map zoom level. Below 10 returns res-6 (larger cells), 10+ returns res-8 (smaller cells)",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get H3 cells as GeoJSON polygons within the bounding box.

    Returns a GeoJSON FeatureCollection with polygon geometries
    for each H3 cell the user has visited within the specified viewport.

    Resolution selection based on zoom:
    - zoom < 10: Returns res-6 cells (~3.2km hexagons)
    - zoom >= 10: Returns res-8 cells (~460m hexagons)
    """
    # Validate bounding box
    try:
        bbox = BoundingBox(
            min_lng=min_lng,
            min_lat=min_lat,
            max_lng=max_lng,
            max_lat=max_lat,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.errors()[0]["msg"]),
        )

    service = MapService(db, current_user.id)
    result = service.get_polygons_in_viewport(
        min_lng=bbox.min_lng,
        min_lat=bbox.min_lat,
        max_lng=bbox.max_lng,
        max_lat=bbox.max_lat,
        zoom=zoom,
    )

    return result


@router.get("/polygons/countries", response_model=MapPolygonsResponse)
def get_country_polygons(
    min_lng: float,
    min_lat: float,
    max_lng: float,
    max_lat: float,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get visited country geometries as GeoJSON polygons.

    Returns a GeoJSON FeatureCollection with country boundary polygons
    for countries the user has visited within the specified viewport.
    Best used at zoom levels < 4 for country-level fog of war.
    """
    try:
        bbox = LargeBoundingBox(
            min_lng=min_lng,
            min_lat=min_lat,
            max_lng=max_lng,
            max_lat=max_lat,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.errors()[0]["msg"]),
        )

    service = MapService(db, current_user.id)
    result = service.get_visited_country_polygons(
        min_lng=bbox.min_lng,
        min_lat=bbox.min_lat,
        max_lng=bbox.max_lng,
        max_lat=bbox.max_lat,
    )

    return result


@router.get("/polygons/states", response_model=MapPolygonsResponse)
def get_state_polygons(
    min_lng: float,
    min_lat: float,
    max_lng: float,
    max_lat: float,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get visited state/region geometries as GeoJSON polygons.

    Returns a GeoJSON FeatureCollection with state/province boundary polygons
    for states the user has visited within the specified viewport.
    Best used at zoom levels 4-6 for regional fog of war.
    """
    try:
        bbox = LargeBoundingBox(
            min_lng=min_lng,
            min_lat=min_lat,
            max_lng=max_lng,
            max_lat=max_lat,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.errors()[0]["msg"]),
        )

    service = MapService(db, current_user.id)
    result = service.get_visited_state_polygons(
        min_lng=bbox.min_lng,
        min_lat=bbox.min_lat,
        max_lng=bbox.max_lng,
        max_lat=bbox.max_lat,
    )

    return result
