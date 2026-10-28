# api/admin_panel/viewsets/MessagingCPAAdminViewSet.py
"""
CPA Messaging Admin Control — Full admin view of CPA notification system.
Controls: CPANotification, CPABroadcast, MessageTemplate, AffiliateThread.
Previously missing — now 100% covered.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.db.models import Count, Q
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class MessagingCPAAdminViewSet(viewsets.ViewSet):
    """
    CPA Messaging admin panel.
    Route: /api/admin-panel/messaging-cpa/
    """
    permission_classes = [IsAdminUser]

    # ── OVERVIEW ──────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            from api.messaging.models import CPANotification, CPABroadcast, MessageTemplate
            today = timezone.now().date()
            data = {
                'notifications': CPANotification.objects.aggregate(
                    total=Count('id'),
                    unread=Count('id', filter=Q(is_read=False)),
                    today=Count('id', filter=Q(created_at__date=today)),
                    dismissed=Count('id', filter=Q(is_dismissed=True)),
                ),
                'broadcasts': CPABroadcast.objects.aggregate(
                    total=Count('id'),
                    active=Count('id', filter=Q(status='active')),
                    draft=Count('id', filter=Q(status='draft')),
                    scheduled=Count('id', filter=Q(status='scheduled')),
                ),
                'templates': MessageTemplate.objects.aggregate(
                    total=Count('id'),
                    active=Count('id', filter=Q(is_active=True)),
                ),
            }
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    # ── NOTIFICATIONS ─────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def notifications(self, request):
        """List CPA notifications with filters."""
        try:
            from api.messaging.models import CPANotification
            notif_type = request.query_params.get('type')
            user_id    = request.query_params.get('user_id')
            unread     = request.query_params.get('unread')
            page       = int(request.query_params.get('page', 1))
            per_page   = int(request.query_params.get('per_page', 50))

            TYPE_MAP = {
                'offers':      ['offer.approved', 'offer.rejected', 'offer.paused',
                                'offer.new', 'offer.expiring', 'offer.reactivated'],
                'conversions': ['conversion.received', 'conversion.approved',
                                'conversion.rejected', 'conversion.chargeback', 'postback.failed'],
                'payments':    ['payout.processed', 'payout.reminder',
                                'payout.threshold', 'payout.failed', 'payout.hold'],
                'account':     ['affiliate.approved', 'affiliate.rejected', 'affiliate.suspended',
                                'affiliate.reinstated', 'affiliate.banned', 'affiliate.manager'],
                'system':      ['system.maintenance', 'system.announcement',
                                'api.key_expiring', 'terms.updated'],
                'performance': ['milestone.reached', 'epc.drop', 'fraud.alert'],
            }

            qs = CPANotification.objects.all()
            if notif_type and notif_type in TYPE_MAP:
                qs = qs.filter(notification_type__in=TYPE_MAP[notif_type])
            if user_id:
                qs = qs.filter(recipient_id=user_id)
            if unread == '1':
                qs = qs.filter(is_read=False)

            total = qs.count()
            items = list(qs.values(
                'id', 'recipient_id', 'notification_type', 'title',
                'body', 'priority', 'is_read', 'is_dismissed',
                'object_type', 'object_id', 'created_at',
            ).order_by('-created_at')[(page-1)*per_page : page*per_page])
            return Response({'success': True, 'total': total, 'page': page, 'data': items})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def send_cpa_notification(self, request):
        """Send a CPA notification to specific affiliates."""
        try:
            from api.messaging.models import CPANotification
            user_ids  = request.data.get('user_ids', [])
            notif_type = request.data.get('type', 'system.announcement')
            title     = request.data.get('title', '')
            body      = request.data.get('body', '')
            priority  = request.data.get('priority', 'normal')
            payload   = request.data.get('payload', {})

            if not title or not body:
                return Response({'error': 'title and body required'}, status=400)
            if not user_ids:
                return Response({'error': 'user_ids required'}, status=400)

            notifications = [
                CPANotification(
                    recipient_id=uid,
                    notification_type=notif_type,
                    title=title,
                    body=body,
                    priority=priority,
                    payload=payload,
                )
                for uid in user_ids
            ]
            CPANotification.objects.bulk_create(notifications, batch_size=500, ignore_conflicts=True)

            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=request.user, action='send_cpa_notification',
                                  model_name='CPANotification', object_id='bulk',
                                  changes={'type': notif_type, 'count': len(notifications), 'title': title})
            except Exception:
                pass

            return Response({'success': True, 'sent_count': len(notifications), 'type': notif_type})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def clear_user_notifications(self, request):
        """Dismiss/clear all notifications for a user."""
        try:
            from api.messaging.models import CPANotification
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({'error': 'user_id required'}, status=400)
            count = CPANotification.objects.filter(
                recipient_id=user_id, is_dismissed=False
            ).update(is_dismissed=True, dismissed_at=timezone.now())
            return Response({'success': True, 'user_id': user_id, 'cleared': count})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ── BROADCASTS ────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def broadcasts(self, request):
        """List all CPA broadcasts."""
        try:
            from api.messaging.models import CPABroadcast
            status_f = request.query_params.get('status')
            qs = CPABroadcast.objects.all()
            if status_f:
                qs = qs.filter(status=status_f)
            data = list(qs.values(
                'id', 'title', 'notification_type', 'status',
                'target_audience', 'recipient_count', 'sent_count',
                'scheduled_at', 'sent_at', 'created_at',
            ).order_by('-created_at')[:100])
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def create_broadcast(self, request):
        """Create and optionally schedule a CPA broadcast."""
        try:
            from api.messaging.models import CPABroadcast
            broadcast = CPABroadcast.objects.create(
                title=request.data.get('title', ''),
                body=request.data.get('body', ''),
                notification_type=request.data.get('type', 'system.announcement'),
                priority=request.data.get('priority', 'normal'),
                target_audience=request.data.get('audience', 'all'),
                status='draft',
                payload=request.data.get('payload', {}),
                created_by_id=request.user.pk,
            )
            return Response({'success': True, 'broadcast_id': broadcast.pk,
                             'status': 'draft', 'title': broadcast.title})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def send_broadcast(self, request):
        """Send a draft broadcast immediately."""
        try:
            from api.messaging.models import CPABroadcast, CPANotification
            broadcast_id = request.data.get('broadcast_id')
            broadcast = CPABroadcast.objects.get(pk=broadcast_id, status='draft')

            # Determine recipients
            try:
                from api.users.models import User
                if broadcast.target_audience == 'all':
                    user_ids = list(User.objects.filter(is_active=True).values_list('id', flat=True))
                else:
                    user_ids = list(User.objects.filter(
                        is_active=True,
                        last_login__gte=timezone.now() - timedelta(days=30)
                    ).values_list('id', flat=True))
            except Exception:
                user_ids = []

            if user_ids:
                notifications = [
                    CPANotification(
                        recipient_id=uid,
                        notification_type=broadcast.notification_type,
                        title=broadcast.title,
                        body=broadcast.body,
                        priority=broadcast.priority,
                        payload=broadcast.payload,
                    )
                    for uid in user_ids
                ]
                CPANotification.objects.bulk_create(notifications, batch_size=500, ignore_conflicts=True)

            broadcast.status = 'active'
            broadcast.sent_at = timezone.now()
            broadcast.recipient_count = len(user_ids)
            broadcast.sent_count = len(user_ids)
            broadcast.save(update_fields=['status', 'sent_at', 'recipient_count', 'sent_count'])

            return Response({'success': True, 'broadcast_id': broadcast_id,
                             'sent_count': len(user_ids), 'status': 'active'})
        except CPABroadcast.DoesNotExist:
            return Response({'error': 'Broadcast not found or not draft'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ── MESSAGE TEMPLATES ─────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def templates(self, request):
        """List all CPA message templates."""
        try:
            from api.messaging.models import MessageTemplate
            data = list(MessageTemplate.objects.values(
                'id', 'name', 'notification_type', 'title_template',
                'body_template', 'is_active', 'created_at',
            ).order_by('notification_type', 'name'))
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def update_template(self, request):
        """Update a message template."""
        try:
            from api.messaging.models import MessageTemplate
            template_id    = request.data.get('template_id')
            title_template = request.data.get('title_template')
            body_template  = request.data.get('body_template')
            is_active      = request.data.get('is_active')

            update = {}
            if title_template is not None: update['title_template'] = title_template
            if body_template is not None:  update['body_template'] = body_template
            if is_active is not None:      update['is_active'] = is_active

            MessageTemplate.objects.filter(pk=template_id).update(**update)
            cache.delete(f'msg_template_{template_id}')
            return Response({'success': True, 'template_id': template_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ── AFFILIATE THREADS ─────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def affiliate_threads(self, request):
        """List affiliate conversation threads."""
        try:
            from api.messaging.models import AffiliateConversationThread
            status_f = request.query_params.get('status', 'open')
            items = list(
                AffiliateConversationThread.objects.filter(status=status_f)
                .values('id', 'subject', 'affiliate_id', 'status',
                        'message_count', 'last_message_at', 'created_at')
                .order_by('-last_message_at')[:100]
            )
            return Response({'success': True, 'data': items})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    # ── STATS ─────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def notification_stats(self, request):
        """Daily notification stats — last 14 days."""
        try:
            from api.messaging.models import CPANotification
            from django.db.models.functions import TruncDate
            stats = list(
                CPANotification.objects
                .filter(created_at__gte=timezone.now() - timedelta(days=14))
                .annotate(date=TruncDate('created_at'))
                .values('date', 'notification_type')
                .annotate(count=Count('id'))
                .order_by('date')
            )
            return Response({'success': True, 'data': stats})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})