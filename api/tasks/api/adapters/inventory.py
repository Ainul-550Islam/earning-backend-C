"""
api/adapters/inventory.py
Task inventory management adapter.
Checks slot/budget availability before allowing task starts.
"""
import logging
from decimal import Decimal
logger = logging.getLogger(__name__)

def check_slot_available(task_id: int) -> bool:
    from api.tasks.models import TaskInventory
    try:
        inv = TaskInventory.objects.get(task_id=task_id)
        return not inv.is_exhausted and inv.available_slots > 0
    except TaskInventory.DoesNotExist:
        return True  # No inventory cap = unlimited

def consume_slot(task_id: int, payout_usd: Decimal = Decimal('0')) -> bool:
    from api.tasks.models import TaskInventory
    from django.db import transaction
    try:
        with transaction.atomic():
            inv = TaskInventory.objects.select_for_update().get(task_id=task_id)
            if inv.is_exhausted:
                return False
            inv.filled_slots += 1
            inv.spent_usd += payout_usd
            if inv.filled_slots >= inv.total_slots or inv.spent_usd >= inv.total_budget_usd:
                inv.is_exhausted = True
            inv.save(update_fields=['filled_slots', 'spent_usd', 'is_exhausted'])
            return True
    except TaskInventory.DoesNotExist:
        return True  # No cap

def release_slot(task_id: int, payout_usd: Decimal = Decimal('0')) -> None:
    from api.tasks.models import TaskInventory
    from django.db import transaction
    try:
        with transaction.atomic():
            inv = TaskInventory.objects.select_for_update().get(task_id=task_id)
            inv.filled_slots = max(0, inv.filled_slots - 1)
            inv.spent_usd = max(Decimal('0'), inv.spent_usd - payout_usd)
            inv.is_exhausted = False
            inv.save(update_fields=['filled_slots', 'spent_usd', 'is_exhausted'])
    except TaskInventory.DoesNotExist:
        pass
