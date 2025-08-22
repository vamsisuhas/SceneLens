"""Database connection and session management."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://scenelens:scenelens_dev@localhost:5432/scenelens"
)

# Create engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db_session():
    """Get a database session for scripts."""
    return SessionLocal()
