# kyc/services.py  ── WORLD #1 COMPLETE — existing + new services
import logging
from typing import Optional, Dict, Any
from django.utils import timezone

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# ORIGINAL KYCService  (existing — unchanged)
# ══════════════════════════════════════════════════════════════
class KYCService:

    @staticmethod
    def get_kyc_status(user) -> Optional[Dict[str, Any]]:
        try:
            from .models import KYC
            kyc = KYC.objects.filter(user=user).first()
            if not kyc:
                return {"status": "not_submitted", "verified": False}
            return {
                "status": kyc.status,
                "verified": kyc.status == 'verified',
                "document_type": getattr(kyc, 'document_type', None),
                "rejection_reason": kyc.rejection_reason if kyc.status == 'rejected' else None,
                "submitted_at": kyc.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            }
        except Exception as e:
            logger.error("KYC status error: %s", e)
            return None

    @staticmethod
    def check_duplicate(kyc) -> bool:
        from .models import KYC
        if kyc.document_number:
            if KYC.objects.filter(document_number=kyc.document_number, status='verified').exclude(id=kyc.id).exists():
                kyc.is_duplicate = True; kyc.save(); return True
        if kyc.phone_number:
            if KYC.objects.filter(phone_number=kyc.phone_number, status='verified').exclude(id=kyc.id).exists():
                kyc.is_duplicate = True; kyc.save(); return True
        return False

    @staticmethod
    def is_user_verified(user) -> bool:
        from .models import KYC
        return KYC.objects.filter(user=user, status='verified').exists()


# ══════════════════════════════════════════════════════════════
# NEW SERVICES — World #1
# ══════════════════════════════════════════════════════════════

class KYCBlacklistService:
    """Blacklist check service"""

    @staticmethod
    def check_all(phone: str = None, doc_number: str = None, ip: str = None, email: str = None) -> dict:
        from .models import KYCBlacklist
        result = {'is_blocked': False, 'blocked_fields': []}
        checks = [('phone', phone), ('document', doc_number), ('ip', ip), ('email', email)]
        for btype, value in checks:
            if value and KYCBlacklist.is_blacklisted(btype, value):
                result['is_blocked'] = True
                result['blocked_fields'].append(btype)
        return result

    @staticmethod
    def add(btype: str, value: str, reason: str = '', added_by=None, tenant=None):
        from .models import KYCBlacklist
        obj, created = KYCBlacklist.objects.get_or_create(
            type=btype, value=value,
            defaults={'reason': reason, 'added_by': added_by, 'tenant': tenant, 'is_active': True}
        )
        if not created:
            obj.is_active = True; obj.save()
        return obj, created


class KYCRiskService:
    """Comprehensive risk scoring service"""

    @staticmethod
    def compute_full_risk(kyc) -> int:
        from .models import KYCRiskProfile, KYCOCRResult, KYCFaceMatchResult
        profile, _ = KYCRiskProfile.objects.get_or_create(kyc=kyc)

        ocr_result  = KYCOCRResult.objects.filter(kyc=kyc).order_by('-created_at').first()
        face_result = KYCFaceMatchResult.objects.filter(kyc=kyc).order_by('-created_at').first()

        profile.name_match_score       = ocr_result.confidence  if ocr_result  else 0.0
        profile.face_match_score       = face_result.match_confidence if face_result else 0.0
        profile.document_clarity_score = kyc.ocr_confidence * 100
        profile.ocr_confidence_score   = kyc.ocr_confidence
        profile.duplicate_flag         = kyc.is_duplicate
        profile.age_flag               = KYCRiskService._check_age(kyc)
        profile.blacklist_flag         = KYCRiskService._check_blacklist(kyc)

        score = profile.compute()
        kyc.risk_score = score; kyc.risk_factors = profile.factors; kyc.save(update_fields=['risk_score', 'risk_factors', 'updated_at'])
        return score

    @staticmethod
    def _check_age(kyc) -> bool:
        if not kyc.date_of_birth: return False
        from datetime import date
        age = (date.today() - kyc.date_of_birth).days / 365.25
        return age < 18

    @staticmethod
    def _check_blacklist(kyc) -> bool:
        from .models import KYCBlacklist
        checks = [
            ('phone',    kyc.phone_number),
            ('document', kyc.document_number),
        ]
        return any(KYCBlacklist.is_blacklisted(t, v) for t, v in checks if v)


