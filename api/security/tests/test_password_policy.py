"""
Enhanced Password Policy Tests
Comprehensive test suite for password policy functionality
Author: System Security Team
Version: 2.0.0
"""
from datetime import timedelta

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from rest_framework.test import APITestCase

from ..services.PasswordHistoryService import PasswordHistoryService
from .factories import (
    UserFactory, StaffUserFactory, PasswordHistoryFactory,
    SecurityLogFactory, SecurityPolicyFactory
)


class PasswordHistoryServiceTest(TestCase):
    """Test PasswordHistoryService class"""
    
    def setUp(self):
        self.service = PasswordHistoryService()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        cache.clear()
    
    def test_password_history_service_initialization(self):
        """Test PasswordHistoryService initialization"""
        self.assertIsNotNone(self.service.cache_manager)
        self.assertIsNotNone(self.service.logger)
        self.assertIsNotNone(self.service.default_password_history_limit)
        self.assertIsNotNone(self.service.default_password_lifetime_days)
    
    def test_password_history_service_default_config(self):
        """Test default configuration"""
        self.assertEqual(self.service.default_password_history_limit, 12)
        self.assertEqual(self.service.default_password_lifetime_days, 90)
    
    def test_record_password_change(self):
        """Test recording password change"""
        password_data = {
            'password_hash': 'hashed_password_123',
            'password_algorithm': 'bcrypt',
            'salt': 'salt_value_456',
            'ip_address': '192.168.1.100',
            'user_agent': 'TestAgent/1.0'
        }
        
        with patch('api.security.models.PasswordHistory.objects.create') as mock_create:
            mock_password_history = MagicMock()
            mock_password_history.id = 'password-history-id'
            mock_create.return_value = mock_password_history
            
            result = self.service.record_password_change(
                self.user,
                **password_data
            )
            
            self.assertEqual(result, mock_password_history)
            mock_create.assert_called_once()
            
            # Check call arguments
            call_args = mock_create.call_args[1]
            self.assertEqual(call_args['user'], self.user)
            self.assertEqual(call_args['password_hash'], 'hashed_password_123')
            self.assertEqual(call_args['password_algorithm'], 'bcrypt')
            self.assertEqual(call_args['salt'], 'salt_value_456')
            self.assertFalse(call_args['is_active'])
    
    def test_record_password_change_with_metadata(self):
        """Test recording password change with metadata"""
        password_data = {
            'password_hash': 'hashed_password_123',
            'password_algorithm': 'bcrypt',
            'salt': 'salt_value_456',
            'metadata': {
                'change_reason': 'user_request',
                'admin_initiated': False,
                'previous_password_age_days': 45
            }
        }
        
        with patch('api.security.models.PasswordHistory.objects.create') as mock_create:
            mock_password_history = MagicMock()
            mock_password_history.id = 'password-history-id'
            mock_create.return_value = mock_password_history
            
            result = self.service.record_password_change(
                self.user,
                **password_data
            )
            
            self.assertEqual(result, mock_password_history)
            call_args = mock_create.call_args[1]
            self.assertIn('change_reason', call_args['metadata'])
            self.assertIn('previous_password_age_days', call_args['metadata'])
    
    def test_get_password_history(self):
        """Test getting password history"""
        with patch('api.security.models.PasswordHistory.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 5
            mock_queryset.order_by.return_value = [
                PasswordHistoryFactory(user=self.user),
                PasswordHistoryFactory(user=self.user)
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_password_history(
                self.user.id,
                limit=10
            )
            
            self.assertEqual(result['count'], 5)
            self.assertEqual(len(result['history']), 2)
            mock_filter.assert_called_once_with(user=self.user)
    
    def test_get_password_history_with_limit(self):
        """Test getting password history with limit"""
        with patch('api.security.models.PasswordHistory.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 15
            mock_queryset.order_by.return_value = [MagicMock() for _ in range(10)]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_password_history(
                self.user.id,
                limit=10
            )
            
            self.assertEqual(result['count'], 15)
            self.assertEqual(len(result['history']), 10)
    
    def test_get_password_history_include_inactive(self):
        """Test getting password history including inactive"""
        with patch('api.security.models.PasswordHistory.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 8
            mock_queryset.order_by.return_value = [MagicMock() for _ in range(5)]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_password_history(
                self.user.id,
                include_inactive=True
            )
            
            self.assertEqual(result['count'], 8)
            self.assertEqual(len(result['history']), 5)
            mock_filter.assert_called_once_with(user=self.user)
    
    def test_check_password_reuse(self):
        """Test checking password reuse"""
        password_hash = 'hashed_password_123'
        
        with patch.object(self.service, '_check_password_against_history') as mock_check:
            mock_check.return_value = {
                'is_reused': False,
                'reused_count': 0,
                'last_used': None
            }
            
            result = self.service.check_password_reuse(
                self.user.id,
                password_hash
            )
            
            self.assertFalse(result['is_reused'])
            self.assertEqual(result['reused_count'], 0)
            mock_check.assert_called_once_with(self.user.id, password_hash)
    
    def test_check_password_reuse_reused_password(self):
        """Test checking password reuse with reused password"""
        password_hash = 'hashed_password_123'
        
        with patch.object(self.service, '_check_password_against_history') as mock_check:
            mock_check.return_value = {
                'is_reused': True,
                'reused_count': 2,
                'last_used': timezone.now() - timedelta(days=30)
            }
            
            result = self.service.check_password_reuse(
                self.user.id,
                password_hash
            )
            
            self.assertTrue(result['is_reused'])
            self.assertEqual(result['reused_count'], 2)
            self.assertIsNotNone(result['last_used'])
    
    def test_check_password_against_history(self):
        """Test checking password against history"""
        password_hash = 'hashed_password_123'
        
        with patch('api.security.models.PasswordHistory.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 0  # No matches
            mock_filter.return_value = mock_queryset
            
            result = self.service._check_password_against_history(
                self.user.id,
                password_hash
            )
            
            self.assertFalse(result['is_reused'])
            self.assertEqual(result['reused_count'], 0)
    
    def test_check_password_against_history_with_matches(self):
        """Test checking password against history with matches"""
        password_hash = 'hashed_password_123'
        
        with patch('api.security.models.PasswordHistory.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 2  # Found 2 matches
            mock_queryset.order_by.return_value = [
                MagicMock(created_at=timezone.now() - timedelta(days=30)),
                MagicMock(created_at=timezone.now() - timedelta(days=60))
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service._check_password_against_history(
                self.user.id,
                password_hash
            )
            
            self.assertTrue(result['is_reused'])
            self.assertEqual(result['reused_count'], 2)
            self.assertIsNotNone(result['last_used'])
    
    def test_check_password_strength(self):
        """Test checking password strength"""
        password = 'StrongP@ssw0rd123!'
        
        result = self.service.check_password_strength(password)
        
        self.assertIn('strength_score', result)
        self.assertIn('strength_level', result)
        self.assertIn('feedback', result)
        self.assertIn('suggestions', result)
    
    def test_check_password_strength_weak_password(self):
        """Test checking password strength for weak password"""
        password = 'weak'
        
        result = self.service.check_password_strength(password)
        
        self.assertLess(result['strength_score'], 30)
        self.assertEqual(result['strength_level'], 'weak')
        self.assertGreater(len(result['feedback']), 0)
    
    def test_check_password_strength_strong_password(self):
        """Test checking password strength for strong password"""
        password = 'VeryStr0ngP@ssw0rd!WithNumbers123'
        
        result = self.service.check_password_strength(password)
        
        self.assertGreater(result['strength_score'], 80)
        self.assertEqual(result['strength_level'], 'strong')
    
    def test_calculate_password_strength_score(self):
        """Test calculating password strength score"""
        # Test various password characteristics
        test_cases = [
            ('weak', 10),
            ('password', 20),
            ('Password123', 40),
            ('Password123!', 60),
            ('StrongP@ssw0rd!', 80),
            ('VeryStr0ngP@ssw0rd!123', 90)
        ]
        
        for password, expected_range in test_cases:
            score = self.service._calculate_password_strength_score(password)
            self.assertGreaterEqual(score, expected_range - 10)
            self.assertLessEqual(score, expected_range + 10)
    
    def test_get_password_policy(self):
        """Test getting password policy"""
        with patch('api.security.models.SecurityPolicy.objects.filter') as mock_filter:
            mock_policy = MagicMock()
            mock_policy.policy_value = {
                'min_length': 8,
                'require_uppercase': True,
                'require_lowercase': True,
                'require_numbers': True,
                'require_special_chars': True,
                'prevent_reuse': True,
                'reuse_limit': 12,
                'max_age_days': 90
            }
            mock_filter.return_value.first.return_value = mock_policy
            
            result = self.service.get_password_policy(self.user.id)
            
            self.assertEqual(result['min_length'], 8)
            self.assertTrue(result['require_uppercase'])
            self.assertEqual(result['reuse_limit'], 12)
    
    def test_get_password_policy_default(self):
        """Test getting default password policy"""
        with patch('api.security.models.SecurityPolicy.objects.filter') as mock_filter:
            mock_filter.return_value.first.return_value = None
            
            result = self.service.get_password_policy(self.user.id)
            
            # Should return default policy
            self.assertIn('min_length', result)
            self.assertIn('require_uppercase', result)
            self.assertIn('prevent_reuse', result)
    
    def test_validate_password_against_policy(self):
        """Test validating password against policy"""
        password = 'StrongP@ssw0rd!'
        policy = {
            'min_length': 8,
            'require_uppercase': True,
            'require_lowercase': True,
            'require_numbers': True,
            'require_special_chars': True,
            'prevent_reuse': True,
            'reuse_limit': 12
        }
        
        with patch.object(self.service, 'check_password_reuse') as mock_reuse:
            mock_reuse.return_value = {'is_reused': False}
            
            result = self.service.validate_password_against_policy(
                self.user.id,
                password,
                policy
            )
            
            self.assertTrue(result['is_valid'])
            self.assertEqual(len(result['violations']), 0)
    
    def test_validate_password_against_policy_violations(self):
        """Test validating password against policy with violations"""
        password = 'weak'  # Too short, no required characters
        policy = {
            'min_length': 8,
            'require_uppercase': True,
            'require_lowercase': True,
            'require_numbers': True,
            'require_special_chars': True
        }
        
        result = self.service.validate_password_against_policy(
            self.user.id,
            password,
            policy
        )
        
        self.assertFalse(result['is_valid'])
        self.assertGreater(len(result['violations']), 0)
    
    def test_validate_password_against_policy_reuse_violation(self):
        """Test validating password against policy with reuse violation"""
        password = 'StrongP@ssw0rd!'
        policy = {
            'min_length': 8,
            'require_uppercase': True,
            'require_lowercase': True,
            'require_numbers': True,
            'require_special_chars': True,
            'prevent_reuse': True,
            'reuse_limit': 12
        }
        
        with patch.object(self.service, 'check_password_reuse') as mock_reuse:
            mock_reuse.return_value = {'is_reused': True, 'reused_count': 2}
            
            result = self.service.validate_password_against_policy(
                self.user.id,
                password,
                policy
            )
            
            self.assertFalse(result['is_valid'])
            self.assertIn('password_reuse', [v['type'] for v in result['violations']])
    
    def test_get_password_age(self):
        """Test getting password age"""
        with patch.object(self.service, '_get_last_password_change') as mock_last_change:
            mock_last_change.return_value = timezone.now() - timedelta(days=45)
            
            result = self.service.get_password_age(self.user.id)
            
            self.assertEqual(result['age_days'], 45)
            self.assertIn('last_changed', result)
    
    def test_get_password_age_no_history(self):
        """Test getting password age with no history"""
        with patch.object(self.service, '_get_last_password_change') as mock_last_change:
            mock_last_change.return_value = None
            
            result = self.service.get_password_age(self.user.id)
            
            self.assertIsNone(result['age_days'])
            self.assertIsNone(result['last_changed'])
    
    def test_get_last_password_change(self):
        """Test getting last password change"""
        with patch('api.security.models.PasswordHistory.objects.filter') as mock_filter:
            mock_password_history = PasswordHistoryFactory(
                user=self.user,
                created_at=timezone.now() - timedelta(days=30)
            )
            mock_queryset = MagicMock()
            mock_queryset.first.return_value = mock_password_history
            mock_filter.return_value = mock_queryset
            
            result = self.service._get_last_password_change(self.user.id)
            
            self.assertEqual(result, mock_password_history)
            mock_filter.assert_called_once_with(user=self.user)
    
    def test_check_password_expiration(self):
        """Test checking password expiration"""
        with patch.object(self.service, 'get_password_age') as mock_age:
            mock_age.return_value = {'age_days': 85}
            
            policy = {'max_age_days': 90}
            
            result = self.service.check_password_expiration(
                self.user.id,
                policy
            )
            
            self.assertFalse(result['is_expired'])
            self.assertEqual(result['days_until_expiration'], 5)
            self.assertEqual(result['expiration_percentage'], 94.4)
    
    def test_check_password_expiration_expired(self):
        """Test checking password expiration for expired password"""
        with patch.object(self.service, 'get_password_age') as mock_age:
            mock_age.return_value = {'age_days': 95}
            
            policy = {'max_age_days': 90}
            
            result = self.service.check_password_expiration(
                self.user.id,
                policy
            )
            
            self.assertTrue(result['is_expired'])
            self.assertEqual(result['days_until_expiration'], -5)
            self.assertEqual(result['expiration_percentage'], 105.6)
    
    def test_check_password_expiration_no_policy(self):
        """Test checking password expiration with no policy"""
        with patch.object(self.service, 'get_password_age') as mock_age:
            mock_age.return_value = {'age_days': 45}
            
            result = self.service.check_password_expiration(self.user.id)
            
            self.assertFalse(result['is_expired'])
            self.assertIsNone(result['days_until_expiration'])
    
    def test_get_password_compliance_status(self):
        """Test getting password compliance status"""
        with patch.object(self.service, 'get_password_policy') as mock_policy:
            mock_policy.return_value = {
                'min_length': 8,
                'require_uppercase': True,
                'require_lowercase': True,
                'require_numbers': True,
                'require_special_chars': True,
                'prevent_reuse': True,
                'reuse_limit': 12,
                'max_age_days': 90
            }
            
            with patch.object(self.service, 'get_password_age') as mock_age:
                mock_age.return_value = {'age_days': 45}
                
                result = self.service.get_password_compliance_status(self.user.id)
                
                self.assertIn('policy_compliance', result)
                self.assertIn('age_compliance', result)
                self.assertIn('overall_compliance', result)
    
    def test_get_password_compliance_status_non_compliant(self):
        """Test getting password compliance status for non-compliant password"""
        with patch.object(self.service, 'get_password_policy') as mock_policy:
            mock_policy.return_value = {
                'min_length': 12,
                'max_age_days': 60
            }
            
            with patch.object(self.service, 'get_password_age') as mock_age:
                mock_age.return_value = {'age_days': 75}  # Over limit
                
                result = self.service.get_password_compliance_status(self.user.id)
                
                self.assertFalse(result['overall_compliance'])
                self.assertFalse(result['age_compliance'])
    
    def test_cleanup_old_password_history(self):
        """Test cleaning up old password history"""
        # Create old password history entries
        old_entries = PasswordHistoryFactory.create_batch(
            5,
            user=self.user,
            created_at=timezone.now() - timedelta(days=400)
        )
        
        with patch('api.security.models.PasswordHistory.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 5
            mock_queryset.delete.return_value = (5, {'api.security.PasswordHistory': 5})
            mock_filter.return_value = mock_queryset
            
            result = self.service.cleanup_old_password_history(days=365)
            
            self.assertEqual(result['deleted_count'], 5)
            mock_filter.assert_called_once()
    
    def test_cleanup_old_password_history_by_user(self):
        """Test cleaning up old password history for specific user"""
        # Create old password history entries for user
        old_entries = PasswordHistoryFactory.create_batch(
            3,
            user=self.user,
            created_at=timezone.now() - timedelta(days=200)
        )
        
        with patch('api.security.models.PasswordHistory.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 3
            mock_queryset.delete.return_value = (3, {'api.security.PasswordHistory': 3})
            mock_filter.return_value = mock_queryset
            
            result = self.service.cleanup_old_password_history(
                days=180,
                user_id=self.user.id
            )
            
            self.assertEqual(result['deleted_count'], 3)
            mock_filter.assert_called_once()
    
    def test_export_password_history(self):
        """Test exporting password history"""
        with patch('api.security.models.PasswordHistory.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.values.return_value = [
                {
                    'id': 'history-1',
                    'user_id': self.user.id,
                    'password_algorithm': 'bcrypt',
                    'created_at': timezone.now(),
                    'expires_at': timezone.now() + timedelta(days=90)
                },
                {
                    'id': 'history-2',
                    'user_id': self.user.id,
                    'password_algorithm': 'pbkdf2',
                    'created_at': timezone.now() - timedelta(days=30),
                    'expires_at': timezone.now() + timedelta(days=60)
                }
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.export_password_history(
                user_id=self.user.id,
                format='json'
            )
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['password_algorithm'], 'bcrypt')
            self.assertEqual(result[1]['password_algorithm'], 'pbkdf2')
    
    def test_export_password_history_csv(self):
        """Test exporting password history in CSV format"""
        with patch('api.security.models.PasswordHistory.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.values.return_value = [
                {
                    'id': 'history-1',
                    'user_id': self.user.id,
                    'password_algorithm': 'bcrypt',
                    'created_at': timezone.now()
                }
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.export_password_history(
                user_id=self.user.id,
                format='csv'
            )
            
            self.assertIn('id', result)
            self.assertIn('history-1', result)
    
    def test_get_password_statistics(self):
        """Test getting password statistics"""
        with patch('api.security.models.PasswordHistory.objects') as mock_model:
            mock_model.objects.count.return_value = 1000
            mock_model.objects.filter.return_value.count.return_value = 250
            
            with patch.object(self.service, '_calculate_password_algorithm_distribution') as mock_dist:
                mock_dist.return_value = {
                    'bcrypt': 600,
                    'pbkdf2': 300,
                    'argon2': 100
                }
                
                result = self.service.get_password_statistics()
                
                self.assertEqual(result['total_password_changes'], 1000)
                self.assertEqual(result['active_passwords'], 250)
                self.assertIn('algorithm_distribution', result)
    
    def test_calculate_password_algorithm_distribution(self):
        """Test calculating password algorithm distribution"""
        with patch('api.security.models.PasswordHistory.objects') as mock_model:
            mock_model.objects.values.return_value.annotate.return_value = [
                {'password_algorithm': 'bcrypt', 'count': 600},
                {'password_algorithm': 'pbkdf2', 'count': 300},
                {'password_algorithm': 'argon2', 'count': 100}
            ]
            
            distribution = self.service._calculate_password_algorithm_distribution()
            
            self.assertEqual(distribution['bcrypt'], 600)
            self.assertEqual(distribution['pbkdf2'], 300)
            self.assertEqual(distribution['argon2'], 100)
    
    def test_get_password_change_trends(self):
        """Test getting password change trends"""
        with patch.object(self.service, '_calculate_password_change_trends') as mock_trends:
            mock_trends.return_value = [
                {
                    'date': '2023-01-01',
                    'changes': 25,
                    'unique_users': 20
                },
                {
                    'date': '2023-01-02',
                    'changes': 30,
                    'unique_users': 25
                }
            ]
            
            result = self.service.get_password_change_trends(days=30)
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['changes'], 25)
            self.assertEqual(result[1]['unique_users'], 25)
    
    def test_calculate_password_change_trends(self):
        """Test calculating password change trends"""
        with patch('api.security.models.PasswordHistory.objects') as mock_model:
            mock_model.objects.extra.return_value = [
                {'date': '2023-01-01', 'changes': 25, 'unique_users': 20},
                {'date': '2023-01-02', 'changes': 30, 'unique_users': 25}
            ]
            
            trends = self.service._calculate_password_change_trends(days=30)
            
            self.assertEqual(len(trends), 2)
            self.assertEqual(trends[0]['changes'], 25)
            self.assertEqual(trends[0]['unique_users'], 20)
    
    def test_get_password_strength_distribution(self):
        """Test getting password strength distribution"""
        with patch.object(self.service, '_calculate_strength_distribution') as mock_distribution:
            mock_distribution.return_value = {
                'weak': 10,
                'fair': 20,
                'good': 40,
                'strong': 25,
                'very_strong': 5
            }
            
            result = self.service.get_password_strength_distribution()
            
            self.assertEqual(result['weak'], 10)
            self.assertEqual(result['strong'], 25)
            self.assertEqual(result['very_strong'], 5)
    
    def test_calculate_strength_distribution(self):
        """Test calculating password strength distribution"""
        # This would require actual password data from recent changes
        # For testing, we'll mock the calculation
        with patch('api.security.models.PasswordHistory.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 100
            mock_filter.return_value = mock_queryset
            
            distribution = self.service._calculate_strength_distribution()
            
            self.assertIn('weak', distribution)
            self.assertIn('fair', distribution)
            self.assertIn('good', distribution)
            self.assertIn('strong', distribution)
            self.assertIn('very_strong', distribution)
    
    def test_get_password_policy_compliance_report(self):
        """Test getting password policy compliance report"""
        with patch.object(self.service, '_generate_compliance_report') as mock_report:
            mock_report.return_value = {
                'total_users': 1000,
                'compliant_users': 850,
                'non_compliant_users': 150,
                'compliance_rate': 85.0,
                'common_violations': [
                    {'violation': 'password_too_short', 'count': 50},
                    {'violation': 'password_no_uppercase', 'count': 30},
                    {'violation': 'password_expired', 'count': 40}
                ],
                'recommendations': [
                    'Enforce stronger password policies',
                    'Implement password expiration reminders'
                ]
            }
            
            result = self.service.get_password_policy_compliance_report()
            
            self.assertEqual(result['total_users'], 1000)
            self.assertEqual(result['compliance_rate'], 85.0)
            self.assertEqual(len(result['common_violations']), 3)
    
    def test_generate_compliance_report(self):
        """Test generating compliance report"""
        with patch('api.security.models.User.objects') as mock_user_model:
            mock_user_model.objects.count.return_value = 1000
            
            with patch.object(self.service, '_analyze_compliance_violations') as mock_violations:
                mock_violations.return_value = [
                    {'violation': 'password_too_short', 'count': 50},
                    {'violation': 'password_no_uppercase', 'count': 30}
                ]
                
                report = self.service._generate_compliance_report()
                
                self.assertEqual(report['total_users'], 1000)
                self.assertIn('compliant_users', report)
                self.assertIn('non_compliant_users', report)
                self.assertIn('compliance_rate', report)
    
    def test_analyze_compliance_violations(self):
        """Test analyzing compliance violations"""
        # This would require actual user data and password analysis
        # For testing, we'll mock the analysis
        violations = self.service._analyze_compliance_violations()
        
        self.assertIsInstance(violations, list)
        
        for violation in violations:
            self.assertIn('violation', violation)
            self.assertIn('count', violation)
    
    def test_get_password_security_insights(self):
        """Test getting password security insights"""
        with patch.object(self.service, '_generate_security_insights') as mock_insights:
            mock_insights.return_value = {
                'risk_factors': [
                    {
                        'factor': 'weak_passwords',
                        'risk_level': 'medium',
                        'affected_users': 150,
                        'mitigation': 'Enforce stronger password policies'
                    },
                    {
                        'factor': 'password_reuse',
                        'risk_level': 'high',
                        'affected_users': 75,
                        'mitigation': 'Implement password history checking'
                    }
                ],
                'recommendations': [
                    'Implement multi-factor authentication',
                    'Regular password expiration policies'
                ],
                'security_score': 75.5
            }
            
            result = self.service.get_password_security_insights()
            
            self.assertEqual(len(result['risk_factors']), 2)
            self.assertEqual(result['security_score'], 75.5)
    
    def test_generate_security_insights(self):
        """Test generating security insights"""
        insights = self.service._generate_security_insights()
        
        self.assertIn('risk_factors', insights)
        self.assertIn('recommendations', insights)
        self.assertIn('security_score', insights)
        
        for factor in insights['risk_factors']:
            self.assertIn('factor', factor)
            self.assertIn('risk_level', factor)
            self.assertIn('affected_users', factor)
            self.assertIn('mitigation', factor)
    
    def test_get_password_change_notifications(self):
        """Test getting password change notifications"""
        with patch.object(self.service, '_get_users_requiring_notification') as mock_users:
            mock_users.return_value = [
                {
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'password_age': 85,
                    'days_until_expiration': 5,
                    'notification_type': 'expiration_warning'
                }
            ]
            
            result = self.service.get_password_change_notifications()
            
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['notification_type'], 'expiration_warning')
    
    def test_get_users_requiring_notification(self):
        """Test getting users requiring notification"""
        with patch('api.security.models.PasswordHistory.objects') as mock_model:
            mock_queryset = MagicMock()
            mock_queryset.select_related.return_value.filter.return_value = [
                MagicMock(
                    user=self.user,
                    created_at=timezone.now() - timedelta(days=85)
                )
            ]
            mock_model.objects.return_value = mock_queryset
            
            users = self.service._get_users_requiring_notification()
            
            self.assertIsInstance(users, list)
            
            for user_data in users:
                self.assertIn('user_id', user_data)
                self.assertIn('password_age', user_data)
                self.assertIn('days_until_expiration', user_data)
    
    def test_send_password_expiration_notification(self):
        """Test sending password expiration notification"""
        notification_data = {
            'user': self.user,
            'password_age': 85,
            'days_until_expiration': 5,
            'notification_type': 'expiration_warning'
        }
        
        with patch('django.core.mail.send_mail') as mock_send:
            mock_send.return_value = True
            
            result = self.service.send_password_expiration_notification(notification_data)
            
            self.assertTrue(result)
            mock_send.assert_called_once()
    
    def test_get_password_policy_violations_report(self):
        """Test getting password policy violations report"""
        with patch.object(self.service, '_analyze_policy_violations') as mock_violations:
            mock_violations.return_value = {
                'total_violations': 125,
                'violation_types': [
                    {
                        'type': 'password_too_short',
                        'count': 45,
                        'percentage': 36.0
                    },
                    {
                        'type': 'password_no_uppercase',
                        'count': 30,
                        'percentage': 24.0
                    },
                    {
                        'type': 'password_expired',
                        'count': 25,
                        'percentage': 20.0
                    },
                    {
                        'type': 'password_reused',
                        'count': 25,
                        'percentage': 20.0
                    }
                ],
                'trend_data': [
                    {'date': '2023-01-01', 'violations': 120},
                    {'date': '2023-01-02', 'violations': 125}
                ],
                'recommendations': [
                    'Strengthen password requirements',
                    'Implement regular password expiration',
                    'Enable password history checking'
                ]
            }
            
            result = self.service.get_password_policy_violations_report()
            
            self.assertEqual(result['total_violations'], 125)
            self.assertEqual(len(result['violation_types']), 4)
            self.assertEqual(result['violation_types'][0]['type'], 'password_too_short')
    
    def test_analyze_policy_violations(self):
        """Test analyzing policy violations"""
        violations = self.service._analyze_policy_violations()
        
        self.assertIn('total_violations', violations)
        self.assertIn('violation_types', violations)
        self.assertIn('trend_data', violations)
        self.assertIn('recommendations', violations)
        
        for violation_type in violations['violation_types']:
            self.assertIn('type', violation_type)
            self.assertIn('count', violation_type)
            self.assertIn('percentage', violation_type)
    
    def test_get_password_security_metrics(self):
        """Test getting password security metrics"""
        with patch.object(self.service, '_calculate_security_metrics') as mock_metrics:
            mock_metrics.return_value = {
                'average_password_strength': 72.5,
                'password_change_frequency': 45.2,
                'compliance_rate': 85.0,
                'security_incidents': 5,
                'risk_score': 25.5,
                'metrics_trend': 'improving'
            }
            
            result = self.service.get_password_security_metrics(days=30)
            
            self.assertEqual(result['average_password_strength'], 72.5)
            self.assertEqual(result['compliance_rate'], 85.0)
            self.assertEqual(result['risk_score'], 25.5)
    
    def test_calculate_security_metrics(self):
        """Test calculating security metrics"""
        metrics = self.service._calculate_security_metrics(days=30)
        
        self.assertIn('average_password_strength', metrics)
        self.assertIn('password_change_frequency', metrics)
        self.assertIn('compliance_rate', metrics)
        self.assertIn('security_incidents', metrics)
        self.assertIn('risk_score', metrics)
        self.assertIn('metrics_trend', metrics)
    
    def test_get_password_anomaly_detection(self):
        """Test getting password anomaly detection"""
        with patch.object(self.service, '_detect_password_anomalies') as mock_anomalies:
            mock_anomalies.return_value = [
                {
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'anomaly_type': 'rapid_password_changes',
                    'severity': 'medium',
                    'details': {
                        'changes_in_period': 5,
                        'time_period': '24 hours',
                        'normal_rate': 0.1
                    },
                    'recommendation': 'Monitor account for suspicious activity'
                }
            ]
            
            result = self.service.get_password_anomaly_detection(hours=24)
            
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['anomaly_type'], 'rapid_password_changes')
    
    def test_detect_password_anomalies(self):
        """Test detecting password anomalies"""
        anomalies = self.service._detect_password_anomalies(hours=24)
        
        self.assertIsInstance(anomalies, list)
        
        for anomaly in anomalies:
            self.assertIn('user_id', anomaly)
            self.assertIn('anomaly_type', anomaly)
            self.assertIn('severity', anomaly)
            self.assertIn('details', anomaly)
            self.assertIn('recommendation', anomaly)
    
    def test_get_password_breach_detection(self):
        """Test getting password breach detection"""
        with patch.object(self.service, '_check_password_breaches') as mock_breaches:
            mock_breaches.return_value = [
                {
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'breach_type': 'known_compromised_password',
                    'severity': 'high',
                    'details': {
                        'breach_source': 'haveibeenpwned',
                        'breach_date': '2023-01-01',
                        'compromised_accounts': 3
                    },
                    'action_required': 'immediate_password_change'
                }
            ]
            
            result = self.service.get_password_breach_detection()
            
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['breach_type'], 'known_compromised_password')
    
    def test_check_password_breaches(self):
        """Test checking password breaches"""
        breaches = self.service._check_password_breaches()
        
        self.assertIsInstance(breaches, list)
        
        for breach in breaches:
            self.assertIn('user_id', breach)
            self.assertIn('breach_type', breach)
            self.assertIn('severity', breach)
            self.assertIn('details', breach)
            self.assertIn('action_required', breach)
    
    def test_get_password_health_score(self):
        """Test getting password health score"""
        with patch.object(self.service, '_calculate_password_health_score') as mock_score:
            mock_score.return_value = {
                'overall_score': 78.5,
                'strength_score': 82.0,
                'compliance_score': 75.0,
                'freshness_score': 80.0,
                'uniqueness_score': 75.0,
                'grade': 'B',
                'improvement_areas': [
                    'Increase password complexity requirements',
                    'Reduce password reuse frequency'
                ]
            }
            
            result = self.service.get_password_health_score(self.user.id)
            
            self.assertEqual(result['overall_score'], 78.5)
            self.assertEqual(result['grade'], 'B')
            self.assertEqual(len(result['improvement_areas']), 2)
    
    def test_calculate_password_health_score(self):
        """Test calculating password health score"""
        score = self.service._calculate_password_health_score(self.user.id)
        
        self.assertIn('overall_score', score)
        self.assertIn('strength_score', score)
        self.assertIn('compliance_score', score)
        self.assertIn('freshness_score', score)
        self.assertIn('uniqueness_score', score)
        self.assertIn('grade', score)
        self.assertIn('improvement_areas', score)
    
    def test_get_password_recommendations(self):
        """Test getting password recommendations"""
        with patch.object(self.service, '_generate_password_recommendations') as mock_recommendations:
            mock_recommendations.return_value = [
                {
                    'category': 'strength',
                    'priority': 'high',
                    'recommendation': 'Increase minimum password length to 12 characters',
                    'impact': 'Significant improvement in password security',
                    'implementation': 'Update password policy settings'
                },
                {
                    'category': 'expiration',
                    'priority': 'medium',
                    'recommendation': 'Implement 90-day password expiration',
                    'impact': 'Reduced risk from compromised passwords',
                    'implementation': 'Configure expiration policy and notifications'
                }
            ]
            
            result = self.service.get_password_recommendations()
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['category'], 'strength')
            self.assertEqual(result[0]['priority'], 'high')
    
    def test_generate_password_recommendations(self):
        """Test generating password recommendations"""
        recommendations = self.service._generate_password_recommendations()
        
        self.assertIsInstance(recommendations, list)
        
        for recommendation in recommendations:
            self.assertIn('category', recommendation)
            self.assertIn('priority', recommendation)
            self.assertIn('recommendation', recommendation)
            self.assertIn('impact', recommendation)
            self.assertIn('implementation', recommendation)
    
    def test_get_password_security_dashboard(self):
        """Test getting password security dashboard"""
        with patch.object(self.service, '_build_security_dashboard') as mock_dashboard:
            mock_dashboard.return_value = {
                'overview': {
                    'total_users': 1000,
                    'compliant_users': 850,
                    'security_score': 78.5,
                    'active_threats': 5
                },
                'metrics': {
                    'password_strength_distribution': {
                        'weak': 50,
                        'fair': 150,
                        'good': 400,
                        'strong': 300,
                        'very_strong': 100
                    },
                    'policy_violations': 125,
                    'recent_changes': 45
                },
                'trends': [
                    {'date': '2023-01-01', 'compliance_rate': 83.0},
                    {'date': '2023-01-02', 'compliance_rate': 85.0}
                ],
                'alerts': [
                    {
                        'type': 'high_violation_rate',
                        'message': 'Password policy violations increased by 15%',
                        'severity': 'warning'
                    }
                ]
            }
            
            result = self.service.get_password_security_dashboard()
            
            self.assertEqual(result['overview']['total_users'], 1000)
            self.assertEqual(result['overview']['security_score'], 78.5)
            self.assertIn('metrics', result)
            self.assertIn('trends', result)
            self.assertIn('alerts', result)
    
    def test_build_security_dashboard(self):
        """Test building security dashboard"""
        dashboard = self.service._build_security_dashboard()
        
        self.assertIn('overview', dashboard)
        self.assertIn('metrics', dashboard)
        self.assertIn('trends', dashboard)
        self.assertIn('alerts', dashboard)
        
        self.assertIn('total_users', dashboard['overview'])
        self.assertIn('compliant_users', dashboard['overview'])
        self.assertIn('security_score', dashboard['overview'])
    
    def test_export_password_security_report(self):
        """Test exporting password security report"""
        with patch.object(self.service, '_generate_security_report') as mock_report:
            mock_report.return_value = {
                'executive_summary': {
                    'total_users': 1000,
                    'compliance_rate': 85.0,
                    'security_score': 78.5,
                    'risk_level': 'medium'
                },
                'detailed_analysis': {
                    'password_strength': {'average': 72.5, 'distribution': {}},
                    'policy_compliance': {'compliant': 850, 'violations': 150},
                    'security_incidents': {'total': 5, 'types': {}}
                },
                'recommendations': [
                    'Strengthen password requirements',
                    'Implement regular expiration'
                ],
                'appendices': {
                    'methodology': 'Statistical analysis of password data',
                    'data_sources': 'Password history, user accounts'
                }
            }
            
            result = self.service.export_password_security_report(format='json')
            
            self.assertEqual(result['executive_summary']['total_users'], 1000)
            self.assertEqual(result['executive_summary']['compliance_rate'], 85.0)
            self.assertIn('detailed_analysis', result)
            self.assertIn('recommendations', result)
    
    def test_generate_security_report(self):
        """Test generating security report"""
        report = self.service._generate_security_report()
        
        self.assertIn('executive_summary', report)
        self.assertIn('detailed_analysis', report)
        self.assertIn('recommendations', report)
        self.assertIn('appendices', report)
        
        self.assertIn('total_users', report['executive_summary'])
        self.assertIn('compliance_rate', report['executive_summary'])
        self.assertIn('security_score', report['executive_summary'])
    
    def test_get_password_forecasting(self):
        """Test getting password security forecasting"""
        with patch.object(self.service, '_forecast_password_security') as mock_forecast:
            mock_forecast.return_value = {
                'forecast_period': '30 days',
                'predicted_compliance_rate': 88.5,
                'predicted_security_score': 82.0,
                'confidence_interval': [85.0, 92.0],
                'trend_direction': 'improving',
                'key_factors': [
                    'New password policy implementation',
                    'User education campaign'
                ],
                'recommendations': [
                    'Continue current security initiatives',
                    'Monitor for emerging threats'
                ]
            }
            
            result = self.service.get_password_forecasting(days=30)
            
            self.assertEqual(result['predicted_compliance_rate'], 88.5)
            self.assertEqual(result['trend_direction'], 'improving')
            self.assertIn('confidence_interval', result)
    
    def test_forecast_password_security(self):
        """Test forecasting password security"""
        forecast = self.service._forecast_password_security(days=30)
        
        self.assertIn('forecast_period', forecast)
        self.assertIn('predicted_compliance_rate', forecast)
        self.assertIn('predicted_security_score', forecast)
        self.assertIn('confidence_interval', forecast)
        self.assertIn('trend_direction', forecast)
    
    def test_get_password_benchmarking(self):
        """Test getting password security benchmarking"""
        with patch.object(self.service, '_benchmark_password_security') as mock_benchmark:
            mock_benchmark.return_value = {
                'industry_average': {
                    'compliance_rate': 75.0,
                    'security_score': 70.0,
                    'average_strength': 65.0
                },
                'your_metrics': {
                    'compliance_rate': 85.0,
                    'security_score': 78.5,
                    'average_strength': 72.5
                },
                'comparison': {
                    'compliance_rate': 'above_average',
                    'security_score': 'above_average',
                    'average_strength': 'above_average'
                },
                'percentile_rank': 75,
                'recommendations': [
                    'Maintain current security practices',
                    'Focus on continuous improvement'
                ]
            }
            
            result = self.service.get_password_benchmarking()
            
            self.assertEqual(result['percentile_rank'], 75)
            self.assertEqual(result['comparison']['compliance_rate'], 'above_average')
    
    def test_benchmark_password_security(self):
        """Test benchmarking password security"""
        benchmark = self.service._benchmark_password_security()
        
        self.assertIn('industry_average', benchmark)
        self.assertIn('your_metrics', benchmark)
        self.assertIn('comparison', benchmark)
        self.assertIn('percentile_rank', benchmark)
    
    def test_get_password_optimization_suggestions(self):
        """Test getting password optimization suggestions"""
        with patch.object(self.service, '_generate_optimization_suggestions') as mock_suggestions:
            mock_suggestions.return_value = [
                {
                    'area': 'password_strength',
                    'current_performance': 72.5,
                    'target_performance': 85.0,
                    'improvement_actions': [
                        'Increase minimum length requirements',
                        'Add complexity requirements'
                    ],
                    'expected_impact': '15% improvement in security',
                    'implementation_effort': 'medium',
                    'priority': 'high'
                },
                {
                    'area': 'policy_compliance',
                    'current_performance': 85.0,
                    'target_performance': 95.0,
                    'improvement_actions': [
                        'Regular policy reviews',
                        'User education programs'
                    ],
                    'expected_impact': '10% improvement in compliance',
                    'implementation_effort': 'low',
                    'priority': 'medium'
                }
            ]
            
            result = self.service.get_password_optimization_suggestions()
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['area'], 'password_strength')
            self.assertEqual(result[0]['priority'], 'high')
    
    def test_generate_optimization_suggestions(self):
        """Test generating optimization suggestions"""
        suggestions = self.service._generate_optimization_suggestions()
        
        self.assertIsInstance(suggestions, list)
        
        for suggestion in suggestions:
            self.assertIn('area', suggestion)
            self.assertIn('current_performance', suggestion)
            self.assertIn('target_performance', suggestion)
            self.assertIn('improvement_actions', suggestion)
            self.assertIn('expected_impact', suggestion)
            self.assertIn('implementation_effort', suggestion)
            self.assertIn('priority', suggestion)