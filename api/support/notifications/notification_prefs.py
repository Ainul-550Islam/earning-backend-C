"""
api/support/notifications/notification_prefs.py
FILE 35/70 — Notification Preferences Manager

User নিজের notification preferences set করতে পারবে।
কোন channel-এ কোন event-এর notification পাবে।

API:
    GET  /support/notifications/prefs/
    POST /support/notifications/prefs/
    DELETE /support/notifications/prefs/{channel}/
"""
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_PREFS = {
    'email':    True,
    'telegram': True,
    'whatsapp': False,
    'sms':      False,
    'push':     True,

    # Event-level overrides
    'events': {
        'ticket_created':   {'email': True,  'push': True,  'telegram': True},
        'ticket_replied':   {'email': True,  'push': True,  'telegram': True},
        'ticket_resolved':  {'email': True,  'push': True,  'telegram': True},
        'csat_request':     {'email': True,  'push': False, 'telegram': False},
        'reminder':         {'email': True,  'push': False, 'telegram': False},
    },

    # Quiet hours (no notifications)
    'quiet_hours': {
        'enabled':   False,
        'start_hour':22,  # 10 PM
        'end_hour':  8,   # 8 AM
        'timezone':  'Asia/Dhaka',
    },

    # Frequency limits
    'max_per_hour': 10,
    'max_per_day':  50,
}


class NotificationPrefsManager:
    """User notification preferences CRUD"""

    PREFS_TTL = 86400  # 24 hours cache

    def get_prefs(self, user) -> dict:
        """User-এর preferences পাও"""
        cache_key = f'notif_prefs:{user.id}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        try:
            from api.support.models import SupportNotificationLog
            # Try loading from DB or profile
            prefs = self._load_from_profile(user) or dict(DEFAULT_PREFS)
            cache.set(cache_key, prefs, timeout=self.PREFS_TTL)
            return prefs
        except Exception:
            return dict(DEFAULT_PREFS)

    def update_prefs(self, user, updates: dict) -> dict:
        """Preferences update করো"""
        prefs = self.get_prefs(user)

        # Channel toggles
        for channel in ['email', 'telegram', 'whatsapp', 'sms', 'push']:
            if channel in updates:
                prefs[channel] = bool(updates[channel])

        # Event overrides
        if 'events' in updates:
            prefs['events'].update(updates['events'])

        # Quiet hours
        if 'quiet_hours' in updates:
            prefs['quiet_hours'].update(updates['quiet_hours'])

        # Frequency limits
        if 'max_per_day' in updates:
            prefs['max_per_day'] = min(int(updates['max_per_day']), 100)

        # Save
        self._save_to_profile(user, prefs)
        cache.set(f'notif_prefs:{user.id}', prefs, timeout=self.PREFS_TTL)

        return prefs

    def disable_channel(self, user, channel: str) -> bool:
        """Specific channel disable করো"""
        prefs = self.get_prefs(user)
        if channel in prefs:
            prefs[channel] = False
            self._save_to_profile(user, prefs)
            cache.set(f'notif_prefs:{user.id}', prefs, timeout=self.PREFS_TTL)
            return True
        return False

    def enable_channel(self, user, channel: str) -> bool:
        """Specific channel enable করো"""
        prefs = self.get_prefs(user)
        if channel in DEFAULT_PREFS:
            prefs[channel] = True
            self._save_to_profile(user, prefs)
            cache.set(f'notif_prefs:{user.id}', prefs, timeout=self.PREFS_TTL)
            return True
        return False

    def reset_to_defaults(self, user) -> dict:
        """Default-এ reset করো"""
        prefs = dict(DEFAULT_PREFS)
        self._save_to_profile(user, prefs)
        cache.set(f'notif_prefs:{user.id}', prefs, timeout=self.PREFS_TTL)
        return prefs

    def is_in_quiet_hours(self, user) -> bool:
        """Quiet hours-এ আছে কিনা"""
        prefs = self.get_prefs(user)
        quiet = prefs.get('quiet_hours', {})
        if not quiet.get('enabled'):
            return False

        try:
            import pytz
            tz    = pytz.timezone(quiet.get('timezone', 'UTC'))
            now   = timezone.now().astimezone(tz).hour
            start = quiet.get('start_hour', 22)
            end   = quiet.get('end_hour', 8)

            if start > end:  # Crosses midnight
                return now >= start or now < end
            return start <= now < end
        except Exception:
            return False

    def check_rate_limit(self, user) -> bool:
        """Rate limit check — too many notifications?"""
        prefs   = self.get_prefs(user)
        max_hr  = prefs.get('max_per_hour', 10)
        max_day = prefs.get('max_per_day', 50)

        hr_key  = f'notif_rate_hr:{user.id}'
        day_key = f'notif_rate_day:{user.id}'

        hr_count  = cache.get(hr_key, 0)
        day_count = cache.get(day_key, 0)

        if hr_count >= max_hr or day_count >= max_day:
            return False  # Rate limited

        # Increment counters
        cache.set(hr_key,  hr_count + 1,  timeout=3600)
        cache.set(day_key, day_count + 1, timeout=86400)
        return True

    def get_prefs_for_api(self, user) -> dict:
        """API response format"""
        prefs = self.get_prefs(user)
        return {
            'channels': {
                'email':    prefs.get('email', True),
                'telegram': prefs.get('telegram', True),
                'whatsapp': prefs.get('whatsapp', False),
                'sms':      prefs.get('sms', False),
                'push':     prefs.get('push', True),
            },
            'quiet_hours': prefs.get('quiet_hours', {}),
            'max_per_day': prefs.get('max_per_day', 50),
        }

    def _load_from_profile(self, user) -> dict | None:
        try:
            if hasattr(user, 'profile'):
                raw = getattr(user.profile, 'notification_prefs', None)
                if raw:
                    import json
                    return json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            pass
        return None

    def _save_to_profile(self, user, prefs: dict) -> None:
        try:
            if hasattr(user, 'profile'):
                import json
                user.profile.notification_prefs = json.dumps(prefs)
                user.profile.save(update_fields=['notification_prefs'])
        except Exception:
            pass


# ViewSet-এর জন্য API views
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(['GET', 'POST'])
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def notification_prefs_view(request):
    """GET/POST /support/notifications/prefs/"""
    manager = NotificationPrefsManager()
    if request.method == 'GET':
        return Response({
            'success': True,
            'prefs':   manager.get_prefs_for_api(request.user),
        })
    updates = request.data
    prefs   = manager.update_prefs(request.user, updates)
    return Response({'success': True, 'prefs': manager.get_prefs_for_api(request.user)})
@permission_classes([IsAuthenticated])
def disable_channel_view(request, channel):
    """DELETE /support/notifications/prefs/{channel}/"""
    manager = NotificationPrefsManager()
    manager.disable_channel(request.user, channel)
    return Response({'success': True, 'message': f'{channel} notifications disabled.'})


prefs_manager = NotificationPrefsManager()