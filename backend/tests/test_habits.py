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


def test_week_history_boundaries_empty_days_and_isolation(store, frozen_today):
    from datetime import date
    from backend.models import Completion
    engine, owner, other = store
    with Session(engine) as session:
        own = Habit(owner_id=owner, name="Read")
        private = Habit(owner_id=other, name="Private")
        session.add_all([own, private])
        session.flush()
        own_id = own.id
        for day in (3, 4, 7, 10, 11):
            session.add(Completion(habit_id=own.id, owner_id=owner, completed_on=date(2026, 9, day)))
        session.add(Completion(habit_id=private.id, owner_id=other, completed_on=date(2026, 9, 10)))
        session.commit()
    result = request("GET", "/api/today?timezone=Asia/Colombo").json()
    assert result["timezone"] == "Asia/Colombo"
    assert [day["date"] for day in result["history"]] == [f"2026-09-{day:02}" for day in range(4, 11)]
    assert [len(day["completed_ids"]) for day in result["history"]] == [1, 0, 0, 1, 0, 0, 1]
    assert all(day["completed_ids"] in ([], [str(own_id)]) for day in result["history"])
    assert result["completed_ids"] == [str(own_id)]
    request("PUT", f"/api/habits/{own_id}/check-in", {"date": "2026-09-10", "timezone": "UTC", "completed": False})
    assert request("GET", "/api/today").json()["history"][-1]["completed_ids"] == []


def test_week_history_crosses_year_and_includes_empty_days(store, monkeypatch):
    from datetime import date
    monkeypatch.setattr("backend.main.current_date", lambda zone: date(2027, 1, 2))
    days = request("GET", "/api/today").json()["history"]
    assert days[0]["date"] == "2026-12-27"
    assert days[-1]["date"] == "2027-01-02"
    assert len(days) == 7
    assert all(day["completed_ids"] == [] for day in days)


def test_daily_totals_use_creation_dates_not_busiest_day(store, frozen_today):
    from datetime import date, datetime, timezone
    from backend.models import Completion
    engine, owner, other = store
    with Session(engine) as session:
        habits = [Habit(owner_id=owner, name=f"Habit {n}", created_at=datetime(2026, 9, 10, tzinfo=timezone.utc)) for n in range(5)]
        session.add_all(habits)
        session.add(Habit(owner_id=other, name="Private", created_at=datetime(2026, 9, 1, tzinfo=timezone.utc)))
        session.flush()
        for habit in habits[:4]:
            session.add(Completion(owner_id=owner, habit_id=habit.id, completed_on=date(2026, 9, 10)))
        session.commit()
    history = request("GET", "/api/today?timezone=UTC").json()["history"]
    assert all(day["total"] == 0 for day in history[:-1])
    assert history[-1]["total"] == 5
    assert len(history[-1]["completed_ids"]) == 4


