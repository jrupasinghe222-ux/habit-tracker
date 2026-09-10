"""Create private habit storage and a restricted runtime role."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Deliberately fail if this app-specific role/schema already exists.
    # The role has no login until the owner sets its password separately.
    op.execute("CREATE ROLE habit_api NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS")
    op.execute("CREATE SCHEMA habit_app")
    op.execute("REVOKE ALL ON SCHEMA habit_app FROM PUBLIC, anon, authenticated")
    op.execute("GRANT USAGE ON SCHEMA habit_app TO habit_api")
    op.create_table(
        "habits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 80", name="habit_name_length"),
        sa.ForeignKeyConstraint(["owner_id"], ["auth.users.id"], ondelete="CASCADE"),
        schema="habit_app",
    )
    op.create_index("ix_habit_app_habits_owner_id", "habits", ["owner_id"], schema="habit_app")
    op.execute("REVOKE ALL ON habit_app.habits FROM PUBLIC, anon, authenticated")
    op.execute("GRANT SELECT, INSERT, DELETE ON habit_app.habits TO habit_api")
    op.execute("ALTER TABLE habit_app.habits ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE habit_app.habits FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY own_habits ON habit_app.habits TO habit_api
        USING (owner_id = nullif(current_setting('app.user_id', true), '')::uuid)
        WITH CHECK (owner_id = nullif(current_setting('app.user_id', true), '')::uuid)
    """)


def downgrade():
    # Destructive rollback: only run against disposable development data.
    op.drop_table("habits", schema="habit_app")
    op.execute("DROP SCHEMA habit_app")
    op.execute("DROP ROLE habit_api")
