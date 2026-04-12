"""CORE_FILES/signals.py — Re-exports signal receivers (imported for side-effects)."""
# Importing signals registers them with Django's signal dispatcher.
from ..signals import *  # noqa: F401, F403
