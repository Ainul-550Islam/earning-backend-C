# =============================================================================
# behavior_analytics/signals.py
# =============================================================================
"""
Custom Django signals emitted by the behavior_analytics application.

Consumers (other apps) can connect to these signals without importing
internal services directly, keeping coupling minimal.
"""

from django.dispatch import Signal

# Fired after a UserPath session is closed (status → completed/bounced/expired).
# kwargs: path (UserPath instance), previous_status (str)
path_closed = Signal()

# Fired after an EngagementScore is created or updated.
# kwargs: engagement_score (EngagementScore instance), created (bool)
engagement_score_updated = Signal()

# Fired when a user's engagement tier changes.
# kwargs: user, old_tier (str), new_tier (str), date (date)
engagement_tier_changed = Signal()

# Fired after a batch of ClickMetrics has been persisted.
# kwargs: path (UserPath instance), count (int)
click_batch_recorded = Signal()