@pytest.fixture
def daily_seed(store, frozen_today):
    from datetime import datetime, timezone, date
    from backend.models import Completion
    engine, owner, other = store
    with Session(engine) as session:
        habit = Habit(owner_id=owner, name="Read", created_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
        session.add(habit)
        session.flush()
        task_id = str(habit.id)
        session.add(Completion(owner_id=owner, habit_id=habit.id, completed_on=date(2026, 9, 9)))
        session.commit()
    return task_id


def test_day_edit_complete_delete_do_not_change_other_dates(store, daily_seed):
    task_id = daily_seed
    assert request("GET", "/api/calendar?selected=2026-09-09").json()["tasks"][0]["completed"] is True
    path = f"/api/days/2026-09-09/tasks/{task_id}"
    assert request("PATCH", path, {"name": "Read a novel", "completed": False}).status_code == 200
    yesterday = request("GET", "/api/calendar?selected=2026-09-09").json()
    assert yesterday["tasks"] == [{"id": task_id, "name": "Read a novel", "completed": False}]
    today = request("GET", "/api/calendar?selected=2026-09-10").json()
    assert today["tasks"] == [{"id": task_id, "name": "Read", "completed": False}]
    assert request("DELETE", path).status_code == 204
    for _ in range(2):
        deleted = request("GET", "/api/calendar?selected=2026-09-09").json()
        assert deleted["tasks"] == []
        assert next(day for day in deleted["history"] if day["date"] == "2026-09-09")["total"] == 0
    assert len(request("GET", "/api/calendar?selected=2026-09-10").json()["tasks"]) == 1


def test_added_task_is_date_only_and_creation_retry_is_idempotent(store, daily_seed):
    task_id = str(uuid4())
    body = {"id": task_id, "name": "  Call dentist  "}
    for _ in range(2):
        assert request("POST", "/api/days/2026-09-08/tasks", body).status_code == 201
    selected = request("GET", "/api/calendar?selected=2026-09-08").json()
    assert len(selected["tasks"]) == 2
    assert selected["tasks"][-1]["name"] == "Call dentist"
    assert all(task["id"] != task_id for task in request("GET", "/api/calendar?selected=2026-09-09").json()["tasks"])
    assert request("PATCH", f"/api/days/2026-09-09/tasks/{task_id}", {"completed": True}).status_code == 404


def test_daily_tasks_are_private(store, daily_seed):
    _, _, other = store
    request("GET", "/api/calendar?selected=2026-09-09")
    app.dependency_overrides[current_user] = lambda: other
    assert request("GET", "/api/calendar?selected=2026-09-09").json()["tasks"] == []
    path = f"/api/days/2026-09-09/tasks/{daily_seed}"
    assert request("PATCH", path, {"name": "Stolen"}).status_code == 404
    assert request("PATCH", path, {"completed": True}).status_code == 404
    assert request("DELETE", path).status_code == 404


@pytest.mark.parametrize("body", [{"name": " "}, {"name": None}, {"completed": None}, {"completed": "true"}, {}, {"owner_id": str(uuid4())}, {"task_date": "2026-09-08"}])
def test_daily_task_validation(store, daily_seed, body):
    assert request("PATCH", f"/api/days/2026-09-09/tasks/{daily_seed}", body).status_code == 422


def test_daily_future_and_invalid_timezone_rejected(store, daily_seed):
    assert request("GET", "/api/calendar?selected=2026-09-11").status_code == 422
    assert request("POST", "/api/days/2026-09-11/tasks", {"id": str(uuid4()), "name": "Future"}).status_code == 422
    assert request("GET", "/api/calendar?selected=1999-12-31").status_code == 422


def test_daily_totals_preserve_completed_and_pending_snapshots(store, daily_seed):
    request("GET", "/api/calendar?selected=2026-09-09")
    request("POST", "/api/days/2026-09-09/tasks", {"id": str(uuid4()), "name": "Extra"})
    result = request("GET", "/api/calendar?selected=2026-09-10").json()
    yesterday, today = result["history"][-2:]
    assert yesterday["total"] == 2
    assert len(yesterday["completed_ids"]) == 1
    assert today["total"] == 1
    assert today["completed_ids"] == []


@pytest.mark.parametrize("selected", ["2026-09-09", "2026-09-02"])
def test_calendar_week_stays_anchored_to_today(store, daily_seed, selected):
    task_id = str(uuid4())
    assert request("POST", f"/api/days/{selected}/tasks", {"id": task_id, "name": "Dated task"}).status_code == 201
    result = request("GET", f"/api/calendar?selected={selected}").json()
    assert result["date"] == selected
    assert any(task["id"] == task_id for task in result["tasks"])
    assert [day["date"] for day in result["history"]] == [f"2026-09-{day:02}" for day in range(4, 11)]
    assert result["today"] == "2026-09-10"
    assert len(result["history"]) == 7


def test_existing_day_task_edit_skips_template_initialization(store, daily_seed):
    engine, _, _ = store
    request("GET", "/api/calendar?selected=2026-09-09")
    statements = []
    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(engine, "before_cursor_execute", record)
    try:
        response = request("PATCH", f"/api/days/2026-09-09/tasks/{daily_seed}", {"completed": False})
        assert response.status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert not any('INSERT' in statement.upper() for statement in statements)
    assert not any('FROM main.habits' in statement or 'FROM main.completions' in statement for statement in statements)
