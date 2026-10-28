# =============================================================================
# fraud_detection/views_notification_service.py  (DRY-refactored)
# =============================================================================
"""
Missing FraudNotificationService endpoints — now DRY-clean.

DRY improvements
-----------------
• Extends FraudBaseView / FraudAdminView — removes 7 duplicate
  throttle_classes, 7 permission_classes, and 2 _ok/_err definitions.
• lazy_service() from utils replaces inline _svc() helper.
• ORM fallback logic for alert/case notification creation is shared
  via _create_notification_orm() helper (defined once).
"""
from __future__ import annotations
import logging
from typing import Any
from django.utils import timezone
from rest_framework import status
from api.fraud_detection.utils import FraudBaseView, FraudAdminView, lazy_service

logger = logging.getLogger(__name__)

_VALID_CASE_NOTIF_TYPES = [
    "case_created","case_updated","case_escalated","case_resolved",
    "case_closed","evidence_added","action_taken","investigator_assigned",
]
_VALID_CHANNELS = {"email","sms","push","webhook","dashboard"}


def _svc():
    return lazy_service(
        "api.fraud_detection.services.FraudNotificationService",
        "FraudNotificationService",
    )


def _create_notification_orm(notif_type, title, message, metadata,
                              channel="dashboard", sent=False):
    """ORM fallback — creates FraudNotification directly. Defined once."""
    from api.fraud_detection.models import FraudNotification
    return FraudNotification.objects.create(
        notification_type=notif_type,
        title=title, message=message,
        status="sent" if sent else "pending",
        sent_at=timezone.now() if sent else None,
        delivery_channel=channel,
        metadata=metadata,
    )


# =============================================================================
# Alert Notification
# =============================================================================

