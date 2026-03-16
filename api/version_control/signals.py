# =============================================================================
# version_control/signals.py
# =============================================================================
"""Custom signals for the version_control application."""

from django.dispatch import Signal

# Fired when an AppUpdatePolicy transitions to ACTIVE.
# kwargs: policy (AppUpdatePolicy instance)
update_policy_activated = Signal()

# Fired when a MaintenanceSchedule becomes ACTIVE.
# kwargs: schedule (MaintenanceSchedule instance)
maintenance_started = Signal()

# Fired when a MaintenanceSchedule is COMPLETED.
# kwargs: schedule (MaintenanceSchedule instance)
maintenance_ended = Signal()

# Fired when any platform redirect URL changes.
# kwargs: redirect (PlatformRedirect instance), old_url (str)
redirect_url_changed = Signal()
