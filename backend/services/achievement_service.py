"""Achievement service for checking and unlocking achievements."""

from datetime import datetime, timezone
from typing import List

from sqlalchemy import text
from sqlalchemy.orm import Session

from database import is_sqlite_session
from models.achievements import Achievement, UserAchievement


class AchievementService:
    """Service for evaluating and unlocking user achievements."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self._is_sqlite = is_sqlite_session(db)

    def check_and_unlock(self) -> List[Achievement]:
        """Check all achievements and unlock newly earned ones.

        IMPORTANT: This method does **not** commit the transaction. It will `flush()`
        new `UserAchievement` rows so they are visible within the current transaction,
        but the **caller owns the commit boundary** (e.g. `LocationProcessor`).

        Returns list of newly unlocked achievements (Achievement ORM objects).
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
                    unlocked_at=datetime.now(timezone.utc),
                )
                self.db.add(user_achievement)
                newly_unlocked.append(achievement)

        if newly_unlocked:
            # Flush so subsequent queries in the same transaction can see unlocks.
            # The caller (e.g., LocationProcessor) owns the final commit boundary.
            self.db.flush()

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
        # SQLite doesn't have PostGIS, so we skip hemisphere calculation in dev
        if self._is_sqlite:
            stats["hemispheres"] = 0
        else:
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
        # SQLite uses CAST(... AS REAL), PostgreSQL uses ::float
        if self._is_sqlite:
            result = self.db.execute(text("""
                SELECT MAX(coverage) as max_coverage
                FROM (
                    SELECT
                        hc.country_id,
                        CAST(COUNT(DISTINCT ucv.h3_index) AS REAL) / NULLIF(rc.land_cells_total_resolution8, 0) as coverage
                    FROM user_cell_visits ucv
                    JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                    JOIN regions_country rc ON hc.country_id = rc.id
                    WHERE ucv.user_id = :user_id AND ucv.res = 8
                      AND hc.country_id IS NOT NULL
                      AND rc.land_cells_total_resolution8 > 0
                    GROUP BY hc.country_id, rc.land_cells_total_resolution8
                ) sub
            """), {"user_id": self.user_id}).fetchone()
        else:
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
        if self._is_sqlite:
            result = self.db.execute(text("""
                SELECT MAX(coverage) as max_coverage
                FROM (
                    SELECT
                        hc.state_id,
                        CAST(COUNT(DISTINCT ucv.h3_index) AS REAL) / NULLIF(rs.land_cells_total_resolution8, 0) as coverage
                    FROM user_cell_visits ucv
                    JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                    JOIN regions_state rs ON hc.state_id = rs.id
                    WHERE ucv.user_id = :user_id AND ucv.res = 8
                      AND hc.state_id IS NOT NULL
                      AND rs.land_cells_total_resolution8 > 0
                    GROUP BY hc.state_id, rs.land_cells_total_resolution8
                ) sub
            """), {"user_id": self.user_id}).fetchone()
        else:
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
        result = self.db.execute(text("""
            SELECT
                a.code,
                a.name,
                a.description,
                TRUE as unlocked,
                ua.unlocked_at
            FROM achievements a
            INNER JOIN user_achievements ua
                ON a.id = ua.achievement_id
            WHERE ua.user_id = :user_id
            ORDER BY ua.unlocked_at DESC
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
