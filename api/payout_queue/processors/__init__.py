"""
payout_queue/processors/__init__.py

Exports all 5 gateway processors.
Callers can write:
    from api.payout_queue.processors import BkashProcessor
instead of drilling into submodules.

Processor map used by services._get_processor():
    BKASH  → BkashProcessor
    NAGAD  → NagadProcessor
    ROCKET → RocketProcessor
    BANK   → BankProcessor
    MANUAL → ManualProcessor
"""
from .bkash  import BkashProcessor
from .nagad  import NagadProcessor
from .rocket import RocketProcessor
from .bank   import BankProcessor
from .manual import ManualProcessor

__all__ = [
    "BkashProcessor",
    "NagadProcessor",
    "RocketProcessor",
    "BankProcessor",
    "ManualProcessor",
]
