# api/djoyalty/services/ReceiptScanService.py
"""
ReceiptScanService -- receipt scan -> points earn (Fetch Rewards style)।
World: Fetch Rewards $2.5B valuation, Snipp receipt processing।
2025: AI-powered OCR + AI fraud detection (AI-generated receipts spike)।
"""
import hashlib
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class ReceiptScanService:

    @staticmethod
    @transaction.atomic
    def submit_receipt(customer, receipt_image_url: str, channel: str = 'app',
                        device_info: str = None, tenant=None):
        """
        Customer receipt submit করো -- OCR processing queue এ রাখো।
        """
        from ..models.family_eco import ReceiptScan

        # Hash for duplicate detection
        receipt_hash = hashlib.sha256(receipt_image_url.encode()).hexdigest()

        # Duplicate check
        duplicate = ReceiptScan.objects.filter(
            customer=customer,
            receipt_hash=receipt_hash,
        ).first()
        if duplicate:
            raise ValueError(f'This receipt was already submitted (ref: #{duplicate.id})')

        scan = ReceiptScan.objects.create(
            customer=customer,
            tenant=tenant or customer.tenant,
            receipt_image_url=receipt_image_url,
            receipt_hash=receipt_hash,
            channel=channel,
            status='pending',
        )

        logger.info('ReceiptScanService: receipt submitted by %s (scan #%d)', customer.code, scan.id)
        return scan

    @staticmethod
    @transaction.atomic
    def process_receipt(scan_id: int, ocr_results: dict = None, reviewed_by: str = 'system'):
        """
        OCR results process করো + points award করো।
        ocr_results: {
            merchant_name, total_amount, purchase_date, items, raw_text, fraud_score
        }
        """
        from ..models.family_eco import ReceiptScan, ReceiptEarnRule
        from ..models.points import LoyaltyPoints, PointsLedger
        from ..choices import LEDGER_CREDIT

        scan = ReceiptScan.objects.select_for_update().get(id=scan_id)

        if scan.status not in ('pending', 'processing'):
            raise ValueError(f'Receipt scan #{scan_id} is already {scan.status}')

        scan.status = 'processing'
        scan.save(update_fields=['status'])

        ocr = ocr_results or {}

        # Update OCR data
        scan.merchant_name = ocr.get('merchant_name', '')
        scan.total_amount = Decimal(str(ocr.get('total_amount', 0))) if ocr.get('total_amount') else None
        scan.raw_ocr_text = ocr.get('raw_text', '')
        scan.items_detected = ocr.get('items', [])
        scan.ai_fraud_score = Decimal(str(ocr.get('fraud_score', 0)))
        scan.is_ai_generated = ocr.get('is_ai_generated', False)

        # Fraud check
        if scan.ai_fraud_score > Decimal('0.7') or scan.is_ai_generated:
            scan.status = 'fraud_suspected'
            scan.rejection_reason = 'AI fraud detection: suspicious receipt'
            scan.processed_at = timezone.now()
            scan.reviewed_by = reviewed_by
            scan.save()
            logger.warning('ReceiptScanService: fraud suspected for scan #%d (score=%s)',
                           scan_id, scan.ai_fraud_score)
            return scan

        # Find applicable earn rule
        earn_rule = ReceiptScanService._find_earn_rule(
            scan.merchant_name, scan.total_amount, scan.customer
        )

        if not earn_rule:
            scan.status = 'rejected'
            scan.rejection_reason = 'No applicable earn rule found'
            scan.processed_at = timezone.now()
            scan.save()
            return scan

        # Calculate points
        points = ReceiptScanService._calculate_points(earn_rule, scan.total_amount)

        if points <= 0:
            scan.status = 'rejected'
            scan.rejection_reason = 'Receipt amount below minimum'
            scan.processed_at = timezone.now()
            scan.save()
            return scan

        # Award points
        lp, _ = LoyaltyPoints.objects.get_or_create(
            customer=scan.customer,
            defaults={'tenant': scan.tenant, 'balance': Decimal('0')},
        )
        lp.credit(points)

        PointsLedger.objects.create(
            customer=scan.customer,
            tenant=scan.tenant,
            txn_type=LEDGER_CREDIT,
            source='purchase',
            points=points,
            balance_after=lp.balance,
            description=f'Receipt scan: {scan.merchant_name or "Purchase"} -- {scan.total_amount}',
            reference_id=f'RECEIPT-{scan.id}',
        )

        scan.points_awarded = points
        scan.status = 'approved'
        scan.processed_at = timezone.now()
        scan.reviewed_by = reviewed_by
        scan.save()

        logger.info('ReceiptScanService: scan #%d approved -- +%s pts for %s',
                    scan_id, points, scan.customer.code)
        return scan

    @staticmethod
    def _find_earn_rule(merchant_name: str, amount, customer):
        """Applicable receipt earn rule খোঁজো।"""
        from ..models.family_eco import ReceiptEarnRule
        qs = ReceiptEarnRule.objects.filter(is_active=True)

        # Merchant-specific rule first
        if merchant_name:
            merchant_rule = qs.filter(
                target_merchant__icontains=merchant_name
            ).first()
            if merchant_rule:
                return merchant_rule

        # General rule
        return qs.filter(target_merchant__isnull=True).order_by('-points_value').first()

    @staticmethod
    def _calculate_points(rule, total_amount) -> Decimal:
        """Points calculate করো from earn rule।"""
        if not total_amount:
            return Decimal('0')
        amount = Decimal(str(total_amount))
        if amount < rule.min_amount:
            return Decimal('0')
        if rule.earn_type == 'fixed':
            points = rule.points_value
        else:  # percentage
            points = amount * (rule.points_value / Decimal('100'))
        if rule.max_points_per_receipt:
            points = min(points, rule.max_points_per_receipt)
        return points.quantize(Decimal('0.01'))

    @staticmethod
    def get_customer_receipt_history(customer, limit: int = 20) -> list:
        """Customer এর receipt scan history।"""
        from ..models.family_eco import ReceiptScan
        return list(
            ReceiptScan.objects.filter(customer=customer)
            .order_by('-submitted_at')[:limit]
            .values(
                'id', 'merchant_name', 'total_amount', 'points_awarded',
                'status', 'submitted_at', 'channel',
            )
        )

    @staticmethod
    def submit(customer, image_url: str = '', channel: str = 'app',
               metadata: dict = None, tenant=None) -> dict:
        """Alias for submit_receipt() -- matches viewset call signature."""
        return ReceiptScanService.submit_receipt(
            customer=customer,
            receipt_image_url=image_url or (metadata or {}).get('image_url', ''),
            channel=channel,
            metadata=metadata,
            tenant=tenant,
        )

    @staticmethod
    def approve(scan_id: int = None, scan=None, approved_by: str = 'admin',
                ocr_results: dict = None) -> dict:
        """Alias for process_receipt() approve flow -- matches viewset call signature."""
        sid = scan_id or (scan.id if scan else None)
        if not sid:
            return {'success': False, 'error': 'scan_id required'}
        return ReceiptScanService.process_receipt(
            scan_id=sid,
            ocr_results=ocr_results or {},
            reviewed_by=approved_by,
        )
