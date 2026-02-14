"""DeclarativeBase for all ORM models."""

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    New provenance/compliance models use mapped_column style.
    Legacy tables in cortex.db.tables remain as Table() definitions.
    """

    type_annotation_map = {
        dict: JSONB,
    }
