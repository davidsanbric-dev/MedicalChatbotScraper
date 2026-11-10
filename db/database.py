"""Connection to the shared pipeline database, used only with --database.

The engine is created on first use, so writing JSON files needs no DATABASE_URL.
"""

import os
from functools import cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session


@cache
def _engine() -> Engine:
    return create_engine(os.environ["DATABASE_URL"])


def open_session() -> Session:
    """A new session; use it as `with open_session() as session:`."""
    return Session(_engine())
