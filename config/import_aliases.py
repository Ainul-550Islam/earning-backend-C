"""
Legacy bare module names → api.* package aliases.

Many sub-apps were written against short names like `offer_routing`,
`alerts`, and `publisher_tools`. Register import aliases so those paths
resolve to the installed `api.*` packages without duplicating code.
"""
from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys

_ALIASES = {
    'offer_routing': 'api.offer_routing',
    'alerts': 'api.alerts',
    'publisher_tools': 'api.publisher_tools',
}


class _ApiPackageAliasLoader(importlib.abc.Loader):
    def __init__(self, real_name: str):
        self.real_name = real_name

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        real_module = importlib.import_module(self.real_name)
        module.__dict__.update(real_module.__dict__)
        module.__name__ = module.__spec__.name
        if getattr(real_module, '__file__', None):
            module.__file__ = real_module.__file__
        if getattr(real_module, '__path__', None):
            module.__path__ = real_module.__path__
        sys.modules[module.__spec__.name] = real_module


class _ApiPackageAliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        for alias, real_prefix in _ALIASES.items():
            if fullname == alias:
                return importlib.util.spec_from_loader(
                    fullname,
                    _ApiPackageAliasLoader(real_prefix),
                )
            if fullname.startswith(f'{alias}.'):
                suffix = fullname[len(alias):]
                return importlib.util.spec_from_loader(
                    fullname,
                    _ApiPackageAliasLoader(real_prefix + suffix),
                )
        return None


def install_import_aliases() -> None:
    if not any(isinstance(finder, _ApiPackageAliasFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _ApiPackageAliasFinder())
