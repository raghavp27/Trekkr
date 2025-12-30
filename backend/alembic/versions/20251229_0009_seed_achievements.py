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
