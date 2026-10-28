"""
Service tests for Feature Flags & A/B Testing.
"""
import pytest

from ..services.feature_flag_service import FeatureFlagService
from ..services.experiment_service import ExperimentService
from ..services.rollout_service import RolloutService
from ..services.analytics_service import AnalyticsService
from ..services.variant_assignment_service import VariantAssignmentService


@pytest.mark.django_db
class TestFeatureFlagService:
    """Tests for FeatureFlagService."""
    
    def test_create_flag(self):
        """Test creating a flag."""
        service = FeatureFlagService()
        
        flag = service.create_flag({
            'name': 'test-flag',
            'flag_type': 'boolean',
            'status': 'draft',
            'environment': 'production'
        })
        
        assert flag.name == 'test-flag'
    
    def test_get_flag(self):
        """Test getting a flag."""
        service = FeatureFlagService()
        
        service.create_flag({
            'name': 'test-flag',
            'flag_type': 'boolean',
            'status': 'draft',
            'environment': 'production'
        })
        
        flag = service.get_flag('test-flag')
        
        assert flag is not None
        assert flag.name == 'test-flag'
    
    def test_activate_flag(self):
        """Test activating a flag."""
        service = FeatureFlagService()
        
        service.create_flag({
            'name': 'test-flag',
            'flag_type': 'boolean',
            'status': 'draft',
            'environment': 'production'
        })
        
        service.activate_flag('test-flag')
        
        flag = service.get_flag('test-flag')
        assert flag.status == 'active'

    def test_create_flag_rejects_invalid_rollout(self):
        """NEW: create_flag must validate rollout_percentage (was previously unvalidated)."""
        service = FeatureFlagService()

        with pytest.raises(ValueError):
            service.create_flag({
                'name': 'bad-flag',
                'rollout_percentage': 999,
                'environment': 'production',
            })

    def test_create_flag_rejects_invalid_name(self):
        """NEW: create_flag must validate the name format (was previously unvalidated)."""
        service = FeatureFlagService()

        with pytest.raises(ValueError):
            service.create_flag({
                'name': 'bad flag name',
                'environment': 'production',
            })

    def test_create_flag_rejects_duplicate_name_in_environment(self):
        """NEW: create_flag must reject duplicate (name, environment) pairs."""
        service = FeatureFlagService()
        service.create_flag({'name': 'dup-flag', 'environment': 'production'})

        with pytest.raises(ValueError):
            service.create_flag({'name': 'dup-flag', 'environment': 'production'})

    def test_create_flag_allows_same_name_different_environment(self):
        """NEW: multi-environment support — same name, different environment, is allowed."""
        service = FeatureFlagService()
        service.create_flag({'name': 'multi-env-flag', 'environment': 'staging'})
        prod_flag = service.create_flag({'name': 'multi-env-flag', 'environment': 'production'})

        assert prod_flag.environment == 'production'

    def test_restore_flag(self):
        """NEW: restore_flag brings an archived flag back to draft."""
        service = FeatureFlagService()
        service.create_flag({'name': 'restorable-flag', 'status': 'active', 'environment': 'production'})
        service.archive_flag('restorable-flag')

        assert service.get_flag('restorable-flag').status == 'archived'

        service.restore_flag('restorable-flag')

        assert service.get_flag('restorable-flag').status == 'draft'

    def test_clone_flag_copies_fields_and_variants(self):
        """NEW: clone_flag duplicates a flag's fields and variants under a new name."""
        from ..models.flag_variant import FlagVariant

        service = FeatureFlagService()
        source = service.create_flag({
            'name': 'source-flag',
            'status': 'active',
            'rollout_percentage': 80,
            'environment': 'production',
            'description': 'original description',
        })
        FlagVariant.objects.create(flag=source, name='control', weight=50, value='A')
        FlagVariant.objects.create(flag=source, name='treatment', weight=50, value='B')

        clone = service.clone_flag('source-flag', 'cloned-flag', 'production')

        assert clone.name == 'cloned-flag'
        # Clones always start safe: draft + 0% rollout, regardless of source state.
        assert clone.status == 'draft'
        assert clone.rollout_percentage == 0
        assert FlagVariant.objects.filter(flag=clone).count() == 2
        assert set(FlagVariant.objects.filter(flag=clone).values_list('name', flat=True)) == {'control', 'treatment'}

    def test_clone_flag_raises_for_missing_source(self):
        """NEW: clone_flag raises FlagNotFoundError when the source doesn't exist."""
        from ..exceptions import FlagNotFoundError

        service = FeatureFlagService()
        with pytest.raises(FlagNotFoundError):
            service.clone_flag('does-not-exist', 'new-name', 'production')

    def test_clone_flag_raises_for_duplicate_new_name(self):
        """NEW: clone_flag raises ValueError if new_name is already taken."""
        service = FeatureFlagService()
        service.create_flag({'name': 'source-flag-2', 'environment': 'production'})
        service.create_flag({'name': 'taken-name', 'environment': 'production'})

        with pytest.raises(ValueError):
            service.clone_flag('source-flag-2', 'taken-name', 'production')


