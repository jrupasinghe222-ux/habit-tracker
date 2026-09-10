"""Habit Tracker API. Authentication and database are configured separately."""
from datetime import date, datetime, timedelta, timezone as utc_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.auth import current_user
from backend.database import user_session
from backend.models import Completion, Habit

app = FastAPI(title="Habit Tracker API", version="0.2.0")
User = Annotated[UUID, Depends(current_user)]


@app.middleware("http")
async def private_responses(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


class HealthResponse(BaseModel):
    status: str


@app.get("/api/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}


@app.get("/api/me")
def me(user_id: User):
    return {"id": str(user_id)}


def database(user_id: User):
    try:
        yield from user_session(user_id)
    except SQLAlchemyError:
        raise HTTPException(503, "Your data is temporarily unavailable. Please try again.") from None


Database = Annotated[Session, Depends(database, scope="function")]


class HabitInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class HabitOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str


@app.get("/api/habits", response_model=list[HabitOutput])
def list_habits(user_id: User, session: Database):
    return session.scalars(
        select(Habit).where(Habit.owner_id == user_id).order_by(Habit.created_at, Habit.id).limit(100)
    ).all()


@app.post("/api/habits", response_model=HabitOutput, status_code=201)
def create_habit(body: HabitInput, user_id: User, session: Database):
    habit = Habit(owner_id=user_id, name=body.name)
    session.add(habit)
    session.flush()
    return habit


@app.delete("/api/habits/{habit_id}", status_code=204)
def delete_habit(habit_id: UUID, user_id: User, session: Database):
    habit = session.scalar(select(Habit).where(Habit.id == habit_id, Habit.owner_id == user_id))
    if habit is None:
        raise HTTPException(404, "Habit not found.")
    session.delete(habit)
    session.flush()
    return Response(status_code=204)


@app.patch("/api/habits/{habit_id}", response_model=HabitOutput)
def update_habit(habit_id: UUID, body: HabitInput, user_id: User, session: Database):
    habit = session.scalar(select(Habit).where(Habit.id == habit_id, Habit.owner_id == user_id))
    if habit is None:
        raise HTTPException(404, "Habit not found.")
    habit.name = body.name
    session.flush()
    return habit


def current_date(timezone: str) -> date:
    if len(timezone) > 100:
        raise HTTPException(422, "Choose a valid timezone.")
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Choose a valid timezone.") from None
    return datetime.now(utc_timezone.utc).astimezone(zone).date()


@app.get("/api/today")
def today(user_id: User, session: Database, timezone: str = "UTC"):
    day = current_date(timezone)
    completed = session.scalars(select(Completion.habit_id).where(
        Completion.owner_id == user_id, Completion.completed_on == day,
    )).all()
    start = day - timedelta(days=6)
    # Match the current habit list's bounded, deterministic selection.
    visible = select(Habit.id).where(Habit.owner_id == user_id).order_by(Habit.created_at, Habit.id).limit(100)
    visible_habits = session.scalars(select(Habit).where(Habit.id.in_(visible))).all()
    rows = session.execute(select(Completion.completed_on, Completion.habit_id).where(
        Completion.owner_id == user_id, Completion.completed_on.between(start, day),
        Completion.habit_id.in_(visible),
    )).all()
    history = [{"date": start + timedelta(days=offset), "completed_ids": []} for offset in range(7)]
    for completed_on, habit_id in rows:
        history[(completed_on - start).days]["completed_ids"].append(habit_id)
    zone = ZoneInfo(timezone)
    for entry in history:
        available = set(entry["completed_ids"])
        for habit in visible_habits:
            created = habit.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=utc_timezone.utc)
            if created.astimezone(zone).date() <= entry["date"]:
                available.add(habit.id)
        entry["total"] = len(available)
    return {"date": day, "timezone": timezone, "completed_ids": completed, "history": history}


class CheckInInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date
    timezone: str = Field(min_length=1, max_length=100)
    completed: bool = Field(strict=True)


@app.put("/api/habits/{habit_id}/check-in")
def check_in(habit_id: UUID, body: CheckInInput, user_id: User, session: Database):
    if body.date != current_date(body.timezone):
        raise HTTPException(409, "The day has changed. Reload today's progress and try again.")
    habit = session.scalar(select(Habit).where(Habit.id == habit_id, Habit.owner_id == user_id))
    if habit is None:
        raise HTTPException(404, "Habit not found.")
    if body.completed:
        # A single atomic insert handles concurrent clicks/retries without duplicates.
        if session.get_bind().dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        session.execute(insert(Completion).values(
            habit_id=habit_id, owner_id=user_id, completed_on=body.date,
        ).on_conflict_do_nothing(index_elements=["habit_id", "completed_on"]))
    else:
        session.execute(delete(Completion).where(
            Completion.habit_id == habit_id, Completion.owner_id == user_id,
            Completion.completed_on == body.date,
        ))
    return {"habit_id": habit_id, "date": body.date, "completed": body.completed}
