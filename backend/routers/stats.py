"""Stats endpoints for retrieving user travel statistics."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Literal

from database import get_db
from models.user import User
from schemas.stats import CountriesStatsResponse, RegionsStatsResponse
from services.auth import get_current_user
from services.stats_service import StatsService


router = APIRouter()


@router.get("/countries", response_model=CountriesStatsResponse)
def get_countries_stats(
    sort_by: Literal["coverage_pct", "first_visited_at", "last_visited_at", "name"] = Query(
        default="last_visited_at",
        description="Field to sort by",
    ),
    order: Literal["asc", "desc"] = Query(
        default="desc",
        description="Sort order",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of results",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Pagination offset",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all countries the user has visited with coverage statistics.

    Returns country codes, names, coverage percentages, and visit timestamps.
    Supports sorting and pagination.
    """
    service = StatsService(db, current_user.id)
    result = service.get_countries(
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )

    return CountriesStatsResponse(
        total_countries_visited=result["total_countries_visited"],
        countries=result["countries"],
    )


@router.get("/regions", response_model=RegionsStatsResponse)
def get_regions_stats(
    sort_by: Literal["coverage_pct", "first_visited_at", "last_visited_at", "name"] = Query(
        default="last_visited_at",
        description="Field to sort by",
    ),
    order: Literal["asc", "desc"] = Query(
        default="desc",
        description="Sort order",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of results",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Pagination offset",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all regions/states the user has visited with coverage statistics.

    Returns region codes, names, parent country info, coverage percentages,
    and visit timestamps. Supports sorting and pagination.
    """
    service = StatsService(db, current_user.id)
    result = service.get_regions(
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )

    return RegionsStatsResponse(
        total_regions_visited=result["total_regions_visited"],
        regions=result["regions"],
    )
