# api/admin_panel/EXTENSION_GUIDE.py
"""
============================================================
ADMIN PANEL — FUTURE EXTENSION GUIDE (1 YEAR+ PROOF)
============================================================

নতুন feature/app যোগ করতে admin_panel-এর কোনো ফাইল
বদলাতে হবে না। শুধু AppExtension register করো।

============================================================
STEP 1: নতুন app-এ extension file তৈরি করো
============================================================

# api/new_feature/admin_extension.py

from api.admin_panel.plugins import AppExtension


class NewFeatureExtension(AppExtension):
    #
    # ── পরিচয় ──────────────────────────────────────────────
    name        = 'new_feature'           # unique key, snake_case
    label       = 'New Feature'           # admin menu label
    version     = '1.0.0'
    description = 'Describe the feature'
    icon        = '🚀'
    menu_group  = 'Finance'  # Finance | Users | Offers | Security | Analytics | Other
    menu_order  = 45         # lower = higher in sidebar

    # ── ViewSets (REST endpoints) ────────────────────────────
    def get_viewsets(self):
        from .viewsets import NewFeatureAdminViewSet
        return [
            ('new-feature', NewFeatureAdminViewSet),
            # multiple viewsets OK:
            # ('new-feature-reports', NewFeatureReportViewSet),
        ]
        # এই viewset auto-এ /api/admin-panel/new-feature/ URL পাবে

    # ── Global Search ────────────────────────────────────────
    def get_search_handlers(self):
        from .search import search_new_feature_records
        return [
            # (model_name, app_name, search_fn, icon)
            ('NewFeatureRecord', 'new_feature', search_new_feature_records, '🚀'),
        ]
        # search_new_feature_records(query, limit) -> List[Dict]

    # ── Admin Dashboard Widgets ──────────────────────────────
    def get_dashboard_widgets(self):
        def my_widget_data():
            from .models import NewFeatureModel
            return {
                'widget': 'new_feature_stat',
                'label':  'New Feature Count',
                'value':  NewFeatureModel.objects.count(),
                'icon':   '🚀',
                'color':  '#8B5CF6',
            }
        return [my_widget_data()]

    # ── Feature Flags ────────────────────────────────────────
    def get_feature_flags(self):
        # These auto-seed in FeatureFlag table
        return [
            # (flag_key, default_enabled, description)
            ('enabled',      True,  'Enable new feature'),
            ('beta_mode',    False, 'Enable beta features'),
            ('daily_limit',  True,  'Enforce daily limits'),
        ]
        # Access: from api.admin_panel.feature_flags import is_enabled
        #         is_enabled('new_feature.enabled')

    # ── System Config Defaults ───────────────────────────────
    def get_system_config_defaults(self):
        # These auto-seed in SystemConfig table
        return [
            # (key, value, value_type, group)
            ('max_per_day',    '100', 'integer', 'new_feature'),
            ('payout_rate',    '0.5', 'float',   'new_feature'),
            ('enabled_geos',   'BD',  'string',  'new_feature'),
        ]
        # Access: SystemConfig.objects.get(key='new_feature.max_per_day').get_typed_value()

    # ── Celery Beat Schedule ─────────────────────────────────
    def get_celery_beat_schedule(self):
        from celery.schedules import crontab
        return {
            'daily_reset': {
                'task':     'api.new_feature.tasks.daily_reset',
                'schedule': crontab(hour=0, minute=0),
            },
            'hourly_sync': {
                'task':     'api.new_feature.tasks.sync',
                'schedule': crontab(minute=0),
            },
        }

    # ── Django Signals ───────────────────────────────────────
    def get_signals(self):
        from .signals import on_user_earned_new_feature
        return [
            # (admin_panel signal_name, your_handler_fn)
            ('admin_withdrawal_approved', on_user_earned_new_feature),
        ]

    # ── EventBus Handlers ────────────────────────────────────
    def get_event_handlers(self):
        from .handlers import on_user_banned_handler
        return {
            'admin_panel.user_banned':     on_user_banned_handler,
            'admin_panel.config_changed':  self._on_config_changed,
        }

    def _on_config_changed(self, payload):
        from django.core.cache import cache
        cache.delete('new_feature:config')

    # ── Notification Templates ───────────────────────────────
    def get_notification_templates(self):
        # Auto-seeded in EmailTemplate table
        return {
            'reward_earned': {
                'email_subject': '🎉 You earned a reward!',
                'email_body':    'Dear {{username}}, you earned {{amount}} from {{feature}}.',
                'push_title':    '🎉 Reward Earned!',
                'push_body':     'You earned {{amount}} BDT.',
                'sms':           'Reward: {{amount}} BDT credited.',
                'email_html':    '<h2>You earned {{amount}} BDT!</h2>',
            },
        }

    # ── Health Checks ────────────────────────────────────────
    def get_health_checks(self):
        def check_new_feature_db():
            from .models import NewFeatureModel
            count = NewFeatureModel.objects.count()
            return {'status': 'ok', 'record_count': count}
        return [check_new_feature_db]

    # ── Role Permissions ────────────────────────────────────-
    def get_permissions(self):
        return {
            'view_new_feature':   ['superadmin', 'admin', 'analyst', 'viewer'],
            'edit_new_feature':   ['superadmin', 'admin'],
            'delete_new_feature': ['superadmin'],
        }

    # ── Admin Menu Items ─────────────────────────────────────
    def get_admin_menu_items(self):
        return [
            {
                'label':    'New Feature Overview',
                'url':      '/api/admin-panel/new-feature/',
                'icon':     '🚀',
                'group':    self.menu_group,
                'order':    self.menu_order,
                'badge_fn': lambda: NewFeatureModel.objects.filter(status='pending').count(),
            }
        ]

    # ── Audit Event Types ────────────────────────────────────
    def get_audit_event_types(self):
        return [
            'new_feature.created',
            'new_feature.approved',
            'new_feature.rejected',
        ]

    # ── Lifecycle hooks ──────────────────────────────────────
    def on_install(self):
        # Called once when extension first registered
        pass

    def on_ready(self):
        # Called every Django startup (after all apps loaded)
        pass

    def on_uninstall(self):
        # Called when extension removed
        pass


============================================================
STEP 2: app-এর apps.py-এ register করো
============================================================

# api/new_feature/apps.py

from django.apps import AppConfig

class NewFeatureConfig(AppConfig):
    name = 'api.new_feature'

    def ready(self):
        # শুধু এই 2 লাইন যোগ করো
        from api.admin_panel.plugins import extension_registry
        from .admin_extension import NewFeatureExtension
        extension_registry.register(NewFeatureExtension())

        # Signal connections যদি থাকে
        import api.new_feature.signals  # noqa


============================================================
STEP 3: settings.py-এ INSTALLED_APPS এ যোগ করো
============================================================

INSTALLED_APPS = [
    ...
    'api.admin_panel',   # এটা আগে থাকতে হবে
    'api.new_feature',   # নতুন app এর পরে
    ...
]

শেষ — কোনো urls.py, views.py, আর কোনো admin_panel ফাইল
বদলাতে হবে না। সব auto-wire হয়ে যাবে।


============================================================
EXTENSION SYSTEM কী কী auto করে?
============================================================

✅ get_viewsets()              → router.register() auto
✅ get_search_handlers()       → global search auto-registered
✅ get_dashboard_widgets()     → dashboard widget list-এ auto-added
✅ get_celery_beat_schedule()  → Celery Beat auto-scheduled
✅ get_signals()               → signal_router auto-connected
✅ get_event_handlers()        → EventBus auto-subscribed
✅ get_feature_flags()         → FeatureFlag DB auto-seeded
✅ get_system_config_defaults() → SystemConfig DB auto-seeded
✅ get_notification_templates() → EmailTemplate DB auto-seeded
✅ get_health_checks()         → health check auto-registered
✅ get_admin_menu_items()      → sidebar menu auto-populated
✅ on_install() / on_ready()   → lifecycle hooks auto-called

============================================================
QUICK REFERENCE — সব extension point
============================================================

from api.admin_panel.plugins import extension_registry

# সব registered extensions দেখো
extension_registry.list_extensions()

# নির্দিষ্ট extension পাও
ext = extension_registry.get_extension('new_feature')

# সব viewsets (urls.py auto-uses this)
extension_registry.get_all_viewsets()

# সব menu items
extension_registry.get_all_menu_items()

# সব widgets
extension_registry.get_all_widgets()

# সব beat schedules
extension_registry.get_all_beat_schedule()

# Health summary
extension_registry.get_health_summary()

============================================================
AVAILABLE HOOKS — যে events-এ subscribe করা যায়
============================================================

# EventBus events:
'admin_panel.user_banned'
'admin_panel.user_unbanned'
'admin_panel.withdrawal_approved'
'admin_panel.withdrawal_rejected'
'admin_panel.kyc_approved'
'admin_panel.kyc_rejected'
'admin_panel.config_changed'
'admin_panel.flag_changed'
'admin_panel.maintenance_started'
'admin_panel.maintenance_ended'
'admin_panel.fraud_detected'
'admin_panel.offer_paused'
'admin_panel.offer_cap_reached'
'admin_panel.circuit_breaker_open'
'admin_panel.wallet_drift'

# Admin_panel signals:
admin_user_banned
admin_user_unbanned
admin_withdrawal_approved
admin_withdrawal_rejected
admin_config_changed
admin_flag_changed
admin_maintenance_on
admin_maintenance_off
admin_fraud_blocked
admin_wallet_adjusted

============================================================
FEATURE FLAG PATTERN — নতুন feature gate করা
============================================================

# Extension-এর flag check:
from api.admin_panel.feature_flags import is_enabled

if is_enabled('new_feature.enabled', user=request.user):
    # feature active
    pass

# SystemConfig read:
from api.admin_panel.models.config import SystemConfig
max_per_day = SystemConfig.objects.get(key='new_feature.max_per_day').get_typed_value()

============================================================
AUDIT TRAIL PATTERN
============================================================

from api.admin_panel.audit_trail import audit_trail
audit_trail.log(
    event_type='new_feature.created',
    actor_id=request.user.pk,
    actor_name=request.user.username,
    payload={'record_id': record.pk, 'amount': amount},
    ip=request.META.get('REMOTE_ADDR', ''),
    severity='info',
)

============================================================
NOTIFICATION PATTERN
============================================================

from api.admin_panel.notification_dispatcher import dispatcher
dispatcher.send(
    user_id=user_id,
    template_key='new_feature.reward_earned',
    context={'username': user.username, 'amount': amount, 'feature': 'New Feature'},
    channels=['push', 'email', 'sms'],
)

============================================================
"""

# This file is documentation only — not imported