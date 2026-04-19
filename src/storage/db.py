"""
Database connection and session management for SQLite.

This module provides database connectivity using SQLAlchemy with SQLite,
including connection pooling, session management, and initialization utilities.
"""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import StaticPool

from src.storage.schema import Base
from src.core.logging import get_logger

logger = get_logger(__name__)


class Database:
    """
    Database connection manager for SQLite.

    Provides engine and session management with proper connection pooling
    and thread-safe session handling.
    """

    def __init__(
        self,
        db_path: str = "/data/db/competitor.db",
        echo: bool = False,
    ):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
            echo: Whether to echo SQL statements (for debugging)
        """
        self.db_path = Path(db_path)
        self.echo = echo
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[scoped_session] = None

    @property
    def engine(self) -> Engine:
        """Get or create database engine."""
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine

    @property
    def session_factory(self) -> scoped_session:
        """Get or create session factory."""
        if self._session_factory is None:
            self._session_factory = scoped_session(
                sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    bind=self.engine
                )
            )
        return self._session_factory

    def _create_engine(self) -> Engine:
        """
        Create SQLAlchemy engine with appropriate settings for SQLite.

        Returns:
            SQLAlchemy engine instance
        """
        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # SQLite connection URL
        database_url = f"sqlite:///{self.db_path}"

        # Create engine with SQLite-specific optimizations
        engine = create_engine(
            database_url,
            echo=self.echo,
            connect_args={
                "check_same_thread": False,  # Allow multi-threaded access
                "timeout": 30,  # 30 second timeout for locks
            },
            poolclass=StaticPool,  # Use static pool for SQLite
            pool_pre_ping=True,  # Verify connections before using
        )

        logger.info(
            "Database engine created",
            extra={"db_path": str(self.db_path)}
        )

        return engine

    def init_db(self) -> None:
        """
        Initialize database schema.

        Creates all tables if they don't exist.
        This is idempotent and safe to call multiple times.
        """
        logger.info("Initializing database schema")

        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database schema initialized successfully")
        except Exception as e:
            logger.error(
                "Failed to initialize database schema",
                extra={"error": str(e)},
                exc_info=True
            )
            raise

    def drop_all(self) -> None:
        """
        Drop all database tables.

        WARNING: This will delete all data. Use with caution.
        """
        logger.warning("Dropping all database tables")
        Base.metadata.drop_all(self.engine)

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope for database operations.

        This context manager handles session lifecycle, including:
        - Creating a new session
        - Committing on success
        - Rolling back on error
        - Closing the session

        Yields:
            SQLAlchemy session instance

        Example:
            >>> with db.session() as session:
            ...     session.add(HierarchyNode(...))
            ...     # Automatically commits on success, rolls back on error
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            logger.error(
                "Database operation failed, transaction rolled back",
                exc_info=True
            )
            raise
        finally:
            session.close()

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        if self._session_factory:
            self._session_factory.remove()
            self._session_factory = None

        if self._engine:
            self._engine.dispose()
            self._engine = None

        logger.info("Database connections closed")


# Global database instance
_db: Optional[Database] = None


def get_database(
    db_path: Optional[str] = None,
    echo: bool = False,
) -> Database:
    """
    Get global database instance.

    Args:
        db_path: Optional database path (uses default if not specified)
        echo: Whether to echo SQL statements

    Returns:
        Database instance
    """
    global _db

    if _db is None:
        if db_path is None:
            # Check environment variable or use default
            db_path = os.getenv(
                "DB_PATH",
                "/data/db/competitor.db"
            )

        _db = Database(db_path=db_path, echo=echo)

    return _db


def init_database(
    db_path: Optional[str] = None,
    echo: bool = False,
) -> Database:
    """
    Initialize database connection and create schema.

    Args:
        db_path: Optional database path
        echo: Whether to echo SQL statements

    Returns:
        Initialized database instance
    """
    db = get_database(db_path=db_path, echo=echo)
    db.init_db()
    return db


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Convenience function to get a database session.

    Yields:
        SQLAlchemy session instance

    Example:
        >>> with get_session() as session:
        ...     products = session.query(ProductCatalog).all()
    """
    db = get_database()
    with db.session() as session:
        yield session
