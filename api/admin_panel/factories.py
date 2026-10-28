# api/admin_panel/factories.py
"""
Test factories for admin_panel models.
Uses factory_boy — pip install factory-boy
"""
try:
    import factory
    import factory.django
    FACTORY_BOY_AVAILABLE = True
except ImportError:
    FACTORY_BOY_AVAILABLE = False
    # Stub classes so factories.py doesn't break on import
    class _FactoryStub:
        def __init_subclass__(cls, **kwargs): pass
    class factory:
        django = type('django', (), {'DjangoModelFactory': _FactoryStub})()
        Sequence = lambda fn: fn(0)
        SubFactory = lambda *a, **k: None
        LazyAttribute = lambda fn: fn
        PostGenerationMethodCall = lambda *a, **k: None
        LazyFunction = lambda fn: fn
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
    username = factory.Sequence(lambda n: f'user_{n}')
    email    = factory.LazyAttribute(lambda o: f'{o.username}@test.com')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    is_active = True


class AdminUserFactory(UserFactory):
    is_staff = True
    is_superuser = False


class SuperUserFactory(UserFactory):
    is_staff = True
    is_superuser = True


class AdminProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.AdminProfile'
    user       = factory.SubFactory(AdminUserFactory)
    role       = 'admin'
    phone      = factory.Sequence(lambda n: f'+8801{n:09d}')
    department = 'Operations'
    receive_digest = True
    receive_alerts = True


class SystemSettingsFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.SystemSettings'
        django_get_or_create = ('site_name',)
    site_name       = 'Test Earning Platform'
    currency_code   = 'BDT'
    currency_symbol = '৳'
    enable_referral = True
    maintenance_mode = False


class SystemConfigFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.SystemConfig'
    key        = factory.Sequence(lambda n: f'test_config_{n}')
    value      = 'test_value'
    value_type = 'string'
    group      = 'general'


class FeatureFlagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.FeatureFlag'
    flag_key    = factory.Sequence(lambda n: f'test_flag_{n}')
    is_enabled  = True
    rollout_pct = 100


class MaintenanceWindowFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.MaintenanceWindow'
    title      = factory.Sequence(lambda n: f'Maintenance {n}')
    message    = 'Test maintenance'
    start_at   = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=1))
    end_at     = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=2))
    is_active  = False


class AdminActivityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.AdminActivity'
    actor       = factory.SubFactory(AdminUserFactory)
    action      = 'test_action'
    model_name  = 'TestModel'
    object_id   = factory.Sequence(lambda n: str(n))
    status      = 'success'
    ip          = '127.0.0.1'


class AdminSessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.AdminSession'
    user        = factory.SubFactory(AdminUserFactory)
    session_key = factory.Sequence(lambda n: f'sess{n:040d}')
    ip          = '127.0.0.1'
    is_active   = True
    status      = 'active'


class DashboardMetricFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.DashboardMetric'
    metric_key = factory.Sequence(lambda n: f'metric_{n}')
    label      = factory.Sequence(lambda n: f'Metric {n}')
    value      = 100
    period     = 'daily'


class ReportDefinitionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.ReportDefinition'
    name        = factory.Sequence(lambda n: f'Report {n}')
    report_type = 'user'
    is_active   = True


class DataExportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.DataExport'
    model_name    = 'auth.User'
    format        = 'csv'
    status        = 'queued'
    requested_by  = factory.SubFactory(AdminUserFactory)


class AdminInsightFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.AdminInsight'
    type        = 'summary'
    title       = factory.Sequence(lambda n: f'Insight {n}')
    body        = 'Test insight body.'
    priority    = 'medium'
    is_read     = False
    is_dismissed = False


class SiteNotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.SiteNotification'
    title             = factory.Sequence(lambda n: f'Notification {n}')
    message           = 'Test notification.'
    notification_type = 'INFO'
    is_active         = True
    start_date        = factory.LazyFunction(timezone.now)


class EndpointToggleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.EndpointToggle'
    path       = factory.Sequence(lambda n: f'/api/test-{n}/')
    method     = 'ALL'
    group      = 'test'
    label      = factory.Sequence(lambda n: f'Toggle {n}')
    is_enabled = True