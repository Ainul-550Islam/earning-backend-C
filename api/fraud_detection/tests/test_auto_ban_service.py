# =============================================================================
# fraud_detection/tests/test_auto_ban_service.py
# =============================================================================
"""
Auto Ban Service Tests.

Comprehensive tests for automatic banning service including
rule evaluation, ban execution, and appeal processing.
"""

import json
import pytest
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User

from api.fraud_detection.services.AutoBanService import AutoBanService
from api.fraud_detection.models import FraudAttempt, FraudAlert, UserRiskProfile, FraudWhitelist
from api.fraud_detection.choices import FraudAttemptStatus, AlertPriority, WhitelistType
from .factories import (
    UserFactory, FraudAttemptFactory, FraudAlertFactory,
    UserRiskProfileFactory, FraudWhitelistFactory
)


class TestAutoBanService(TestCase):
    """Test cases for AutoBanService."""
    
    def setUp(self):
        """Set up test data."""
        self.auto_ban_service = AutoBanService()
        self.user = UserFactory.create()
        self.staff_user = UserFactory.create(is_staff=True)
        
    def test_evaluate_ban_rules_low_risk(self):
        """Test ban rule evaluation for low risk user."""
        # Create low risk user
        UserRiskProfileFactory.create(
            user=self.user,
            overall_risk_score=25,
            is_flagged=False
        )
        
        # Create minor fraud attempts
        FraudAttemptFactory.create(
            user=self.user,
            fraud_score=30,
            status='reviewing'
        )
        
        result = self.auto_ban_service.evaluate_ban_rules(self.user.id)
        
        self.assertIsInstance(result, dict)
        self.assertIn('should_ban', result)
        self.assertIn('ban_reason', result)
        self.assertIn('risk_score', result)
        self.assertIn('rule_violations', result)
        
        self.assertFalse(result['should_ban'])
        self.assertEqual(result['risk_score'], 25)
    
    def test_evaluate_ban_rules_high_risk(self):
        """Test ban rule evaluation for high risk user."""
        # Create high risk user
        UserRiskProfileFactory.create(
            user=self.user,
            overall_risk_score=85,
            is_flagged=True
        )
        
        # Create serious fraud attempts
        FraudAttemptFactory.create_batch(
            3,
            user=self.user,
            fraud_score=80,
            status='confirmed'
        )
        
        result = self.auto_ban_service.evaluate_ban_rules(self.user.id)
        
        self.assertIsInstance(result, dict)
        self.assertIn('should_ban', result)
        self.assertIn('ban_reason', result)
        self.assertIn('risk_score', result)
        self.assertIn('rule_violations', result)
        
        self.assertTrue(result['should_ban'])
        self.assertGreaterEqual(result['risk_score'], 80)
    
    def test_evaluate_ban_rules_multiple_violations(self):
        """Test ban rule evaluation with multiple violations."""
        # Create user with multiple violations
        risk_profile = UserRiskProfileFactory.create(
            user=self.user,
            overall_risk_score=60,
            is_flagged=True
        )
        
        # Multiple confirmed fraud attempts
        FraudAttemptFactory.create_batch(
            5,
            user=self.user,
            fraud_score=70,
            status='confirmed'
        )
        
        # Create high-value fraud attempts
        FraudAttemptFactory.create(
            user=self.user,
            fraud_score=90,
            amount_involved=1000.00,
            status='confirmed'
        )
        
        result = self.auto_ban_service.evaluate_ban_rules(self.user.id)
        
        self.assertTrue(result['should_ban'])
        
        # Should have multiple rule violations
        rule_violations = result['rule_violations']
        self.assertIsInstance(rule_violations, list)
        self.assertGreater(len(rule_violations), 1)
        
        # Check violation types
        violation_types = [v['type'] for v in rule_violations]
        self.assertIn('high_fraud_score', violation_types)
        self.assertIn('multiple_confirmed_attempts', violation_types)
    
    def test_execute_ban(self):
        """Test ban execution."""
        # Create user with high risk
        UserRiskProfileFactory.create(
            user=self.user,
            overall_risk_score=90,
            is_flagged=True
        )
        
        ban_reason = "High fraud score and multiple confirmed attempts"
        
        result = self.auto_ban_service.execute_ban(
            self.user.id,
            ban_reason,
            banned_by=self.staff_user.id
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        self.assertIn('ban_id', result)
        self.assertIn('banned_at', result)
        self.assertIn('expires_at', result)
        
        self.assertTrue(result['success'])
        
        # Verify user is banned
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        
        # Verify ban record is created
        self.assertIn('ban_id', result)
    
    def test_execute_ban_with_duration(self):
        """Test ban execution with custom duration."""
        UserRiskProfileFactory.create(
            user=self.user,
            overall_risk_score=85,
            is_flagged=True
        )
        
        ban_reason = "Temporary ban for review"
        duration_days = 7
        
        result = self.auto_ban_service.execute_ban(
            self.user.id,
            ban_reason,
            banned_by=self.staff_user.id,
            duration_days=duration_days
        )
        
        self.assertTrue(result['success'])
        
        # Verify expiration date
        expected_expiry = timezone.now() + timedelta(days=duration_days)
        actual_expiry = result['expires_at']
        
        self.assertAlmostEqual(
            expected_expiry.timestamp(),
            actual_expiry.timestamp(),
            delta=60  # Within 1 minute
        )
    
    def test_execute_ban_whitelisted_user(self):
        """Test ban execution for whitelisted user."""
        # Create whitelisted user
        FraudWhitelistFactory.create(
            entity_type='user',
            entity_value=str(self.user.id),
            is_blacklisted=False,
            is_active=True
        )
        
        UserRiskProfileFactory.create(
            user=self.user,
            overall_risk_score=95,
            is_flagged=True
        )
        
        ban_reason = "High fraud score"
        
        result = self.auto_ban_service.execute_ban(
            self.user.id,
            ban_reason,
            banned_by=self.staff_user.id
        )
        
        # Should fail due to whitelist
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('whitelisted', result['error'])
        
        # User should remain active
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
    
    def test_execute_ban_staff_user(self):
        """Test ban execution for staff user."""
        # Create staff user with high risk
        staff_user = UserFactory.create(is_staff=True)
        UserRiskProfileFactory.create(
            user=staff_user,
            overall_risk_score=90,
            is_flagged=True
        )
        
        ban_reason = "High fraud score"
        
        result = self.auto_ban_service.execute_ban(
            staff_user.id,
            ban_reason,
            banned_by=self.staff_user.id
        )
        
        # Should fail due to staff protection
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('staff_user', result['error'])
        
        # Staff user should remain active
        staff_user.refresh_from_db()
        self.assertTrue(staff_user.is_active)
    
    def test_lift_ban(self):
        """Test ban lifting."""
        # First ban the user
        UserRiskProfileFactory.create(
            user=self.user,
            overall_risk_score=90,
            is_flagged=True
        )
        
        ban_result = self.auto_ban_service.execute_ban(
            self.user.id,
            "Test ban",
            banned_by=self.staff_user.id
        )
        
        self.assertTrue(ban_result['success'])
        
        # Now lift the ban
        lift_reason = "Ban reviewed and lifted"
        
        result = self.auto_ban_service.lift_ban(
            self.user.id,
            lift_reason,
            lifted_by=self.staff_user.id
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        self.assertIn('lifted_at', result)
        
        self.assertTrue(result['success'])
        
        # Verify user is active again
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
    
    def test_lift_nonexistent_ban(self):
        """Test lifting ban for user with no active ban."""
        result = self.auto_ban_service.lift_ban(
            self.user.id,
            "Test lift",
            lifted_by=self.staff_user.id
        )
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('no_active_ban', result['error'])
    
    def test_check_ban_status(self):
        """Test ban status checking."""
        # Test non-banned user
        result = self.auto_ban_service.check_ban_status(self.user.id)
        
        self.assertIsInstance(result, dict)
        self.assertIn('is_banned', result)
        self.assertIn('ban_info', result)
        
        self.assertFalse(result['is_banned'])
        self.assertIsNone(result['ban_info'])
        
        # Ban the user
        UserRiskProfileFactory.create(
            user=self.user,
            overall_risk_score=90,
            is_flagged=True
        )
        
        ban_result = self.auto_ban_service.execute_ban(
            self.user.id,
            "Test ban",
            banned_by=self.staff_user.id
        )
        
        # Check banned user
        result = self.auto_ban_service.check_ban_status(self.user.id)
        
        self.assertTrue(result['is_banned'])
        self.assertIsNotNone(result['ban_info'])
        
        ban_info = result['ban_info']
        self.assertIn('ban_id', ban_info)
        self.assertIn('banned_at', ban_info)
        self.assertIn('reason', ban_info)
    
    def test_get_ban_history(self):
        """Test ban history retrieval."""
        # Create multiple bans
        UserRiskProfileFactory.create(
            user=self.user,
            overall_risk_score=85,
            is_flagged=True
        )
        
        # First ban
        ban1 = self.auto_ban_service.execute_ban(
            self.user.id,
            "First ban",
            banned_by=self.staff_user.id,
            duration_days=1
        )
        
        # Wait a bit and lift
        from django.utils import timezone
        import time
        time.sleep(0.1)
        
        self.auto_ban_service.lift_ban(
            self.user.id,
            "First lift",
            lifted_by=self.staff_user.id
        )
        
        # Second ban
        ban2 = self.auto_ban_service.execute_ban(
            self.user.id,
            "Second ban",
            banned_by=self.staff_user.id
        )
        
        # Get history
        history = self.auto_ban_service.get_ban_history(self.user.id)
        
        self.assertIsInstance(history, list)
        self.assertEqual(len(history), 2)
        
        # Verify ban order (most recent first)
        self.assertEqual(history[0]['reason'], "Second ban")
        self.assertEqual(history[1]['reason'], "First ban")
        
        # Verify ban structure
        for ban_record in history:
            self.assertIn('ban_id', ban_record)
            self.assertIn('reason', ban_record)
            self.assertIn('banned_at', ban_record)
            self.assertIn('banned_by', ban_record)
            self.assertIn('status', ban_record)
    
    def test_update_ban_rules(self):
        """Test ban rule updates."""
        new_rules = {
            'max_fraud_score': 80,
            'min_confirmed_attempts': 3,
            'min_risk_score': 70,
            'high_value_threshold': 500.00,
            'staff_protection': True,
            'whitelist_protection': True,
        }
        
        result = self.auto_ban_service.update_ban_rules(new_rules)
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        self.assertIn('updated_rules', result)
        
        self.assertTrue(result['success'])
        
        # Verify rules were updated
        self.assertEqual(result['updated_rules']['max_fraud_score'], 80)
        self.assertEqual(result['updated_rules']['min_confirmed_attempts'], 3)
    
    def test_auto_ban_evaluation(self):
        """Test automatic ban evaluation."""
        # Create user that should be auto-banned
        UserRiskProfileFactory.create(
            user=self.user,
            overall_risk_score=95,
            is_flagged=True
        )
        
        # Create multiple confirmed fraud attempts
        FraudAttemptFactory.create_batch(
            5,
            user=self.user,
            fraud_score=90,
            status='confirmed'
        )
        
        # Auto evaluate
        result = self.auto_ban_service.auto_evaluate_ban(self.user.id)
        
        self.assertIsInstance(result, dict)
        self.assertIn('should_ban', result)
        self.assertIn('auto_banned', result)
        
        # Should recommend ban
        self.assertTrue(result['should_ban'])
    
    def test_auto_ban_execution(self):
        """Test automatic ban execution."""
        # Create user that should be auto-banned
        UserRiskProfileFactory.create(
            user=self.user,
            overall_risk_score=95,
            is_flagged=True
        )
        
        FraudAttemptFactory.create_batch(
            5,
            user=self.user,
            fraud_score=90,
            status='confirmed'
        )
        
        # Auto ban
        result = self.auto_ban_service.auto_ban(
            self.user.id,
            auto_reason="Automatic ban due to high fraud activity"
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        self.assertIn('ban_id', result)
        
        self.assertTrue(result['success'])
        
        # Verify user is banned
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
    
    def test_batch_ban_evaluation(self):
        """Test batch ban evaluation."""
        # Create multiple users
        users = UserFactory.create_batch(5)
        
        # Create mixed risk profiles
        for i, user in enumerate(users):
            risk_score = 50 + (i * 10)  # 50, 60, 70, 80, 90
            UserRiskProfileFactory.create(
                user=user,
                overall_risk_score=risk_score,
                is_flagged=risk_score > 70
            )
            
            # Create fraud attempts based on risk
            attempt_count = max(1, i - 1)
            FraudAttemptFactory.create_batch(
                attempt_count,
                user=user,
                fraud_score=risk_score,
                status='confirmed'
            )
        
        # Batch evaluation
        results = self.auto_ban_service.batch_evaluate_bans([u.id for u in users])
        
        self.assertIsInstance(results, dict)
        self.assertEqual(len(results), 5)
        
        # Should recommend bans for high-risk users
        ban_recommendations = [r for r in results.values() if r['should_ban']]
        self.assertGreater(len(ban_recommendations), 1)
    
    def test_ban_notification(self):
        """Test ban notification creation."""
        # Create user and ban them
        UserRiskProfileFactory.create(
            user=self.user,
            overall_risk_score=90,
            is_flagged=True
        )
        
        ban_result = self.auto_ban_service.execute_ban(
            self.user.id,
            "Test ban with notification",
            banned_by=self.staff_user.id
        )
        
        self.assertTrue(ban_result['success'])
        
        # Check if notification was created
        notifications = FraudAlert.objects.filter(
            user=self.user,
            alert_type='ban_notification'
        )
        
        self.assertGreater(notifications.count(), 0)
    
    def test_ban_appeal_process(self):
        """Test ban appeal process."""
        # Ban the user
        UserRiskProfileFactory.create(
            user=self.user,
            overall_risk_score=85,
            is_flagged=True
        )
        
        ban_result = self.auto_ban_service.execute_ban(
            self.user.id,
            "Test ban for appeal",
            banned_by=self.staff_user.id
        )
        
        self.assertTrue(ban_result['success'])
        
        # Create appeal
        appeal_reason = "Incorrect ban - user activity was legitimate"
        appeal_evidence = {
            'explanation': 'User activity was verified as legitimate',
            'supporting_docs': ['doc1.pdf', 'doc2.pdf'],
        }
        
        result = self.auto_ban_service.create_appeal(
            self.user.id,
            appeal_reason,
            appeal_evidence,
            appealed_by=self.user.id
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        self.assertIn('appeal_id', result)
        
        self.assertTrue(result['success'])
    
    def test_ban_appeal_review(self):
        """Test ban appeal review."""
        # Ban the user
        UserRiskProfileFactory.create(
            user=self.user,
            overall_risk_score=85,
            is_flagged=True
        )
        
        ban_result = self.auto_ban_service.execute_ban(
            self.user.id,
            "Test ban for appeal review",
            banned_by=self.staff_user.id
        )
        
        # Create appeal
        appeal_result = self.auto_ban_service.create_appeal(
            self.user.id,
            "Appeal for review",
            {},
            appealed_by=self.user.id
        )
        
        # Review appeal (approve)
        review_result = self.auto_ban_service.review_appeal(
            appeal_result['appeal_id'],
            approved=True,
            review_notes="Appeal approved - user activity verified",
            reviewed_by=self.staff_user.id
        )
        
        self.assertIsInstance(review_result, dict)
        self.assertIn('success', result)
        self.assertIn('decision', review_result)
        
        self.assertTrue(review_result['success'])
        self.assertEqual(review_result['decision'], 'approved')
        
        # User should be unbanned
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
    
    @patch('fraud_detection.services.AutoBanService.logger')
    def test_error_handling(self, mock_logger):
        """Test error handling in auto ban service."""
        # Test with invalid user ID
        with self.assertRaises(ValueError):
            self.auto_ban_service.evaluate_ban_rules(999999)
        
        # Test ban without proper permissions
        with self.assertRaises(ValueError):
            self.auto_ban_service.execute_ban(
                self.user.id,
                "Test ban",
                banned_by=999999
            )
        
        # Verify error logging
        mock_logger.error.assert_called()
    
    def test_ban_rule_validation(self):
        """Test ban rule validation."""
        # Test invalid rules
        invalid_rules = {
            'max_fraud_score': 150,  # Invalid (> 100)
            'min_confirmed_attempts': -1,  # Invalid (< 0)
            'min_risk_score': 101,  # Invalid (> 100)
        }
        
        with self.assertRaises(ValueError):
            self.auto_ban_service.update_ban_rules(invalid_rules)
    
    def test_performance_with_large_dataset(self):
        """Test performance with large dataset."""
        # Create large number of users
        users = UserFactory.create_batch(100)
        
        for user in users:
            UserRiskProfileFactory.create(
                user=user,
                overall_risk_score=random.randint(20, 90),
                is_flagged=random.choice([True, False])
            )
            
            # Create fraud attempts
            FraudAttemptFactory.create_batch(
                random.randint(0, 10),
                user=user,
                fraud_score=random.randint(30, 95),
                status=random.choice(['confirmed', 'reviewing', 'false_positive'])
            )
        
        # Test batch evaluation performance
        import time
        start_time = time.time()
        
        results = self.auto_ban_service.batch_evaluate_bans([u.id for u in users])
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(processing_time, 10.0)  # 10 seconds max
        self.assertEqual(len(results), 100)


class TestAutoBanServiceIntegration(TestCase):
    """Integration tests for AutoBanService."""
    
    def setUp(self):
        """Set up integration test data."""
        self.auto_ban_service = AutoBanService()
        self.staff_user = UserFactory.create(is_staff=True)
    
    def test_end_to_end_auto_ban_workflow(self):
        """Test end-to-end auto ban workflow."""
        user = UserFactory.create()
        
        # Create high-risk scenario
        UserRiskProfileFactory.create(
            user=user,
            overall_risk_score=95,
            is_flagged=True,
            total_fraud_attempts=8,
            confirmed_fraud_attempts=6
        )
        
        # Create serious fraud attempts
        FraudAttemptFactory.create_batch(
            6,
            user=user,
            fraud_score=90,
            status='confirmed',
            amount_involved=random.uniform(100, 500)
        )
        
        # Create high-value fraud attempt
        FraudAttemptFactory.create(
            user=user,
            fraud_score=95,
            amount_involved=1500.00,
            status='confirmed'
        )
        
        # Auto evaluate ban
        evaluation = self.auto_ban_service.auto_evaluate_ban(user.id)
        
        self.assertTrue(evaluation['should_ban'])
        
        # Execute auto ban
        ban_result = self.auto_ban_service.auto_ban(
            user.id,
            "Automatic ban due to high fraud activity and multiple confirmed attempts"
        )
        
        self.assertTrue(ban_result['success'])
        
        # Verify user is banned
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        
        # Check ban status
        status = self.auto_ban_service.check_ban_status(user.id)
        
        self.assertTrue(status['is_banned'])
        self.assertIsNotNone(status['ban_info'])
        
        # Create and review appeal
        appeal = self.auto_ban_service.create_appeal(
            user.id,
            "User claims activity was legitimate",
            {'explanation': 'User provided verification documents'}
        )
        
        # Appeal review (deny)
        review = self.auto_ban_service.review_appeal(
            appeal['appeal_id'],
            approved=False,
            review_notes="Insufficient evidence to overturn ban",
            reviewed_by=self.staff_user.id
        )
        
        self.assertTrue(review['success'])
        self.assertEqual(review['decision'], 'denied')
        
        # User should remain banned
        user.refresh_from_db()
        self.assertFalse(user.is_active)
    
    def test_batch_auto_ban_processing(self):
        """Test batch auto ban processing."""
        # Create mixed user scenarios
        users = UserFactory.create_batch(20)
        
        high_risk_users = []
        low_risk_users = []
        
        for i, user in enumerate(users):
            if i < 5:  # High risk users
                UserRiskProfileFactory.create(
                    user=user,
                    overall_risk_score=random.randint(80, 95),
                    is_flagged=True
                )
                
                FraudAttemptFactory.create_batch(
                    random.randint(3, 8),
                    user=user,
                    fraud_score=random.randint(70, 95),
                    status='confirmed'
                )
                
                high_risk_users.append(user)
            else:  # Low risk users
                UserRiskProfileFactory.create(
                    user=user,
                    overall_risk_score=random.randint(20, 40),
                    is_flagged=False
                )
                
                FraudAttemptFactory.create_batch(
                    random.randint(0, 2),
                    user=user,
                    fraud_score=random.randint(20, 50),
                    status='false_positive'
                )
                
                low_risk_users.append(user)
        
        # Batch evaluate
        evaluations = self.auto_ban_service.batch_evaluate_bans([u.id for u in users])
        
        # Should recommend bans for high-risk users
        ban_recommendations = [uid for uid, result in evaluations.items() if result['should_ban']]
        
        self.assertGreaterEqual(len(ban_recommendations), len(high_risk_users))
        
        # Execute bans for recommended users
        ban_results = {}
        for user_id in ban_recommendations[:3]:  # Ban first 3 recommended
            result = self.auto_ban_service.auto_ban(
                user_id,
                "Batch auto ban execution"
            )
            ban_results[user_id] = result
        
        # Verify bans
        banned_count = sum(1 for result in ban_results.values() if result['success'])
        self.assertEqual(banned_count, len(ban_results))
        
        # Check final status
        for user_id in ban_results:
            if ban_results[user_id]['success']:
                status = self.auto_ban_service.check_ban_status(user_id)
                self.assertTrue(status['is_banned'])
    
    def test_ban_system_integration_with_fraud_detection(self):
        """Test ban system integration with fraud detection."""
        user = UserFactory.create()
        
        # Create fraud detection scenario
        UserRiskProfileFactory.create(
            user=user,
            overall_risk_score=85,
            is_flagged=True
        )
        
        # Create fraud attempts that trigger alerts
        attempts = FraudAttemptFactory.create_batch(
            4,
            user=user,
            fraud_score=80,
            status='confirmed'
        )
        
        # Create fraud alerts
        for attempt in attempts:
            FraudAlertFactory.create(
                user=user,
                priority='high',
                title=f"Fraud detected: {attempt.id}",
                description="High fraud score detected",
                is_resolved=False
            )
        
        # Auto ban should be triggered by multiple factors
        evaluation = self.auto_ban_service.evaluate_ban_rules(user.id)
        
        self.assertTrue(evaluation['should_ban'])
        
        # Execute ban
        ban_result = self.auto_ban_service.execute_ban(
            user.id,
            "Auto ban triggered by multiple fraud alerts and high risk score",
            banned_by=self.staff_user.id
        )
        
        self.assertTrue(ban_result['success'])
        
        # Verify integration with fraud detection system
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        
        # Check that related fraud alerts are updated
        alerts = FraudAlert.objects.filter(user=user)
        for alert in alerts:
            self.assertFalse(alert.is_resolved)  # Should remain unresolved for manual review


if __name__ == '__main__':
    import random
    
    # Add random import for integration tests
    TestAutoBanServiceIntegration.setUp = lambda self: (
        setattr(self, 'auto_ban_service', AutoBanService()) or
        setattr(self, 'staff_user', UserFactory.create(is_staff=True))
    )
