# api/djoyalty/signals.py
"""
AUDIT FIX (v2) -- SHADOW FILE RESOLVED।

THIS FILE IS A COMPATIBILITY SHIM। DO NOT ADD LOGIC HERE।

Root cause:
  Python resolves `signals/` (the package) over `signals.py` (this flat
  file) when both exist in the same directory।  When apps.py runs
  `from . import signals`, it imports the PACKAGE -- this flat file is
  NEVER loaded, and any @receiver decorators written here are dead code।

  All six signal object definitions and all @receiver connections now
  live in signals/__init__.py (loaded correctly by AppConfig.ready())।

  This flat file is kept as a no-op shim so that:
    - Any IDE or `grep` search for `signals.py` finds a clear explanation
      instead of silent confusion।
    - Any external tool that tries to `from djoyalty.signals import X`
      imports from the package (Python resolution) and gets the real
      signal objects -- so this file's existence cannot cause regressions।

Action: this file may safely be deleted।  No runtime behaviour changes।
"""
# Re-export the signal objects from the package so that if Python somehow
# loads this flat file (it should not), callers still get real objects।
# Under normal Python module resolution, this import block is unreachable।
try:
    from .signals import (  # noqa: F401 -- re-export for IDE navigation
        points_earned,
        points_redeemed,
        tier_changed,
        badge_unlocked,
        cashout_approved,
        fraud_detected,
    )
except ImportError:
    # If circular import occurs at startup, fail silently।
    # The real signals in signals/__init__.py are the authoritative source।
    pass
