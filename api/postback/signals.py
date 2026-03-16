"""signals.py – Postback module signals."""
from django.dispatch import Signal

postback_received = Signal()     # instance
postback_validated = Signal()    # instance
postback_rejected = Signal()     # instance, reason
postback_rewarded = Signal()     # instance, points
postback_duplicate = Signal()    # instance
postback_failed = Signal()       # instance, error
network_created = Signal()       # instance
network_activated = Signal()     # instance
network_deactivated = Signal()   # instance
