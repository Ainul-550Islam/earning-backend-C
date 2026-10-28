# publisher_tools/views_fraud.py
# Exposes fraud_prevention/ subfolder logic via DRF.
# Register: router.register(r'fraud', FraudViewSet, basename='fraud')

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher


class FraudViewSet(BaseViewSet):
    """
    Fraud Detection & Prevention API.
    fraud_prevention/ subfolder-এর সব logic expose করা হয়েছে।

    Publisher endpoints:
      GET  /fraud/my-summary/        — নিজের IVT summary
      GET  /fraud/ip-check/          — IP reputation check
      GET  /fraud/alerts/            — active fraud alerts

    Admin endpoints:
      GET  /fraud/platform-report/   — platform-wide fraud report
      POST /fraud/check-impression/  — impression fraud check
      POST /fraud/check-click/       — click fraud check
      POST /fraud/check-conversion/  — conversion fraud check
      POST /fraud/block-ip/          — manual IP block
      POST /fraud/unblock-ip/        — IP unblock
      GET  /fraud/blocked-ips/       — blocked IP list
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_publisher(self):
        try:
            return self.request.user.publisher_profile
        except Exception:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No active publisher profile.')

    # ── PUBLISHER: My Summary ─────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='my-summary')
    def my_summary(self, request):
        """
        Publisher-এর নিজের IVT + fraud summary।
        GET /fraud/my-summary/?days=30
        """
        publisher = self._get_publisher()
        days = int(request.query_params.get('days', 30))

        try:
            from .fraud_prevention import generate_fraud_report
            data = generate_fraud_report(publisher, days=days)
        except (ImportError, Exception) as e:
            # Fallback: inline summary
            from .models import TrafficSafetyLog
            from django.utils import timezone
            from django.db.models import Count, Sum, Avg
            cutoff = timezone.now() - __import__('datetime').timedelta(days=days)
            qs = TrafficSafetyLog.objects.filter(
                publisher=publisher,
                detected_at__gte=cutoff,
            )
            agg = qs.aggregate(
                total=Count('id'),
                revenue_at_risk=Sum('revenue_at_risk'),
                avg_score=Avg('fraud_score'),
            )
            by_type = list(
                qs.values('traffic_type').annotate(count=Count('id')).order_by('-count')
            )
            data = {
                'publisher_id':     publisher.publisher_id,
                'period_days':      days,
                'total_events':     agg.get('total') or 0,
                'revenue_at_risk':  float(agg.get('revenue_at_risk') or 0),
                'avg_fraud_score':  float(agg.get('avg_score') or 0),
                'by_traffic_type':  by_type,
            }

        return self.success_response(data=data)

    # ── PUBLISHER: IP Check ───────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='ip-check')
    def ip_check(self, request):
        """
        IP reputation check।
        GET /fraud/ip-check/?ip=1.2.3.4
        """
        ip = request.query_params.get('ip')
        if not ip:
            return self.error_response('ip parameter required.', status_code=400)

        try:
            from .fraud_prevention import check_ip_reputation, is_ip_blocked
            reputation = check_ip_reputation(ip)
            blocked    = is_ip_blocked(ip)
        except (ImportError, Exception):
            from .models import BlockedIP
            from django.utils import timezone
            blocked_obj = BlockedIP.objects.filter(ip_address=ip).first()
            blocked     = blocked_obj is not None and (
                blocked_obj.is_permanent or
                (blocked_obj.expires_at and blocked_obj.expires_at > timezone.now())
            )
            reputation  = {
                'ip': ip,
                'is_blocked': blocked,
                'source': 'db_lookup',
            }

        return self.success_response(data={
            'ip':         ip,
            'is_blocked': blocked,
            'reputation': reputation,
        })

    # ── PUBLISHER: Active Alerts ──────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='alerts')
    def alerts(self, request):
        """
        Active fraud alerts for the publisher。
        GET /fraud/alerts/
        """
        publisher = self._get_publisher()

        try:
            from .fraud_prevention import get_active_fraud_alerts
            data = get_active_fraud_alerts(publisher)
        except (ImportError, Exception):
            from .models import TrafficSafetyLog
            logs = TrafficSafetyLog.objects.filter(
                publisher=publisher,
                action_taken='pending',
                severity__in=['high', 'critical'],
            ).order_by('-detected_at')[:20]
            from .serializers import TrafficSafetyLogSerializer
            data = TrafficSafetyLogSerializer(logs, many=True).data

        return self.success_response(data=data)

    # ── ADMIN: Platform Report ────────────────────────────────────────────────

    @action(
        detail=False, methods=['get'], url_path='platform-report',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def platform_report(self, request):
        """
        Platform-wide fraud report (admin only)。
        GET /fraud/platform-report/?days=30
        """
        days = int(request.query_params.get('days', 30))

        try:
            from .fraud_prevention import generate_platform_fraud_report
            data = generate_platform_fraud_report(days=days)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=data)

    # ── ADMIN: Check Impression ───────────────────────────────────────────────

    @action(
        detail=False, methods=['post'], url_path='check-impression',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def check_impression(self, request):
        """
        Impression fraud check।
        POST /fraud/check-impression/
        Body: {"ip": "1.2.3.4", "user_agent": "...", "ad_unit_id": "..."}
        """
        try:
            from .fraud_prevention import detect_impression_fraud
            result = detect_impression_fraud(request.data)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=result)

    # ── ADMIN: Check Click ────────────────────────────────────────────────────

    @action(
        detail=False, methods=['post'], url_path='check-click',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def check_click(self, request):
        """
        Click fraud check।
        POST /fraud/check-click/
        Body: {"identifier": "ip_or_user_id", "unit_id": "unit_xxx"}
        """
        identifier = request.data.get('identifier')
        unit_id    = request.data.get('unit_id', '')

        if not identifier:
            return self.error_response('identifier is required.', status_code=400)

        try:
            from .fraud_prevention import check_click_velocity
            result = check_click_velocity(identifier, unit_id)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=result)

    # ── ADMIN: Check Conversion ───────────────────────────────────────────────

    @action(
        detail=False, methods=['post'], url_path='check-conversion',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def check_conversion(self, request):
        """
        Conversion fraud check。
        POST /fraud/check-conversion/
        """
        try:
            from .fraud_prevention import detect_conversion_fraud
            result = detect_conversion_fraud(request.data)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=result)

    # ── ADMIN: Block IP ───────────────────────────────────────────────────────

    @action(
        detail=False, methods=['post'], url_path='block-ip',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def block_ip(self, request):
        """
        Manual IP block।
        POST /fraud/block-ip/
        Body: {"ip": "1.2.3.4", "reason": "...", "hours": 24, "permanent": false}
        """
        ip        = request.data.get('ip')
        reason    = request.data.get('reason', 'Manual block by admin')
        hours     = int(request.data.get('hours', 24))
        permanent = request.data.get('permanent', False)

        if not ip:
            return self.error_response('ip is required.', status_code=400)

        try:
            from .fraud_prevention import block_ip as do_block
            do_block(ip, reason=reason, fraud_score=100, hours=hours)
        except (ImportError, Exception):
            pass

        # Always persist to DB
        from .models import BlockedIP
        from django.utils import timezone
        expires_at = None if permanent else timezone.now() + __import__('datetime').timedelta(hours=hours)
        obj, created = BlockedIP.objects.get_or_create(
            ip_address=ip,
            defaults={
                'reason':         reason,
                'blocked_by':     request.user,
                'is_auto_blocked': False,
                'is_permanent':   permanent,
                'expires_at':     expires_at,
                'fraud_score':    100,
            }
        )

        return self.success_response(
            data={'ip': ip, 'reason': reason, 'permanent': permanent, 'created': created},
            message=f'IP {ip} blocked.' if created else f'IP {ip} already blocked (updated).',
        )

    # ── ADMIN: Unblock IP ────────────────────────────────────────────────────

    @action(
        detail=False, methods=['post'], url_path='unblock-ip',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def unblock_ip(self, request):
        """
        IP unblock।
        POST /fraud/unblock-ip/
        Body: {"ip": "1.2.3.4"}
        """
        ip = request.data.get('ip')
        if not ip:
            return self.error_response('ip is required.', status_code=400)

        try:
            from .fraud_prevention import unblock_ip as do_unblock
            do_unblock(ip)
        except (ImportError, Exception):
            pass

        from .models import BlockedIP
        from django.utils import timezone
        count, _ = BlockedIP.objects.filter(ip_address=ip).update(
            unblocked_at=timezone.now()
        )

        return self.success_response(
            data={'ip': ip},
            message=f'IP {ip} unblocked.' if count else f'IP {ip} was not blocked.',
        )

    # ── ADMIN: Blocked IPs List ───────────────────────────────────────────────

    @action(
        detail=False, methods=['get'], url_path='blocked-ips',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def blocked_ips(self, request):
        """
        Currently blocked IPs list (admin)。
        GET /fraud/blocked-ips/?active_only=true
        """
        from .models import BlockedIP
        from django.utils import timezone

        active_only = request.query_params.get('active_only', 'true').lower() == 'true'
        qs = BlockedIP.objects.all().order_by('-created_at')

        if active_only:
            qs = qs.filter(unblocked_at__isnull=True).filter(
                __import__('django.db.models', fromlist=['Q']).Q(is_permanent=True) |
                __import__('django.db.models', fromlist=['Q']).Q(expires_at__gt=timezone.now())
            )

        data = list(qs.values(
            'ip_address', 'reason', 'fraud_score',
            'is_permanent', 'expires_at', 'created_at',
        )[:200])

        return self.success_response(data={'count': len(data), 'blocked_ips': data})
