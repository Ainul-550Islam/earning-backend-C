# api/djoyalty/tasks/receipt_scan_tasks.py
"""
Receipt Scan Celery Tasks।
OCR processing, fraud check, points award।
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='djoyalty.process_receipt_scan', bind=True, max_retries=2)
def process_receipt_scan_task(self, scan_id: int):
    """
    Process a pending receipt scan via OCR।
    Called when customer submits receipt।
    """
    try:
        from ..models.family_eco import ReceiptScan
        from ..services.ReceiptScanService import ReceiptScanService
        from ..integrations.ocr import OCRService

        scan = ReceiptScan.objects.get(id=scan_id)
        if scan.status not in ('pending', 'processing'):
            return {'skipped': True, 'status': scan.status}

        # Run OCR
        ocr_result = OCRService.process_receipt(scan.receipt_image_url)

        # Process result
        processed_scan = ReceiptScanService.process_receipt(
            scan_id=scan_id,
            ocr_results=ocr_result,
            reviewed_by='system_ocr',
        )

        logger.info('process_receipt_scan_task: scan #%d -> %s (+%s pts)',
                    scan_id, processed_scan.status, processed_scan.points_awarded)
        return {
            'scan_id': scan_id,
            'status': processed_scan.status,
            'points_awarded': str(processed_scan.points_awarded),
        }
    except Exception as exc:
        logger.error('process_receipt_scan_task #%d error: %s', scan_id, exc)
        raise self.retry(exc=exc, countdown=60)


@shared_task(name='djoyalty.cleanup_old_receipt_scans')
def cleanup_old_receipt_scans_task(days: int = 90):
    """Remove old receipt scan raw OCR data to save storage।"""
    try:
        from datetime import timedelta
        from django.utils import timezone
        from ..models.family_eco import ReceiptScan

        cutoff = timezone.now() - timedelta(days=days)
        updated = ReceiptScan.objects.filter(
            submitted_at__lt=cutoff,
            status__in=['approved', 'rejected', 'fraud_suspected'],
        ).update(raw_ocr_text='', items_detected=[])

        logger.info('cleanup_old_receipt_scans_task: cleaned %d records', updated)
        return {'cleaned': updated}
    except Exception as exc:
        logger.error('cleanup_old_receipt_scans_task error: %s', exc)
        return {'error': str(exc)}


@shared_task(name='djoyalty.flag_suspicious_receipts')
def flag_suspicious_receipts_task():
    """Scan recent receipts for AI fraud patterns।"""
    try:
        from decimal import Decimal
        from django.utils import timezone
        from datetime import timedelta
        from ..models.family_eco import ReceiptScan

        recent = ReceiptScan.objects.filter(
            submitted_at__gte=timezone.now() - timedelta(hours=24),
            status='pending',
        )

        flagged = 0
        for scan in recent:
            if scan.ai_fraud_score > Decimal('0.6') or scan.is_ai_generated:
                scan.status = 'fraud_suspected'
                scan.save(update_fields=['status'])
                flagged += 1

        logger.info('flag_suspicious_receipts_task: flagged %d', flagged)
        return {'flagged': flagged}
    except Exception as exc:
        logger.error('flag_suspicious_receipts_task error: %s', exc)
        return {'error': str(exc)}
