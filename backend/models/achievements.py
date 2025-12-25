"""Achievements catalog and user unlocks."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class Achievement(Base):
    """Defines an unlockable achievement with flexible JSON criteria."""

    __tablename__ = "achievements"
    __table_args__ = (
        UniqueConstraint("code", name="uq_achievements_code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(String(512), nullable=True)
    criteria_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user_unlocks = relationship("UserAchievement", back_populates="achievement")


class UserAchievement(Base):
    """Join table recording when a user unlocked an achievement."""

    __tablename__ = "user_achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    achievement_id = Column(
        Integer,
        ForeignKey("achievements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unlocked_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", backref="achievements")
    achievement = relationship("Achievement", back_populates="user_unlocks")

