import os
from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from backend.config import supabase_url  # Loads .env without requiring auth configuration.
from backend.models import Base

url = os.getenv("MIGRATION_DATABASE_URL", "")
if not url:
    raise RuntimeError("Set MIGRATION_DATABASE_URL in the ignored root .env file.")
if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql+psycopg://", 1)

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=NullPool, hide_parameters=True,
                           connect_args={"sslmode": "require", "connect_timeout": 10})
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
