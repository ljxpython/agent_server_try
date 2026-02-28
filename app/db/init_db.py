from __future__ import annotations

from sqlalchemy.engine import Engine

from app.db.base import Base
from app.db import models  # noqa: F401


def create_core_tables(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)
