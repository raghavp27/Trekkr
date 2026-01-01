"""Per-user visits and ingestion audit records."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, backref

from database import Base


class UserCellVisit(Base):
    """Tracks a user's ownership of an H3 cell plus revisit metadata."""

    __tablename__ = "user_cell_visits"
    __table_args__ = (
        UniqueConstraint("user_id", "h3_index", name="uq_user_cell"),
        Index("ix_user_cell_visits_user_res", "user_id", "res"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id = Column(
        Integer,
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    h3_index = Column(
        String(25),
        ForeignKey("h3_cells.h3_index", ondelete="CASCADE"),
        nullable=False,
        index=True,  # Added explicit index for FK lookups
    )
    res = Column(SmallInteger, nullable=False, index=True)
    first_visited_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_visited_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    visit_count = Column(Integer, default=1, nullable=False)

    cell = relationship("H3Cell", back_populates="user_visits")
    user = relationship("User", backref=backref("cell_visits", passive_deletes=True))
    device = relationship("Device", backref="cell_visits")


class IngestBatch(Base):
    """Audit record for each uploaded batch of visits."""

    __tablename__ = "ingest_batches"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id = Column(
        Integer,
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    cells_count = Column(Integer, nullable=False)
    res_min = Column(SmallInteger, nullable=True)
    res_max = Column(SmallInteger, nullable=True)

    user = relationship("User", backref=backref("ingest_batches", passive_deletes=True))
    device = relationship("Device", backref="ingest_batches")

