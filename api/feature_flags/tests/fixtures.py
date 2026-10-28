"""
Test fixtures for Feature Flags & A/B Testing.
"""
import pytest
from django.utils import timezone

from ..models.feature_flag import FeatureFlag
from ..models.flag_variant import FlagVariant
from ..models.experiment import Experiment
from ..models.experiment_participant import ExperimentParticipant
from ..models.rollout_rule import RolloutRule
from ..models.flag_analytics import FlagAnalytics


@pytest.fixture
def sample_flag():
    """
    Create a sample feature flag for testing.
    
    Returns:
        FeatureFlag instance
    """
    return FeatureFlag.objects.create(
        name='sample-flag',
        description='Sample flag for testing',
        flag_type='boolean',
        status='active',
        default_value=False,
        rollout_percentage=50,
        targeting_rules=[],
        metadata={'key': 'value'},
        tags=['tag1', 'tag2'],
        owner='test-owner',
        team='test-team',
        environment='production'
    )


@pytest.fixture
def sample_string_flag():
    """
    Create a sample string flag for testing.
    
    Returns:
        FeatureFlag instance
    """
    return FeatureFlag.objects.create(
        name='sample-string-flag',
        description='Sample string flag',
        flag_type='string',
        status='active',
        default_value='default-value',
        rollout_percentage=100,
        environment='production'
    )


@pytest.fixture
def sample_variant():
    """
    Create a sample flag variant for testing.
    
    Returns:
        FlagVariant instance
    """
    flag = FeatureFlag.objects.create(
        name='sample-flag',
        flag_type='boolean',
        status='active',
        environment='production'
    )
    return FlagVariant.objects.create(
        flag=flag,
        name='variant-a',
        description='Variant A',
        value='A',
        weight=50,
        is_control=True,
        is_active=True,
        metadata={'key': 'value'}
    )


@pytest.fixture
def sample_experiment():
    """
    Create a sample experiment for testing.
    
    Returns:
        Experiment instance
    """
    flag = FeatureFlag.objects.create(
        name='sample-flag',
        flag_type='boolean',
        status='active',
        environment='production'
    )
    return Experiment.objects.create(
        name='sample-experiment',
        description='Sample experiment',
        flag=flag,
        status='draft',
        start_date=timezone.now(),
        end_date=timezone.now() + timezone.timedelta(days=7),
        target_audience={'segment': 'all'},
        success_metrics=['conversion_rate'],
        min_sample_size=100,
        significance_threshold=0.95,
        metadata={'key': 'value'},
        owner='test-owner',
        team='test-team'
    )


@pytest.fixture
def sample_participant():
    """
    Create a sample experiment participant for testing.
    
    Returns:
        ExperimentParticipant instance
    """
    flag = FeatureFlag.objects.create(
        name='sample-flag',
        flag_type='boolean',
        status='active',
        environment='production'
    )
    experiment = Experiment.objects.create(
        name='sample-experiment',
        flag=flag,
        status='running'
    )
    variant = FlagVariant.objects.create(
        flag=flag,
        name='variant-a',
        value='A',
        weight=50
    )
    return ExperimentParticipant.objects.create(
        experiment=experiment,
        variant=variant,
        user_id='user-123',
        session_id='session-456',
        converted=False,
        context={'key': 'value'},
        metadata={'key': 'value'}
    )


@pytest.fixture
def sample_converted_participant():
    """
    Create a sample converted participant for testing.
    
    Returns:
        ExperimentParticipant instance
    """
    flag = FeatureFlag.objects.create(
        name='sample-flag',
        flag_type='boolean',
        status='active',
        environment='production'
    )
    experiment = Experiment.objects.create(
        name='sample-experiment',
        flag=flag,
        status='running'
    )
    variant = FlagVariant.objects.create(
        flag=flag,
        name='variant-a',
        value='A',
        weight=50
    )
    return ExperimentParticipant.objects.create(
        experiment=experiment,
        variant=variant,
        user_id='user-789',
        session_id='session-012',
        converted=True,
        converted_at=timezone.now(),
        context={'key': 'value'}
    )


@pytest.fixture
def sample_rollout_rule():
    """
    Create a sample rollout rule for testing.
    
    Returns:
        RolloutRule instance
    """
    flag = FeatureFlag.objects.create(
        name='sample-flag',
        flag_type='boolean',
        status='active',
        environment='production'
    )
    return RolloutRule.objects.create(
        flag=flag,
        rule_type='user_id',
        field='user_id',
        operator='equals',
        value='user-123',
        priority=10,
        is_active=True,
        description='Sample rule',
        metadata={'key': 'value'}
    )


@pytest.fixture
def sample_analytics():
    """
    Create a sample flag analytics for testing.
    
    Returns:
        FlagAnalytics instance
    """
    flag = FeatureFlag.objects.create(
        name='sample-flag',
        flag_type='boolean',
        status='active',
        environment='production'
    )
    return FlagAnalytics.objects.create(
        flag=flag,
        date=timezone.now().date(),
        hour=12,
        evaluation_count=1000,
        enabled_count=500,
        disabled_count=500,
        unique_users=800,
        conversion_count=100,
        metrics={'custom_metric': 123},
        environment='production'
    )


@pytest.fixture
def sample_variant_analytics():
    """
    Create a sample variant analytics for testing.
    
    Returns:
        FlagAnalytics instance
    """
    flag = FeatureFlag.objects.create(
        name='sample-flag',
        flag_type='boolean',
        status='active',
        environment='production'
    )
    variant = FlagVariant.objects.create(
        flag=flag,
        name='variant-a',
        value='A',
        weight=50
    )
    return FlagAnalytics.objects.create(
        flag=flag,
        variant=variant,
        date=timezone.now().date(),
        hour=12,
        evaluation_count=500,
        enabled_count=250,
        unique_users=400,
        conversion_count=50,
        environment='production'
    )
