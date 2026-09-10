"""Allow the application to update habit names only."""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # Existing ownership RLS policy also applies to UPDATE.
    op.execute("GRANT UPDATE (name) ON habit_app.habits TO habit_api")


def downgrade():
    op.execute("REVOKE UPDATE (name) ON habit_app.habits FROM habit_api")
