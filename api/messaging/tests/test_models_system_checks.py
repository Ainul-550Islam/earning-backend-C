"""
test_models_system_checks.py
==============================
Audit addition (Part 19, Item 5 - models.py line-by-line pass): runs
Django's own model system-check framework (fields.E3xx/E304 related_name
collisions, invalid on_delete/FK setups, constraint definition errors,
etc.) as a real regression test, not just a one-off manual run. 40
models across 3351 lines is easy to introduce a collision or malformed
constraint into by hand later without noticing - this catches that
automatically going forward. Passed cleanly on the full manual audit
pass with zero findings.

Scoped to tags=['models'] deliberately, not the full check suite: the
standalone test harness's conftest.py doesn't configure
django.contrib.messages or an admin-capable TEMPLATES backend (that's
the parent earning_backend project's job, not this module's - see the
CORS/CSRF findings for the same category of external-config
dependency), so a full check() here would fail on admin.E403/E406 that
have nothing to do with this module's model correctness.
"""
from django.core.management import call_command
from django.test import SimpleTestCase


class TestDjangoSystemChecks(SimpleTestCase):
    def test_run_models_check(self):
        call_command('check', tags=['models'])
