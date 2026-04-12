"""
api/ai_engine/MIGRATIONS/env.py
================================
Alembic migrations environment।
"""
from alembic import context
from django.conf import settings

target_metadata = None

def run_migrations_offline():
    context.configure(url=settings.DATABASES["default"]["URL"])
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    from django.db import connections
    connection = connections["default"]
    with connection.schema_editor() as schema_editor:
        context.configure(connection=connection.connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
