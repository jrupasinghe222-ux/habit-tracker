"""Habit Tracker API. Authentication and database are configured separately."""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.auth import current_user
from backend.database import user_session
from backend.models import Habit

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
