# api/admin_panel/viewsets/NotificationReferralAdminViewSet.py
"""
Admin control for Notifications system + Referral system.
Send broadcast, manage referral settings, view referral tree.
PostgreSQL-optimized.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class NotificationAdminViewSet(viewsets.ViewSet):
    """Admin Notification broadcast & management."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            stats = {}
            try:
                from api.notifications.models import Notification
                stats['total'] = Notification.objects.count()
                stats['unread'] = Notification.objects.filter(is_read=False).count()
                stats['last_24h'] = Notification.objects.filter(
                    created_at__gte=timezone.now() - timedelta(hours=24)
                ).count()
            except Exception as e:
                stats['error'] = str(e)
            return Response({'success': True, 'data': stats})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def send_broadcast(self, request):
        """Send notification to all users, a group, or specific users."""
        try:
            title = request.data.get('title', '')
            message = request.data.get('message', '')
            target = request.data.get('target', 'all')  # all | active | user_ids
            user_ids = request.data.get('user_ids', [])
            notification_type = request.data.get('type', 'INFO')
            send_push = request.data.get('send_push', False)
            send_email = request.data.get('send_email', False)

            if not title or not message:
                return Response({'error': 'title and message required'}, status=400)

            from api.users.models import User
            if target == 'all':
                users = User.objects.filter(is_active=True).values_list('id', flat=True)
            elif target == 'active':
                users = User.objects.filter(is_active=True, last_login__gte=timezone.now() - timedelta(days=30)).values_list('id', flat=True)
            elif target == 'user_ids' and user_ids:
                users = user_ids
            else:
                return Response({'error': 'Invalid target'}, status=400)

            sent_count = 0
            try:
                from api.notifications.models import Notification
                notifications = [
                    Notification(
                        user_id=uid,
                        title=title,
                        message=message,
                        notification_type=notification_type,
                        is_read=False,
                    )
                    for uid in users
                ]
                Notification.objects.bulk_create(notifications, batch_size=500, ignore_conflicts=True)
                sent_count = len(notifications)
            except Exception as e:
                logger.warning(f"[NotificationAdmin] bulk create error: {e}")

            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=request.user, action='send_broadcast',
                                  model_name='Notification', object_id='bulk',
                                  changes={'title': title, 'target': target, 'sent': sent_count})
            except Exception: pass

            return Response({
                'success': True,
                'sent_count': sent_count,
                'title': title,
                'target': target,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def create_site_notification(self, request):
        """Create a site-wide banner notification."""
        try:
            from api.admin_panel.models import SiteNotification
            notif = SiteNotification.objects.create(
                title=request.data.get('title', ''),
                message=request.data.get('message', ''),
                notification_type=request.data.get('type', 'INFO'),
                is_active=request.data.get('is_active', True),
                show_on_login=request.data.get('show_on_login', False),
                priority=request.data.get('priority', 0),
            )
            return Response({'success': True, 'id': notif.pk, 'title': notif.title})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def templates(self, request):
        """List available email/push notification templates."""
        try:
            from api.admin_panel.models.config import EmailTemplate
            tmpl = list(EmailTemplate.objects.values(
                'id', 'name', 'subject', 'template_type', 'is_active', 'updated_at'
            ).order_by('template_type', 'name'))
            return Response({'success': True, 'data': tmpl})
        except Exception as e:
            return Response({'success': False, 'error': str(e), 'data': []})


class ReferralAdminViewSet(viewsets.ViewSet):
    """Admin control for Referral system — settings, stats, tree view."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            from api.referral.models import ReferralSettings
            settings_obj = ReferralSettings.objects.first()
            stats = {}
            try:
                from api.users.models import UserProfile
                stats['total_referrers'] = UserProfile.objects.filter(referred_by__isnull=False).values('referred_by').distinct().count()
                stats['total_referred'] = UserProfile.objects.filter(referred_by__isnull=False).count()
            except Exception: pass
            return Response({
                'success': True,
                'settings': {
                    'enabled': getattr(settings_obj, 'is_active', True) if settings_obj else True,
                    'level1_pct': float(getattr(settings_obj, 'level1_percentage', 10)),
                    'level2_pct': float(getattr(settings_obj, 'level2_percentage', 5)),
                    'level3_pct': float(getattr(settings_obj, 'level3_percentage', 2.5)),
                } if settings_obj else {},
                'stats': stats,
            })
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def update_settings(self, request):
        try:
            from api.referral.models import ReferralSettings
            settings_obj, _ = ReferralSettings.objects.get_or_create()
            for field in ['level1_percentage', 'level2_percentage', 'level3_percentage',
                          'is_active', 'min_referrals_for_withdrawal', 'bonus_amount']:
                if field in request.data:
                    setattr(settings_obj, field, request.data[field])
            settings_obj.save()
            cache.delete('referral_settings')
            return Response({'success': True, 'message': 'Referral settings updated'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def top_referrers(self, request):
        try:
            from api.users.models import UserProfile
            top = list(
                UserProfile.objects.values('user__username', 'user__email')
                .annotate(referral_count=Count('user__referred_users'))
                .filter(referral_count__gt=0)
                .order_by('-referral_count')[:50]
            )
            return Response({'success': True, 'data': top})
        except Exception as e:
            return Response({'success': False, 'error': str(e), 'data': []})

    @action(detail=False, methods=['get'])
    def user_referral_tree(self, request):
        try:
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response({'error': 'user_id required'}, status=400)
            from api.users.models import UserProfile
            level1 = list(UserProfile.objects.filter(
                referred_by_id=user_id
            ).values('user_id', 'user__username', 'user__email', 'user__date_joined'))
            return Response({'success': True, 'data': {
                'user_id': user_id,
                'level1_referrals': level1,
                'level1_count': len(level1),
            }})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class BackupDRAdminViewSet(viewsets.ViewSet):
    """Admin control for Backup & Disaster Recovery system."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def status(self, request):
        try:
            from api.backup.models import BackupJob
            last_backup = BackupJob.objects.order_by('-created_at').values(
                'id', 'backup_type', 'status', 'file_size', 'created_at', 'completed_at'
            ).first()
            total = BackupJob.objects.count()
            success = BackupJob.objects.filter(status='completed').count()
            failed = BackupJob.objects.filter(status='failed').count()
            return Response({'success': True, 'data': {
                'last_backup': last_backup,
                'total_backups': total, 'successful': success, 'failed': failed,
            }})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def trigger_backup(self, request):
        try:
            backup_type = request.data.get('type', 'full')  # full | incremental | db_only
            try:
                from api.backup.tasks import run_backup
                run_backup.delay(backup_type=backup_type, triggered_by=str(request.user.pk))
                return Response({'success': True, 'message': f'{backup_type} backup triggered', 'queued': True})
            except Exception:
                from api.backup.models import BackupJob
                job = BackupJob.objects.create(backup_type=backup_type, status='queued')
                return Response({'success': True, 'backup_id': job.pk, 'status': 'queued'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def dr_status(self, request):
        try:
            from api.disaster_recovery.models import DRStatus
            dr = DRStatus.objects.first()
            return Response({'success': True, 'data': {
                'rpo': getattr(dr, 'rpo_minutes', 60),
                'rto': getattr(dr, 'rto_minutes', 120),
                'last_dr_test': str(getattr(dr, 'last_test_date', '')),
                'replication_lag': getattr(dr, 'replication_lag_seconds', 0),
                'status': getattr(dr, 'status', 'unknown'),
            } if dr else {}})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})