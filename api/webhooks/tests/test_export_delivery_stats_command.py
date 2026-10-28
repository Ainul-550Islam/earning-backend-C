"""Test 'export_delivery_stats' Management Command

Regression coverage for management/commands/export_delivery_stats.py,
which had no test coverage at all before Session 9. Focused on the three
confirmed bugs (see the command's own inline BUG FIX comments):
endpoint__url (wrong field name), and two backend-portability bugs in the
date grouping (raw date()/date_trunc() SQL, confirmed to behave
differently - or not exist at all - on SQLite vs the fixture behavior
production code implicitly assumed).
"""

import csv
import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from ..models import WebhookEndpoint, WebhookDeliveryLog
from ..constants import WebhookStatus, DeliveryStatus

User = get_user_model()


class ExportDeliveryStatsCommandTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='export_stats_user', email='esu@example.com', password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            label='Test Endpoint',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint, event_type='user.created', payload={},
            status=DeliveryStatus.SUCCESS, response_time_ms=100,
        )
        self.output_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.output_dir, ignore_errors=True)

    def _read_csv(self, filename_contains):
        matches = [f for f in os.listdir(self.output_dir) if filename_contains in f]
        self.assertTrue(matches, f"no output file containing {filename_contains!r} in {os.listdir(self.output_dir)}")
        with open(os.path.join(self.output_dir, matches[0]), newline='', encoding='utf-8') as f:
            return list(csv.reader(f))

    def test_group_by_day_default_produces_valid_rows(self):
        """Regression test: the default --group-by (day) used raw SQL
        (`date(created_at)` via .extra()) whose *return type* differs by
        backend - confirmed empirically it comes back as a plain string on
        SQLite ('2026-08-31'), not a date object, so
        stat['date'].strftime(...) raised AttributeError: 'str' object
        has no attribute 'strftime' on the very first row. Since 'day' is
        the default group_by, this broke the command's default
        invocation, not just an edge case. TruncDate fixes this.
        """
        call_command('export_delivery_stats', f'--output-dir={self.output_dir}')
        rows = self._read_csv('webhook_delivery_stats_')
        self.assertEqual(rows[0][0], 'Date')
        self.assertEqual(len(rows), 2)  # header + 1 day's data
        self.assertEqual(rows[1][1], '1')  # total requests

    def test_group_by_hour_produces_valid_rows(self):
        """Regression test: --group-by hour used date_trunc('hour', ...)
        via raw SQL - Postgres-only syntax, confirmed empirically it
        raises OperationalError: no such function: date_trunc on SQLite.
        TruncHour fixes this and is portable to the real Postgres backend
        too.
        """
        call_command('export_delivery_stats', f'--output-dir={self.output_dir}', '--group-by=hour')
        rows = self._read_csv('webhook_delivery_stats_')
        self.assertEqual(rows[0][0], 'Hour')
        self.assertEqual(len(rows), 2)

    def test_group_by_endpoint_produces_valid_rows(self):
        """Regression test: --group-by endpoint used
        .values('endpoint__url', ...) - WebhookEndpoint has no url field
        (confirmed against the model; the real field is target_url, used
        correctly everywhere else in this same file). Raised
        django.core.exceptions.FieldError immediately.
        """
        call_command('export_delivery_stats', f'--output-dir={self.output_dir}', '--group-by=endpoint')
        rows = self._read_csv('webhook_delivery_stats_')
        self.assertEqual(rows[0][0], 'Endpoint URL')
        self.assertEqual(rows[1][0], self.endpoint.target_url)

    def test_group_by_event_type_unaffected_still_works(self):
        """Sanity check that the one grouping mode with no bug found still
        works after the surrounding edits."""
        call_command('export_delivery_stats', f'--output-dir={self.output_dir}', '--group-by=event_type')
        rows = self._read_csv('webhook_delivery_stats_')
        self.assertEqual(rows[0][0], 'Event Type')
        self.assertEqual(rows[1][0], 'user.created')
