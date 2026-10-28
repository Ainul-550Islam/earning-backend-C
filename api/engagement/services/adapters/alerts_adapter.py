# engagement/services/adapters/alerts_adapter.py
"""
AlertsAdapter
=============
Wraps api.alerts for engagement system-level alerts.

Fires alerts for:
    - High anti-cheat flag rate (possible coordinated fraud)
    - Leaderboard reward distribution failures
    - Battle pass expiry soon (admin action needed)
    - Spin/checkin error spike
    - Auction system anomaly
    - Revenue anomaly (coins depleted unusually fast)
"""

import logging
logger = logging.getLogger("engagement.adapters.alerts")

# Alert severity levels
SEVERITY = {
    "info":     "info",
    "warning":  "warning",
    "critical": "critical",
    "error":    "error",
}


class AlertsAdapter:

    @staticmethod
    def _fire(title: str, message: str, severity: str = "warning",
               tags: list = None, data: dict = None) -> bool:
        """Core alert fire — tries api.alerts then logs as fallback."""
        payload = {
            "title":    f"[Engagement] {title}",
            "message":  message,
            "severity": SEVERITY.get(severity, "warning"),
            "source":   "engagement",
            "tags":     (tags or []) + ["engagement"],
            "data":     data or {},
        }
        try:
            from api.alerts.services.core import AlertProcessorService
            AlertProcessorService().create_alert(**payload)
            return True
        except Exception:
            pass

        # Fallback: structured log
        log_fn = logger.critical if severity == "critical" else \
                 logger.error    if severity == "error" else \
                 logger.warning  if severity == "warning" else logger.info
        log_fn(f"[ALERT] {title}: {message} | data={data}")
        return False

    # ── Specific alert methods ────────────────────────────────────────────────

    @staticmethod
    def fraud_spike(flagged_count: int, window_minutes: int = 60):
        AlertsAdapter._fire(
            title="Anti-Cheat Fraud Spike Detected",
            message=f"{flagged_count} users flagged in last {window_minutes} minutes.",
            severity="critical",
            tags=["fraud", "anti_cheat"],
            data={"flagged_count": flagged_count, "window": window_minutes},
        )

    @staticmethod
    def reward_distribution_failure(date: str, failed_count: int, reason: str = ""):
        AlertsAdapter._fire(
            title="Leaderboard Reward Distribution Failed",
            message=f"{failed_count} rewards failed for date={date}. Reason: {reason}",
            severity="error",
            tags=["leaderboard", "rewards"],
            data={"date": date, "failed": failed_count, "reason": reason},
        )

    @staticmethod
    def battle_pass_expiring(season_name: str, hours_left: int):
        AlertsAdapter._fire(
            title="Battle Pass Season Expiring Soon",
            message=f"Season '{season_name}' expires in {hours_left}h. Create next season.",
            severity="warning",
            tags=["battle_pass"],
            data={"season": season_name, "hours_left": hours_left},
        )

    @staticmethod
    def coin_drain_anomaly(user_id: int, amount: float, source: str, ip: str = ""):
        AlertsAdapter._fire(
            title="Abnormal Coin Drain Detected",
            message=f"User {user_id} drained {amount:.0f} coins via {source}.",
            severity="warning",
            tags=["coins", "anomaly", "fraud"],
            data={"user_id": user_id, "amount": amount, "source": source, "ip": ip},
        )

    @staticmethod
    def error_spike(service: str, error_count: int, sample_error: str = ""):
        AlertsAdapter._fire(
            title=f"Error Spike in {service}",
            message=f"{error_count} errors in {service}. Sample: {sample_error[:200]}",
            severity="error",
            tags=["error_spike", service.lower()],
            data={"service": service, "count": error_count},
        )

    @staticmethod
    def admin_action(admin_id: int, action: str, target_id: int, details: dict = None):
        AlertsAdapter._fire(
            title=f"Admin Action: {action}",
            message=f"Admin {admin_id} performed '{action}' on user {target_id}.",
            severity="info",
            tags=["admin"],
            data={"admin_id": admin_id, "action": action,
                  "target_id": target_id, "details": details or {}},
        )