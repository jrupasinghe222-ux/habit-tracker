"""Independent task records for each calendar date."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("day_tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("task_date", sa.Date(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("removed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 80", name="day_task_name_length"),
        sa.ForeignKeyConstraint(["owner_id"], ["auth.users.id"], ondelete="CASCADE"),
        schema="habit_app")
    op.create_index("ix_day_tasks_owner_date", "day_tasks", ["owner_id", "task_date"], schema="habit_app")
    op.execute("REVOKE ALL ON habit_app.day_tasks FROM PUBLIC, anon, authenticated")
    op.execute("GRANT SELECT, INSERT ON habit_app.day_tasks TO habit_api")
    op.execute("GRANT UPDATE (name, completed, removed) ON habit_app.day_tasks TO habit_api")
    op.execute("ALTER TABLE habit_app.day_tasks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE habit_app.day_tasks FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY own_day_tasks ON habit_app.day_tasks TO habit_api
        USING (owner_id = nullif(current_setting('app.user_id', true), '')::uuid)
        WITH CHECK (owner_id = nullif(current_setting('app.user_id', true), '')::uuid)""")


def downgrade():
    # Destructive: daily edits cannot be represented in the older shared habit model.
    op.drop_table("day_tasks", schema="habit_app")