class KYCNotificationService:
    """Notification sending service"""

    @staticmethod
    def send(user, event_type: str, kyc=None, channel: str = 'in_app', extra: dict = None):
        from .models import KYCNotificationLog
        from .constants import NotificationTemplates
        templates = {
            'kyc_submitted': NotificationTemplates.KYC_SUBMITTED,
            'kyc_verified':  NotificationTemplates.KYC_VERIFIED,
            'kyc_rejected':  NotificationTemplates.KYC_REJECTED,
            'kyc_expired':   NotificationTemplates.KYC_EXPIRED,
        }
        tpl = templates.get(event_type, {'title': event_type, 'message': '', 'type': event_type})
        message = tpl['message']
        if extra:
            try: message = message.format(**extra)
            except Exception: pass

        log = KYCNotificationLog.objects.create(
            user=user, kyc=kyc, channel=channel,
            event_type=event_type, title=tpl['title'], message=message,
        )
        # Try sending via real notification system
        try:
            from api.notifications.models import Notification
            Notification.objects.create(
                user=user, title=tpl['title'], message=message, notification_type=event_type
            )
            log.is_sent = True; log.sent_at = timezone.now(); log.save(update_fields=['is_sent','sent_at'])
        except Exception as e:
            log.error = str(e); log.save(update_fields=['error'])

        return log


class KYCAuditService:
    """Centralized audit trail service"""

    @staticmethod
    def log(entity_type, entity_id, action, actor=None, tenant=None,
            before=None, after=None, description='', severity='low',
            request=None):
        from .models import KYCAuditTrail
        actor_ip    = ''
        actor_agent = ''
        session_id  = ''
        request_id  = ''

        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            actor_ip    = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR', '')
            actor_agent = request.META.get('HTTP_USER_AGENT', '')
            session_id  = request.session.session_key or '' if hasattr(request, 'session') else ''

        return KYCAuditTrail.log(
            entity_type=entity_type, entity_id=entity_id, action=action,
            actor=actor, tenant=tenant, before=before, after=after,
            description=description, severity=severity,
            actor_ip=actor_ip, actor_agent=actor_agent,
            session_id=session_id, request_id=request_id,
        )


class KYCWebhookService:
    """Webhook dispatch service"""

    @staticmethod
    def dispatch(event: str, payload: dict, tenant=None):
        from .models import KYCWebhookEndpoint, KYCWebhookDeliveryLog
        import json, hashlib, hmac, time
        try:
            import requests
        except ImportError:
            logger.warning("requests not installed — webhook dispatch skipped")
            return

        endpoints = KYCWebhookEndpoint.objects.filter(is_active=True, tenant=tenant)
        if not endpoints.exists():
            endpoints = KYCWebhookEndpoint.objects.filter(is_active=True, tenant__isnull=True)

        for endpoint in endpoints:
            if event not in (endpoint.events or []):
                continue
            body        = json.dumps(payload)
            headers     = {'Content-Type': 'application/json', **(endpoint.headers or {})}
            if endpoint.secret_key:
                sig = hmac.new(endpoint.secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()
                headers['X-KYC-Signature'] = f"sha256={sig}"

            start = time.time()
            try:
                resp = requests.post(endpoint.url, data=body, headers=headers, timeout=endpoint.timeout_sec)
                duration_ms  = int((time.time() - start) * 1000)
                is_success   = resp.status_code < 400
                KYCWebhookDeliveryLog.objects.create(
                    endpoint=endpoint, event=event, payload=payload,
                    response_code=resp.status_code, response_body=resp.text[:2000],
                    is_success=is_success, duration_ms=duration_ms,
                )
            except Exception as e:
                KYCWebhookDeliveryLog.objects.create(
                    endpoint=endpoint, event=event, payload=payload,
                    is_success=False, error=str(e),
                )


class KYCAnalyticsService:
    """Analytics snapshot generation"""

    @staticmethod
    def generate_daily_snapshot(tenant=None, date=None):
        from .models import KYCAnalyticsSnapshot, KYC
        from django.db.models import Count, Avg
        import datetime

        date    = date or timezone.now().date()
        start   = timezone.make_aware(datetime.datetime.combine(date, datetime.time.min))
        end     = timezone.make_aware(datetime.datetime.combine(date, datetime.time.max))
        qs      = KYC.objects.filter(tenant=tenant) if tenant else KYC.objects.all()
        day_qs  = qs.filter(created_at__range=(start, end))

        total   = day_qs.count()
        verified = day_qs.filter(status='verified').count()

        snap, _ = KYCAnalyticsSnapshot.objects.update_or_create(
            tenant=tenant, period='daily', period_start=start,
            defaults={
                'period_end':      end,
                'total_submitted': total,
                'total_verified':  verified,
                'total_rejected':  day_qs.filter(status='rejected').count(),
                'total_pending':   day_qs.filter(status='pending').count(),
                'total_expired':   day_qs.filter(status='expired').count(),
                'avg_risk_score':  day_qs.aggregate(avg=Avg('risk_score'))['avg'] or 0.0,
                'high_risk_count': day_qs.filter(risk_score__gt=60).count(),
                'duplicate_count': day_qs.filter(is_duplicate=True).count(),
                'verification_rate': (verified / total * 100) if total else 0.0,
            }
        )
        return snap
