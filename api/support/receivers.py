# api/support/receivers.py
import logging
logger = logging.getLogger(__name__)

def connect_receivers():
    """Explicitly connect all receivers. Called from apps.py ready()."""
    from support import signals  # noqa
    logger.debug('Support receivers connected.')