import pytest

@pytest.fixture(autouse=True)
def _no_fk(db):
    from django.db import connection
    if connection.vendor == 'sqlite':
        with connection.cursor() as cur:
            cur.execute('PRAGMA foreign_keys = OFF;')
