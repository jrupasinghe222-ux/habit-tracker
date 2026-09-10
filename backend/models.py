from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKeyConstraint, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Habit(Base):
    __tablename__ = "habits"
    __table_args__ = (
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 80", name="habit_name_length"),
        UniqueConstraint("id", "owner_id", name="habit_id_owner_unique"),
        {"schema": "habit_app"},
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Completion(Base):
    __tablename__ = "completions"
    __table_args__ = (
        ForeignKeyConstraint(["habit_id", "owner_id"], ["habit_app.habits.id", "habit_app.habits.owner_id"], ondelete="CASCADE"),
        {"schema": "habit_app"},
    )
    habit_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    completed_on: Mapped[date] = mapped_column(Date, primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DayTask(Base):
    __tablename__ = "day_tasks"
    __table_args__ = (CheckConstraint("length(trim(name)) BETWEEN 1 AND 80", name="day_task_name_length"), {"schema": "habit_app"})
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_date: Mapped[date] = mapped_column(Date, primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    removed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
