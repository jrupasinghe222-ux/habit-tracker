"""Verify the development database without leaving test rows behind."""
from uuid import uuid4
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

def connect(url):
    return create_engine(
        make_url(url).set(drivername="postgresql+psycopg"),
        poolclass=NullPool, hide_parameters=True,
        connect_args={"sslmode": "require", "connect_timeout": 10, "prepare_threshold": None},
    )

def main():
    settings = dotenv_values(".env")
    admin = connect(settings["MIGRATION_DATABASE_URL"])
    runtime = connect(settings["DATABASE_URL"])
    with admin.connect() as c:
        user_id = c.scalar(text("SELECT id FROM auth.users ORDER BY created_at LIMIT 1"))
        if user_id is None:
            raise RuntimeError("Sign in once before running this check.")
        assert c.scalar(text("SELECT version_num FROM public.alembic_version")) == "0004"
        assert c.scalar(text("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='habit_app.habits'::regclass"))
        assert c.scalar(text("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='habit_app.completions'::regclass"))
        assert c.scalar(text("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='habit_app.day_tasks'::regclass"))
        for role in ("anon", "authenticated"):
            assert not c.scalar(text("SELECT has_schema_privilege(:role, 'habit_app', 'USAGE')"), {"role": role})
    habit_id, other_user = uuid4(), uuid4()
    with runtime.connect() as c:
        transaction = c.begin()
        try:
            assert c.scalar(text("SELECT current_user")) == "habit_api"
            assert not c.scalar(text("SELECT rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole FROM pg_roles WHERE rolname=current_user"))
            c.execute(text("SELECT set_config('app.user_id', :owner, true)"), {"owner": str(user_id)})
            c.execute(text("INSERT INTO habit_app.habits(id,owner_id,name) VALUES (:id,:owner,:name)"),
                      {"id": habit_id, "owner": user_id, "name": "Temporary isolation check"})
            assert c.scalar(text("SELECT count(*) FROM habit_app.habits WHERE id=:id"), {"id": habit_id}) == 1
            assert c.execute(text("UPDATE habit_app.habits SET name='Updated isolation check' WHERE id=:id"), {"id": habit_id}).rowcount == 1
            assert c.scalar(text("SELECT name FROM habit_app.habits WHERE id=:id"), {"id": habit_id}) == "Updated isolation check"
            c.execute(text("INSERT INTO habit_app.day_tasks(id, task_date, owner_id, name) VALUES (:id, CURRENT_DATE, :owner, 'Temporary daily task')"), {"id": habit_id, "owner": user_id})
            assert c.execute(text("UPDATE habit_app.day_tasks SET name='Edited daily task', completed=true, removed=true WHERE id=:id"), {"id": habit_id}).rowcount == 1
            completion_params = {"id": habit_id, "owner": user_id}
            for _ in range(2):
                c.execute(text("INSERT INTO habit_app.completions(habit_id,owner_id,completed_on) VALUES (:id,:owner,CURRENT_DATE) ON CONFLICT DO NOTHING"), completion_params)
            assert c.scalar(text("SELECT count(*) FROM habit_app.completions WHERE habit_id=:id"), {"id": habit_id}) == 1
            c.execute(text("SELECT set_config('app.user_id', :owner, true)"), {"owner": str(other_user)})
            assert c.scalar(text("SELECT count(*) FROM habit_app.completions WHERE habit_id=:id"), {"id": habit_id}) == 0
            assert c.execute(text("DELETE FROM habit_app.completions WHERE habit_id=:id"), {"id": habit_id}).rowcount == 0
            for forged_owner, expected in ((user_id, "42501"), (other_user, "23503")):
                try:
                    with c.begin_nested():
                        c.execute(text("INSERT INTO habit_app.completions(habit_id,owner_id,completed_on) VALUES (:id,:owner,CURRENT_DATE - 1)"), {"id": habit_id, "owner": forged_owner})
                except DBAPIError as error:
                    assert getattr(error.orig, "sqlstate", None) == expected
                else:
                    raise AssertionError("Completion ownership protection failed")
            assert c.scalar(text("SELECT count(*) FROM habit_app.day_tasks WHERE id=:id"), {"id": habit_id}) == 0
            assert c.execute(text("UPDATE habit_app.day_tasks SET name='Forbidden', completed=false, removed=false WHERE id=:id"), {"id": habit_id}).rowcount == 0
            try:
                with c.begin_nested():
                    c.execute(text("INSERT INTO habit_app.day_tasks(id, task_date, owner_id, name) VALUES (:id, CURRENT_DATE, :owner, 'Forged')"), {"id": uuid4(), "owner": user_id})
            except DBAPIError as error:
                assert getattr(error.orig, "sqlstate", None) == "42501"
            else:
                raise AssertionError("Daily task RLS allowed a forged owner")
            assert c.execute(text("UPDATE habit_app.habits SET name='Forbidden update' WHERE id=:id"), {"id": habit_id}).rowcount == 0
            assert c.scalar(text("SELECT count(*) FROM habit_app.habits WHERE id=:id"), {"id": habit_id}) == 0
            assert c.execute(text("DELETE FROM habit_app.habits WHERE id=:id"), {"id": habit_id}).rowcount == 0
            try:
                with c.begin_nested():
                    c.execute(text("INSERT INTO habit_app.habits(id,owner_id,name) VALUES (:id,:owner,:name)"),
                              {"id": uuid4(), "owner": user_id, "name": "Should be rejected"})
            except DBAPIError as error:
                assert getattr(error.orig, "sqlstate", None) == "42501"
            else:
                raise AssertionError("RLS allowed a forged owner")
            c.execute(text("SELECT set_config('app.user_id', :owner, true)"), {"owner": str(user_id)})
            assert c.execute(text("DELETE FROM habit_app.habits WHERE id=:id"), {"id": habit_id}).rowcount == 1
            assert c.scalar(text("SELECT count(*) FROM habit_app.completions WHERE habit_id=:id"), {"id": habit_id}) == 0
        finally:
            transaction.rollback()
    with admin.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM habit_app.habits WHERE id=:id"), {"id": habit_id}) == 0
    admin.dispose()
    runtime.dispose()
    print("PASS: migration, restricted role, private schema, own-row access, cross-user read/update/delete blocking, forged-owner blocking.")
    print("PASS: completion RLS, duplicate protection, forged ownership, cross-user read/delete blocking, cascade deletion.")
    print("PASS: daily task RLS, own-row edits, cross-user read/update blocking, forged owner rejection.")
    print("All temporary data rolled back.")

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Never print connection URLs, SQL parameters, user IDs, or credentials.
        print("Database verification failed:", type(error).__name__)
        print("SQLSTATE:", getattr(getattr(error, "orig", None), "sqlstate", None))
        raise SystemExit(1)
