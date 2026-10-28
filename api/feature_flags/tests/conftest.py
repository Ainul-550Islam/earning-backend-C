"""
Pytest configuration for Feature Flags & A/B Testing tests.
"""
import pytest
from django.test import Client
from django.utils import timezone  # FIX: was missing — active_experiment fixture used
                                    # timezone.now() and raised NameError on every use.
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    """
    Fixture for DRF API client.
    
    Returns:
        APIClient instance
    """
    return APIClient()


@pytest.fixture
def client():
    """
    Fixture for Django test client.
    
    Returns:
        Client instance
    """
    return Client()


@pytest.fixture
def feature_flag():
    """
    Fixture for a test feature flag.
    
    Returns:
        FeatureFlag instance
    """
    from ..models.feature_flag import FeatureFlag
    return FeatureFlag.objects.create(
        name='test-flag',
        flag_type='boolean',
        status='draft',
        environment='production'
    )


@pytest.fixture
def active_flag():
    """
    Fixture for an active feature flag.
    
    Returns:
        FeatureFlag instance
    """
    from ..models.feature_flag import FeatureFlag
    return FeatureFlag.objects.create(
        name='active-flag',
        flag_type='boolean',
        status='active',
        rollout_percentage=100,
        environment='production'
    )


@pytest.fixture
def flag_variant():
    """
    Fixture for a test flag variant.
    
    Returns:
        FlagVariant instance
    """
    from ..models.feature_flag import FeatureFlag
    from ..models.flag_variant import FlagVariant
    flag = FeatureFlag.objects.create(
        name='test-flag',
        flag_type='boolean',
        status='active',
        environment='production'
    )
    return FlagVariant.objects.create(
        flag=flag,
        name='variant-a',
        value='A',
        weight=50
    )


@pytest.fixture
def experiment():
    """
    Fixture for a test experiment.
    
    Returns:
        Experiment instance
    """
    from ..models.feature_flag import FeatureFlag
    from ..models.experiment import Experiment
    flag = FeatureFlag.objects.create(
        name='test-flag',
        flag_type='boolean',
        status='active',
        environment='production'
    )
    return Experiment.objects.create(
        name='test-experiment',
        flag=flag,
        status='draft',
        min_sample_size=100
    )


@pytest.fixture
def active_experiment():
    """
    Fixture for an active experiment.
    
    Returns:
        Experiment instance
    """
    from ..models.feature_flag import FeatureFlag
    from ..models.experiment import Experiment
    flag = FeatureFlag.objects.create(
        name='test-flag',
        flag_type='boolean',
        status='active',
        environment='production'
    )
    return Experiment.objects.create(
        name='active-experiment',
        flag=flag,
        status='running',
        start_date=timezone.now()
    )


@pytest.fixture
def rollout_rule():
    """
    Fixture for a test rollout rule.
    
    Returns:
        RolloutRule instance
    """
    from ..models.feature_flag import FeatureFlag
    from ..models.rollout_rule import RolloutRule
    flag = FeatureFlag.objects.create(
        name='test-flag',
        flag_type='boolean',
        status='active',
        environment='production'
    )
    return RolloutRule.objects.create(
        flag=flag,
        rule_type='user_id',
        field='user_id',
        operator='equals',
        value='user-123'
    )


@pytest.fixture
def flag_analytics():
    """
    Fixture for test flag analytics.
    
    Returns:
        FlagAnalytics instance
    """
    from ..models.feature_flag import FeatureFlag
    from ..models.flag_analytics import FlagAnalytics
    flag = FeatureFlag.objects.create(
        name='test-flag',
        flag_type='boolean',
        status='active',
        environment='production'
    )
    return FlagAnalytics.objects.create(
        flag=flag,
        date=timezone.now().date(),
        evaluation_count=100,
        enabled_count=50,
        unique_users=80,
        environment='production'
    )


@pytest.fixture
def feature_flag_service():
    """
    Fixture for feature flag service.
    
    Returns:
        FeatureFlagService instance
    """
    from ..services.feature_flag_service import FeatureFlagService
    return FeatureFlagService()


@pytest.fixture
def flag_engine():
    """
    Fixture for the flag engine.

    FIX (replaces the old `flag_engine_service` fixture): `FlagEngineService`
    was deleted as a DRY violation — it was a 100% redundant wrapper around
    `FlagEngine`. Tests that need engine-level evaluation should use `FlagEngine`
    directly, which is what this fixture provides.

    Returns:
        FlagEngine instance
    """
    from ..flag_engine import FlagEngine
    return FlagEngine()


