import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./trekkr.db")

# Determine database type and set appropriate connection args
_is_sqlite = DATABASE_URL.startswith("sqlite")

# Create engine with database-specific options
engine = create_engine(
    DATABASE_URL,
    # check_same_thread is SQLite-specific (required for FastAPI's async handling)
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)


# Only register SpatiaLite loader for SQLite databases
if _is_sqlite:
    @event.listens_for(engine, "connect")
    def load_spatialite(dbapi_conn, connection_record):
        """Load SpatiaLite extension for geographic queries (optional)."""
        # Check if extension loading is supported
        if not hasattr(dbapi_conn, "enable_load_extension"):
            # Extension loading not supported by this Python/SQLite build
            return

        try:
            dbapi_conn.enable_load_extension(True)
            # Try common SpatiaLite library paths
            spatialite_paths = [
                "mod_spatialite",
                "mod_spatialite.so",
                "mod_spatialite.dylib",
                "/usr/lib/x86_64-linux-gnu/mod_spatialite.so",
                "/usr/local/lib/mod_spatialite.dylib",
                "/opt/homebrew/lib/mod_spatialite.dylib",
            ]
            for path in spatialite_paths:
                try:
                    dbapi_conn.load_extension(path)
                    break
                except Exception:
                    continue
        except (AttributeError, Exception):
            # Extension loading not supported or failed
            pass
        finally:
            try:
                dbapi_conn.enable_load_extension(False)
            except (AttributeError, Exception):
                pass


# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database sessions in FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_sqlite_session(db) -> bool:
    """Check if the database session is using SQLite."""
    return "sqlite" in str(db.bind.url) if db.bind else False


def init_db():
    """Initialize the database and create all tables."""
    # Import models here to ensure they're registered with Base
    from models import (  # noqa: F401
        Achievement,
        CountryRegion,
        Device,
        H3Cell,
        IngestBatch,
        StateRegion,
        User,
        UserAchievement,
        UserCellVisit,
        UserCountryStat,
        UserStateStat,
        UserStreak,
    )

    Base.metadata.create_all(bind=engine)

