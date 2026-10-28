# Reconstructed from services/FIX_ALL_PART1_Services5-10.py (was never split into
# individual files, leaving alerts.services unimportable — see audit).
# Fixed on extraction: AlertNotification -> Notification (real model name),
# api.alerts.utils.* -> real existing module paths.

import logging

logger = logging.getLogger(__name__)


class TestingService:
    """
    Consolidates alert testing logic.
    Eliminates duplicates from: views.py + tasks/core.py
    """
    __test__ = False  # not a pytest test class - see audit notes (name collision
    # with pytest's Test*/test_* discovery convention; methods are business logic)

    @staticmethod
    def test_alert_rule(rule):
        """
        Test an alert rule.
        
        Previously duplicated in:
        - alerts/views.py
        - alerts/tasks/core.py
        
        Args:
            rule: AlertRule instance
            
        Returns:
            dict: Test results
        """
        logger.info(f"Testing alert rule {rule.id}")
        
        test_results = {
            'rule_id': rule.id,
            'rule_name': rule.name,
            'tests': []
        }
        
        # Test 1: Rule is active
        test_results['tests'].append({
            'name': 'Rule is active',
            'passed': rule.is_active
        })
        
        # Test 2: Has recipients
        recipients = rule.get_recipients()
        test_results['tests'].append({
            'name': 'Has recipients',
            'passed': len(recipients) > 0,
            'recipient_count': len(recipients)
        })
        
        # Test 3: Has valid condition
        try:
            rule.evaluate_condition()
            test_results['tests'].append({
                'name': 'Condition is valid',
                'passed': True
            })
        except Exception as e:
            test_results['tests'].append({
                'name': 'Condition is valid',
                'passed': False,
                'error': str(e)
            })
        
        # Test 4: Has notification channels
        from api.alerts.models import AlertChannel
        enabled_types = [
            t for t, flag in [('email', rule.send_email), ('telegram', rule.send_telegram),
                               ('sms', rule.send_sms), ('webhook', rule.send_webhook)] if flag
        ]
        channels = AlertChannel.objects.filter(channel_type__in=enabled_types, is_enabled=True)
        test_results['tests'].append({
            'name': 'Has notification channels',
            'passed': channels.count() > 0,
            'channel_count': channels.count()
        })
        
        # Test 5: Can send test notification
        try:
            # Create test notification
            test_passed = TestingService._send_test_notification(rule, recipients[0] if recipients else None)
            test_results['tests'].append({
                'name': 'Can send test notification',
                'passed': test_passed
            })
        except Exception as e:
            test_results['tests'].append({
                'name': 'Can send test notification',
                'passed': False,
                'error': str(e)
            })
        
        # Calculate overall result
        passed_tests = sum(1 for t in test_results['tests'] if t['passed'])
        total_tests = len(test_results['tests'])
        test_results['passed'] = passed_tests
        test_results['total'] = total_tests
        test_results['success'] = passed_tests == total_tests
        
        logger.info(f"Rule test complete: {passed_tests}/{total_tests} tests passed")
        
        return test_results

    @staticmethod
    def _send_test_notification(rule, recipient):
        """Send a test notification"""
        from api.alerts.models import Notification
        from api.alerts.services.notification import NotificationService
        
        try:
            # Create test notification
            test_notification = Notification.objects.create(
                alert_log=None,  # No real alert
                recipient=recipient,
                notification_type='test'
            )
            
            # Send it
            NotificationService.send_notification(test_notification)
            
            return True
        except:
            return False

    @staticmethod
    def test_alert_channel(channel):
        """Test an alert channel"""
        logger.info(f"Testing alert channel {channel.id}")
        
        test_results = {
            'channel_id': channel.id,
            'channel_name': channel.name,
            'channel_type': channel.channel_type,
            'tests': []
        }
        
        # Test 1: Channel is active
        test_results['tests'].append({
            'name': 'Channel is active',
            'passed': channel.is_enabled
        })
        
        # Test 2: Has configuration
        test_results['tests'].append({
            'name': 'Has configuration',
            'passed': bool(channel.config)
        })
        
        # Test 3: Can connect
        try:
            can_connect = channel.test_connection()
            test_results['tests'].append({
                'name': 'Can connect',
                'passed': can_connect
            })
        except Exception as e:
            test_results['tests'].append({
                'name': 'Can connect',
                'passed': False,
                'error': str(e)
            })
        
        # Calculate results
        passed_tests = sum(1 for t in test_results['tests'] if t['passed'])
        test_results['passed'] = passed_tests
        test_results['total'] = len(test_results['tests'])
        test_results['success'] = passed_tests == len(test_results['tests'])
        
        return test_results


__all__ = ['TestingService']
