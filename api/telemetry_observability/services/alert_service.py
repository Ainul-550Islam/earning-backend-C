"""
AlertService — thin facade over logic.AlertLogic.

DRY RULE: Zero business logic here.
All implementation lives in logic.AlertLogic → alerting.AlertingService.
"""
from typing import Any, Dict, List, Optional

from ..logic import AlertLogic
from ..models.alert import Alert
from ..decorators import trace_operation


class AlertService:
    """
    Public service interface for alert operations.
    All methods delegate to AlertLogic — never re-implemented here.
    """

    def __init__(self):
        self._logic = AlertLogic()

    @trace_operation(service='alert-service', operation_name='create_alert')
    def create_alert(self, data: Dict[str, Any]) -> Alert:
        """Create a new alert. Delegates to AlertLogic."""
        return self._logic.create_alert(data)

    def batch_create_alerts(self, data_list: List[Dict[str, Any]]) -> List[Alert]:
        """Batch-create alerts."""
        return self._logic.batch_create(data_list)

    def get_alerts(
        self,
        alert_type: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
        service: Optional[str] = None,
        environment: Optional[str] = None,
        limit: int = 100,
    ) -> List[Alert]:
        """Filter and return alerts."""
        return self._logic.get_alerts(
            alert_type=alert_type,
            severity=severity,
            status=status,
            source=source,
            service=service,
            environment=environment,
            limit=limit,
        )

    def acknowledge_alert(self, alert_id: int, user: str) -> bool:
        """Acknowledge an alert. Returns True if found."""
        return self._logic.acknowledge(alert_id, user)

    def resolve_alert(self, alert_id: int) -> bool:
        """Resolve an alert. Returns True if found."""
        return self._logic.resolve(alert_id)

    def get_alert_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Return alert volume and severity statistics."""
        return self._logic.get_statistics(hours=hours)

    def get_open_alerts(self, service: Optional[str] = None) -> List[Alert]:
        """Return all open alerts."""
        return self._logic.get_open(service=service)

    def get_critical_alerts(self, service: Optional[str] = None) -> List[Alert]:
        """Return all critical alerts."""
        return self._logic.get_critical(service=service)
