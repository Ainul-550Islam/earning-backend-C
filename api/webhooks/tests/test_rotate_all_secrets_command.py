"""Test 'rotate_all_secrets' Management Command

Regression coverage for management/commands/rotate_all_secrets.py, which
had no test coverage at all before Session 9. Focused on
is_rotation_needed(), which did not exist anywhere in the codebase before
this fix (confirmed via a full-repo search) - every default (non --force)
invocation raised AttributeError for every endpoint. See
SecretRotationService.is_rotation_needed()'s own docstring for the full
root-cause writeup, including why this involved a real judgment call
about what "needs rotation" should mean here - flagged for review in
FIXES_APPLIED_SESSION9.md, not assumed correct.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ..models import WebhookEndpoint, WebhookSecret
from ..constants import WebhookStatus

User = get_user_model()


class RotateAllSecretsCommandTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='rotate_secrets_user', email='rsu@example.com', password='testpass123'
        )

    def _make_endpoint(self, created_days_ago=None, secret_key='original-secret'):
        endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key=secret_key,
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        if created_days_ago is not None:
            WebhookEndpoint.objects.filter(pk=endpoint.pk).update(
                created_at=timezone.now() - timedelta(days=created_days_ago)
            )
        return endpoint

    def test_default_invocation_no_longer_errors_on_every_endpoint(self):
        """Regression test: is_rotation_needed() did not exist anywhere
        before this fix - confirmed via a full-repo search - so
        `rotation_service.is_rotation_needed(endpoint, grace_period)`
        raised AttributeError for every endpoint on every default (non
        --force) run. Caught by the command's own per-endpoint except and
        counted as an error, so the default invocation failed 100% of the
        time regardless of what endpoints existed. This just confirms the
        command completes and reports zero errors now - the specific
        rotate-vs-skip decision is covered by the tests below.
        """
        from io import StringIO
        self._make_endpoint(created_days_ago=100)

        out = StringIO()
        call_command('rotate_all_secrets', stdout=out)

        self.assertIn("Errors: 0", out.getvalue())

    def test_old_never_rotated_secret_gets_rotated(self):
        """An endpoint whose secret has never been archived (never
        rotated) and was created well outside the default 7-day grace
        period should be rotated."""
        endpoint = self._make_endpoint(created_days_ago=30)
        original_secret = endpoint.secret_key

        call_command('rotate_all_secrets')

        endpoint.refresh_from_db()
        self.assertNotEqual(endpoint.secret_key, original_secret)
        self.assertTrue(
            WebhookSecret.objects.filter(endpoint=endpoint, is_active=False).exists()
        )

    def test_recently_rotated_secret_is_skipped(self):
        """An endpoint with a recent rotation record (well inside the
        grace period) should not be rotated again."""
        endpoint = self._make_endpoint(created_days_ago=30)
        # Simulate a rotation 1 day ago by creating the archive record
        # rotate_secret() itself would have created.
        WebhookSecret.objects.create(
            endpoint=endpoint, secret_hash='x', is_active=False,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        WebhookSecret.objects.filter(endpoint=endpoint).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        original_secret = endpoint.secret_key

        call_command('rotate_all_secrets', '--grace-period=7')

        endpoint.refresh_from_db()
        self.assertEqual(endpoint.secret_key, original_secret)

    def test_force_rotates_regardless_of_recency(self):
        """--force should bypass is_rotation_needed() entirely, even for
        a just-rotated endpoint."""
        endpoint = self._make_endpoint(created_days_ago=1)
        original_secret = endpoint.secret_key

        call_command('rotate_all_secrets', '--force')

        endpoint.refresh_from_db()
        self.assertNotEqual(endpoint.secret_key, original_secret)

    def test_endpoint_with_no_secret_needs_rotation(self):
        """An endpoint with no secret at all should always be considered
        due, regardless of age."""
        endpoint = self._make_endpoint(created_days_ago=1, secret_key='')

        call_command('rotate_all_secrets')

        endpoint.refresh_from_db()
        self.assertTrue(endpoint.secret_key)
