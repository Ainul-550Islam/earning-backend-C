"""
Small helpers for the few places that must build SQL from names (backup / restore /
data bridges). Values are always passed as parameters; only *identifiers* go through here.
"""
import re

_IDENTIFIER = re.compile(r'^[A-Za-z_][A-Za-z0-9_$]{0,62}$')


def safe_identifier(name, what='identifier'):
    """Return ``name`` unchanged if it is a plain SQL identifier, else raise ValueError."""
    if not isinstance(name, str) or not _IDENTIFIER.match(name):
        raise ValueError(f'Unsafe SQL {what}: {name!r}')
    return name


def quote_identifier(name, connection=None, what='identifier'):
    """Validate ``name`` and quote it for the given Django connection (default connection if omitted)."""
    safe_identifier(name, what)
    if connection is None:
        from django.db import connection as default_connection
        connection = default_connection
    return connection.ops.quote_name(name)
