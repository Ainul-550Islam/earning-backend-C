# cms/INTEGRATION_SYSTEM/integ_registry.py
"""
CMS Integration Registry — service locator pattern.
Maps named capabilities to their implementing class paths.
Allows apps.py to register services once; consumers resolve lazily.
"""
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger('cms.integration.registry')

_registry: Dict[str, Dict[str, Any]] = {}


class CMSRegistry:
    """
    Lightweight service registry.
    Thread-safe for read (dict lookup); write only at startup.
    """

    @classmethod
    def register(cls, name: str, path: str,
                 capabilities: Optional[List[str]] = None,
                 metadata: Optional[Dict] = None) -> None:
        """Register a named service with its import path and capabilities."""
        _registry[name] = {
            'path': path,
            'capabilities': capabilities or [],
            'metadata': metadata or {},
            'instance': None,
        }
        logger.debug(f'[CMSRegistry] Registered: {name} → {path}')

    @classmethod
    def resolve(cls, name: str) -> Optional[Any]:
        """
        Lazily import and return the registered service.
        Caches the imported object on first call.
        Returns None (never raises) if the service is unavailable.
        """
        entry = _registry.get(name)
        if not entry:
            logger.warning(f'[CMSRegistry] Unknown service: {name}')
            return None
        if entry['instance'] is None:
            try:
                module_path, attr = entry['path'].rsplit('.', 1)
                import importlib
                mod = importlib.import_module(module_path)
                entry['instance'] = getattr(mod, attr)
            except Exception as e:
                logger.warning(f'[CMSRegistry] Cannot resolve {name}: {e}')
                return None
        return entry['instance']

    @classmethod
    def status(cls) -> Dict[str, Any]:
        """Return a health snapshot of the registry."""
        return {
            'registered': list(_registry.keys()),
            'count': len(_registry),
            'resolved': [k for k, v in _registry.items() if v['instance'] is not None],
        }

    @classmethod
    def get_capabilities(cls, name: str) -> List[str]:
        return _registry.get(name, {}).get('capabilities', [])

    @classmethod
    def has(cls, name: str) -> bool:
        return name in _registry

    @classmethod
    def all_names(cls) -> List[str]:
        return list(_registry.keys())

    @classmethod
    def clear(cls) -> None:
        """Used in tests only — clears all registrations."""
        _registry.clear()
