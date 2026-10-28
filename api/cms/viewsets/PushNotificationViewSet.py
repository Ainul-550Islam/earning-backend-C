# cms/viewsets/PushNotificationViewSet.py
"""
PushNotificationViewSet — exposes cms/notifications_push.py to REST clients.

Business value:
  • Mobile apps (iOS/Android) register their FCM/APNs token here
  • Frontend (PWA) registers Web Push subscription here
  • Users see their full notification history
  • Admin can send test push to any user
  • Admin bulk-pushes to user segments

Previously: DeviceToken.register(), FCMPushSender.send_to_user(),
CMSPushNotificationService.notify_reward_earned() etc. all existed
but had ZERO API endpoint — mobile apps could not call them.
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from .cms_viewset_base import CMSUserThrottle, CMSWriteThrottle

logger = logging.getLogger('cms.viewsets.push_notification')


class PushNotificationViewSet(viewsets.GenericViewSet):
    """
    REST API for push notification device management and delivery.
    """
    authentication_classes = [JWTAuthentication]

    # ─────────────────────────────────────────────────────────────────────────
    # Device Token Management
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSWriteThrottle])
    def register_device(self, request):
        """
        POST /api/cms/push/register-device/

        Register a push notification token for the current user's device.

        Body:
          {
            "token": "fcm_token_or_web_push_subscription_json",
            "platform": "fcm|apns|webpush",
            "device_info": {         ← optional
              "device_model": "iPhone 15",
              "os_version": "iOS 17.4",
              "app_version": "2.1.0"
            }
          }

        Mobile use: call on app launch / when FCM token refreshes.
        """
        token       = request.data.get('token', '').strip()
        platform    = request.data.get('platform', 'fcm').lower()
        device_info = request.data.get('device_info', {})

        if not token:
            return Response({'error': 'token is required'},
                            status=status.HTTP_400_BAD_REQUEST)
        if platform not in ('fcm', 'apns', 'webpush', 'web'):
            return Response({'error': 'platform must be fcm, apns, or webpush'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            from api.cms.notifications_push import DeviceToken
            record = DeviceToken.register(
                user=request.user,
                token=token,
                platform=platform,
                device_info=device_info,
            )
            return Response({
                'success': True,
                'platform': platform,
                'registered_at': str(record.created_at if hasattr(record, 'created_at')
                                     else ''),
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f'[PushNotif] register_device error: {e}')
            return Response({'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['delete'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSWriteThrottle])
    def unregister_device(self, request):
        """
        DELETE /api/cms/push/unregister-device/

        Body: { "token": "...", "platform": "fcm" }

        Call on logout or when user turns off notifications.
        """
        token    = request.data.get('token', '').strip()
        platform = request.data.get('platform', 'fcm').lower()
        if not token:
            return Response({'error': 'token is required'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            from api.cms.notifications_push import DeviceToken
            success = DeviceToken.unregister(
                user=request.user, token=token, platform=platform
            )
            return Response({'success': success, 'platform': platform})
        except Exception as e:
            logger.error(f'[PushNotif] unregister_device error: {e}')
            return Response({'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def my_devices(self, request):
        """
        GET /api/cms/push/my-devices/

        Returns a list of all registered devices for the current user.
        Frontend use: settings screen showing active devices.
        """
        try:
            from api.cms.notifications_push import DeviceToken
            tokens = DeviceToken.get_tokens(request.user)
            return Response({
                'devices': tokens,
                'count': len(tokens),
            })
        except Exception as e:
            logger.error(f'[PushNotif] my_devices error: {e}')
            return Response({'devices': [], 'count': 0})

    # ─────────────────────────────────────────────────────────────────────────
    # Notification History
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def history(self, request):
        """
        GET /api/cms/push/history/?limit=20

        Returns the push notification history for the current user.
        Frontend use: notification inbox / history tab.
        """
        limit = min(int(request.query_params.get('limit', 20)), 100)
        try:
            from api.cms.notifications_push import EnhancedPushNotificationManager
            mgr = EnhancedPushNotificationManager()
            history = mgr.get_notification_history(
                user_id=request.user.pk, limit=limit
            )
            return Response({'notifications': history, 'count': len(history)})
        except Exception as e:
            logger.warning(f'[PushNotif] history fallback: {e}')
            # Fallback to Notification model
            try:
                from api.cms.repositories import NotificationRepository
                qs = NotificationRepository.get_unread(request.user, limit=limit)
                return Response({
                    'notifications': list(qs.values(
                        'id', 'notification_type', 'title', 'message',
                        'is_read', 'created_at'
                    )),
                    'count': qs.count(),
                })
            except Exception:
                return Response({'notifications': [], 'count': 0})

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def unread_count(self, request):
        """
        GET /api/cms/push/unread-count/

        Returns the unread push notification count.
        Frontend use: notification badge on nav bar.
        """
        try:
            from api.cms.repositories import NotificationRepository
            count = NotificationRepository.get_unread(
                request.user, limit=1000
            ).count()
            return Response({'unread_count': count})
        except Exception:
            return Response({'unread_count': 0})

    @action(detail=False, methods=['post'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSWriteThrottle])
    def mark_all_read(self, request):
        """
        POST /api/cms/push/mark-all-read/

        Marks all notifications as read for the current user.
        """
        try:
            from api.cms.repositories import NotificationRepository
            marked = NotificationRepository.mark_all_read(request.user)
            return Response({'success': True, 'marked': marked})
        except Exception as e:
            return Response({'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ─────────────────────────────────────────────────────────────────────────
    # Specific Push Types (user-facing)
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSWriteThrottle])
    def subscribe_topic(self, request):
        """
        POST /api/cms/push/subscribe-topic/

        Body: { "topic": "new_offers|streak_reminders|leaderboard" }

        Opt in to a specific push topic category.
        """
        topic = request.data.get('topic', '').strip()
        valid_topics = ('new_offers', 'streak_reminders', 'leaderboard',
                        'survey_recommendations', 'withdrawal_updates',
                        'referral_bonuses', 'system_announcements')
        if topic not in valid_topics:
            return Response({
                'error': f'Invalid topic. Valid: {valid_topics}'
            }, status=status.HTTP_400_BAD_REQUEST)
        # Store user preference in cache/model
        try:
            from django.core.cache import cache
            pref_key = f'push_topic_{request.user.pk}_{topic}'
            cache.set(pref_key, True, timeout=None)
        except Exception:
            pass
        return Response({'success': True, 'topic': topic, 'subscribed': True})

    @action(detail=False, methods=['post'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSWriteThrottle])
    def unsubscribe_topic(self, request):
        """
        POST /api/cms/push/unsubscribe-topic/

        Body: { "topic": "new_offers" }
        """
        topic = request.data.get('topic', '').strip()
        try:
            from django.core.cache import cache
            pref_key = f'push_topic_{request.user.pk}_{topic}'
            cache.delete(pref_key)
        except Exception:
            pass
        return Response({'success': True, 'topic': topic, 'subscribed': False})

    # ─────────────────────────────────────────────────────────────────────────
    # Admin push endpoints
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'],
            permission_classes=[IsAdminUser],
            throttle_classes=[CMSWriteThrottle])
    def send_test(self, request):
        """
        POST /api/cms/push/send-test/

        Admin: send a test push notification to a specific user.

        Body:
          {
            "user_id": 42,
            "title": "Test Push",
            "body": "This is a test notification",
            "data": {}   ← optional extra payload
          }
        """
        user_id = request.data.get('user_id')
        title   = request.data.get('title', 'Test Push')
        body    = request.data.get('body', 'This is a test notification')
        data    = request.data.get('data', {})
        if not user_id:
            return Response({'error': 'user_id required'},
                            status=status.HTTP_400_BAD_REQUEST)
        from django.contrib.auth import get_user_model
        try:
            target = get_user_model().objects.get(pk=int(user_id))
        except Exception:
            return Response({'error': 'User not found'}, status=404)
        try:
            from api.cms.notifications_push import CMSPushNotificationService
            result = CMSPushNotificationService.send_to_user(
                user=target, title=title, body=body, data=data
            )
            return Response({'success': result, 'user_id': user_id})
        except Exception as e:
            logger.error(f'[PushNotif] send_test error: {e}')
            return Response({'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'],
            permission_classes=[IsAdminUser],
            throttle_classes=[CMSWriteThrottle])
    def bulk_push(self, request):
        """
        POST /api/cms/push/bulk-push/

        Admin: send a push notification to multiple users.

        Body:
          {
            "user_ids": [1, 2, 3],   ← list of user PKs OR
            "segment": "new_user",   ← user segment name
            "title": "...",
            "body": "...",
            "data": {}
          }
        """
        user_ids = request.data.get('user_ids', [])
        segment  = request.data.get('segment', '')
        title    = request.data.get('title', '')
        body     = request.data.get('body', '')
        data     = request.data.get('data', {})

        if not title or not body:
            return Response({'error': 'title and body are required'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Resolve segment to user IDs if segment given
        if segment and not user_ids:
            try:
                from api.cms.selectors import UserSelector
                users = UserSelector.get_active_users(days=30)
                user_ids = [u.pk for u in users]
            except Exception:
                pass

        if not user_ids:
            return Response({'error': 'user_ids or segment is required'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            from api.cms.notifications_push import EnhancedPushNotificationManager
            mgr = EnhancedPushNotificationManager()
            result = mgr.send_bulk_notification(
                user_ids=user_ids, title=title, body=body, data=data
            )
            return Response({
                'success': True,
                'sent_count': result.get('sent', len(user_ids)),
                'failed_count': result.get('failed', 0),
            })
        except Exception as e:
            logger.error(f'[PushNotif] bulk_push error: {e}')
            return Response({'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'],
            permission_classes=[IsAdminUser],
            throttle_classes=[CMSUserThrottle])
    def push_stats(self, request):
        """
        GET /api/cms/push/stats/

        Admin: registered device counts, send rates, open rates.
        """
        try:
            from django.core.cache import cache
            stats = cache.get('push_notification_stats', {})
            if not stats:
                # Compute basic stats
                try:
                    from api.cms.notifications_push import DeviceToken
                    fcm_count  = len(DeviceToken.get_tokens(None, platform='fcm'))
                    web_count  = len(DeviceToken.get_tokens(None, platform='webpush'))
                except Exception:
                    fcm_count = web_count = 0
                stats = {
                    'fcm_registered_devices':  fcm_count,
                    'web_push_subscriptions':  web_count,
                    'push_enabled': True,
                }
                cache.set('push_notification_stats', stats, timeout=300)
            return Response(stats)
        except Exception as e:
            return Response({'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
