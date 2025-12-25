"""Aggregates for coverage and streak tracking."""

from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


class UserCountryStat(Base):
    """Per-user coverage rollup at country level."""

    __tablename__ = "user_country_stats"
    __table_args__ = (
        UniqueConstraint("user_id", "country_id", name="uq_user_country_stat"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    country_id = Column(
        Integer,
        ForeignKey("regions_country.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cells_visited = Column(Integer, nullable=False, default=0)
    coverage_pct = Column(Numeric(5, 2), nullable=False, default=0)
    first_visited_at = Column(DateTime, nullable=True)
    last_visited_at = Column(DateTime, nullable=True)

    user = relationship("User", backref="country_stats")
    country = relationship("CountryRegion")


class UserStateStat(Base):
    """Per-user coverage rollup at state/province level."""

    __tablename__ = "user_state_stats"
    __table_args__ = (
        UniqueConstraint("user_id", "state_id", name="uq_user_state_stat"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    state_id = Column(
        Integer,
        ForeignKey("regions_state.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cells_visited = Column(Integer, nullable=False, default=0)
    coverage_pct = Column(Numeric(5, 2), nullable=False, default=0)
    first_visited_at = Column(DateTime, nullable=True)
    last_visited_at = Column(DateTime, nullable=True)

    user = relationship("User", backref="state_stats")
    state = relationship("StateRegion")


class UserStreak(Base):
    """Stores current and longest streaks for quick reads."""

    __tablename__ = "user_streaks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    current_streak_days = Column(Integer, nullable=False, default=0)
    longest_streak_days = Column(Integer, nullable=False, default=0)
    current_streak_start = Column(Date, nullable=True)
    current_streak_end = Column(Date, nullable=True)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = relationship("User", backref="streak")

