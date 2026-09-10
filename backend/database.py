"""Short-lived PostgreSQL sessions for Supabase transaction pooling."""
import os
from functools import lru_cache
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool


@lru_cache
def engine():
    raw_url = os.getenv("DATABASE_URL", "")
    if not raw_url:
        raise HTTPException(503, "Database is not configured.")
    url = make_url(raw_url).set(drivername="postgresql+psycopg")
    if not url.username or url.username.split(".")[0] != "habit_api":
        raise HTTPException(503, "Database requires the restricted application role.")
    return create_engine(
        url, poolclass=NullPool,
        connect_args={"sslmode": "require", "prepare_threshold": None, "connect_timeout": 5},
        hide_parameters=True,
    )


def user_session(user_id: UUID):
    with Session(engine()) as session:
        with session.begin():
            session.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id)})
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            yield session
