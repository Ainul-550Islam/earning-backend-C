"""
Payout Queue Signals — Signal definitions.
Connected in PayoutQueueConfig.ready() via receivers.py.
"""

from django.dispatch import Signal

# Fired after a PayoutBatch transitions to COMPLETED or PARTIALLY_COMPLETED.
# kwargs: batch (PayoutBatch)
payout_batch_completed = Signal()

# Fired after a PayoutBatch transitions to FAILED.
# kwargs: batch (PayoutBatch), error_summary (str)
payout_batch_failed = Signal()

# Fired after a PayoutItem is successfully processed.
# kwargs: item (PayoutItem)
payout_item_succeeded = Signal()

# Fired after a PayoutItem exhausts all retries and reaches FAILED.
# kwargs: item (PayoutItem)
payout_item_permanently_failed = Signal()

# Fired after a WithdrawalPriority is created (escalation/assignment).
# kwargs: priority (WithdrawalPriority)
withdrawal_priority_assigned = Signal()
