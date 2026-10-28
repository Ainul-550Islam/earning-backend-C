"""Batch Services Module

This module contains services for webhook batch processing and status tracking.
"""

# BUG FIX: see services/analytics/__init__.py for the full explanation -
# __all__ named these classes but nothing actually imported them, so
# `from ..services.batch import X` resolved to the submodule, not the class,
# and every `X()` call site crashed with "'module' object is not callable".
# BatchService is added here too - it has the exact same broken import
# pattern at 5 production call sites but wasn't even declared in __all__.
from .BatchDispatchService import BatchDispatchService
from .BatchService import BatchService
from .BatchStatusService import BatchStatusService

# Export all batch services for easy access
__all__ = [
    'BatchDispatchService',
    'BatchService',
    'BatchStatusService',
]