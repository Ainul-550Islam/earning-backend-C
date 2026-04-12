# kyc/tasks/kyc_tasks.py  ── WORLD #1 — All Celery Tasks
"""
Celery tasks for KYC system.
Requires celery installed + configured in settings.
Falls back gracefully if celery not available.
"""
import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task
except ImportError:
    # Graceful fallback — celery not installed
    def shared_task(func=None, **kwargs):
        if func: return func
        def wrapper(f): return f
        return wrapper


# ══════════════════════════════════════════════════════════════
# OCR TASKS
# ══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_ocr_extraction(self, kyc_id: int, document_side: str = 'front'):
    """Async OCR extraction task"""
    try:
        from api.kyc.models import KYC, KYCOCRResult, KYCVerificationStep
        import time

        kyc = KYC.objects.get(id=kyc_id)
        step, _ = KYCVerificationStep.objects.get_or_create(kyc=kyc, step='ocr_check', defaults={'order': 3})
        step.status = 'in_progress'; step.started_at = __import__('django.utils.timezone', fromlist=['timezone']).timezone.now(); step.save()

        image = kyc.document_front if document_side == 'front' else kyc.document_back
        if not image:
            step.mark_failed('No image found'); return

        start = time.time()
        # Mock OCR — replace with real provider
        result = KYCOCRResult.objects.create(
            kyc=kyc, provider='tesseract', document_side=document_side,
            extracted_name=kyc.full_name or '',
            confidence=0.85, is_successful=True,
            processing_time_ms=int((time.time() - start) * 1000),
        )

        kyc.ocr_confidence = result.confidence; kyc.save(update_fields=['ocr_confidence', 'updated_at'])
        step.mark_done({'confidence': result.confidence, 'ocr_result_id': result.id})
        logger.info(f"OCR completed for KYC {kyc_id}")
    except Exception as exc:
        logger.error(f"OCR task failed for KYC {kyc_id}: {exc}")
        raise self.retry(exc=exc)


# ══════════════════════════════════════════════════════════════
# FACE MATCH TASKS
# ══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_face_match(self, kyc_id: int):
    """Async face matching task"""
    try:
        from api.kyc.models import KYC, KYCFaceMatchResult, KYCVerificationStep
        import time

        kyc = KYC.objects.get(id=kyc_id)
        step, _ = KYCVerificationStep.objects.get_or_create(kyc=kyc, step='face_check', defaults={'order': 4})
        step.status = 'in_progress'; step.save()

        if not kyc.selfie_photo or not kyc.document_front:
            step.mark_failed('Missing images'); return

        start = time.time()
        # Mock face match — replace with real provider (AWS Rekognition, etc.)
        result = KYCFaceMatchResult.objects.create(
            kyc=kyc, provider='deepface', match_confidence=0.92, liveness_score=0.88,
            is_matched=True, is_liveness_pass=True,
            face_detected_selfie=True, face_detected_doc=True,
            processing_time_ms=int((time.time() - start) * 1000),
        )

        kyc.is_face_verified = result.is_matched; kyc.save(update_fields=['is_face_verified', 'updated_at'])
        step.mark_done({'matched': result.is_matched, 'confidence': result.match_confidence})
        logger.info(f"Face match completed for KYC {kyc_id}: matched={result.is_matched}")
    except Exception as exc:
        logger.error(f"Face match task failed for KYC {kyc_id}: {exc}")
        raise self.retry(exc=exc)


# ══════════════════════════════════════════════════════════════
# RISK TASKS
# ══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2)
def run_risk_scoring(self, kyc_id: int):
    """Async risk score computation"""
    try:
        from api.kyc.models import KYC
        from api.kyc.services import KYCRiskService
        kyc   = KYC.objects.get(id=kyc_id)
        score = KYCRiskService.compute_full_risk(kyc)
        logger.info(f"Risk scored for KYC {kyc_id}: score={score}")
    except Exception as exc:
        logger.error(f"Risk task failed for KYC {kyc_id}: {exc}")
        raise self.retry(exc=exc)


# ══════════════════════════════════════════════════════════════
# NOTIFICATION TASKS
# ══════════════════════════════════════════════════════════════

@shared_task
def send_kyc_notification(user_id: int, event_type: str, kyc_id: int = None, extra: dict = None):
    """Async notification send"""
    try:
        from django.contrib.auth import get_user_model
        from api.kyc.services import KYCNotificationService
        from api.kyc.models import KYC
        User = get_user_model()
        user = User.objects.get(id=user_id)
        kyc  = KYC.objects.filter(id=kyc_id).first() if kyc_id else None
        KYCNotificationService.send(user=user, event_type=event_type, kyc=kyc, extra=extra or {})
    except Exception as e:
        logger.error(f"Notification task failed: {e}")


# ══════════════════════════════════════════════════════════════
# EXPIRY TASKS
# ══════════════════════════════════════════════════════════════

@shared_task
def expire_overdue_kycs():
    """Mark expired KYCs — run daily via celery beat"""
    from api.kyc.models import KYC
    from django.utils import timezone

    expired = KYC.objects.filter(status='verified', expires_at__lt=timezone.now())
    count   = expired.count()
    expired.update(status='expired')
    logger.info(f"Expired {count} KYC records")
    return count


