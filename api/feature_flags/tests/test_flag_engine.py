"""
Flag Engine tests for Feature Flags & A/B Testing.
"""
import pytest

from ..flag_engine import FlagEngine
from ..models.feature_flag import FeatureFlag


@pytest.mark.django_db
class TestFlagEngine:
    """Tests for FlagEngine."""
    
    def test_is_enabled(self):
        """Test is_enabled method."""
        engine = FlagEngine()
        
        FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            rollout_percentage=100,
            environment='production'
        )
        
        assert engine.is_enabled('test-flag') is True
    
    def test_is_disabled(self):
        """Test is_enabled with disabled flag."""
        engine = FlagEngine()
        
        FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='draft',
            rollout_percentage=100,
            environment='production'
        )
        
        assert engine.is_enabled('test-flag') is False
    
    def test_get_value(self):
        """Test get_value method."""
        engine = FlagEngine()
        
        FeatureFlag.objects.create(
            name='test-flag',
            flag_type='string',
            status='active',
            default_value='default',
            rollout_percentage=100,
            environment='production'
        )
        
        value = engine.get_value('test-flag')
        assert value == 'default'
    
    def test_clear_flag_cache(self):
        """Test clear_flag_cache method."""
        engine = FlagEngine()
        
        FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            rollout_percentage=100,
            environment='production'
        )
        
        engine.clear_flag_cache('test-flag')
        
        # Should not raise any error
        assert True
    
    def test_get_active_flags(self):
        """Test get_active_flags method."""
        engine = FlagEngine()
        
        FeatureFlag.objects.create(
            name='test-flag',
            flag_type='boolean',
            status='active',
            environment='production'
        )
        
        flags = engine.get_active_flags()
        
        assert len(flags) == 1
        assert flags[0].name == 'test-flag'
