"""Test 'seed_event_types' Management Command

Regression coverage for management/commands/seed_event_types.py, which had
no test coverage at all before Session 9. This command's only fix was
removing dead/redundant leftover code (see the command's own inline BUG
FIX comment) - lower severity than the other six commands audited this
session, since the removed block was inert rather than broken. Coverage
here is a basic sanity check that the real seeding logic still works and
the redundant output is gone, not exhaustive.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from ..models import WebhookEventStat


class SeedEventTypesCommandTest(TestCase):

    def test_seeds_event_stat_rows(self):
        call_command('seed_event_types')
        self.assertGreater(WebhookEventStat.objects.count(), 0)

    def test_no_longer_prints_the_redundant_pre_pass_output(self):
        """The removed block used to print "Event type available: X" once
        per EventType constant before the real seeding loop, duplicating
        output for no purpose. Confirms it's gone."""
        out = StringIO()
        call_command('seed_event_types', stdout=out)
        self.assertNotIn("Event type available:", out.getvalue())

    def test_second_run_without_force_skips_existing(self):
        call_command('seed_event_types')
        first_count = WebhookEventStat.objects.count()

        out = StringIO()
        call_command('seed_event_types', stdout=out)

        self.assertEqual(WebhookEventStat.objects.count(), first_count)
        self.assertIn("already exists", out.getvalue())
