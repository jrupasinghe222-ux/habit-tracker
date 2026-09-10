from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, String, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Habit(Base):
    __tablename__ = "habits"
    __table_args__ = (
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 80", name="habit_name_length"),
        {"schema": "habit_app"},
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
