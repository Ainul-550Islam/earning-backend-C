"""
tests/test_route_audit.py -- breadth-first regression net for the alerts URL surface.

  * every URL -> ViewSet action mapping resolves to a real method
  * every URL kwarg (<int:pk> ...) is accepted by its handler
  * every (route, HTTP method), hit as a superuser with an empty DB / empty body,
    answers with something other than a 5xx.  404/400/403/405 are all fine; a 5xx
    means an exception escaped or was swallowed into a "500" response.

Scoped to THIS package's views, so unrelated apps in the host project don't matter.
"""
import re
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from api.alerts.management.commands.audit_routes import find_problems

PKG = __name__.rsplit('.tests', 1)[0]          # 'alerts' standalone, 'api.alerts' when installed
_CONV = {'int': '1', 'uuid': str(uuid.uuid4()), 'str': 'x', 'slug': 'x', 'path': 'x'}


def _routes():
    def walk(patterns, prefix=''):
        for p in patterns:
            if isinstance(p, URLResolver):
                yield from walk(p.url_patterns, prefix + str(p.pattern))
            elif isinstance(p, URLPattern):
                yield prefix + str(p.pattern), p.callback
    for route, cb in walk(get_resolver().url_patterns):
        mod = (getattr(cb, 'cls', None) or cb).__module__
        if mod.startswith(PKG + '.') or mod == PKG:
            yield route, cb


def _methods(cb):
    acts = getattr(cb, 'actions', None)
    if acts:
        return [m.upper() for m in acts]
    cls = getattr(cb, 'cls', None)
    if cls is not None:
        return [m.upper() for m in ('get', 'post', 'put', 'patch', 'delete') if hasattr(cls, m)]
    return ['GET', 'POST']


def test_every_route_maps_to_a_real_handler_with_matching_kwargs():
    problems = find_problems(PKG)
    assert not problems, '\n'.join(' '.join(map(str, p)) for p in problems)


@pytest.mark.django_db
def test_no_route_returns_5xx(admin_user):
    client = APIClient(raise_request_exception=False)
    client.force_authenticate(user=admin_user)
    bad, total = [], 0
    for route, cb in _routes():
        path = '/' + re.sub(r'<(?:(\w+):)?\w+>', lambda m: _CONV.get(m.group(1) or 'str', 'x'), route).lstrip('/')
        for method in _methods(cb):
            total += 1
            try:
                if method in ('GET', 'DELETE'):
                    resp = getattr(client, method.lower())(path)
                else:
                    resp = getattr(client, method.lower())(path, data={}, format='json')
            except Exception as exc:                      # noqa: BLE001 - report, don't stop
                bad.append(f'{method} {path} raised {type(exc).__name__}: {exc}')
                continue
            if resp.status_code >= 500:
                bad.append(f'{method} {path} -> {resp.status_code}')
    assert total > 300, f'sweep only found {total} (route, method) pairs - URL discovery broke'
    assert not bad, f'{len(bad)}/{total} server errors:\n' + '\n'.join(bad)
