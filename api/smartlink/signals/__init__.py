"""
SmartLink Signals package __init__.py
Registers ALL signal handlers when imported by SmartLinkConfig.ready().

Previously this file was empty, so apps.py's
  import api.smartlink.signals
loaded THIS empty file (Python prefers packages over .py modules)
and zero signal handlers were ever connected.

Fix: import all sub-modules here so every handler registers on startup.
"""
from .smartlink_signals import *   # noqa: F401, F403
from .click_signals import *       # noqa: F401, F403
from .conversion_signals import *  # noqa: F401, F403
from .fraud_signals import *       # noqa: F401, F403
from .offer_signals import *       # noqa: F401, F403
from .ab_test_signals import *     # noqa: F401, F403
from .domain_signals import *      # noqa: F401, F403
