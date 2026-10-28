"""Inbound Services Module

This module contains services for inbound webhook processing and verification.
"""

# BUG FIX: see services/analytics/__init__.py for the full explanation -
# __all__ named these classes but nothing actually imported them, so
# `from ..services.inbound import X` resolved to the submodule, not the
# class, and every `X()` call site crashed with "'module' object is not
# callable".
from .InboundEventRouter import InboundEventRouter
from .InboundWebhookService import InboundWebhookService
from .PayloadParser import PayloadParser
from .SignatureVerifier import SignatureVerifier

# Export all inbound services for easy access
__all__ = [
    'InboundWebhookService',
    'SignatureVerifier',
    'PayloadParser',
    'InboundEventRouter',
]