@pytest.mark.django_db
class TestFlagEngine:
    """
    Tests for FlagEngine, used directly.

    FIX: `FlagEngineService` was deleted as a DRY violation (100%
    redundant wrapper around `FlagEngine.is_enabled()`/`.get_value()`,
    and it carried its own copy of the `cache.keys()` bug that has been
    fixed in `flag_engine.py`/`utils/cache_manager.py`). These tests
    exercise `FlagEngine` directly instead.
    """

    def test_evaluate_flag_enabled(self):
        """Test evaluating an enabled flag."""
        from ..flag_engine import FlagEngine
        engine = FlagEngine()

        from ..models.feature_flag import FeatureFlag
        FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            rollout_percentage=100,
            environment='production'
        )

        assert engine.is_enabled('test-flag', environment='production') is True

    def test_evaluate_flag_disabled_when_draft(self):
        """A draft-status flag is never enabled, regardless of rollout percentage."""
        from ..flag_engine import FlagEngine
        engine = FlagEngine()

        from ..models.feature_flag import FeatureFlag
        FeatureFlag.objects.create(
            name='draft-flag',
            flag_type='boolean',
            status='draft',
            rollout_percentage=100,
            environment='production'
        )

        assert engine.is_enabled('draft-flag', environment='production') is False

    def test_clear_all_cache_does_not_raise(self):
        """
        FIX: `clear_all_cache()` used to call `cache.delete_many(cache.keys(...))`,
        which raised AttributeError on Django's default LocMemCache backend
        (cache.keys() is a django-redis-only extension). It must now succeed
        on any configured cache backend.
        """
        from ..flag_engine import FlagEngine
        engine = FlagEngine()
        engine.clear_all_cache()  # should not raise


@pytest.mark.django_db
class TestExperimentService:
    """Tests for ExperimentService."""
    
    def test_create_experiment(self):
        """Test creating an experiment."""
        service = ExperimentService()
        
        from ..models.feature_flag import FeatureFlag
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        experiment = service.create_experiment({
            'name': 'test-experiment',
            'flag': flag.id,
            'status': 'draft'
        })
        
        assert experiment.name == 'test-experiment'
    
    def test_start_experiment(self):
        """Test starting an experiment."""
        service = ExperimentService()
        
        from ..models.feature_flag import FeatureFlag
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        service.create_experiment({
            'name': 'test-experiment',
            'flag': flag.id,
            'status': 'draft'
        })
        
        service.start_experiment('test-experiment')
        
        experiment = service.get_experiment('test-experiment')
        assert experiment.status == 'running'


@pytest.mark.django_db
class TestRolloutService:
    """Tests for RolloutService."""
    
    def test_create_rule(self):
        """Test creating a rollout rule."""
        service = RolloutService()
        
        from ..models.feature_flag import FeatureFlag
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        rule = service.create_rule({
            'flag': flag.id,
            'rule_type': 'user_id',
            'field': 'user_id',
            'operator': 'equals',
            'value': 'user-123'
        })
        
        assert rule.rule_type == 'user_id'
    
    def test_activate_rule(self):
        """Test activating a rule."""
        service = RolloutService()
        
        from ..models.feature_flag import FeatureFlag
        flag = FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        service.create_rule({
            'flag': flag.id,
            'rule_type': 'user_id',
            'field': 'user_id',
            'operator': 'equals',
            'value': 'user-123',
            'is_active': False
        })
        
        rules = service.get_rules(flag_id=flag.id)
        service.activate_rule(rules[0].id)
        
        rule = service.get_rule(rules[0].id)
        assert rule.is_active is True


@pytest.mark.django_db
class TestAnalyticsService:
    """Tests for AnalyticsService."""
    
    def test_get_flag_analytics(self):
        """Test getting flag analytics."""
        service = AnalyticsService()
        
        from ..models.feature_flag import FeatureFlag
        FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        analytics = service.get_flag_analytics('test-flag', days=7)
        
        assert 'flag_name' in analytics
        assert analytics['flag_name'] == 'test-flag'


@pytest.mark.django_db
class TestVariantAssignmentService:
    """Tests for VariantAssignmentService."""
    
    def test_assign_variant_for_flag(self):
        """Test assigning variant for flag."""
        service = VariantAssignmentService()
        
        from ..models.feature_flag import FeatureFlag
        from ..models.flag_variant import FlagVariant
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
            weight=100
        )
        
        context = {'user_id': 'user-123'}
        variant = service.assign_variant_for_flag('test-flag', context)
        
        assert variant is not None
        assert variant.name == 'variant-a'
