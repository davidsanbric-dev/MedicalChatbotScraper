"""Save each parsed page: as a raw_data row (--database) or as a JSON file.

Step 4, "Save the record", on https://medicalchatbot.demos.davieldev.com/scraper#record
"""

import json
from pathlib import Path
from typing import Protocol

from sqlalchemy import select

from db.database import open_session
from db.models import RawData

SOURCE_PREFIX = "medical_conditions:"  # raw_data.source = "medical_conditions:<slug>"


class PageStore(Protocol):
    def saved_slugs(self) -> set[str]:
        """Pages a previous run already saved, which this run skips."""
        ...

    def save(self, slug: str, page: dict) -> str:
        """Save one page and say where it went."""
        ...


class DatabaseStore:
    """One raw_data row per page. Saved pages are skipped, so a re-run only fills the gaps."""

    def saved_slugs(self) -> set[str]:
        with open_session() as session:
            sources = session.scalars(select(RawData.source).where(RawData.source.startswith(SOURCE_PREFIX)))
            return {source.removeprefix(SOURCE_PREFIX) for source in sources}

    def save(self, slug: str, page: dict) -> str:
        with open_session() as session, session.begin():
            row = RawData(content=page, source=f"{SOURCE_PREFIX}{slug}")
            session.add(row)
            session.flush()  # assigns row.id
            return f"raw_data (id {row.id})"


class JsonFileStore:
    """One <slug>.json file per page. Existing files are rewritten, not skipped."""

    def __init__(self, directory: Path):
        self.directory = directory

    def saved_slugs(self) -> set[str]:
        return set()

    def save(self, slug: str, page: dict) -> str:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{slug}.json"
        path.write_text(json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(path)
