# api/djoyalty/services/notification_service.py
"""
notification_service -- Canonical import path shim।

AUDIT FIX (v2 -- Import Ambiguity):
  Two valid import paths existed for NotificationService:
    from .services.NotificationService import NotificationService   # PascalCase
    from .services.notification_service import NotificationService  # snake_case

  Different files across the codebase used different paths।  If
  NotificationService.py is refactored and imports updated in some
  places, the snake_case alias path can silently resolve to a stale
  version if this file is not updated in sync।

  FIX: This file is now the CANONICAL import path।
  PascalCase path (services/NotificationService.py) remains the
  implementation file।  This shim ALWAYS re-exports from it।

  ALL new code should import via:
    from ..services.notification_service import NotificationService

  The PascalCase path is retained for backward compatibility only।

  TO UNIFY IMPORTS: run the following to find all import sites:
    grep -rn "from .NotificationService\\|from ..services.NotificationService" \
         api/djoyalty/ --include="*.py"
  Then update each to use `notification_service` (snake_case)।
"""
from .NotificationService import NotificationService  # noqa: F401

__all__ = ['NotificationService']
