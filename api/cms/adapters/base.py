# api/cms/adapters/base.py
"""
Base adapter — lazy import pattern for CMS ↔ other system communication.

Rule: CMS adapters NEVER import other systems at module load time.
      All cross-system imports are inside methods (lazy), so CMS can
      boot independently even if a sibling app is not installed.
"""
import logging
from typing import Any, Optional

logger = logging.getLogger('api.cms.adapters')


class AdapterUnavailableError(Exception):
    """Raised when the target system is not installed or not reachable."""


class BaseAdapter:
    """
    Common plumbing for all CMS outbound adapters.

    Subclasses implement the actual system calls.
    All public methods must:
      - Use lazy imports inside the method body
      - Catch ImportError and return a safe fallback (never crash)
      - Log warnings when a system is unavailable
    """

    _system_name: str = 'unknown'

    @classmethod
    def _unavailable(cls, method: str, fallback: Any = None) -> Any:
        logger.warning(
            "[CMS Adapter] %s.%s: system '%s' is not available — returning fallback.",
            cls.__name__, method, cls._system_name,
        )
        return fallback

    @classmethod
    def is_available(cls) -> bool:
        """Return True if the target system is importable."""
        try:
            cls._check_available()
            return True
        except (ImportError, Exception):
            return False

    @classmethod
    def _check_available(cls):
        """Subclasses override: attempt the minimal import to verify availability."""
        raise NotImplementedError
