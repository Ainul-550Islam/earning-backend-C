"""signals.py – Custom Django signals for the subscription module."""
from django.dispatch import Signal

# Subscription lifecycle signals
subscription_activated = Signal()   # provides: instance
subscription_cancelled = Signal()   # provides: instance, at_period_end
subscription_expired = Signal()     # provides: instance
subscription_renewed = Signal()     # provides: instance, payment
subscription_paused = Signal()      # provides: instance
subscription_resumed = Signal()     # provides: instance
plan_changed = Signal()             # provides: instance, old_plan, new_plan

# Payment signals
payment_succeeded = Signal()        # provides: instance
payment_failed = Signal()           # provides: instance, exc
payment_refunded = Signal()         # provides: instance, amount

# Trial signals
trial_started = Signal()            # provides: instance
trial_ending_soon = Signal()        # provides: instance, days_remaining
trial_ended = Signal()              # provides: instance