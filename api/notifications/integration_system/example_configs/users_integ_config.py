# api/users/integ_config.py
"""
Users Module — Integration Configuration
"এক কাজের জন্য একটাই মালিক"

Users module OWNS user data. Provides a clean API for other modules
to query user info without direct ORM access to UserProfile.
"""
from api.notifications.integration_system.module_protocol import (
    ModuleConfig, SignalMap, EventMap, HealthCheck
)

class UsersIntegConfig(ModuleConfig):
    module_name = 'users'
    version = '1.0.0'
    description = 'User Management & Authentication'

    signal_maps = [
        SignalMap(
            model_path='users.User',
            field='is_active',
            value=True,
            event_type='user.registered',
            user_field='id',
            data_fields=['username', 'email', 'date_joined'],
            on_created=True,
            on_update=False,
        ),
        SignalMap(
            model_path='users.User',
            field='level',
            value=None,  # Any level change
            event_type='user.level_up',
            user_field='id',
            data_fields=['new_level', 'previous_level', 'username'],
            on_created=False,
            on_update=True,
            condition_fn=lambda instance: (
                getattr(instance, '_original_level', 0) < getattr(instance, 'level', 0)
                if hasattr(instance, '_original_level') else False
            ),
        ),
    ]

    event_maps = [
        EventMap(
            event_type='user.registered',
            notification_type='announcement',
            title_template='স্বাগতম! 🎉',
            message_template='আপনার account সফলভাবে তৈরি হয়েছে। এখন task করে আয় শুরু করুন!',
            channel='in_app',
            priority='medium',
            send_email=True,
        ),
        EventMap(
            event_type='user.level_up',
            notification_type='level_up',
            title_template='Level Up! 🚀 Level {new_level}',
            message_template='অভিনন্দন! আপনি Level {new_level} এ উন্নীত হয়েছেন। নতুন সুবিধা unlock হয়েছে!',
            channel='in_app',
            priority='high',
            send_push=True,
        ),
    ]

    health_checks = [HealthCheck(name='users_db', model_path='users.User')]
    allowed_targets = ['notifications', 'wallet', 'kyc', 'analytics']

    @classmethod
    def on_registered(cls):
        """Register users module as a data provider for filtered user queries."""
        try:
            from api.notifications.integration_system.integ_registry import registry
            from api.notifications.integration_system.integ_adapter import BaseAdapter
            from api.notifications.integration_system.integ_constants import HealthStatus

            class UsersDataAdapter(BaseAdapter):
                name = 'users'

                def _do_send(self, payload, **kwargs):
                    action = payload.get('action', '')
                    if action == 'get_user_ids_by_profile':
                        return self._get_user_ids_by_profile(payload.get('filters', {}))
                    if action == 'get_user_profile':
                        return self._get_user_profile(payload.get('user_id'))
                    return {'success': True, 'data': {}}

                def _get_user_ids_by_profile(self, filters):
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    qs = User.objects.filter(is_active=True)
                    if filters.get('country'):
                        qs = qs.filter(profile__country__in=filters['country'])
                    if filters.get('language'):
                        qs = qs.filter(profile__language__in=filters['language'])
                    if filters.get('user_type'):
                        qs = qs.filter(profile__user_type__in=filters['user_type'])
                    if filters.get('tier'):
                        qs = qs.filter(profile__tier=filters['tier'])
                    return {'success': True, 'data': {'user_ids': list(qs.values_list('pk', flat=True))}}

                def _get_user_profile(self, user_id):
                    try:
                        from django.contrib.auth import get_user_model
                        user = get_user_model().objects.select_related('profile').get(pk=user_id)
                        profile = getattr(user, 'profile', None)
                        return {'success': True, 'data': {
                            'user_id': user.pk,
                            'username': user.username,
                            'email': user.email,
                            'country': getattr(profile, 'country', ''),
                            'language': getattr(profile, 'language', 'en'),
                            'user_type': getattr(profile, 'user_type', 'user'),
                            'tier': getattr(profile, 'tier', 'basic'),
                        }}
                    except Exception as exc:
                        return {'success': False, 'error': str(exc)}

                def health_check(self):
                    try:
                        from django.contrib.auth import get_user_model
                        get_user_model().objects.first()
                        return HealthStatus.HEALTHY
                    except Exception:
                        return HealthStatus.UNHEALTHY

            registry.register('users', UsersDataAdapter, overwrite=True,
                              description='Users data API — profile queries')
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(f'UsersIntegConfig.on_registered: {exc}')
