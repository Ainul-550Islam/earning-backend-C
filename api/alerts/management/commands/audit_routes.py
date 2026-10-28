"""
python manage.py audit_routes [--module-prefix PREFIX]

Static audit of every URL pattern wired to a DRF ViewSet / view.  Finds the
class of bug that only shows up when a client hits the URL:

  MISSING-ACTION   the URLconf maps an action name the ViewSet class does not define
                   (e.g. as_view({'post': 'add_user'}) but no add_user method)
  KWARG-MISMATCH   the URL captures a kwarg (e.g. <int:pk>) that the handler's
                   signature cannot accept -> TypeError on every request

--module-prefix limits the report to views whose module starts with PREFIX
(e.g. api.tasks).  Exit status is 1 when anything is found.
"""
import inspect
import re

from django.core.management.base import BaseCommand
from django.urls import URLPattern, URLResolver, get_resolver


def _url_kwargs(pattern):
    names = set(re.findall(r'<(?:\w+:)?(\w+)>', str(pattern.pattern)))
    names |= set((pattern.default_args or {}).keys())
    return names


def _walk(patterns, prefix=''):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _walk(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern), p


def find_problems(module_prefix=None):
    """Return a sorted list of (kind, handler, detail, route)."""
    problems = set()
    for route, p in _walk(get_resolver().url_patterns):
        cb = p.callback
        cls = getattr(cb, 'cls', None)
        actions = getattr(cb, 'actions', None)
        module = (cls or cb).__module__ if (cls or hasattr(cb, '__module__')) else ''
        if module_prefix and not module.startswith(module_prefix):
            continue
        handlers = []
        if cls is not None and actions:
            for name in set(actions.values()):
                if not hasattr(cls, name):
                    problems.add(('MISSING-ACTION', f'{cls.__module__}.{cls.__name__}', name, route))
                else:
                    handlers.append((f'{cls.__name__}.{name}', getattr(cls, name)))
        elif cls is not None:
            for verb in ('get', 'post', 'put', 'patch', 'delete'):
                if hasattr(cls, verb):
                    handlers.append((f'{cls.__name__}.{verb}', getattr(cls, verb)))
        else:
            handlers.append((getattr(cb, '__name__', str(cb)), getattr(cb, '__wrapped__', cb)))
        wanted = _url_kwargs(p)
        for label, fn in handlers:
            try:
                params = inspect.signature(fn).parameters
            except (TypeError, ValueError):
                continue
            if any(v.kind == v.VAR_KEYWORD for v in params.values()):
                continue
            missing = sorted(k for k in wanted if k not in params)
            if missing:
                problems.add(('KWARG-MISMATCH', label, ','.join(missing), route))
    return sorted(problems)


class Command(BaseCommand):
    help = 'Audit URL patterns for missing ViewSet actions and URL-kwarg/signature mismatches.'

    def add_arguments(self, parser):
        parser.add_argument('--module-prefix', default=None,
                            help='Only report views whose module starts with this (e.g. api.alerts)')

    def handle(self, *args, **opts):
        problems = find_problems(opts['module_prefix'])
        for kind, handler, detail, route in problems:
            self.stdout.write(f'{kind:15} {handler} {detail}  <-  {route}')
        self.stdout.write(f'TOTAL PROBLEMS: {len(problems)}')
        if problems:
            raise SystemExit(1)
