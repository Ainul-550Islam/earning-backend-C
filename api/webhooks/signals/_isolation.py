"""Run webhook signal receivers inside a savepoint.

A webhook problem (missing table, bad attribute, ...) must never break or
poison the business transaction (wallet credit, withdrawal, ...) that fired
the signal. Errors are logged and swallowed.
"""
import functools
import logging

from django.db import transaction

logger = logging.getLogger("ainul.webhooks.signals")


def isolated_receiver(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            with transaction.atomic():
                return fn(*args, **kwargs)
        except Exception:
            logger.exception("webhook receiver %s failed (ignored)", getattr(fn, "__name__", fn))
            return None
    return wrapper
