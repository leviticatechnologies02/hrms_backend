"""
Database Connection and Session Management
Handles PostgreSQL connections using SQLAlchemy
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
import logging

from .config import settings

logger = logging.getLogger(__name__)


def _get_database_url() -> str:
    """
    Get the database URL, ensuring sslmode=require is in the URL itself
    (Render PostgreSQL requires SSL for both internal and external connections).
    """
    url = settings.database_url
    # Append sslmode=require to the URL if not already present
    if "sslmode" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}sslmode=require"
    return url


# Create database engine with NullPool
# NullPool creates a fresh connection per request and closes it immediately after.
# This avoids stale/pooled connection issues on Render's managed PostgreSQL proxy.
engine = create_engine(
    _get_database_url(),
    poolclass=NullPool,
    connect_args={
        "connect_timeout": 30,     # Allow 30s for cold-start connections on Render free tier
    },
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