"""
Experiment Runner tests for Feature Flags & A/B Testing.
"""
import pytest
from django.utils import timezone

from ..experiment_runner import ExperimentRunner
from ..models.feature_flag import FeatureFlag
from ..models.experiment import Experiment
from ..models.flag_variant import FlagVariant


@pytest.mark.django_db
class TestExperimentRunner:
    """Tests for ExperimentRunner."""
    
    def test_initialize_experiment(self):
        """Test initializing an experiment."""
        runner = ExperimentRunner()
        
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        FlagVariant.objects.create(
            flag=flag,
            name='variant-a',
            value='A',
            weight=50
        )
        
        experiment = Experiment.objects.create(
            name='test-experiment',
            flag=flag,
            status='draft'
        )
        
        result = runner.initialize_experiment(experiment)
        assert result is True
    
    def test_start_experiment(self):
        """Test starting an experiment."""
        runner = ExperimentRunner()
        
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        FlagVariant.objects.create(
            flag=flag,
            name='variant-a',
            value='A',
            weight=50
        )
        
        experiment = Experiment.objects.create(
            name='test-experiment',
            flag=flag,
            status='running',
            start_date=timezone.now()
        )
        
        result = runner.start_experiment(experiment)
        assert result is True
    
    def test_assign_variant(self):
        """Test assigning a variant."""
        runner = ExperimentRunner()
        
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        FlagVariant.objects.create(
            flag=flag,
            name='variant-a',
            value='A',
            weight=50
        )
        
        FlagVariant.objects.create(
            flag=flag,
            name='variant-b',
            value='B',
            weight=50
        )
        
        experiment = Experiment.objects.create(
            name='test-experiment',
            flag=flag,
            status='running',
            start_date=timezone.now()
        )
        
        context = {'user_id': 'user-123'}
        variant = runner.assign_variant('test-experiment', context)
        
        assert variant is not None
        assert variant.name in ['variant-a', 'variant-b']
    
    def test_track_conversion(self):
        """Test tracking conversion."""
        runner = ExperimentRunner()
        
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
        
        experiment = Experiment.objects.create(
            name='test-experiment',
            flag=flag,
            status='running'
        )
        
        from ..models.experiment_participant import ExperimentParticipant
        ExperimentParticipant.objects.create(
            experiment=experiment,
            variant=variant,
            user_id='user-123'
        )
        
        context = {'user_id': 'user-123'}
        result = runner.track_conversion('test-experiment', context)
        
        assert result is True
    
    def test_get_experiment_results(self):
        """Test getting experiment results."""
        runner = ExperimentRunner()
        
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        FlagVariant.objects.create(
            flag=flag,
            name='variant-a',
            value='A',
            weight=50
        )
        
        experiment = Experiment.objects.create(
            name='test-experiment',
            flag=flag,
            status='running'
        )
        
        results = runner.get_experiment_results('test-experiment')
        
        assert 'experiment_name' in results
        assert results['experiment_name'] == 'test-experiment'
    
    def test_get_active_experiments(self):
        """Test getting active experiments."""
        runner = ExperimentRunner()
        
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        Experiment.objects.create(
            name='test-experiment',
            flag=flag,
            status='running',
            start_date=timezone.now()
        )
        
        experiments = runner.get_active_experiments()
        
        assert len(experiments) == 1
        assert experiments[0].name == 'test-experiment'
