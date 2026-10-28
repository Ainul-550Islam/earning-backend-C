# api/admin_panel/viewsets/RealtimeDashboardViewSet.py
"""
RealtimeDashboardViewSet — World-class live admin dashboard.
Provides: real-time KPIs, live user activity, revenue stream,
fraud alerts, system health — all in one endpoint.
WebSocket-ready (Django Channels compatible).
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.core.cache import cache
from django.db.models import Count, Sum, Avg, Q
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class RealtimeDashboardViewSet(viewsets.ViewSet):
    """
    Real-time admin dashboard — single endpoint for all live metrics.
    Designed for 5-second auto-refresh in the frontend.
    """
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def live_kpis(self, request):
        """
        Master KPI endpoint — returns ALL critical metrics.
        Cache: 30 seconds (balances freshness vs DB load).
        """
        cache_key = 'admin:live_kpis'
        cached = cache.get(cache_key)
        if cached and not request.query_params.get('force'):
            return Response({'success': True, 'data': cached, 'from_cache': True})

        now = timezone.now()
        today = now.date()
        yesterday = today - timedelta(days=1)
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)

        kpis = {
            'timestamp': now.isoformat(),
            'users': {},
            'wallet': {},
            'conversions': {},
            'withdrawals': {},
            'fraud': {},
            'system': {},
        }

        # Users
        try:
            kpis['users'] = {
                'total': User.objects.count(),
                'active': User.objects.filter(is_active=True).count(),
                'online_now': cache.get('admin:users_online', 0),
                'new_today': User.objects.filter(date_joined__date=today).count(),
                'new_24h': User.objects.filter(date_joined__gte=last_24h).count(),
                'new_7d': User.objects.filter(date_joined__gte=last_7d).count(),
                'new_30d': User.objects.filter(date_joined__gte=last_30d).count(),
                'banned': User.objects.filter(is_active=False).count(),
            }
        except Exception:
            pass

        # Wallet
        try:
            from api.wallet.models.core import Wallet, WalletTransaction
            kpis['wallet'] = {
                'total_balance': float(Wallet.objects.aggregate(t=Sum('current_balance'))['t'] or 0),
                'total_earned_today': float(
                    WalletTransaction.objects.filter(
                        created_at__date=today, transaction_type='earning'
                    ).aggregate(t=Sum('gross_amount'))['t'] or 0
                ),
                'total_earned_7d': float(
                    WalletTransaction.objects.filter(
                        created_at__gte=last_7d, transaction_type='earning'
                    ).aggregate(t=Sum('gross_amount'))['t'] or 0
                ),
                'active_wallets': Wallet.objects.filter(balance__gt=0).count(),
                'frozen_wallets': Wallet.objects.filter(is_locked=True).count(),
            }
        except Exception:
            pass

        # Conversions (TaskSubmission in promotions app)
        try:
            from api.promotions.models import TaskSubmission
            kpis['conversions'] = {
                'today': TaskSubmission.objects.filter(created_at__date=today).count(),
                'today_revenue': float(
                    TaskSubmission.objects.filter(created_at__date=today, status='SUCCESS')
                    .aggregate(t=Sum('reward_amount'))['t'] or 0
                ),
                'pending': TaskSubmission.objects.filter(status='QUEUED').count(),
                '7d': TaskSubmission.objects.filter(created_at__gte=last_7d).count(),
                '7d_revenue': float(
                    TaskSubmission.objects.filter(created_at__gte=last_7d, status='SUCCESS')
                    .aggregate(t=Sum('reward_amount'))['t'] or 0
                ),
            }
        except Exception:
            pass

        # Withdrawals / Payouts
        try:
            from api.payout_queue.models import PayoutItem
            kpis['withdrawals'] = {
                'pending_count': PayoutItem.objects.filter(status='QUEUED').count(),
                'pending_amount': float(
                    PayoutItem.objects.filter(status='QUEUED').aggregate(t=Sum('gross_amount'))['t'] or 0
                ),
                'paid_today': PayoutItem.objects.filter(status='SUCCESS', updated_at__date=today).count(),
                'paid_today_amount': float(
                    PayoutItem.objects.filter(status='SUCCESS', updated_at__date=today)
                    .aggregate(t=Sum('gross_amount'))['t'] or 0
                ),
                'processing': PayoutItem.objects.filter(status='PROCESSING').count(),
            }
        except Exception:
            pass

        # Fraud
        try:
            from api.fraud_detection.models import FraudAttempt
            kpis['fraud'] = {
                'alerts_24h': FraudAttempt.objects.filter(created_at__gte=last_24h).count(),
                'critical_24h': FraudAttempt.objects.filter(
                    created_at__gte=last_24h, fraud_score__gte=90
                ).count(),
                'blocked_ips': cache.get('fraud:blocked_ips_count', 0),
            }
        except Exception:
            pass

        # System
        try:
            from api.admin_panel.utils import get_full_system_health
            health = cache.get('admin_panel:system_health') or {}
            kpis['system'] = {
                'overall_health': health.get('overall', 'unknown'),
                'maintenance_active': bool(cache.get('admin_panel:maintenance_mode_active')),
                'active_alerts': cache.get('admin:active_alerts_count', 0),
                'integration_health': cache.get('admin_panel:integration_health', {}),
            }
        except Exception:
            pass

        cache.set(cache_key, kpis, 30)  # 30-second cache
        return Response({'success': True, 'data': kpis, 'from_cache': False})

    @action(detail=False, methods=['get'])
    def revenue_stream(self, request):
        """Live revenue data — last 60 minutes by minute."""
        try:
            from api.promotions.models import Conversion
            from django.db.models.functions import TruncMinute
            last_60m = timezone.now() - timedelta(hours=1)
            by_minute = list(
                Conversion.objects.filter(
                    created_at__gte=last_60m, status='SUCCESS'
                ).annotate(
                    minute=TruncMinute('created_at')
                ).values('minute').annotate(
                    count=Count('id'), revenue=Sum('payout')
                ).order_by('minute')
            )
            return Response({'success': True, 'data': by_minute})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def activity_feed(self, request):
        """Live activity feed — last 50 admin actions."""
        try:
            from api.admin_panel.models.activity import AdminActivity
            activities = list(AdminActivity.objects.select_related('actor').values(
                'id', 'actor__username', 'action', 'model_name',
                'object_repr', 'status', 'ip', 'created_at'
            ).order_by('-created_at')[:50])
            return Response({'success': True, 'data': activities})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def fraud_alerts_live(self, request):
        """Live fraud alerts — last 10 minutes."""
        try:
            from api.fraud_detection.models import FraudAttempt
            last_10m = timezone.now() - timedelta(minutes=10)
            alerts = list(FraudAttempt.objects.filter(
                created_at__gte=last_10m,
                fraud_score__gte=70
            ).values(
                'id', 'user_id', 'fraud_score', 'attempt_type',
                'attempt_type', 'created_at'
            ).order_by('-fraud_score')[:20])
            return Response({
                'success': True,
                'data': alerts,
                'critical_count': sum(1 for a in alerts if a.get('fraud_score', 0) >= 90),
            })
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def registration_pulse(self, request):
        """User registration pulse — registrations per minute, last 30 minutes."""
        try:
            from django.db.models.functions import TruncMinute
            last_30m = timezone.now() - timedelta(minutes=30)
            pulse = list(
                User.objects.filter(date_joined__gte=last_30m).annotate(
                    minute=TruncMinute('date_joined')
                ).values('minute').annotate(count=Count('id')).order_by('minute')
            )
            return Response({'success': True, 'data': pulse})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def integration_status(self, request):
        """Live INTEGRATION_SYSTEM status."""
        try:
            from api.admin_panel.INTEGRATION_SYSTEM.integ_registry import registry
            from api.admin_panel.INTEGRATION_SYSTEM.health_check import HealthCheck
            health = HealthCheck.get_cached_health() or HealthCheck.check_all()
            apps = registry.list_registrations()
            perf = cache.get('admin_panel:perf_stats') or {}
            return Response({
                'success': True,
                'data': {
                    'health': health,
                    'registered_apps': len(apps),
                    'active_apps': len(registry.list_apps(active_only=True)),
                    'performance': perf,
                    'event_bus': cache.get('admin_panel:event_bus:recent', [])[:10],
                }
            })
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})