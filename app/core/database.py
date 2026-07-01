"""
Database Connection and Session Management
Handles PostgreSQL connections using SQLAlchemy
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import logging

from .config import settings

logger = logging.getLogger(__name__)


def _build_connect_args() -> dict:
    """
    Build connect_args for psycopg2.

    On Render, DATABASE_URL already points to Render's managed PostgreSQL which
    requires SSL. When building from individual components we also require SSL.
    We only add keepalive + SSL args for direct psycopg2 connections; asyncpg
    (if ever used) has its own SSL handling.
    """
    return {
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
        "sslmode": "require",
        "connect_timeout": 10,
    }


# Create database engine with QueuePool (prevents connection exhaustion on Render free tier)
engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=5,           # Keep 5 persistent connections
    max_overflow=2,        # Allow up to 2 extra connections under burst
    pool_timeout=30,       # Wait up to 30s for a free connection
    pool_recycle=1800,     # Recycle connections every 30 min (avoids stale connections)
    pool_pre_ping=True,    # Test connection before using from pool (handles Render restarts)
    connect_args=_build_connect_args(),
    echo=settings.DB_ECHO,
    future=True,
)

# Session factory for creating database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)


def get_db():
    """
    FastAPI dependency for database sessions.
    
    Usage in routes:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            ...
    
    Automatically commits on success and rolls back on errors.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        logger.error(f"Database session error: {str(e)}")
        raise
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Context manager for database sessions in scripts and background tasks.
    
    Usage:
        with get_db_context() as db:
            user = db.query(User).first()
            # Changes are automatically committed
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database context error: {str(e)}")
        raise
    finally:
        db.close()


def check_db_connection() -> bool:
    """
    Verify database connectivity.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False


def close_db_connection():
    """Close all database connections in the pool."""
    engine.dispose()
    logger.info("Database connections closed")