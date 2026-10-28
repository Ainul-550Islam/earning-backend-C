# api/admin_panel/viewsets/RemainingAppsViewSet.py
"""
Admin control for ALL remaining uncontrolled apps.
cache, engagement, inventory, gateways, rate_limit,
security, support, disaster_recovery, dr_integration, dashboard_assets.
"Do not summarize or skip any logic. Provide the full code."
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.core.cache import cache
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


# ==================== PAYMENT GATEWAYS ADMIN ====================

class PaymentGatewayAdminViewSet(viewsets.ViewSet):
    """Admin control for Payment Gateways — bKash, Nagad, Rocket, Stripe, PayPal."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            from api.payment_gateways.models.core import PaymentGateway, GatewayTransaction
            last_24h = timezone.now() - timedelta(hours=24)
            gateways = list(PaymentGateway.objects.values(
                'id', 'name', 'gateway_type', 'is_active', 'is_maintenance',
                'min_amount', 'max_amount', 'fee_percentage', 'fee_fixed',
                'processing_time_hours', 'total_transactions', 'total_volume'
            ).order_by('-is_active', '-total_volume'))

            txn_today = GatewayTransaction.objects.filter(created_at__date=timezone.now().date())
            stats = txn_today.aggregate(
                count=Count('id'),
                total_amount=Sum('gross_amount'),
                failed=Count('id', filter=Q(status='failed')),
                success=Count('id', filter=Q(status='completed')),
            )
            return Response({'success': True, 'gateways': gateways, 'today_stats': stats})
        except Exception as e:
            return Response({'success': True, 'gateways': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_gateway(self, request):
        try:
            from api.payment_gateways.models.core import PaymentGateway
            gateway_id = request.data.get('gateway_id')
            gw = PaymentGateway.objects.get(pk=gateway_id)
            gw.is_active = not gw.is_active
            gw.save(update_fields=['is_active'])
            cache.delete(f'gateway:{gateway_id}')
            cache.delete('gateways_active')
            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=request.user, action='toggle_gateway',
                                  model_name='PaymentGateway', object_id=str(gateway_id),
                                  changes={'name': gw.name, 'is_active': gw.is_active})
            except Exception: pass
            return Response({'success': True, 'gateway': gw.name, 'is_active': gw.is_active})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def set_maintenance(self, request):
        """Put a gateway in maintenance mode (e.g. bKash is down)."""
        try:
            from api.payment_gateways.models.core import PaymentGateway
            gateway_id = request.data.get('gateway_id')
            maintenance = bool(request.data.get('maintenance', True))
            reason = request.data.get('reason', '')
            PaymentGateway.objects.filter(pk=gateway_id).update(
                is_maintenance=maintenance, maintenance_reason=reason
            )
            return Response({'success': True, 'gateway_id': gateway_id, 'maintenance': maintenance})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def transaction_logs(self, request):
        try:
            from api.payment_gateways.models.core import GatewayTransaction
            hours = int(request.query_params.get('hours', 24))
            status_filter = request.query_params.get('status')
            cutoff = timezone.now() - timedelta(hours=hours)
            qs = GatewayTransaction.objects.filter(created_at__gte=cutoff)
            if status_filter:
                qs = qs.filter(status=status_filter)
            logs = list(qs.values(
                'id', 'gateway__name', 'user_id', 'amount', 'currency',
                'status', 'reference', 'error_message', 'created_at'
            ).order_by('-created_at')[:200])
            summary = qs.aggregate(
                total=Count('id'), success=Count('id', filter=Q(status='completed')),
                failed=Count('id', filter=Q(status='failed')),
                total_amount=Sum('amount', filter=Q(status='completed')),
            )
            return Response({'success': True, 'data': logs, 'summary': summary})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def gateway_config(self, request):
        """View gateway API credentials (masked) and config."""
        try:
            from api.payment_gateways.models.core import GatewayConfig
            configs = list(GatewayConfig.objects.values(
                'id', 'gateway__name', 'environment', 'is_active',
                'api_key_set', 'webhook_url_set', 'created_at'
            ))
            return Response({'success': True, 'data': configs})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def retry_failed_transactions(self, request):
        """Queue failed transactions for retry."""
        try:
            hours = int(request.data.get('hours', 6))
            from celery import current_app
            current_app.send_task('api.payment_gateways.tasks.retry_failed_transactions', args=[hours])
            return Response({'success': True, 'queued': True, 'hours': hours})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ==================== SECURITY ADMIN ====================

class SecurityAdminViewSet(viewsets.ViewSet):
    """Admin control for Security — device info, risk scores, auto-block rules, audit trail."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            from api.security.models import SecurityLog, RiskScore, AutoBlockRule
            last_24h = timezone.now() - timedelta(hours=24)
            return Response({'success': True, 'data': {
                'security_events_24h': SecurityLog.objects.filter(created_at__gte=last_24h).count(),
                'high_risk_events_24h': SecurityLog.objects.filter(
                    created_at__gte=last_24h, severity__in=['high', 'critical']
                ).count(),
                'active_block_rules': AutoBlockRule.objects.filter(is_active=True).count(),
                'high_risk_users': RiskScore.objects.filter(score__gte=80).count(),
            }})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def security_logs(self, request):
        try:
            from api.security.models import SecurityLog
            hours = int(request.query_params.get('hours', 24))
            severity = request.query_params.get('severity')
            cutoff = timezone.now() - timedelta(hours=hours)
            qs = SecurityLog.objects.filter(created_at__gte=cutoff)
            if severity:
                qs = qs.filter(severity=severity)
            logs = list(qs.values(
                'id', 'event_type', 'severity', 'user_id', 'ip_address',
                'device_id', 'description', 'created_at'
            ).order_by('-severity', '-created_at')[:200])
            return Response({'success': True, 'data': logs})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def auto_block_rules(self, request):
        try:
            from api.security.models import AutoBlockRule
            rules = list(AutoBlockRule.objects.values(
                'id', 'name', 'rule_type', 'condition', 'action',
                'is_active', 'trigger_count', 'created_at'
            ).order_by('-trigger_count'))
            return Response({'success': True, 'data': rules})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_block_rule(self, request):
        try:
            from api.security.models import AutoBlockRule
            rule_id = request.data.get('rule_id')
            rule = AutoBlockRule.objects.get(pk=rule_id)
            rule.is_active = not rule.is_active
            rule.save(update_fields=['is_active'])
            return Response({'success': True, 'rule': rule.name, 'is_active': rule.is_active})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def high_risk_users(self, request):
        try:
            from api.security.models import RiskScore
            threshold = float(request.query_params.get('threshold', 70))
            risky = list(RiskScore.objects.filter(score__gte=threshold).values(
                'user_id', 'score', 'risk_factors', 'last_calculated'
            ).order_by('-score')[:100])
            return Response({'success': True, 'data': risky, 'threshold': threshold})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def device_info(self, request):
        """Registered device info for a user."""
        try:
            from api.security.models import DeviceInfo
            user_id = request.query_params.get('user_id')
            qs = DeviceInfo.objects.all()
            if user_id:
                qs = qs.filter(user_id=user_id)
            devices = list(qs.values(
                'id', 'user_id', 'device_id', 'device_type', 'os',
                'is_trusted', 'is_blocked', 'last_seen', 'created_at'
            ).order_by('-last_seen')[:100])
            return Response({'success': True, 'data': devices})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def block_device(self, request):
        try:
            from api.security.models import DeviceInfo
            device_id_val = request.data.get('device_id')
            reason = request.data.get('reason', 'Admin blocked')
            DeviceInfo.objects.filter(device_id=device_id_val).update(
                is_blocked=True, block_reason=reason
            )
            return Response({'success': True, 'device_id': device_id_val, 'blocked': True})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ==================== SUPPORT ADMIN ====================

class SupportAdminViewSet(viewsets.ViewSet):
    """Admin control for Support — tickets, FAQ, settings."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            from api.support.models import SupportTicket
            return Response({'success': True, 'data': {
                'total_tickets': SupportTicket.objects.count(),
                'open_tickets': SupportTicket.objects.filter(status='open').count(),
                'in_progress': SupportTicket.objects.filter(status='in_progress').count(),
                'closed_today': SupportTicket.objects.filter(
                    status='closed', updated_at__date=timezone.now().date()
                ).count(),
                'urgent_tickets': SupportTicket.objects.filter(
                    status='open', priority='urgent'
                ).count(),
            }})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def open_tickets(self, request):
        try:
            from api.support.models import SupportTicket
            priority = request.query_params.get('priority')
            qs = SupportTicket.objects.filter(status__in=['open', 'in_progress'])
            if priority:
                qs = qs.filter(priority=priority)
            tickets = list(qs.values(
                'id', 'user_id', 'subject', 'category', 'priority',
                'status', 'assigned_to__username', 'created_at', 'updated_at'
            ).order_by('-priority', 'created_at')[:100])
            return Response({'success': True, 'data': tickets})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def close_ticket(self, request):
        try:
            from api.support.models import SupportTicket
            ticket_id = request.data.get('ticket_id')
            resolution = request.data.get('resolution', 'Resolved by admin')
            SupportTicket.objects.filter(pk=ticket_id).update(
                status='closed',
                resolution=resolution,
                resolved_by=request.user,
                resolved_at=timezone.now(),
            )
            return Response({'success': True, 'ticket_id': ticket_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def faq_list(self, request):
        try:
            from api.support.models import FAQ
            faqs = list(FAQ.objects.values(
                'id', 'question', 'category', 'is_published', 'view_count', 'order'
            ).order_by('category', 'order'))
            return Response({'success': True, 'data': faqs})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_faq(self, request):
        try:
            from api.support.models import FAQ
            faq_id = request.data.get('faq_id')
            faq = FAQ.objects.get(pk=faq_id)
            faq.is_published = not faq.is_published
            faq.save(update_fields=['is_published'])
            return Response({'success': True, 'faq_id': faq_id, 'is_published': faq.is_published})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def support_settings(self, request):
        try:
            from api.support.models import SupportSettings
            settings_obj = SupportSettings.objects.first()
            if settings_obj:
                return Response({'success': True, 'data': {
                    'email': settings_obj.support_email,
                    'auto_response_enabled': settings_obj.auto_response_enabled,
                    'max_response_hours': settings_obj.max_response_hours,
                    'categories': settings_obj.ticket_categories,
                }})
            return Response({'success': True, 'data': {}})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})


# ==================== ENGAGEMENT ADMIN ====================

class EngagementAdminViewSet(viewsets.ViewSet):
    """Admin control for Engagement — daily check-in, spin wheel, leaderboard."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            from api.engagement.models import DailyCheckIn, SpinWheel
            last_24h = timezone.now() - timedelta(hours=24)
            return Response({'success': True, 'data': {
                'checkins_today': DailyCheckIn.objects.filter(
                    created_at__date=timezone.now().date()
                ).count(),
                'spin_wheel_today': SpinWheel.objects.filter(
                    created_at__date=timezone.now().date()
                ).count(),
                'checkin_streak_users': DailyCheckIn.objects.filter(
                    streak__gte=7
                ).values('user_id').distinct().count(),
            }})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def checkin_stats(self, request):
        try:
            from api.engagement.models import DailyCheckIn
            last_7d = timezone.now() - timedelta(days=7)
            from django.db.models.functions import TruncDate
            daily = list(
                DailyCheckIn.objects.filter(created_at__gte=last_7d).annotate(
                    day=TruncDate('created_at')
                ).values('day').annotate(count=Count('id'), bonus=Sum('bonus_points')).order_by('day')
            )
            return Response({'success': True, 'data': daily})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def spin_wheel_config(self, request):
        try:
            from api.engagement.models import SpinWheel
            config = SpinWheel.objects.filter(is_active=True).values(
                'id', 'prize_type', 'prize_value', 'probability', 'is_active'
            )
            return Response({'success': True, 'data': list(config)})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})


# ==================== INVENTORY ADMIN ====================

class InventoryAdminViewSet(viewsets.ViewSet):
    """Admin control for Inventory — reward items, stock, redemption codes."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            from api.inventory.models import RewardItem, UserInventory
            return Response({'success': True, 'data': {
                'total_items': RewardItem.objects.count(),
                'active_items': RewardItem.objects.filter(is_active=True).count(),
                'low_stock': RewardItem.objects.filter(
                    stock_quantity__gt=0, stock_quantity__lt=10
                ).count(),
                'out_of_stock': RewardItem.objects.filter(stock_quantity=0).count(),
                'total_redemptions': UserInventory.objects.count(),
            }})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def item_list(self, request):
        try:
            from api.inventory.models import RewardItem
            items = list(RewardItem.objects.values(
                'id', 'name', 'item_type', 'point_cost', 'stock_quantity',
                'is_active', 'total_redeemed', 'created_at'
            ).order_by('-is_active', '-total_redeemed'))
            return Response({'success': True, 'data': items})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def restock(self, request):
        try:
            from api.inventory.models import RewardItem, StockEvent
            item_id = request.data.get('item_id')
            quantity = int(request.data.get('quantity', 0))
            if quantity <= 0:
                return Response({'error': 'quantity must be > 0'}, status=400)
            item = RewardItem.objects.get(pk=item_id)
            item.stock_quantity += quantity
            item.save(update_fields=['stock_quantity'])
            StockEvent.objects.create(
                item=item, quantity=quantity,
                event_type='restock', notes=f'Admin restock by {request.user.username}'
            )
            return Response({'success': True, 'item': item.name, 'new_stock': item.stock_quantity})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ==================== RATE LIMIT ADMIN ====================

class RateLimitAdminViewSet(viewsets.ViewSet):
    """Admin control for Rate Limiting — configs, logs, user overrides."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def configs(self, request):
        try:
            from api.rate_limit.models import RateLimitConfig
            configs = list(RateLimitConfig.objects.values(
                'id', 'endpoint_pattern', 'method', 'limit',
                'window_seconds', 'is_active', 'scope'
            ).order_by('endpoint_pattern'))
            return Response({'success': True, 'data': configs})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_config(self, request):
        try:
            from api.rate_limit.models import RateLimitConfig
            config_id = request.data.get('config_id')
            config = RateLimitConfig.objects.get(pk=config_id)
            config.is_active = not config.is_active
            config.save(update_fields=['is_active'])
            cache.delete(f'rate_limit:config:{config_id}')
            return Response({'success': True, 'config_id': config_id, 'is_active': config.is_active})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def reset_user_limit(self, request):
        """Reset rate limit counter for a specific user."""
        try:
            from api.rate_limit.models import UserRateLimitProfile
            user_id = request.data.get('user_id')
            endpoint = request.data.get('endpoint', '')
            # Clear from cache
            cache_key = f'rate_limit:{user_id}:{endpoint}'
            cache.delete(cache_key)
            return Response({'success': True, 'user_id': user_id, 'endpoint': endpoint, 'reset': True})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def violation_logs(self, request):
        try:
            from api.rate_limit.models import RateLimitLog
            hours = int(request.query_params.get('hours', 1))
            cutoff = timezone.now() - timedelta(hours=hours)
            logs = list(RateLimitLog.objects.filter(
                created_at__gte=cutoff
            ).values(
                'id', 'user_id', 'ip_address', 'endpoint', 'count', 'created_at'
            ).order_by('-count')[:100])
            return Response({'success': True, 'data': logs})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})


# ==================== CACHE ADMIN ====================

class CacheAdminViewSet(viewsets.ViewSet):
    """Admin control for Cache — inspect, flush, warm up."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def cache_stats(self, request):
        """Cache statistics and key groups."""
        from django.core.cache import cache
        key_groups = {
            'admin_panel_config': cache.get('admin_panel:config_all'),
            'feature_flags': cache.get('admin_panel:feature_flags_all'),
            'maintenance_active': cache.get('admin_panel:maintenance_mode_active'),
            'live_kpis': 'set' if cache.get('admin:live_kpis') else 'empty',
            'integration_health': 'set' if cache.get('admin_panel:integration_health_full') else 'empty',
            'system_health': 'set' if cache.get('admin_panel:system_health') else 'empty',
        }
        return Response({'success': True, 'data': key_groups})

    @action(detail=False, methods=['post'])
    def flush_group(self, request):
        """Flush a specific cache group."""
        from django.core.cache import cache
        group = request.data.get('group', 'all')
        flushed = []
        if group == 'all' and request.user.is_superuser:
            cache.clear()
            flushed = ['ALL']
        elif group == 'config':
            for key in ['admin_panel:config_all', 'admin_panel:feature_flags_all']:
                cache.delete(key)
                flushed.append(key)
        elif group == 'kpis':
            for key in ['admin:live_kpis', 'admin_panel:system_kpis']:
                cache.delete(key)
                flushed.append(key)
        elif group == 'health':
            cache.delete('admin_panel:integration_health_full')
            cache.delete('admin_panel:system_health')
            flushed = ['health_caches']
        return Response({'success': True, 'flushed': flushed, 'group': group})

    @action(detail=False, methods=['post'])
    def warm_up(self, request):
        """Warm up critical caches."""
        warmed = []
        try:
            from api.admin_panel.services.SystemConfigService import SystemConfigService
            SystemConfigService.get_all()
            warmed.append('system_config')
        except Exception: pass
        try:
            from api.admin_panel.services.FeatureFlagService import FeatureFlagService
            FeatureFlagService.get_all_states()
            warmed.append('feature_flags')
        except Exception: pass
        try:
            from api.admin_panel.logic import get_dashboard_kpi_snapshot
            from django.core.cache import cache
            cache.set('admin:live_kpis', get_dashboard_kpi_snapshot(), 30)
            warmed.append('live_kpis')
        except Exception: pass
        return Response({'success': True, 'warmed': warmed})


# ==================== DR INTEGRATION ADMIN ====================

class DRIntegrationAdminViewSet(viewsets.ViewSet):
    """Admin control for DR Integration — backup records, failover, DR alerts."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def dr_status(self, request):
        try:
            from api.dr_integration.models import DRSystemStatus
            status_obj = DRSystemStatus.objects.order_by('-updated_at').first()
            if status_obj:
                return Response({'success': True, 'data': {
                    'overall_status': status_obj.overall_status,
                    'primary_status': status_obj.primary_status,
                    'secondary_status': status_obj.secondary_status,
                    'last_backup': status_obj.last_backup_time,
                    'rto_minutes': status_obj.rto_minutes,
                    'rpo_minutes': status_obj.rpo_minutes,
                    'updated_at': status_obj.updated_at,
                }})
            return Response({'success': True, 'data': {'overall_status': 'unknown'}})
        except Exception as e:
            return Response({'success': True, 'data': {'overall_status': 'unknown', 'error': str(e)}})

    @action(detail=False, methods=['get'])
    def backup_records(self, request):
        try:
            from api.dr_integration.models import DRBackupRecord
            records = list(DRBackupRecord.objects.values(
                'id', 'backup_type', 'status', 'file_size_mb',
                'duration_seconds', 'started_at', 'completed_at', 'storage_path'
            ).order_by('-started_at')[:50])
            return Response({'success': True, 'data': records})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def failover_events(self, request):
        try:
            from api.dr_integration.models import DRFailoverEvent
            events = list(DRFailoverEvent.objects.values(
                'id', 'event_type', 'from_region', 'to_region', 'status',
                'triggered_by', 'started_at', 'completed_at', 'notes'
            ).order_by('-started_at')[:20])
            return Response({'success': True, 'data': events})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def dr_alerts(self, request):
        try:
            from api.dr_integration.models import DRAlert
            active = list(DRAlert.objects.filter(
                status='active'
            ).values('id', 'alert_type', 'severity', 'message', 'created_at')
            .order_by('-severity', '-created_at')[:50])
            return Response({'success': True, 'data': active})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def trigger_dr_backup(self, request):
        """Trigger a DR backup via the DR integration bridge."""
        backup_type = request.data.get('type', 'incremental')
        try:
            from celery import current_app
            current_app.send_task('api.dr_integration.tasks.trigger_backup', args=[backup_type])
            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=request.user, action='trigger_dr_backup',
                                  changes={'backup_type': backup_type})
            except Exception: pass
            return Response({'success': True, 'backup_type': backup_type, 'queued': True})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ==================== CACHE ADMIN (already in CacheAdminViewSet above) ====================
# tasks app = Celery tasks (no Django models, controlled via celery inspect)
# disaster_recovery app = no Django models, controlled via DR integration tasks

class TasksAdminViewSet(viewsets.ViewSet):
    """Admin control for Celery tasks — inspect, revoke, purge queues."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def active_tasks(self, request):
        """Show currently running Celery tasks."""
        try:
            from celery import current_app
            inspector = current_app.control.inspect(timeout=3)
            active = inspector.active() or {}
            total = sum(len(v) for v in active.values())
            return Response({'success': True, 'data': active, 'total_active': total})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def queue_lengths(self, request):
        """Show Celery queue lengths."""
        try:
            from django.core.cache import cache
            queues = [
                'admin_panel', 'admin_panel.high', 'admin_panel.bulk',
                'admin_panel.reports', 'admin_panel.ai', 'celery',
            ]
            data = {}
            for q in queues:
                data[q] = cache.get(f'queue_length:{q}', 0)
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def revoke_task(self, request):
        """Revoke (cancel) a running task by ID."""
        if not request.user.is_superuser:
            return Response({'error': 'Superadmin only'}, status=403)
        try:
            task_id = request.data.get('task_id')
            terminate = bool(request.data.get('terminate', False))
            from celery import current_app
            current_app.control.revoke(task_id, terminate=terminate)
            return Response({'success': True, 'task_id': task_id, 'terminated': terminate})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def purge_queue(self, request):
        """Purge all messages from a queue."""
        if not request.user.is_superuser:
            return Response({'error': 'Superadmin only'}, status=403)
        try:
            queue_name = request.data.get('queue', 'celery')
            from celery import current_app
            current_app.control.purge()
            return Response({'success': True, 'queue': queue_name, 'purged': True})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class DisasterRecoveryAdminViewSet2(viewsets.ViewSet):
    """
    Disaster Recovery Admin — controls api.disaster_recovery which has no Django models.
    Uses api.dr_integration for all actual data.
    """
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def status(self, request):
        """DR system status — delegates to dr_integration."""
        try:
            from api.dr_integration.models import DRSystemStatus
            obj = DRSystemStatus.objects.order_by('-updated_at').first()
            if obj:
                return Response({'success': True, 'data': {
                    'overall': obj.overall_status,
                    'primary': obj.primary_status,
                    'secondary': obj.secondary_status,
                    'last_backup': str(obj.last_backup_time),
                    'failover_ready': obj.failover_ready,
                }})
        except Exception:
            pass
        return Response({'success': True, 'data': {
            'overall': cache.get('dr:system_status', 'unknown'),
            'failover_ready': cache.get('dr:failover_ready', False),
        }})

    @action(detail=False, methods=['post'])
    def trigger_backup(self, request):
        """Trigger backup via task queue."""
        backup_type = request.data.get('type', 'incremental')
        try:
            from celery import current_app
            current_app.send_task('api.disaster_recovery.tasks.run_backup', args=[backup_type])
            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=request.user, action='trigger_dr_backup',
                                  changes={'type': backup_type})
            except Exception: pass
            return Response({'success': True, 'queued': True, 'type': backup_type})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ==================== CACHE APP ====================
