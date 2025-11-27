from __future__ import with_statement
import sys
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from flask import current_app

# this Alembic Config object, which provides access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
fileConfig(config.config_file_name)

# Acquire target metadata from Flask-SQLAlchemy via Flask app context (works with Flask-Migrate)
try:
    target_metadata = current_app.extensions['migrate'].db.metadata
except Exception:
    target_metadata = None

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = current_app.config.get("SQLALCHEMY_DATABASE_URI")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = current_app.extensions['migrate'].db.get_engine()
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()