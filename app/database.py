"""
Database configuration and session management using SQLAlchemy.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import config

# Create engine
engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in config.DATABASE_URL else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    from app import models  # Import models to register them
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized")