@shared_task
def notify_expiring_soon_kycs(days: int = 30):
    """Notify users whose KYC expires within `days` days"""
    from api.kyc.models import KYC
    from api.kyc.services import KYCNotificationService
    from django.utils import timezone
    import datetime

    deadline = timezone.now() + datetime.timedelta(days=days)
    expiring = KYC.objects.filter(status='verified', expires_at__lte=deadline, expires_at__gte=timezone.now())
    count = 0
    for kyc in expiring:
        days_left = (kyc.expires_at - timezone.now()).days
        KYCNotificationService.send(
            user=kyc.user, event_type='kyc_expiring_soon', kyc=kyc,
            extra={'days': days_left}
        )
        count += 1
    logger.info(f"Sent expiry warnings to {count} users")
    return count


# ══════════════════════════════════════════════════════════════
# CLEANUP TASKS
# ══════════════════════════════════════════════════════════════

@shared_task
def cleanup_old_export_jobs(days: int = 7):
    """Delete old completed export jobs"""
    from api.kyc.models import KYCExportJob
    from django.utils import timezone
    import datetime

    cutoff = timezone.now() - datetime.timedelta(days=days)
    deleted, _ = KYCExportJob.objects.filter(status__in=['done','failed'], created_at__lt=cutoff).delete()
    logger.info(f"Deleted {deleted} old export jobs")
    return deleted


@shared_task
def cleanup_old_otp_logs(hours: int = 48):
    """Delete expired/used OTP logs"""
    from api.kyc.models import KYCOTPLog
    from django.utils import timezone
    import datetime

    cutoff = timezone.now() - datetime.timedelta(hours=hours)
    deleted, _ = KYCOTPLog.objects.filter(expires_at__lt=cutoff).delete()
    logger.info(f"Deleted {deleted} old OTP logs")
    return deleted


# ══════════════════════════════════════════════════════════════
# EXPORT TASKS
# ══════════════════════════════════════════════════════════════

@shared_task
def export_kyc_data(job_id: int):
    """Process a KYC export job"""
    from api.kyc.models import KYCExportJob, KYC
    from django.utils import timezone
    import csv, io

    try:
        job = KYCExportJob.objects.get(id=job_id)
        job.status = 'processing'; job.started_at = timezone.now(); job.save(update_fields=['status','started_at'])

        qs = KYC.objects.all()
        if job.filters.get('status'): qs = qs.filter(status=job.filters['status'])

        if job.format == 'csv':
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(['ID','Username','Full Name','Status','Document Type','Document Number','Risk Score','Created At'])
            rows = 0
            for kyc in qs.select_related('user'):
                writer.writerow([kyc.id, kyc.user.username, kyc.full_name, kyc.status,
                                  kyc.document_type, kyc.document_number, kyc.risk_score, kyc.created_at])
                rows += 1
            from django.core.files.base import ContentFile
            job.file.save(f'kyc_export_{job_id}.csv', ContentFile(buf.getvalue().encode()))
            job.row_count = rows

        job.status = 'done'; job.completed_at = timezone.now()
        job.save(update_fields=['status','completed_at','row_count','file'])
        logger.info(f"Export job {job_id} completed: {job.row_count} rows")
    except Exception as e:
        if 'job' in dir():
            job.status = 'failed'; job.error = str(e); job.save(update_fields=['status','error'])
        logger.error(f"Export job {job_id} failed: {e}")


# ══════════════════════════════════════════════════════════════
# ANALYTICS TASKS
# ══════════════════════════════════════════════════════════════

@shared_task
def generate_daily_analytics():
    """Generate daily analytics snapshot — run via celery beat"""
    from api.kyc.services import KYCAnalyticsService
    snap = KYCAnalyticsService.generate_daily_snapshot()
    logger.info(f"Daily analytics snapshot generated: {snap}")
    return snap.id if snap else None


# ══════════════════════════════════════════════════════════════
# DUPLICATE DETECTION TASKS
# ══════════════════════════════════════════════════════════════

@shared_task
def detect_duplicates(kyc_id: int):
    """Detect and group duplicate KYC records"""
    try:
        from api.kyc.models import KYC, KYCDuplicateGroup
        kyc = KYC.objects.get(id=kyc_id)
        found = False

        if kyc.document_number:
            dup_kycs = KYC.objects.filter(document_number=kyc.document_number).exclude(id=kyc_id)
            if dup_kycs.exists():
                group, _ = KYCDuplicateGroup.objects.get_or_create(
                    match_type='document', match_value=kyc.document_number
                )
                group.kyc_records.add(kyc, *dup_kycs)
                kyc.is_duplicate = True; kyc.save(update_fields=['is_duplicate', 'updated_at'])
                found = True

        if kyc.phone_number and not found:
            dup_kycs = KYC.objects.filter(phone_number=kyc.phone_number, status='verified').exclude(id=kyc_id)
            if dup_kycs.exists():
                group, _ = KYCDuplicateGroup.objects.get_or_create(
                    match_type='phone', match_value=kyc.phone_number
                )
                group.kyc_records.add(kyc, *dup_kycs)
                kyc.is_duplicate = True; kyc.save(update_fields=['is_duplicate', 'updated_at'])

        logger.info(f"Duplicate detection for KYC {kyc_id}: duplicate={kyc.is_duplicate}")
    except Exception as e:
        logger.error(f"Duplicate detection failed for KYC {kyc_id}: {e}")
