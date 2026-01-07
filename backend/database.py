import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

# Database configuration
def get_database_url() -> str:
    """Get database URL, ensuring correct driver for PostgreSQL."""
    url = os.getenv("DATABASE_URL", "sqlite:///./trekkr.db")

    # Render provides postgresql:// but SQLAlchemy needs postgresql+psycopg2://
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return url

DATABASE_URL = get_database_url()

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
    if db is None:
        return False

    # `Session.bind` can be an Engine or a Connection depending on how the
    # session was constructed (tests often bind to a Connection for per-test
    # transactions). Prefer dialect name since it exists on both.
    bind = None
    try:
        if hasattr(db, "get_bind"):
            bind = db.get_bind()
        elif hasattr(db, "bind"):
            bind = db.bind
    except Exception:
        bind = getattr(db, "bind", None)

    if bind is None:
        return False

    dialect = getattr(bind, "dialect", None)
    dialect_name = getattr(dialect, "name", None)
    if dialect_name:
        return dialect_name == "sqlite"

    # Fallback: engines have `.url`; connections do not.
    url = getattr(bind, "url", None)
    return str(url).startswith("sqlite") if url is not None else False


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

