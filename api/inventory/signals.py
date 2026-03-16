"""signals.py – Inventory module signals."""
from django.dispatch import Signal

# Item lifecycle
item_activated = Signal()           # instance
item_deactivated = Signal()         # instance

# Stock events
stock_replenished = Signal()        # instance, qty, event
stock_depleted = Signal()           # instance (hit 0)
low_stock_alert = Signal()          # instance, alert_level
stock_adjusted = Signal()           # instance, delta, event

# Redemption
code_redeemed = Signal()            # code_instance, user
code_expired = Signal()             # code_instance

# UserInventory fulfilment
inventory_created = Signal()        # inventory_instance
item_delivered = Signal()           # inventory_instance
item_delivery_failed = Signal()     # inventory_instance, error
item_claimed = Signal()             # inventory_instance
item_revoked = Signal()             # inventory_instance, reason
item_expiring_soon = Signal()       # inventory_instance, days_remaining