@pytest.fixture
def performance_service():
    """
    NEW fixture for the performance service (Missing Component #10).

    Returns:
        PerformanceService instance
    """
    from ..services.performance_service import PerformanceService
    return PerformanceService()


# ---------------------------------------------------------------------------
# NEW fixtures — auth / RBAC / organizations (production-readiness additions)
# ---------------------------------------------------------------------------

@pytest.fixture
def role_viewer(db):
    """NEW: the 'viewer' Role, seeded by the 0002_bootstrap_rbac data migration."""
    from ..models.permissions import Role
    return Role.objects.get(name=Role.RoleName.VIEWER)


@pytest.fixture
def role_editor(db):
    """NEW: the 'editor' Role, seeded by the 0002_bootstrap_rbac data migration."""
    from ..models.permissions import Role
    return Role.objects.get(name=Role.RoleName.EDITOR)


@pytest.fixture
def role_admin(db):
    """NEW: the 'admin' Role, seeded by the 0002_bootstrap_rbac data migration."""
    from ..models.permissions import Role
    return Role.objects.get(name=Role.RoleName.ADMIN)


@pytest.fixture
def viewer_user(db, role_viewer):
    """NEW: an authenticated user holding only view permissions."""
    from django.contrib.auth.models import User
    from ..models.permissions import UserRole

    user = User.objects.create_user(username='viewer-user', password='testpass123')
    UserRole.objects.create(user=user, role=role_viewer)
    return user


@pytest.fixture
def editor_user(db, role_editor):
    """NEW: an authenticated user holding create/edit permissions."""
    from django.contrib.auth.models import User
    from ..models.permissions import UserRole

    user = User.objects.create_user(username='editor-user', password='testpass123')
    UserRole.objects.create(user=user, role=role_editor)
    return user


@pytest.fixture
def admin_user(db, role_admin):
    """NEW: an authenticated user holding every permission, including approve_changes."""
    from django.contrib.auth.models import User
    from ..models.permissions import UserRole

    user = User.objects.create_user(username='admin-user', password='testpass123')
    UserRole.objects.create(user=user, role=role_admin)
    return user


@pytest.fixture
def authenticated_editor_client(editor_user):
    """NEW: APIClient pre-authenticated as editor_user."""
    client = APIClient()
    client.force_authenticate(user=editor_user)
    return client


@pytest.fixture
def authenticated_viewer_client(viewer_user):
    """NEW: APIClient pre-authenticated as viewer_user."""
    client = APIClient()
    client.force_authenticate(user=viewer_user)
    return client


@pytest.fixture
def authenticated_admin_client(admin_user):
    """NEW: APIClient pre-authenticated as admin_user."""
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def organization(db):
    """NEW: a sample Organization (Missing Component #2: Team/Org isolation)."""
    from django.contrib.auth.models import User
    from ..models.organization import Organization

    owner = User.objects.create_user(username='org-owner', password='testpass123')
    return Organization.objects.create(name='Acme Inc', slug='acme-inc', owner=owner)


@pytest.fixture
def experiment_service():
    """
    Fixture for experiment service.
    
    Returns:
        ExperimentService instance
    """
    from ..services.experiment_service import ExperimentService
    return ExperimentService()


@pytest.fixture
def rollout_service():
    """
    Fixture for rollout service.
    
    Returns:
        RolloutService instance
    """
    from ..services.rollout_service import RolloutService
    return RolloutService()


@pytest.fixture
def analytics_service():
    """
    Fixture for analytics service.
    
    Returns:
        AnalyticsService instance
    """
    from ..services.analytics_service import AnalyticsService
    return AnalyticsService()


@pytest.fixture
def variant_assignment_service():
    """
    Fixture for variant assignment service.
    
    Returns:
        VariantAssignmentService instance
    """
    from ..services.variant_assignment_service import VariantAssignmentService
    return VariantAssignmentService()


# ---------------------------------------------------------------------------
# NEW: automatic cleanup fixture to prevent stale set_current_user() state
# from leaking across tests and causing AuditLog FK teardown errors.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_current_user():
    """Reset the set_current_user() holder before and after every test.
    Without this, a stale user reference set by one test persists into the
    signal handlers of the next test, and when Django teardown deletes the
    user the AuditLog still references it — causing FK IntegrityErrors."""
    from feature_flags.signals import set_current_user
    set_current_user(None)
    yield
    set_current_user(None)
