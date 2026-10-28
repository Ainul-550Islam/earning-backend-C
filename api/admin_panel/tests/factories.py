# api/admin_panel/tests/factories.py
"""
Test factories for admin_panel models.
Uses factory_boy for generating test data.
CPAlead-style earning platform test data.
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

    username = factory.Sequence(lambda n: f'testuser_{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@test.com')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    is_active = True
    is_staff = False


class AdminUserFactory(UserFactory):
    is_staff = True
    is_superuser = False


class SuperUserFactory(UserFactory):
    is_staff = True
    is_superuser = True


class AdminProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.AdminProfile'

    user = factory.SubFactory(AdminUserFactory)
    role = 'admin'
    phone = factory.Sequence(lambda n: f'+8801700{n:06d}')
    department = 'Operations'
    timezone = 'Asia/Dhaka'
    theme = 'auto'
    receive_digest = True
    receive_alerts = True


class SystemSettingsFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.SystemSettings'
        django_get_or_create = ('site_name',)

    site_name = 'Test Earning Platform'
    currency_code = 'BDT'
    currency_symbol = '৳'
    min_withdrawal_amount = 100
    max_withdrawal_amount = 10000
    enable_referral = True
    maintenance_mode = False


class SiteNotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.SiteNotification'

    title = factory.Sequence(lambda n: f'Test Notification {n}')
    message = 'This is a test notification.'
    notification_type = 'INFO'
    is_active = True
    priority = 0
    start_date = factory.LazyFunction(timezone.now)


class SiteContentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.SiteContent'

    identifier = factory.Sequence(lambda n: f'test-content-{n}')
    title = factory.Sequence(lambda n: f'Test Content {n}')
    content = '<p>Test content body.</p>'
    content_type = 'PAGE'
    is_active = True
    language = 'en'


class EndpointToggleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.EndpointToggle'

    path = factory.Sequence(lambda n: f'/api/test-endpoint-{n}/')
    method = 'ALL'
    group = 'test'
    label = factory.Sequence(lambda n: f'Test Endpoint {n}')
    is_enabled = True


class SystemConfigFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.SystemConfig'

    key = factory.Sequence(lambda n: f'test_config_key_{n}')
    value = 'test_value'
    value_type = 'string'
    group = 'general'
    label = factory.Sequence(lambda n: f'Test Config {n}')
    is_public = False


class FeatureFlagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.FeatureFlag'

    flag_key = factory.Sequence(lambda n: f'test_flag_{n}')
    label = factory.Sequence(lambda n: f'Test Flag {n}')
    is_enabled = True
    rollout_pct = 100
    updated_by = None


class MaintenanceWindowFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.MaintenanceWindow'

    title = factory.Sequence(lambda n: f'Test Maintenance {n}')
    message = 'Scheduled maintenance in progress.'
    maintenance_type = 'scheduled'
    start_at = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=1))
    end_at = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=2))
    is_active = False
    notify_users = False


class AdminActivityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.AdminActivity'

    actor = factory.SubFactory(AdminUserFactory)
    action = 'create'
    model_name = 'TestModel'
    object_id = factory.Sequence(lambda n: str(n))
    status = 'success'
    ip = '127.0.0.1'
    method = 'POST'
    response_code = 201


class AdminSessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.AdminSession'

    user = factory.SubFactory(AdminUserFactory)
    session_key = factory.Sequence(lambda n: f'testsessionkey{n:040d}')
    ip = '127.0.0.1'
    is_active = True
    status = 'active'


class DashboardWidgetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.DashboardWidget'

    user = factory.SubFactory(AdminUserFactory)
    title = factory.Sequence(lambda n: f'Widget {n}')
    widget_type = 'stat_card'
    size = 'md'
    is_visible = True
    position = {'x': 0, 'y': 0, 'w': 4, 'h': 2}


class DashboardMetricFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.DashboardMetric'

    metric_key = factory.Sequence(lambda n: f'test_metric_{n}')
    label = factory.Sequence(lambda n: f'Test Metric {n}')
    value = 1000
    unit = 'users'
    period = 'daily'


class ReportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.Report'

    title = factory.Sequence(lambda n: f'Test Report {n}')
    report_type = 'user'
    status = 'completed'
    generated_by = factory.SubFactory(AdminUserFactory)


class ReportDefinitionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.ReportDefinition'

    name = factory.Sequence(lambda n: f'Test Report Definition {n}')
    report_type = 'user'
    is_active = True
    is_system = False
    created_by = factory.SubFactory(AdminUserFactory)


class DataExportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.DataExport'

    model_name = 'auth.User'
    label = 'Test Export'
    format = 'csv'
    status = 'queued'
    requested_by = factory.SubFactory(AdminUserFactory)


class AdminInsightFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'admin_panel.AdminInsight'

    type = 'summary'
    title = factory.Sequence(lambda n: f'Test Insight {n}')
    body = 'This is a test insight body.'
    priority = 'medium'
    is_read = False
    is_dismissed = False