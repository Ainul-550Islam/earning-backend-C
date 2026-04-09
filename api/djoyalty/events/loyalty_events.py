# api/djoyalty/events/loyalty_events.py
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from django.utils import timezone

@dataclass
class LoyaltyEvent:
    event_type: str
    customer: Optional[object] = None
    tenant: Optional[object] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[object] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()

    def to_dict(self):
        return {
            'event': self.event_type,
            'timestamp': self.timestamp.isoformat(),
            'tenant_id': self.tenant.id if self.tenant else None,
            'customer_code': self.customer.code if self.customer else None,
            'data': self.data,
        }
