"""Habit Tracker API. Authentication and database are configured separately."""
from datetime import date, datetime, timedelta, timezone as utc_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.auth import current_user
from backend.database import user_session
from backend.models import Completion, DayTask, Habit

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


# Daily task endpoints supersede shared-habit operations in the date-based UI.
def day_lock(session: Session, user_id: UUID, day: date):
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                        {"key": f"{user_id}:{day.isoformat()}"})


def validate_day(day: date, timezone: str):
    now = current_date(timezone)
    if day > now:
        raise HTTPException(422, "Future dates cannot be changed.")
    if day < date(2000, 1, 1):
        raise HTTPException(422, "Choose a date on or after January 1, 2000.")
    return now


def day_tasks(session: Session, user_id: UUID, day: date, timezone: str):
    day_lock(session, user_id, day)
    # Existing recurring habits are defaults; a dated snapshot wins on every retry.
    templates = session.scalars(select(Habit).where(Habit.owner_id == user_id)
        .order_by(Habit.created_at, Habit.id).limit(100)).all()
    completed = set(session.scalars(select(Completion.habit_id).where(
        Completion.owner_id == user_id, Completion.completed_on == day)).all())
    if session.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    values = []
    for habit in templates:
        created = habit.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=utc_timezone.utc)
        if created.astimezone(ZoneInfo(timezone)).date() <= day or habit.id in completed:
            values.append(dict(id=habit.id, task_date=day, owner_id=user_id, name=habit.name,
                               completed=habit.id in completed, removed=False, created_at=habit.created_at))
    if values:
        session.execute(insert(DayTask).values(values).on_conflict_do_nothing(index_elements=["id", "task_date"]))
    return session.scalars(select(DayTask).where(DayTask.owner_id == user_id, DayTask.task_date == day,
        DayTask.removed.is_(False)).order_by(DayTask.created_at, DayTask.id)).all()


def day_output(task: DayTask):
    return {"id": task.id, "name": task.name, "completed": task.completed}


@app.get("/api/calendar")
def calendar(user_id: User, session: Database, timezone: str = "UTC", selected: date | None = None):
    now = current_date(timezone)
    selected = selected or now
    validate_day(selected, timezone)
    history = []
    tasks = []
    week = {now - timedelta(days=offset) for offset in range(7)}
    # Include an older selected date, keeping all locks in chronological order.
    for day in sorted(week | {selected}):
        rows = day_tasks(session, user_id, day, timezone)
        if day in week:
            history.append({"date": day, "total": len(rows), "completed_ids": [row.id for row in rows if row.completed]})
        if day == selected:
            tasks = [day_output(row) for row in rows]
    return {"date": selected, "today": now, "timezone": timezone, "tasks": tasks, "history": history}


class DayTaskInput(HabitInput):
    id: UUID


class DayTaskPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=80)
    completed: bool | None = Field(default=None, strict=True)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


@app.post("/api/days/{day}/tasks", status_code=201)
def add_day_task(day: date, body: DayTaskInput, user_id: User, session: Database, timezone: str = "UTC"):
    validate_day(day, timezone)
    rows = day_tasks(session, user_id, day, timezone)
    existing = session.scalar(select(DayTask).where(DayTask.id == body.id, DayTask.task_date == day, DayTask.owner_id == user_id))
    if existing:
        if existing.removed or existing.name != body.name:
            raise HTTPException(409, "This task request has already been used. Reload and try again.")
        return day_output(existing)
    if len(rows) >= 100:
        raise HTTPException(409, "A day can contain at most 100 tasks.")
    task = DayTask(id=body.id, task_date=day, owner_id=user_id, name=body.name, completed=False, removed=False)
    session.add(task)
    session.flush()
    return day_output(task)


def find_day_task(day: date, task_id: UUID, user_id: UUID, session: Session, timezone: str):
    validate_day(day, timezone)
    day_tasks(session, user_id, day, timezone)
    task = session.scalar(select(DayTask).where(DayTask.id == task_id, DayTask.task_date == day,
        DayTask.owner_id == user_id, DayTask.removed.is_(False)))
    if task is None:
        raise HTTPException(404, "Task not found on this day.")
    return task


@app.patch("/api/days/{day}/tasks/{task_id}")
def edit_day_task(day: date, task_id: UUID, body: DayTaskPatch, user_id: User, session: Database, timezone: str = "UTC"):
    if not body.model_fields_set or any(getattr(body, key) is None for key in body.model_fields_set):
        raise HTTPException(422, "Provide a task name or completion state.")
    task = find_day_task(day, task_id, user_id, session, timezone)
    if body.name is not None:
        task.name = body.name
    if body.completed is not None:
        task.completed = body.completed
    session.flush()
    return day_output(task)


@app.delete("/api/days/{day}/tasks/{task_id}", status_code=204)
def remove_day_task(day: date, task_id: UUID, user_id: User, session: Database, timezone: str = "UTC"):
    task = find_day_task(day, task_id, user_id, session, timezone)
    # Keep a dated tombstone so the default task is not recreated on next load.
    task.removed = True
    session.flush()
    return Response(status_code=204)
