# api/admin_panel/viewset_cap.py
"""
ViewSet CAP (Cross-App Propagation) — viewsets that trigger cross-app actions.
These are the HIGH-LEVEL admin actions that affect multiple apps at once.
"এক কাজের জন্য একটাই মালিক admin_panel" — single point of control.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.utils import timezone
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class CrossAppAdminViewSet(viewsets.ViewSet):
    """
    High-level admin actions that propagate across multiple apps.
    These are the most important admin operations.
    """
    permission_classes = [IsAdminUser]

    # ── User ban (propagates to wallet, payout, sessions) ──────────────
    @action(detail=False, methods=['post'], url_path='ban-user')
    def ban_user(self, request):
        """Ban user + freeze wallet + cancel payouts (all at once)."""
        from api.admin_panel.dependencies import validate_required, get_user_or_404
        from api.admin_panel.signals_cap import fire_user_banned
        from api.admin_panel.hooks import fire_hook, HOOK_AFTER_USER_BAN
        from api.admin_panel.decorators import validate_payload

        user_id = request.data.get('user_id')
        reason  = request.data.get('reason', '')
        async_mode = request.data.get('async', False)

        if not user_id or not reason:
            return Response({'error': 'user_id and reason are required'}, status=400)

        if async_mode:
            from api.admin_panel.tasks_cap import task_ban_user_across_apps
            task_ban_user_across_apps.delay(user_id, reason, request.user.pk)
            return Response({'success': True, 'queued': True, 'user_id': user_id})

        # Synchronous ban
        from api.admin_panel.INTEGRATION_SYSTEM.bridge import AdminBridge
        result = AdminBridge.user.ban(user_id=user_id, reason=reason, actor=request.user)
        fire_user_banned(user_id=user_id, reason=reason, banned_by=request.user)
        fire_hook(HOOK_AFTER_USER_BAN, user_id=user_id, reason=reason)
        return Response(result)

    # ── Bulk ban ────────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='bulk-ban')
    def bulk_ban(self, request):
        """Bulk ban users — queues Celery task for large batches."""
        user_ids = request.data.get('user_ids', [])
        reason   = request.data.get('reason', 'Bulk admin ban')
        if not user_ids:
            return Response({'error': 'user_ids required'}, status=400)
        if len(user_ids) > 5000:
            return Response({'error': 'Max 5000 users per bulk ban'}, status=400)

        from api.admin_panel.tasks_cap import task_bulk_ban_users
        task_bulk_ban_users.delay(user_ids, reason, request.user.pk)

        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=request.user, action='bulk_ban',
                              changes={'count': len(user_ids), 'reason': reason})
        except Exception:
            pass
        return Response({'success': True, 'queued': len(user_ids), 'reason': reason})

    # ── Approve withdrawal (propagates wallet + notification) ───────────
    @action(detail=False, methods=['post'], url_path='approve-withdrawal')
    def approve_withdrawal(self, request):
        """Approve withdrawal and propagate to wallet + notifications."""
        item_id = request.data.get('item_id')
        if not item_id:
            return Response({'error': 'item_id required'}, status=400)

        async_mode = request.data.get('async', True)
        if async_mode:
            from api.admin_panel.tasks_cap import task_approve_withdrawal_propagate
            task_approve_withdrawal_propagate.delay(item_id, request.user.pk)
            return Response({'success': True, 'queued': True, 'item_id': item_id})

        from api.payout_queue.models import PayoutItem
        try:
            item = PayoutItem.objects.get(pk=item_id, status='QUEUED')
            item.status = 'SUCCESS'
            item.save(update_fields=['status'])
            from api.admin_panel.signals_cap import fire_withdrawal_approved
            fire_withdrawal_approved(item_id, float(item.gross_amount), item.gateway, item.user_id)
            return Response({'success': True, 'item_id': item_id, 'amount': str(item.gross_amount)})
        except PayoutItem.DoesNotExist:
            return Response({'error': f'PayoutItem {item_id} not found or not pending'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ── Send broadcast (messaging + notifications) ─────────────────────
    @action(detail=False, methods=['post'], url_path='send-broadcast')
    def send_broadcast(self, request):
        """Send admin broadcast — queues delivery task."""
        title    = request.data.get('title', '')
        body     = request.data.get('body', '')
        audience = request.data.get('audience_type', 'all')

        if not title or not body:
            return Response({'error': 'title and body are required'}, status=400)

        try:
            from api.messaging.models import AdminBroadcast
            broadcast = AdminBroadcast.objects.create(
                title=title, body=body,
                audience_type=audience,
                audience_filter=request.data.get('audience_filter', {}),
                sent_by=request.user,
                status='QUEUED',
            )
            from api.admin_panel.tasks_cap import task_send_admin_broadcast_to_all
            task_send_admin_broadcast_to_all.delay(broadcast.pk)
            return Response({'success': True, 'broadcast_id': broadcast.pk, 'status': 'queued'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ── Enable maintenance (propagates across system) ───────────────────
    @action(detail=False, methods=['post'], url_path='enable-maintenance')
    def enable_maintenance(self, request):
        """Enable maintenance mode — propagates to all apps."""
        message  = request.data.get('message', "System maintenance in progress.")
        duration = int(request.data.get('duration_minutes', 60))

        from api.admin_panel.services.MaintenanceModeService import MaintenanceModeService
        result = MaintenanceModeService.enable(message=message, duration_minutes=duration)

        from api.admin_panel.tasks_cap import task_propagate_maintenance_on
        task_propagate_maintenance_on.delay(message, duration)

        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=request.user, action='enable_maintenance',
                              changes={'message': message, 'duration': duration})
        except Exception:
            pass
        return Response({'success': result, 'message': message, 'duration_minutes': duration})

    # ── System KPI refresh ─────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='refresh-kpis')
    def refresh_kpis(self, request):
        """Force refresh all dashboard KPIs."""
        from api.admin_panel.tasks_cap import task_refresh_live_kpis
        task_refresh_live_kpis.delay()
        return Response({'success': True, 'message': 'KPI refresh queued'})

    # ── Integration health ─────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='integration-health')
    def integration_health(self, request):
        """Health check all 50 integrated apps."""
        try:
            from api.admin_panel.INTEGRATION_SYSTEM.health_check import HealthCheck
            result = HealthCheck.check_all(include_apps=False)
            return Response({'success': True, 'data': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    # ── Sync manager ───────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='sync-wallet')
    def sync_wallet(self, request):
        """Sync wallet balance from transactions for a user."""
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'user_id required'}, status=400)
        from api.admin_panel.INTEGRATION_SYSTEM.sync_manager import sync_manager
        result = sync_manager.sync_wallet_with_transactions(user_id)
        return Response(result)