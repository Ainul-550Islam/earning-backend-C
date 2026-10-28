"""
tests/test_full_endpoint_sweep.py — NEW

Systematically fires a real GET request at every registered list-level URL
in alerts.urls (the actual ROOT_URLCONF, and now also what api/alerts/urls.py
delegates to after removing the stale, partial router that used to live at
api/alerts/routes.py), authenticated as a superuser. This is deliberately broad rather than deep -
it exists to catch exactly the class of bug static analysis can't:
filterset_fields/ordering_fields pointing at columns that don't exist,
get_queryset() referencing a removed relation, a serializer that blows up
building its field list, etc. Detail/action endpoints that require a real
object id aren't covered here (each ViewSet's own test file covers those
where it matters); this sweep is a breadth-first regression net across the
whole URL surface.
"""
from django.urls import get_resolver
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


def _collect_list_endpoints():
    """Walk the full URL resolver tree and return every concrete path that
    doesn't require a URL parameter (i.e. list-level, not detail-level)."""
    resolver = get_resolver()
    paths = []

    def walk(patterns, prefix=''):
        for p in patterns:
            if hasattr(p, 'url_patterns'):
                # It's an include() - recurse, carrying the prefix forward
                walk(p.url_patterns, prefix + str(p.pattern))
            else:
                full = prefix + str(p.pattern)
                # Skip anything with a URL parameter (detail/action-on-instance routes)
                if '<' not in full:
                    paths.append('/' + full.lstrip('/'))

    walk(resolver.url_patterns)
    return sorted(set(paths))


class FullEndpointSweepTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.endpoints = _collect_list_endpoints()

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='sweep_admin', email='sweep@example.com', password='x'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_no_endpoint_returns_500(self):
        server_errors = []
        for path in self.endpoints:
            try:
                resp = self.client.get(path)
            except Exception as e:
                server_errors.append((path, f'raised {type(e).__name__}: {e}'))
                continue
            if resp.status_code >= 500:
                body = getattr(resp, 'data', None) or getattr(resp, 'content', b'')[:300]
                server_errors.append((path, f'{resp.status_code}: {body}'))

        if server_errors:
            msg = '\n'.join(f'{p} -> {e}' for p, e in server_errors)
            self.fail(
                f'{len(server_errors)}/{len(self.endpoints)} endpoints '
                f'returned a server error:\n{msg}'
            )

    def test_endpoint_count_sanity(self):
        # Guard against the sweep itself silently finding nothing (e.g. if
        # url resolution changes shape in a future Django version) - this
        # should always find a substantial number of list-level endpoints.
        self.assertGreater(len(self.endpoints), 30, self.endpoints)
