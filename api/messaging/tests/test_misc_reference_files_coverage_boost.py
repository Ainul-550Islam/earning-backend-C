"""
test_misc_reference_files_coverage_boost.py
==============================================
Smoke coverage for three files that sit at 0% not because they're
untested logic, but because they're either a backward-compat re-export
shim or drop-in reference config/settings meant to be imported by the
*host* project (earning_backend), not exercised by this app's own
standalone test harness (conftest.py configures settings directly
rather than importing settings_messaging.py, and nothing in the
standalone test project wires up real Celery beat).

These tests just confirm each file is importable and exports what its
own docstring promises - which is the meaningful thing to verify for a
reference/config file, as opposed to line-by-line branch coverage.
"""
from __future__ import annotations


class TestAttachmentUploadView:
    def test_reexports_the_real_view(self):
        from api.messaging.attachment_upload_view import MessageAttachmentUploadView
        from api.messaging.views import MessageAttachmentUploadView as RealView
        assert MessageAttachmentUploadView is RealView


class TestCeleryBeatConfig:
    def test_schedule_dict_is_well_formed(self):
        from api.messaging.celery_beat_config import MESSAGING_BEAT_SCHEDULE
        assert isinstance(MESSAGING_BEAT_SCHEDULE, dict)
        assert len(MESSAGING_BEAT_SCHEDULE) > 0
        for name, entry in MESSAGING_BEAT_SCHEDULE.items():
            assert "task" in entry
            assert "schedule" in entry
            assert entry["task"] == name

    def test_documented_task_names_are_present(self):
        from api.messaging.celery_beat_config import MESSAGING_BEAT_SCHEDULE
        for name in [
            "messaging.send_scheduled_messages",
            "messaging.cleanup_presence",
            "messaging.expire_disappearing_messages",
            "messaging.send_scheduled_broadcasts",
            "messaging.send_scheduled_cpa_broadcasts",
            "messaging.send_payout_reminders",
        ]:
            assert name in MESSAGING_BEAT_SCHEDULE


class TestSettingsMessaging:
    def test_documented_exports_are_present(self):
        from messaging import settings_messaging as sm
        for name in [
            "MESSAGING_INSTALLED_APPS",
            "MESSAGING_REST_FRAMEWORK",
            "MESSAGING_MIDDLEWARE",
            "MESSAGING_CHANNEL_LAYERS",
            "MESSAGING_CACHES",
        ]:
            assert hasattr(sm, name), f"settings_messaging.py is missing documented export {name}"

    def test_installed_apps_is_a_list_containing_messaging(self):
        from api.messaging.settings_messaging import MESSAGING_INSTALLED_APPS
        assert isinstance(MESSAGING_INSTALLED_APPS, (list, tuple))
        assert any("messaging" in app for app in MESSAGING_INSTALLED_APPS)
