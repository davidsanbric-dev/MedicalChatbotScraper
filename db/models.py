"""The one table the scraper writes.

A mirror of medical_conditions_api/app/core/models.py: the API owns the schema
and creates every table at startup. All tables and how they link:
https://medicalchatbot.demos.davieldev.com/database#schema
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RawData(Base):
    """One scraped page, stored exactly as parsed."""

    __tablename__ = "raw_data"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source: Mapped[str]  # "medical_conditions:<slug>"
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
