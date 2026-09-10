"""API ownership tests; PostgreSQL RLS must also be verified against Supabase."""
import asyncio
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.auth import current_user
from backend.main import app, database
from backend.models import Base, Habit


@pytest.fixture
def store():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"habit_app": None}},
    )
    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    owner, other = uuid4(), uuid4()

    def test_database():
        with Session(engine) as session:
            with session.begin():
                yield session

    app.dependency_overrides[database] = test_database
    app.dependency_overrides[current_user] = lambda: owner
    yield engine, owner, other
    app.dependency_overrides.clear()
    engine.dispose()


def request(method, path, body=None):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, json=body)
    return asyncio.run(run())


def test_create_persist_list_delete(store):
    _, _, _ = store
    created = request("POST", "/api/habits", {"name": "  Read  "})
    assert created.status_code == 201
    row = created.json()
    assert row["name"] == "Read"
    assert request("GET", "/api/habits").json() == [row]
    assert request("DELETE", f"/api/habits/{row['id']}").status_code == 204
    assert request("GET", "/api/habits").json() == []


def test_other_users_data_is_invisible_and_cannot_be_deleted(store):
    engine, _, other = store
    with Session(engine) as session:
        habit = Habit(owner_id=other, name="Private habit")
        session.add(habit)
        session.commit()
        habit_id = habit.id
    assert request("GET", "/api/habits").json() == []
    assert request("DELETE", f"/api/habits/{habit_id}").status_code == 404
    with Session(engine) as session:
        assert session.get(Habit, habit_id) is not None


@pytest.mark.parametrize("body", [
    {"name": ""}, {"name": "    "}, {"name": "a" * 81},
    {"name": "Read", "owner_id": str(uuid4())},
    {"name": 42}, {},
])
def test_invalid_or_owner_injected_input_is_rejected(store, body):
    assert request("POST", "/api/habits", body).status_code == 422

def test_update_persists_name_without_changing_identity(store):
    created = request("POST", "/api/habits", {"name": "Read"}).json()
    response = request("PATCH", f"/api/habits/{created['id']}", {"name": "  Read 20 minutes  "})
    assert response.status_code == 200
    assert response.json() == {"id": created["id"], "name": "Read 20 minutes"}
    assert request("GET", "/api/habits").json() == [response.json()]


def test_cannot_update_another_users_habit(store):
    engine, _, other = store
    with Session(engine) as session:
        habit = Habit(owner_id=other, name="Private habit")
        session.add(habit)
        session.commit()
        habit_id = habit.id
    assert request("PATCH", f"/api/habits/{habit_id}", {"name": "Changed"}).status_code == 404
    with Session(engine) as session:
        assert session.get(Habit, habit_id).name == "Private habit"


@pytest.mark.parametrize("body", [{"name": "   "}, {"name": "x" * 81}, {"name": "Valid", "owner_id": str(uuid4())}])
def test_update_rejects_invalid_names_and_owner_changes(store, body):
    created = request("POST", "/api/habits", {"name": "Read"}).json()
    assert request("PATCH", f"/api/habits/{created['id']}", body).status_code == 422
    assert request("GET", "/api/habits").json() == [created]


def test_update_missing_habit_returns_404(store):
    assert request("PATCH", f"/api/habits/{uuid4()}", {"name": "Read"}).status_code == 404


@pytest.fixture
def frozen_today(monkeypatch):
    from datetime import date
    monkeypatch.setattr("backend.main.current_date", lambda zone: date(2026, 9, 10))


def test_check_in_retry_undo_and_history(store, frozen_today):
    from datetime import date
    from backend.models import Completion
    engine, owner, _ = store
    habit = request("POST", "/api/habits", {"name": "Walk"}).json()
    path = f"/api/habits/{habit['id']}/check-in"
    body = {"date": "2026-09-10", "timezone": "Asia/Colombo", "completed": True}
    for _ in range(2):
        assert request("PUT", path, body).status_code == 200
    assert request("GET", "/api/today").json()["completed_ids"] == [habit["id"]]
    with Session(engine) as session:
        assert len(session.query(Completion).all()) == 1
        session.add(Completion(habit_id=UUID(habit['id']), owner_id=owner, completed_on=date(2026, 9, 9)))
        session.commit()
    for _ in range(2):
        assert request("PUT", path, {**body, "completed": False}).status_code == 200
    assert request("GET", "/api/today").json()["completed_ids"] == []
    with Session(engine) as session:
        assert [row.completed_on for row in session.query(Completion).all()] == [date(2026, 9, 9)]
    assert request("DELETE", f"/api/habits/{habit['id']}").status_code == 204
    with Session(engine) as session:
        assert session.query(Completion).count() == 0


def test_other_user_cannot_read_check_in_or_undo(store, frozen_today):
    _, _, other = store
    habit = request("POST", "/api/habits", {"name": "Walk"}).json()
    path = f"/api/habits/{habit['id']}/check-in"
    body = {"date": "2026-09-10", "timezone": "Asia/Colombo", "completed": True}
    assert request("PUT", path, body).status_code == 200
    app.dependency_overrides[current_user] = lambda: other
    assert request("GET", "/api/today").json()["completed_ids"] == []
    for completed in (True, False):
        assert request("PUT", path, {**body, "completed": completed}).status_code == 404


@pytest.mark.parametrize("day", ["2026-09-09", "2026-09-11"])
def test_stale_or_future_check_ins_rejected(store, frozen_today, day):
    habit = request("POST", "/api/habits", {"name": "Walk"}).json()
    assert request("PUT", f"/api/habits/{habit['id']}/check-in", {
        "date": day, "timezone": "UTC", "completed": True,
    }).status_code == 409


@pytest.mark.parametrize("change", [{"owner_id": str(uuid4())}, {"completed": "true"}, {"date": "bad-date"}])
def test_check_in_input_validation(store, frozen_today, change):
    assert request("PUT", f"/api/habits/{uuid4()}/check-in", {
        "date": "2026-09-10", "timezone": "UTC", "completed": True, **change,
    }).status_code == 422


@pytest.mark.parametrize("zone", ["MadeUp/Timezone", "../UTC", ""])
def test_invalid_timezone_rejected(store, zone):
    assert request("GET", f"/api/today?timezone={zone}").status_code == 422


def test_timezone_dates_and_dst(monkeypatch):
    from datetime import datetime, timezone, date
    from backend.main import current_date
    class Clock:
        instant = datetime(2026, 9, 10, 20, 0, tzinfo=timezone.utc)
        @classmethod
        def now(cls, zone):
            return cls.instant.astimezone(zone)
    monkeypatch.setattr("backend.main.datetime", Clock)
    assert current_date("Asia/Colombo") == date(2026, 9, 11)
    assert current_date("America/Los_Angeles") == date(2026, 9, 10)
    # Spring-forward jumps an hour, without changing the calendar day.
    for hour in (6, 7):
        Clock.instant = datetime(2026, 3, 8, hour, 30, tzinfo=timezone.utc)
        assert current_date("America/New_York") == date(2026, 3, 8)
