# earning_backend/api/notifications/compliance.py
"""Compliance — GDPR, PDPA (Bangladesh), CAN-SPAM compliance."""
import logging
from datetime import timedelta
from typing import Dict, Tuple
from django.utils import timezone
logger = logging.getLogger(__name__)

class GDPRComplianceService:
    def process_erasure_request(self, user):
        try:
            from api.notifications.models import Notification, NotificationPreference, DeviceToken
            from api.notifications.models.analytics import OptOutTracking, NotificationFatigue
            from api.notifications.caching import invalidate_all_user_caches
            Notification.objects.filter(user=user).update(title="[Deleted]",message="[Deleted - GDPR]",metadata={},is_deleted=True,deleted_at=timezone.now())
            DeviceToken.objects.filter(user=user).delete()
            NotificationPreference.objects.filter(user=user).delete()
            OptOutTracking.objects.filter(user=user).update(notes="[GDPR Erased]")
            NotificationFatigue.objects.filter(user=user).delete()
            invalidate_all_user_caches(user.pk)
            logger.info(f"GDPR erasure completed for user #{user.pk}")
            return {"success":True,"user_id":user.pk,"erased_at":timezone.now().isoformat()}
        except Exception as exc:
            logger.error(f"GDPR erasure failed: {exc}")
            return {"success":False,"error":str(exc)}

    def export_user_data(self, user):
        from api.notifications.data_export import export_user_data_gdpr
        return export_user_data_gdpr(user)

    def check_marketing_consent(self, user, channel="email"):
        try:
            profile = getattr(user,"profile",None)
            country = getattr(profile,"country","") or ""
            EU = {"DE","FR","IT","ES","NL","BE","SE","PL","AT","DK","FI","PT","IE","GR"}
            if country.upper() not in EU: return True
            if channel in ("in_app","push"): return True
            return bool(getattr(profile,f"marketing_{channel}_consent",False))
        except Exception: return True

class DataRetentionService:
    RETENTION = {"notifications":365,"delivery_logs":90,"analytics":730,"campaigns":365}
    def enforce_retention(self, dry_run=False):
        results = {}
        cutoff_map = {k: timezone.now()-timedelta(days=v) for k,v in self.RETENTION.items()}
        for dtype, cutoff in cutoff_map.items():
            try:
                count = self._delete_old_data(dtype, cutoff, dry_run)
                results[dtype] = {"deleted":count,"dry_run":dry_run}
            except Exception as exc:
                results[dtype] = {"error":str(exc)}
        return results

    def _delete_old_data(self, dtype, cutoff, dry_run):
        from api.notifications.models import Notification
        if dtype == "notifications":
            qs = Notification.objects.filter(is_deleted=True, deleted_at__lt=cutoff)
            count = qs.count()
            if not dry_run: qs.delete()
            return count
        return 0

class CANSPAMService:
    def validate_email_notification(self, notification):
        issues = []
        if not getattr(notification,"action_url",""): issues.append("Email must include unsubscribe link")
        if not notification.title: issues.append("Subject line required")
        return len(issues)==0, "; ".join(issues)

class BDPDPAService:
    def check_consent(self, user, purpose="notification"):
        try:
            profile = getattr(user,"profile",None)
            return bool(getattr(profile,f"pdpa_consent_{purpose}",True))
        except Exception: return True

gdpr_service = GDPRComplianceService()
data_retention_service = DataRetentionService()
can_spam_service = CANSPAMService()
bdpdpa_service = BDPDPAService()
