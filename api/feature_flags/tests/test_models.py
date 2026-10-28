"""
Model tests for Feature Flags & A/B Testing.
"""
import pytest
from django.utils import timezone

from ..models.feature_flag import FeatureFlag
from ..models.flag_variant import FlagVariant
from ..models.experiment import Experiment
from ..models.experiment_participant import ExperimentParticipant
from ..models.rollout_rule import RolloutRule
from ..models.flag_analytics import FlagAnalytics


@pytest.mark.django_db
class TestFeatureFlagModel:
    """Tests for FeatureFlag model."""
    
    def test_create_flag(self):
        """Test creating a feature flag."""
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='draft',
            environment='production'
        )
        
        assert flag.name == 'test-flag'
        assert flag.flag_type == 'boolean'
        assert flag.status == 'draft'
    
    def test_is_enabled(self):
        """Test is_enabled method."""
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            rollout_percentage=100,
            environment='production'
        )
        
        assert flag.is_enabled() is True
    
    def test_get_value(self):
        """Test get_value method."""
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='string',
            status='active',
            default_value='default',
            rollout_percentage=100,
            environment='production'
        )
        
        value = flag.get_value()
        assert value == 'default'


@pytest.mark.django_db
class TestFlagVariantModel:
    """Tests for FlagVariant model."""
    
    def test_create_variant(self):
        """Test creating a flag variant."""
        flag = FeatureFlag.objects.create(
            name='test-flag',
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
        
        assert variant.name == 'variant-a'
        assert variant.value == 'A'
        assert variant.weight == 50


@pytest.mark.django_db
class TestExperimentModel:
    """Tests for Experiment model."""
    
    def test_create_experiment(self):
        """Test creating an experiment."""
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        experiment = Experiment.objects.create(
            name='test-experiment',
            flag=flag,
            status='draft',
            min_sample_size=100
        )
        
        assert experiment.name == 'test-experiment'
        assert experiment.status == 'draft'
        assert experiment.min_sample_size == 100
    
    def test_is_active(self):
        """Test is_active method."""
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        experiment = Experiment.objects.create(
            name='test-experiment',
            flag=flag,
            status='running',
            start_date=timezone.now()
        )
        
        assert experiment.is_active() is True


@pytest.mark.django_db
class TestExperimentParticipantModel:
    """Tests for ExperimentParticipant model."""
    
    def test_create_participant(self):
        """Test creating an experiment participant."""
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        experiment = Experiment.objects.create(
            name='test-experiment',
            flag=flag,
            status='running'
        )
        
        variant = FlagVariant.objects.create(
            flag=flag,
            name='variant-a',
            value='A',
            weight=50
        )
        
        participant = ExperimentParticipant.objects.create(
            experiment=experiment,
            variant=variant,
            user_id='user-123'
        )
        
        assert participant.user_id == 'user-123'
        assert participant.converted is False


@pytest.mark.django_db
class TestRolloutRuleModel:
    """Tests for RolloutRule model."""
    
    def test_create_rule(self):
        """Test creating a rollout rule."""
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        rule = RolloutRule.objects.create(
            flag=flag,
            rule_type='user_id',
            field='user_id',
            operator='equals',
            value='user-123'
        )
        
        assert rule.rule_type == 'user_id'
        assert rule.field == 'user_id'
        assert rule.operator == 'equals'
    
    def test_evaluate_rule(self):
        """Test evaluate method."""
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        rule = RolloutRule.objects.create(
            flag=flag,
            rule_type='user_id',
            field='user_id',
            operator='equals',
            value='user-123'
        )
        
        context = {'user_id': 'user-123'}
        assert rule.evaluate(context) is True
        
        context = {'user_id': 'user-456'}
        assert rule.evaluate(context) is False


@pytest.mark.django_db
class TestFlagAnalyticsModel:
    """Tests for FlagAnalytics model."""
    
    def test_create_analytics(self):
        """Test creating flag analytics."""
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        analytics = FlagAnalytics.objects.create(
            flag=flag,
            date=timezone.now().date(),
            evaluation_count=100,
            enabled_count=50,
            unique_users=80,
            environment='production'
        )
        
        assert analytics.evaluation_count == 100
        assert analytics.enabled_count == 50
    
    def test_get_enable_rate(self):
        """Test get_enable_rate method."""
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        analytics = FlagAnalytics.objects.create(
            flag=flag,
            date=timezone.now().date(),
            evaluation_count=100,
            enabled_count=50,
            unique_users=80,
            environment='production'
        )
        
        assert analytics.get_enable_rate() == 50.0
    
    def test_get_conversion_rate(self):
        """Test get_conversion_rate method."""
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        analytics = FlagAnalytics.objects.create(
            flag=flag,
            date=timezone.now().date(),
            evaluation_count=100,
            enabled_count=50,
            unique_users=80,
            conversion_count=20,
            environment='production'
        )
        
        assert analytics.get_conversion_rate() == 25.0
