"""Store private daily completions with duplicate and ownership protection."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("habit_id_owner_unique", "habits", ["id", "owner_id"], schema="habit_app")
    op.create_table(
        "completions",
        sa.Column("habit_id", sa.Uuid(), primary_key=True),
        sa.Column("completed_on", sa.Date(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["habit_id", "owner_id"], ["habit_app.habits.id", "habit_app.habits.owner_id"], ondelete="CASCADE"),
        schema="habit_app",
    )
    op.create_index("ix_completion_owner_date", "completions", ["owner_id", "completed_on"], schema="habit_app")
    op.execute("REVOKE ALL ON habit_app.completions FROM PUBLIC, anon, authenticated")
    op.execute("GRANT SELECT, INSERT, DELETE ON habit_app.completions TO habit_api")
    op.execute("ALTER TABLE habit_app.completions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE habit_app.completions FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY own_completions ON habit_app.completions TO habit_api
        USING (owner_id = nullif(current_setting('app.user_id', true), '')::uuid)
        WITH CHECK (owner_id = nullif(current_setting('app.user_id', true), '')::uuid)
    """)


def downgrade():
    # Destructive: deletes completion history. Do not use to roll back application code.
    op.drop_table("completions", schema="habit_app")
    op.drop_constraint("habit_id_owner_unique", "habits", schema="habit_app", type_="unique")
