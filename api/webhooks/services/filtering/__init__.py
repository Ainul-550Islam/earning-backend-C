"""Filtering Services Module

This module contains services for webhook filtering and payload transformation.
"""

# BUG FIX: see services/analytics/__init__.py for the full explanation -
# __all__ named these classes but nothing actually imported them, so
# `from ..services.filtering import X` resolved to the submodule, not the
# class, and every `X()` call site crashed with "'module' object is not
# callable".
from .EventRouter import EventRouter
from .FilterService import FilterService
from .PayloadTransformer import PayloadTransformer

# Export all filtering services for easy access
__all__ = [
    'FilterService',
    'PayloadTransformer',
    'EventRouter',
]