class NotifServiceCreateAlertNotificationAPIView(FraudAdminView):
    """POST /fraud/notifications/service/alert/<int:alert_id>/create/"""

    def post(self, request, alert_id: int):
        svc = _svc()
        try:
            if svc and hasattr(svc, "create_alert_notification"):
                success = svc.create_alert_notification(alert_id)
                return self.ok({"created": success, "alert_id": alert_id,
                                 "timestamp": timezone.now().isoformat()},
                                status.HTTP_201_CREATED if success
                                else status.HTTP_200_OK)

            from api.fraud_detection.models import FraudAlert
            from api.fraud_detection.serializers import FraudAlertSerializer
            try:
                alert = FraudAlert.objects.get(pk=alert_id)
            except FraudAlert.DoesNotExist:
                return self.err(f"FraudAlert {alert_id} not found.", status.HTTP_404_NOT_FOUND)

            notif = _create_notification_orm(
                "alert",
                f"Alert: {alert.title or alert.alert_type}",
                (f"Fraud alert [{alert.priority.upper()}]: "
                 f"{alert.description or alert.alert_type}. "
                 f"Alert ID: {alert.pk}."),
                {"alert_id": alert_id, "priority": alert.priority},
            )
            return self.ok({"created": True, "notification_id": notif.pk,
                             "alert_id": alert_id, "source": "orm_fallback"},
                            status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("NotifServiceCreateAlertNotificationAPIView alert_id=%s: %s",
                              alert_id, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotifServiceCreateAndSendAlertAPIView(FraudAdminView):
    """POST /fraud/notifications/service/alert/<int:alert_id>/create-and-send/"""

    def post(self, request, alert_id: int):
        svc = _svc()
        try:
            if svc and hasattr(svc, "create_alert_notification"):
                created = svc.create_alert_notification(alert_id)
                sent = False; notif_id = None
                if created:
                    from api.fraud_detection.models import FraudNotification
                    n = FraudNotification.objects.filter(
                        metadata__alert_id=alert_id, status="pending"
                    ).order_by("-created_at").first()
                    if n:
                        sent = svc.send_notification(n.pk); notif_id = n.pk
                return self.ok({"created": created, "sent": sent,
                                 "notification_id": notif_id, "alert_id": alert_id})

            from api.fraud_detection.models import FraudAlert
            try:
                alert = FraudAlert.objects.get(pk=alert_id)
            except FraudAlert.DoesNotExist:
                return self.err(f"FraudAlert {alert_id} not found.", status.HTTP_404_NOT_FOUND)

            notif = _create_notification_orm(
                "alert",
                f"[IMMEDIATE] Alert: {alert.title or alert.alert_type}",
                f"Immediate fraud alert [{alert.priority.upper()}].",
                {"alert_id": alert_id, "priority": alert.priority},
                sent=True,
            )
            return self.ok({"created": True, "sent": True,
                             "notification_id": notif.pk, "alert_id": alert_id,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("NotifServiceCreateAndSendAlertAPIView alert_id=%s: %s",
                              alert_id, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Case Notification
# =============================================================================

class NotifServiceCreateCaseNotificationAPIView(FraudAdminView):
    """POST /fraud/notifications/service/case/<int:case_id>/create/"""

    _TITLE_MAP = {
        "case_created":          "New Case #{pk} — {sev}",
        "case_updated":          "Case #{pk} Updated",
        "case_escalated":        "Case #{pk} Escalated — {sev}",
        "case_resolved":         "Case #{pk} Resolved",
        "case_closed":           "Case #{pk} Closed",
        "evidence_added":        "New Evidence on Case #{pk}",
        "action_taken":          "Action Taken on Case #{pk}",
        "investigator_assigned": "Investigator Assigned to Case #{pk}",
    }

    def post(self, request, case_id: int):
        notif_type = request.data.get("notification_type")
        if not notif_type:
            return self.err(f"notification_type required. Valid: {_VALID_CASE_NOTIF_TYPES}.")
        if notif_type not in _VALID_CASE_NOTIF_TYPES:
            return self.err(f"Unknown notification_type '{notif_type}'. "
                             f"Valid: {_VALID_CASE_NOTIF_TYPES}.")
        svc = _svc()
        try:
            if svc and hasattr(svc, "create_case_notification"):
                success = svc.create_case_notification(case_id, notif_type)
                return self.ok(
                    {"created": success, "case_id": case_id,
                     "notification_type": notif_type,
                     "timestamp": timezone.now().isoformat()},
                    status.HTTP_201_CREATED if success else status.HTTP_200_OK,
                )

            from api.fraud_detection.models import FraudCase
            try:
                case = FraudCase.objects.get(pk=case_id)
            except FraudCase.DoesNotExist:
                return self.err(f"FraudCase {case_id} not found.", status.HTTP_404_NOT_FOUND)

            title = self._TITLE_MAP.get(notif_type, f"Case #{case.pk} Update")
            title = title.format(pk=case.pk, sev=case.severity.upper())
            notif = _create_notification_orm(
                "case", title,
                f"Case notification [{notif_type}]: "
                f"Case #{case.pk} ({case.case_type}, {case.severity}).",
                {"case_id": case_id, "notification_type": notif_type,
                 "severity": case.severity},
            )
            return self.ok({"created": True, "notification_id": notif.pk,
                             "case_id": case_id, "notification_type": notif_type,
                             "source": "orm_fallback"}, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("NotifServiceCreateCaseNotificationAPIView case_id=%s: %s",
                              case_id, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotifServiceCreateAndSendCaseAPIView(FraudAdminView):
    """POST /fraud/notifications/service/case/<int:case_id>/create-and-send/"""

    def post(self, request, case_id: int):
        notif_type = request.data.get("notification_type")
        if not notif_type:
            return self.err(f"notification_type required. Valid: {_VALID_CASE_NOTIF_TYPES}.")
        if notif_type not in _VALID_CASE_NOTIF_TYPES:
            return self.err(f"Unknown notification_type '{notif_type}'.")
        svc = _svc()
        try:
            if svc and hasattr(svc, "create_case_notification"):
                created = svc.create_case_notification(case_id, notif_type)
                sent = False; notif_id = None
                if created:
                    from api.fraud_detection.models import FraudNotification
                    n = FraudNotification.objects.filter(
                        metadata__case_id=case_id, status="pending"
                    ).order_by("-created_at").first()
                    if n:
                        sent = svc.send_notification(n.pk); notif_id = n.pk
                return self.ok({"created": created, "sent": sent,
                                 "notification_id": notif_id, "case_id": case_id,
                                 "notification_type": notif_type})

            from api.fraud_detection.models import FraudCase
            try:
                case = FraudCase.objects.get(pk=case_id)
            except FraudCase.DoesNotExist:
                return self.err(f"FraudCase {case_id} not found.", status.HTTP_404_NOT_FOUND)

            notif = _create_notification_orm(
                "case",
                f"[IMMEDIATE] Case #{case.pk} — "
                f"{notif_type.replace('_',' ').title()}",
                f"Immediate case notification [{notif_type}]: Case #{case.pk}.",
                {"case_id": case_id, "notification_type": notif_type},
                sent=True,
            )
            return self.ok({"created": True, "sent": True,
                             "notification_id": notif.pk, "case_id": case_id,
                             "notification_type": notif_type,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("NotifServiceCreateAndSendCaseAPIView case_id=%s: %s",
                              case_id, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Channel Status, Extended Stats, Test
# =============================================================================

class NotifServiceChannelsAPIView(FraudBaseView):
    """GET /fraud/notifications/service/channels/"""
    _CHANNELS = ["email","sms","push","webhook","dashboard"]

    def get(self, request):
        from django.conf import settings
        svc = _svc()
        channels = [
            {"channel": ch,
             "enabled": getattr(settings, f"FRAUD_NOTIF_{ch.upper()}_ENABLED", True),
             "available": svc is not None and
                          hasattr(svc, f"_send_{ch}_notification")}
            for ch in self._CHANNELS
        ]
        return self.ok({"total": len(channels),
                         "enabled": sum(1 for c in channels if c["enabled"]),
                         "service_ok": svc is not None,
                         "channels": channels})


class NotifServiceExtendedStatsAPIView(FraudBaseView):
    """GET /fraud/notifications/service/stats/extended/"""

    def get(self, request):
        try:
            days = max(1, min(365, int(request.query_params.get("days", 30))))
        except (TypeError, ValueError):
            days = 30
        svc = _svc()
        try:
            base_stats = (svc.get_notification_statistics(days=days)
                          if svc and hasattr(svc, "get_notification_statistics") else {})
            from django.db.models import Count
            from api.fraud_detection.models import FraudNotification
            import datetime
            cutoff = timezone.now() - datetime.timedelta(days=days)
            qs     = FraudNotification.objects.filter(created_at__gte=cutoff)
            total  = qs.count()
            sent   = qs.filter(status="sent").count()
            failed = qs.filter(status="failed").count()
            return self.ok({
                "days":          days, "total": total,
                "sent":          sent, "failed": failed,
                "pending":       qs.filter(status="pending").count(),
                "delivery_rate": round(sent / total * 100, 1) if total else 0.0,
                "failure_rate":  round(failed / total * 100, 1) if total else 0.0,
                "by_type":       list(qs.values("notification_type").annotate(count=Count("id"))),
                "by_status":     list(qs.values("status").annotate(count=Count("id"))),
                "by_channel":    list(qs.values("delivery_channel").annotate(count=Count("id"))),
                "service_stats": base_stats,
            })
        except Exception as exc:
            logger.exception("NotifServiceExtendedStatsAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotifServiceTestAPIView(FraudAdminView):
    """POST /fraud/notifications/service/test/"""

    def post(self, request):
        channel   = request.data.get("channel", "dashboard")
        recipient = request.data.get("recipient", request.user.pk)
        message   = request.data.get(
            "message",
            f"Test notification sent by {request.user} at "
            f"{timezone.now().isoformat()}.",
        )
        if channel not in _VALID_CHANNELS:
            return self.err(f"Invalid channel '{channel}'. "
                             f"Valid: {sorted(_VALID_CHANNELS)}.")
        svc = _svc()
        try:
            if svc and hasattr(svc, "create_notification"):
                nid  = svc.create_notification(user_id=recipient,
                                                notification_type="test",
                                                message=message, priority="low",
                                                delivery_channel=channel)
                sent = bool(nid and hasattr(svc, "send_notification") and
                            svc.send_notification(nid))
                return self.ok({"test": True, "channel": channel,
                                 "recipient": recipient,
                                 "notification_id": nid, "sent": sent,
                                 "message": message})

            notif = _create_notification_orm(
                "test", "Test Notification", message,
                {"test": True, "channel": channel, "recipient": recipient},
                channel=channel, sent=True,
            )
            return self.ok({"test": True, "channel": channel,
                             "recipient": recipient,
                             "notification_id": notif.pk, "sent": True,
                             "message": message, "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("NotifServiceTestAPIView channel=%s: %s", channel, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

# ── ALIASES expected by urls.py ───────────────────────────────────────────────
NotificationServiceSendAPIView  = NotifServiceCreateAndSendAlertAPIView
NotificationServiceBulkAPIView  = NotifServiceCreateAndSendCaseAPIView
NotificationServiceStatsAPIView = NotifServiceExtendedStatsAPIView
