# api/djoyalty/services/QRCodeService.py
"""
QRCodeService -- QR code earn rules: generate, scan, verify and award points.
World reference: Subway QR scan earn, McDonald's app scan rewards,
Voucherify QR code campaigns.

Flow:
  1. get_active_rules()  -> list QR earn rules customer can scan
  2. scan()              -> customer scans a QR code, earns points
  3. generate_qr_data()  -> generate QR payload for a rule (for display)
  4. get_scan_history()  -> customer's QR scan history
"""
import logging
import hashlib
import uuid

# FIXED: qr_engine.py (LoyaltyQREngine) was orphaned -- now imported here
# for QR payload generation, validation and signed URL creation
try:
    from ..qr_engine import LoyaltyQREngine as _QREngine
    _qr_engine_available = True
except ImportError:
    _qr_engine_available = False
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class QRCodeService:

    @staticmethod
    def get_active_rules(customer=None, tenant=None, location: str = '') -> list:
        """
        Get active QR earn rules. Optionally filter by location/branch.
        Returns rules the customer hasn't maxed out.
        """
        try:
            from ..models.social import QRCodeEarn, QRCodeScan
            from django.db.models import Q
            from django.utils import timezone as tz

            now = tz.now()
            qs = QRCodeEarn.objects.filter(is_active=True).filter(
                Q(valid_from__isnull=True) | Q(valid_from__lte=now)
            ).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gte=now)
            )

            if tenant:
                qs = qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True))
            if location:
                qs = qs.filter(
                    Q(location_filter='') | Q(location_filter__icontains=location)
                )

            result = []
            for rule in qs:
                # Check daily limit
                scans_today = 0
                if customer:
                    scans_today = QRCodeScan.objects.filter(
                        customer=customer,
                        qr_rule=rule,
                        scanned_at__date=now.date(),
                        status='points_awarded',
                    ).count()
                    max_daily = getattr(rule, 'max_scans_per_day', 1)
                    if scans_today >= max_daily:
                        continue

                result.append({
                    'rule_id': rule.id,
                    'name': rule.name,
                    'description': getattr(rule, 'description', ''),
                    'points_reward': str(rule.points_reward),
                    'qr_code_value': rule.qr_code_value,
                    'scan_type': getattr(rule, 'scan_type', 'static'),
                    'location': getattr(rule, 'location_name', ''),
                    'max_per_day': getattr(rule, 'max_scans_per_day', 1),
                    'scans_today': scans_today,
                })
            return result

        except Exception as e:
            logger.error('QRCodeService.get_active_rules error: %s', e)
            return []

    @staticmethod
    @transaction.atomic
    def scan(customer, qr_value: str, location: str = '',
             device_id: str = '', tenant=None) -> dict:
        """
        Process a QR code scan by customer.
        Looks up matching rule, validates limits, awards points.
        Returns: {'success': True, 'points_awarded': Decimal, 'rule_name': str}
        """
        try:
            from ..models.social import QRCodeEarn, QRCodeScan
            from django.db.models import Q
            from django.utils import timezone as tz

            now = tz.now()

            # Find matching rule by QR value
            rule = QRCodeEarn.objects.filter(
                qr_code_value=qr_value,
                is_active=True,
            ).filter(
                Q(valid_from__isnull=True) | Q(valid_from__lte=now)
            ).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gte=now)
            ).first()

            if not rule:
                # Try hashed lookup (dynamic QR codes)
                rule = QRCodeService._lookup_dynamic_qr(qr_value)

            if not rule:
                return {'success': False, 'error': 'QR code not recognised or expired'}

            # Daily scan limit
            max_daily = getattr(rule, 'max_scans_per_day', 1)
            scans_today = QRCodeScan.objects.filter(
                customer=customer,
                qr_rule=rule,
                scanned_at__date=now.date(),
                status='points_awarded',
            ).count()
            if scans_today >= max_daily:
                return {
                    'success': False,
                    'error': f'Daily scan limit reached ({max_daily}/day for this QR)',
                }

            # Total scans limit
            max_total = getattr(rule, 'max_scans_total', None)
            if max_total:
                total_scans = QRCodeScan.objects.filter(
                    qr_rule=rule, status='points_awarded',
                ).count()
                if total_scans >= max_total:
                    return {'success': False, 'error': 'This QR code has reached its total scan limit'}

            # Record scan
            scan = QRCodeScan.objects.create(
                customer=customer,
                qr_rule=rule,
                tenant=tenant or getattr(customer, 'tenant', None),
                qr_value_scanned=qr_value,
                location=location or '',
                device_id=device_id or '',
                status='pending',
                scanned_at=now,
            )

            # Award points
            points = rule.points_reward or Decimal('0')
            if points > 0:
                from .earn.BonusEventService import BonusEventService
                BonusEventService.award_bonus(
                    customer, points,
                    reason=f'QR scan: {rule.name}',
                    triggered_by='qr_scan',
                    tenant=tenant,
                )

            scan.status = 'points_awarded'
            scan.points_awarded = points
            scan.save(update_fields=['status', 'points_awarded'])

            logger.info('QRCodeService.scan: %s scanned %s -> %s pts',
                        customer.code, rule.name, points)

            return {
                'success': True,
                'scan_id': scan.id,
                'rule_name': rule.name,
                'points_awarded': str(points),
                'scans_remaining_today': max(0, max_daily - scans_today - 1),
            }

        except Exception as e:
            logger.error('QRCodeService.scan error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def generate_qr_data(rule_id: int, customer=None) -> dict:
        """
        Generate QR payload data for a rule.
        For static rules: returns the static value.
        For dynamic rules: generates a time-based signed token.
        Returns: {'qr_value': str, 'display_url': str, 'expires_in': seconds}
        """
        try:
            from ..models.social import QRCodeEarn

            try:
                rule = QRCodeEarn.objects.get(id=rule_id, is_active=True)
            except QRCodeEarn.DoesNotExist:
                return {'success': False, 'error': 'QR rule not found'}

            scan_type = getattr(rule, 'scan_type', 'static')

            if scan_type == 'dynamic' and customer:
                # Time-based token: rule_id + customer_id + timestamp + secret
                timestamp = int(timezone.now().timestamp())
                secret = getattr(rule, 'secret_key', rule.qr_code_value)
                raw = f'{rule.id}:{customer.id}:{timestamp}:{secret}'
                token = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
                qr_value = f'DJL:{rule.id}:{token}'
                # Cache token for 5 minutes
                try:
                    from django.core.cache import cache
                    cache.set(f'qr_token:{qr_value}', rule.id, timeout=300)
                except Exception:
                    pass
                return {
                    'success': True,
                    'qr_value': qr_value,
                    'scan_type': 'dynamic',
                    'expires_in': 300,
                }
            else:
                return {
                    'success': True,
                    'qr_value': rule.qr_code_value,
                    'scan_type': 'static',
                    'expires_in': None,
                }

        except Exception as e:
            logger.error('QRCodeService.generate_qr_data error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_scan_history(customer, limit: int = 20) -> list:
        """Customer's QR scan history."""
        try:
            from ..models.social import QRCodeScan
            return list(
                QRCodeScan.objects.filter(customer=customer)
                .order_by('-scanned_at')[:limit]
                .values(
                    'id', 'qr_rule__name', 'location',
                    'points_awarded', 'status', 'scanned_at',
                )
            )
        except Exception as e:
            logger.error('QRCodeService.get_scan_history error: %s', e)
            return []

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _lookup_dynamic_qr(qr_value: str):
        """Try to resolve a dynamic QR token via cache or prefix match."""
        try:
            from django.core.cache import cache
            rule_id = cache.get(f'qr_token:{qr_value}')
            if rule_id:
                from ..models.social import QRCodeEarn
                return QRCodeEarn.objects.filter(id=rule_id, is_active=True).first()
            # Try DJL prefix parse: DJL:{rule_id}:{token}
            if qr_value.startswith('DJL:'):
                parts = qr_value.split(':')
                if len(parts) >= 2:
                    rule_id = int(parts[1])
                    from ..models.social import QRCodeEarn
                    return QRCodeEarn.objects.filter(id=rule_id, is_active=True).first()
        except Exception:
            pass
        return None

    @staticmethod
    def process_scan(customer, qr_value: str = '', location: str = '',
                     device_id: str = '', tenant=None, **kwargs) -> dict:
        """Alias for scan() -- matches ReceiptSocialViewSet call signature."""
        return QRCodeService.scan(
            customer=customer, qr_value=qr_value,
            location=location, device_id=device_id, tenant=tenant,
        )

    @staticmethod
    def generate(rule_id: int = None, customer=None, **kwargs) -> dict:
        """Alias for generate_qr_data() -- matches ReceiptSocialViewSet call."""
        if not rule_id:
            return {'success': False, 'error': 'rule_id required'}
        return QRCodeService.generate_qr_data(rule_id=rule_id, customer=customer)
    @staticmethod
    def generate_qr_image(rule_id: int, size: int = 256) -> bytes:
        """
        Generate QR code image bytes for a rule।
        FIXED: delegates to LoyaltyQREngine (qr_engine.py) which was orphaned。
        Returns PNG bytes or None if image generation not available。
        """
        if not _qr_engine_available:
            return None
        try:
            from ..models.social import QRCodeEarn
            rule = QRCodeEarn.objects.get(pk=rule_id)
            return _QREngine.generate_png(
                data=rule.qr_code_value or rule.qr_code or str(rule_id),
                size=size,
            )
        except Exception as e:
            logger.error('QRCodeService.generate_qr_image error: %s', e)
            return None

    @staticmethod
    def validate_qr_signature(payload: str, signature: str) -> bool:
        """
        Validate a signed QR payload। Delegates to LoyaltyQREngine。
        FIXED: LoyaltyQREngine.validate_signature() was defined but no callers。
        """
        if not _qr_engine_available:
            return True   # fail open if engine not available
        try:
            return _QREngine.validate_signature(payload=payload, signature=signature)
        except Exception:
            return False