from django.core.cache import cache as django_cache

class CacheAppAdminViewSet(viewsets.ViewSet):
    """Admin control for api.cache app — cache store management."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def stats(self, request):
        try:
            from api.cache.services import CacheService
            stats = CacheService.get_stats() if hasattr(CacheService, 'get_stats') else {}
        except Exception:
            stats = {}
        from api.admin_panel.caching import cache_manager
        stats['admin_cache_status'] = cache_manager.get_cache_stats()
        return Response({'success': True, 'data': stats})

    @action(detail=False, methods=['post'])
    def clear_group(self, request):
        group = request.data.get('group', '')
        if not group:
            return Response({'error': 'group required'}, status=400)
        from api.admin_panel.caching import cache_manager
        deleted = cache_manager.flush_group(group, actor=request.user)
        return Response({'success': True, 'cleared': deleted, 'group': group})

    @action(detail=False, methods=['post'])
    def flush_all(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Superadmin only'}, status=403)
        from api.admin_panel.caching import cache_manager
        ok = cache_manager.flush_all(actor=request.user)
        return Response({'success': ok})

    @action(detail=False, methods=['post'])
    def warm(self, request):
        from api.admin_panel.caching import cache_manager
        results = cache_manager.warm_up()
        return Response({'success': True, 'warmed': results})


# ==================== TASKS APP (MasterTask / UserTaskCompletion) ====================

class TasksAppAdminViewSet(viewsets.ViewSet):
    """Admin control for api.tasks app models (MasterTask, UserTaskCompletion, AdminLedger)."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def master_tasks(self, request):
        try:
            from api.tasks.models import MasterTask
            tasks = list(MasterTask.objects.values(
                'id', 'title', 'task_type', 'reward_amount', 'is_active', 'created_at'
            )[:100])
            return Response({'success': True, 'data': tasks, 'count': len(tasks)})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def completions(self, request):
        try:
            from api.tasks.models import UserTaskCompletion
            from django.db.models import Count
            last_24h = __import__('django.utils.timezone', fromlist=['timezone']).timezone.now() - __import__('datetime').timedelta(hours=24)
            stats = {
                'total': UserTaskCompletion.objects.count(),
                'last_24h': UserTaskCompletion.objects.filter(created_at__gte=last_24h).count(),
            }
            return Response({'success': True, 'data': stats})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def ledger(self, request):
        try:
            from api.tasks.models import AdminLedger
            from django.db.models import Sum
            total = AdminLedger.objects.aggregate(t=Sum('amount'))
            return Response({'success': True, 'data': {
                'total_ledger_amount': float(total['t'] or 0),
                'count': AdminLedger.objects.count(),
            }})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def create_master_task(self, request):
        try:
            from api.tasks.models import MasterTask
            task = MasterTask.objects.create(
                title=request.data.get('title', ''),
                task_type=request.data.get('task_type', 'standard'),
                reward_amount=request.data.get('reward_amount', 0),
                is_active=request.data.get('is_active', True),
            )
            return Response({'success': True, 'task_id': task.pk})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_task(self, request):
        task_id = request.data.get('task_id')
        if not task_id:
            return Response({'error': 'task_id required'}, status=400)
        try:
            from api.tasks.models import MasterTask
            task = MasterTask.objects.get(pk=task_id)
            task.is_active = not task.is_active
            task.save(update_fields=['is_active'])
            return Response({'success': True, 'task_id': task_id, 'is_active': task.is_active})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})