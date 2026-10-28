"""
Alerting tests for Telemetry Observability.
"""
import pytest
from django.utils import timezone
from datetime import timedelta

from ..services.alert_service import AlertService
from ..alerting import AlertingService, AlertRule


@pytest.mark.django_db
class TestAlertService:
    """Tests for AlertService."""
    
    def test_create_alert(self):
        """Test creating an alert."""
        service = AlertService()
        
        alert = service.create_alert({
            'name': 'test-alert',
            'alert_type': 'metric',
            'severity': 'warning',
            'message': 'Test alert message',
            'source': 'test',
            'service': 'test-service'
        })
        
        assert alert.name == 'test-alert'
        assert alert.alert_type == 'metric'
        assert alert.severity == 'warning'
        assert alert.status == 'open'
    
    def test_acknowledge_alert(self):
        """Test acknowledging an alert."""
        service = AlertService()
        
        alert = service.create_alert({
            'name': 'test-alert',
            'alert_type': 'metric',
            'severity': 'warning',
            'message': 'Test alert message',
            'source': 'test',
            'service': 'test-service'
        })
        
        service.acknowledge_alert(alert.id, 'test-user')
        
        alert.refresh_from_db()
        assert alert.status == 'acknowledged'
        assert alert.acknowledged_by == 'test-user'
    
    def test_resolve_alert(self):
        """Test resolving an alert."""
        service = AlertService()
        
        alert = service.create_alert({
            'name': 'test-alert',
            'alert_type': 'metric',
            'severity': 'warning',
            'message': 'Test alert message',
            'source': 'test',
            'service': 'test-service'
        })
        
        service.resolve_alert(alert.id)
        
        alert.refresh_from_db()
        assert alert.status == 'resolved'
        assert alert.resolved_at is not None
    
    def test_get_open_alerts(self):
        """Test getting open alerts."""
        service = AlertService()
        
        service.create_alert({
            'name': 'alert1',
            'alert_type': 'metric',
            'severity': 'warning',
            'message': 'Test alert 1',
            'source': 'test',
            'service': 'test-service'
        })
        
        service.create_alert({
            'name': 'alert2',
            'alert_type': 'metric',
            'severity': 'critical',
            'message': 'Test alert 2',
            'source': 'test',
            'service': 'test-service'
        })
        
        open_alerts = service.get_open_alerts()
        
        assert len(open_alerts) == 2


@pytest.mark.django_db
class TestAlertingService:
    """Tests for AlertingService."""
    
    def test_create_alert(self):
        """Test creating an alert."""
        service = AlertingService()
        
        alert = service.create_alert(
            name='test-alert',
            alert_type='metric',
            severity='warning',
            message='Test alert message',
            source='test',
            service='test-service'
        )
        
        assert alert.name == 'test-alert'
    
    def test_get_alert_statistics(self):
        """Test getting alert statistics."""
        service = AlertingService()
        
        # Create some alerts
        service.create_alert(
            name='alert1',
            alert_type='metric',
            severity='warning',
            message='Test alert 1',
            source='test',
            service='test-service'
        )
        service.create_alert(
            name='alert2',
            alert_type='metric',
            severity='critical',
            message='Test alert 2',
            source='test',
            service='test-service'
        )
        
        stats = service.get_alert_statistics(hours=24)
        
        assert 'total_alerts' in stats
        assert 'open_alerts' in stats
        assert 'critical_alerts' in stats


@pytest.mark.django_db
class TestAlertRule:
    """Tests for AlertRule."""
    
    def test_create_rule(self):
        """Test creating an alert rule."""
        rule = AlertRule(
            name='test-rule',
            condition={'metric_name': 'test', 'threshold': 100},
            severity='warning'
        )
        
        assert rule.name == 'test-rule'
        assert rule.severity == 'warning'
    
    def test_evaluate_rule(self):
        """Test evaluating an alert rule."""
        rule = AlertRule(
            name='test-rule',
            condition={'metric_name': 'test', 'value': 150},
            severity='warning'
        )
        
        data = {'metric_name': 'test', 'value': 150}
        
        assert rule.evaluate(data) is True
    
    def test_evaluate_rule_with_comparison(self):
        """Test evaluating rule with comparison operator."""
        rule = AlertRule(
            name='test-rule',
            condition={'metric_name': 'test', 'value': {'gt': 100}},
            severity='warning'
        )
        
        data = {'metric_name': 'test', 'value': 150}
        
        assert rule.evaluate(data) is True
