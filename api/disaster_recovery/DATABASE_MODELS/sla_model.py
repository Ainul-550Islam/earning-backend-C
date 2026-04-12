"""
SLA Model — SQLAlchemy model for SLA monitoring records.
Tracks uptime percentages, downtime events, and SLA compliance
per service per billing/reporting period.
"""
from ..sa_models import SLA_Monitoring

__all__ = ["SLA_Monitoring"]

SLA_EXAMPLE = {
    "service_name": "api-server",
    "period_start": "2024-01-01T00:00:00Z",
    "period_end": "2024-01-31T23:59:59Z",
    "target_uptime_percent": 99.9,
    "actual_uptime_percent": 99.97,
    "total_downtime_minutes": 13.1,
    "incident_count": 2,
    "sla_met": True,
    "credits_due": 0.0,
}

SLA_BREACH_EXAMPLE = {
    "service_name": "api-server",
    "period_start": "2024-02-01T00:00:00Z",
    "period_end": "2024-02-29T23:59:59Z",
    "target_uptime_percent": 99.9,
    "actual_uptime_percent": 99.81,
    "total_downtime_minutes": 81.4,
    "incident_count": 5,
    "sla_met": False,
    "credits_due": 500.0,
}
