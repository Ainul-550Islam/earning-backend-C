# api/admin_panel/viewsets/MessagingBehaviorAdminViewSet.py
"""
Admin control for Messaging, Behavior Analytics, Auto Moderation,
Postback Engine, Offer Routing, Monetization Tools.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class MessagingAdminViewSet(viewsets.ViewSet):
    """Admin control for in-app Messaging, broadcasts, support threads."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            from api.messaging.models import InternalChat, AdminBroadcast, SupportThread
            return Response({
                'success': True,
                'data': {
                    'total_chats': InternalChat.objects.count(),
                    'active_chats': InternalChat.objects.filter(status='active').count(),
                    'total_broadcasts': AdminBroadcast.objects.count(),
                    'open_support_threads': SupportThread.objects.filter(status='open').count(),
                    'pending_support': SupportThread.objects.filter(status='open', assigned_to__isnull=True).count(),
                }
            })
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def send_broadcast(self, request):
        """Send admin broadcast to all or filtered users."""
        try:
            from api.messaging.models import AdminBroadcast
            title = request.data.get('title')
            body = request.data.get('body')
            audience_type = request.data.get('audience_type', 'all')
            audience_filter = request.data.get('audience_filter', {})

            if not title or not body:
                return Response({'error': 'title and body are required'}, status=400)

            broadcast = AdminBroadcast.objects.create(
                title=title,
                body=body,
                audience_type=audience_type,
                audience_filter=audience_filter,
                sent_by=request.user,
                status='QUEUED',
            )

            # Queue delivery task
            try:
                from api.messaging.tasks import deliver_broadcast
                deliver_broadcast.delay(broadcast.pk)
            except Exception:
                broadcast.status = 'sending'
                broadcast.save(update_fields=['status'])

            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(
                    actor=request.user, action='send_broadcast',
                    model_name='AdminBroadcast', object_id=str(broadcast.pk),
                    changes={'title': title, 'audience': audience_type},
                )
            except Exception:
                pass

            return Response({
                'success': True,
                'broadcast_id': broadcast.pk,
                'title': title,
                'audience': audience_type,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def broadcast_history(self, request):
        try:
            from api.messaging.models import AdminBroadcast
            broadcasts = list(AdminBroadcast.objects.values(
                'id', 'title', 'audience_type', 'status',
                'sent_count', 'read_count', 'created_at'
            ).order_by('-created_at')[:50])
            return Response({'success': True, 'data': broadcasts})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def support_threads(self, request):
        try:
            from api.messaging.models import SupportThread
            status_filter = request.query_params.get('status', 'open')
            priority_filter = request.query_params.get('priority')
            qs = SupportThread.objects.filter(status=status_filter)
            if priority_filter:
                qs = qs.filter(priority=priority_filter)
            threads = list(qs.values(
                'id', 'subject', 'status', 'priority', 'user_id',
                'assigned_to__username', 'message_count', 'created_at'
            ).order_by('-priority', 'created_at')[:100])
            return Response({'success': True, 'data': threads})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def close_support_thread(self, request):
        try:
            from api.messaging.models import SupportThread
            thread_id = request.data.get('thread_id')
            resolution = request.data.get('resolution', 'Resolved by admin')
            SupportThread.objects.filter(pk=thread_id).update(
                status='closed',
                resolution_note=resolution,
                resolved_by=request.user,
                resolved_at=timezone.now(),
            )
            return Response({'success': True, 'thread_id': thread_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def send_direct_message(self, request):
        """Admin sends direct message to a specific user."""
        try:
            from api.messaging.models import UserInbox
            user_id = request.data.get('user_id')
            message = request.data.get('message')
            subject = request.data.get('subject', 'Message from Admin')

            UserInbox.objects.create(
                user_id=user_id,
                subject=subject,
                body=message,
                from_user=request.user,
                inbox_type='admin_message',
                is_read=False,
            )
            return Response({'success': True, 'sent_to': user_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class BehaviorAnalyticsAdminViewSet(viewsets.ViewSet):
    """Admin control for User Behavior Analytics."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            from api.behavior_analytics.models import UserPath, ClickMetric, EngagementScore
            last_7d = timezone.now() - timedelta(days=7)
            return Response({
                'success': True,
                'data': {
                    'user_paths_7d': UserPath.objects.filter(created_at__gte=last_7d).count(),
                    'click_metrics_7d': ClickMetric.objects.filter(created_at__gte=last_7d).count(),
                    'avg_engagement_score': EngagementScore.objects.filter(
                        created_at__gte=last_7d
                    ).aggregate(avg=Avg('score'))['avg'] or 0,
                }
            })
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def top_user_paths(self, request):
        """Most common user navigation paths."""
        try:
            from api.behavior_analytics.models import UserPath
            last_7d = timezone.now() - timedelta(days=7)
            paths = list(UserPath.objects.filter(
                created_at__gte=last_7d
            ).values('path_sequence').annotate(
                count=Count('id')
            ).order_by('-count')[:20])
            return Response({'success': True, 'data': paths})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def low_engagement_users(self, request):
        """Users with low engagement scores — at risk of churning."""
        try:
            from api.behavior_analytics.models import EngagementScore
            threshold = float(request.query_params.get('threshold', 20))
            low = list(EngagementScore.objects.filter(
                score__lt=threshold
            ).values('user_id', 'score', 'last_active').order_by('score')[:100])
            return Response({'success': True, 'data': low, 'threshold': threshold})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def click_heatmap(self, request):
        """Click metric heatmap by screen/section."""
        try:
            from api.behavior_analytics.models import ClickMetric
            last_7d = timezone.now() - timedelta(days=7)
            heatmap = list(ClickMetric.objects.filter(
                created_at__gte=last_7d
            ).values('screen', 'section', 'element').annotate(
                clicks=Count('id')
            ).order_by('-clicks')[:50])
            return Response({'success': True, 'data': heatmap})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})


class AutoModAdminViewSet(viewsets.ViewSet):
    """Admin control for Auto Moderation."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            from api.auto_mod.models import AutoApprovalRule, SuspiciousSubmission
            last_24h = timezone.now() - timedelta(hours=24)
            return Response({
                'success': True,
                'data': {
                    'total_rules': AutoApprovalRule.objects.count(),
                    'active_rules': AutoApprovalRule.objects.filter(is_active=True).count(),
                    'suspicious_24h': SuspiciousSubmission.objects.filter(created_at__gte=last_24h).count(),
                    'pending_review': SuspiciousSubmission.objects.filter(status='QUEUED').count(),
                }
            })
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def suspicious_submissions(self, request):
        try:
            from api.auto_mod.models import SuspiciousSubmission
            submissions = list(SuspiciousSubmission.objects.filter(
                status='QUEUED'
            ).values(
                'id', 'submission_type', 'user_id', 'fraud_score',
                'flags', 'created_at'
            ).order_by('-fraud_score')[:100])
            return Response({'success': True, 'data': submissions})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def approve_submission(self, request):
        try:
            from api.auto_mod.models import SuspiciousSubmission
            submission_id = request.data.get('submission_id')
            SuspiciousSubmission.objects.filter(pk=submission_id).update(
                status='SUCCESS', reviewed_by=request.user, reviewed_at=timezone.now()
            )
            return Response({'success': True, 'submission_id': submission_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def reject_submission(self, request):
        try:
            from api.auto_mod.models import SuspiciousSubmission
            submission_id = request.data.get('submission_id')
            reason = request.data.get('reason', 'Failed moderation check')
            SuspiciousSubmission.objects.filter(pk=submission_id).update(
                status='FAILED', rejection_reason=reason,
                reviewed_by=request.user, reviewed_at=timezone.now()
            )
            return Response({'success': True, 'submission_id': submission_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def create_auto_rule(self, request):
        """Create a new auto-moderation rule."""
        try:
            from api.auto_mod.models import AutoApprovalRule
            rule = AutoApprovalRule.objects.create(
                name=request.data.get('name'),
                rule_type=request.data.get('rule_type', 'keyword'),
                conditions=request.data.get('conditions', {}),
                action=request.data.get('action', 'flag'),
                is_active=True,
                created_by=request.user,
            )
            return Response({'success': True, 'rule_id': rule.pk, 'name': rule.name})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class PostbackEngineAdminViewSet(viewsets.ViewSet):
    """Admin control for Postback Engine — conversion tracking, network configs."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            from api.postback_engine.models import AdNetworkConfig, PostbackQueue, ConversionDeduplication
            last_24h = timezone.now() - timedelta(hours=24)
            return Response({
                'success': True,
                'data': {
                    'total_networks': AdNetworkConfig.objects.count(),
                    'active_networks': AdNetworkConfig.objects.filter(is_active=True).count(),
                    'pending_postbacks': PostbackQueue.objects.filter(status='QUEUED').count(),
                    'failed_postbacks_24h': PostbackQueue.objects.filter(
                        status='failed', created_at__gte=last_24h
                    ).count(),
                    'duplicates_blocked_24h': ConversionDeduplication.objects.filter(
                        created_at__gte=last_24h
                    ).count(),
                }
            })
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def network_configs(self, request):
        try:
            from api.postback_engine.models import AdNetworkConfig
            configs = list(AdNetworkConfig.objects.values(
                'id', 'network_name', 'network_code', 'is_active',
                'postback_url', 'success_rate', 'total_conversions'
            ).order_by('-total_conversions'))
            return Response({'success': True, 'data': configs})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def postback_queue(self, request):
        try:
            from api.postback_engine.models import PostbackQueue
            status_filter = request.query_params.get('status', 'pending')
            queue = list(PostbackQueue.objects.filter(
                status=status_filter
            ).values(
                'id', 'network_name', 'offer_id', 'click_id',
                'payout', 'status', 'retry_count', 'created_at', 'error_message'
            ).order_by('-created_at')[:100])
            return Response({'success': True, 'data': queue})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def retry_failed(self, request):
        try:
            from api.postback_engine.models import PostbackQueue
            hours = int(request.data.get('hours', 6))
            cutoff = timezone.now() - timedelta(hours=hours)
            count = PostbackQueue.objects.filter(
                status='failed',
                created_at__gte=cutoff,
                retry_count__lt=5,
            ).update(status='QUEUED')
            return Response({'success': True, 'queued_for_retry': count})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def ip_blacklist(self, request):
        try:
            from api.postback_engine.models import IPBlacklist
            ips = list(IPBlacklist.objects.values(
                'id', 'ip_address', 'reason', 'network', 'created_at'
            ).order_by('-created_at')[:100])
            return Response({'success': True, 'data': ips, 'total': IPBlacklist.objects.count()})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})


class OfferRoutingAdminViewSet(viewsets.ViewSet):
    """Admin control for Offer Routing — routing rules, AB testing, optimization."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def routing_configs(self, request):
        try:
            from api.offer_inventory.models import Offer as RoutingConfig  # offer_routing not available, using offer_inventory
            configs = list(RoutingConfig.objects.values(
                'id', 'title', 'offer_type', 'is_active',
                'payout', 'created_at'
            ).order_by('-payout'))
            return Response({'success': True, 'data': configs})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_routing_config(self, request):
        try:
            from api.offer_inventory.models import Offer as RoutingConfig  # offer_routing not available, using offer_inventory
            config_id = request.data.get('config_id')
            config = RoutingConfig.objects.get(pk=config_id)
            config.is_active = not config.is_active
            config.save(update_fields=['is_active'])
            return Response({'success': True, 'config_id': config_id, 'is_active': config.is_active})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def ab_tests(self, request):
        # AB test model not available in offer_routing - returns empty
        return Response({'success': True, 'data': [], 'note': 'AB test routing not yet configured'})

    @action(detail=False, methods=['get'])
    def routing_performance(self, request):
        """How well each routing strategy performs — via offer_inventory."""
        try:
            from api.offer_inventory.models import Offer as RoutingConfig
            last_7d = timezone.now() - timedelta(days=7)
            perf = list(RoutingConfig.objects.filter(
                created_at__gte=last_7d
            ).values('routing_type').annotate(
                total_routes=Count('id'),
                conversions=Count('id', filter=Q(resulted_in_conversion=True)),
                avg_payout=Avg('payout'),
            ).order_by('-conversions'))

            for item in perf:
                total = item['total_routes'] or 1
                item['cvr'] = round((item['conversions'] / total) * 100, 2)

            return Response({'success': True, 'data': perf})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})


class MonetizationToolsAdminViewSet(viewsets.ViewSet):
    """Admin control for Monetization Tools — ad formats, revenue models, optimization."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            from api.monetization_tools.models import AdNetwork, AdCampaign, AdUnit
            return Response({
                'success': True,
                'data': {
                    'total_ad_networks': AdNetwork.objects.count(),
                    'active_ad_networks': AdNetwork.objects.filter(is_active=True).count(),
                    'total_campaigns': AdCampaign.objects.count(),
                    'active_campaigns': AdCampaign.objects.filter(status='active').count(),
                    'total_ad_units': AdUnit.objects.count(),
                }
            })
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def ad_performance(self, request):
        """Ad network performance — impressions, CTR, revenue."""
        try:
            from api.monetization_tools.models import AdNetworkDailyStat
            last_7d = timezone.now() - timedelta(days=7)
            stats = list(AdNetworkDailyStat.objects.filter(
                date__gte=last_7d.date()
            ).values(
                'network__name', 'date', 'impressions', 'clicks',
                'revenue', 'ctr', 'rpm', 'fill_rate'
            ).order_by('-revenue')[:100])
            return Response({'success': True, 'data': stats})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_ad_format(self, request):
        """Enable/disable a specific ad format (banner, interstitial, rewarded, native)."""
        try:
            from api.monetization_tools.models import AdUnit
            unit_id = request.data.get('unit_id')
            unit = AdUnit.objects.get(pk=unit_id)
            unit.is_active = not unit.is_active
            unit.save(update_fields=['is_active'])
            return Response({'success': True, 'unit_id': unit_id, 'is_active': unit.is_active})
        except Exception as e:
            return Response({'error': str(e)}, status=400)