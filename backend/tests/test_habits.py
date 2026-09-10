"""API ownership tests; PostgreSQL RLS must also be verified against Supabase."""
import asyncio
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine
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
