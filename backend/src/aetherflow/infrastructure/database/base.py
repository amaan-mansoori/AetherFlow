"""SQLAlchemy declarative base for future domain models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class reserved for application models added in later phases."""
