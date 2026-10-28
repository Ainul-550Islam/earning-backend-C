"""
Enhanced Security Policy Tests
Comprehensive test suite for security policy functionality
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

from ..services.SecurityPolicyService import SecurityPolicyService
from .factories import (
    UserFactory, StaffUserFactory, SecurityPolicyFactory,
    SecurityLogFactory, UserBanFactory
)
from api.security.models import SecurityPolicy


class SecurityPolicyServiceTest(TestCase):
    """Test SecurityPolicyService class"""
    
    def setUp(self):
        self.service = SecurityPolicyService()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        cache.clear()
    
    def test_security_policy_service_initialization(self):
        """Test SecurityPolicyService initialization"""
        self.assertIsNotNone(self.service.cache_manager)
        self.assertIsNotNone(self.service.logger)
        self.assertIsNotNone(self.service.default_cache_timeout)
        self.assertIsNotNone(self.service.policy_cache_prefix)
    
    def test_security_policy_service_default_config(self):
        """Test default configuration"""
        self.assertEqual(self.service.default_cache_timeout, 3600)
        self.assertEqual(self.service.policy_cache_prefix, "security_policy")
    
    def test_get_policy(self):
        """Test getting security policy"""
        with patch('api.security.models.SecurityPolicy.objects.filter') as mock_filter:
            mock_policy = SecurityPolicyFactory(
                user=self.user,
                policy_key='password_policy',
                policy_value=json.dumps({
                    'min_length': 8,
                    'require_uppercase': True,
                    'require_lowercase': True,
                    'require_numbers': True,
                    'require_special_chars': True
                })
            )
            mock_queryset = MagicMock()
            mock_queryset.first.return_value = mock_policy
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_policy(self.user.id, 'password_policy')
            
            self.assertEqual(result['min_length'], 8)
            self.assertTrue(result['require_uppercase'])
            self.assertTrue(result['require_lowercase'])
            self.assertTrue(result['require_numbers'])
            self.assertTrue(result['require_special_chars'])
    
    def test_get_policy_cached(self):
        """Test getting cached security policy"""
        cache_key = f"{self.service.policy_cache_prefix}:user_{self.user.id}:password_policy"
        cached_policy = {
            'min_length': 8,
            'require_uppercase': True,
            'require_lowercase': True
        }
        cache.set(cache_key, cached_policy, self.service.default_cache_timeout)
        
        result = self.service.get_policy(self.user.id, 'password_policy')
        
        self.assertEqual(result['min_length'], 8)
        self.assertTrue(result['require_uppercase'])
    
    def test_get_policy_not_found(self):
        """Test getting non-existent security policy"""
        with patch('api.security.models.SecurityPolicy.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.first.return_value = None
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_policy(self.user.id, 'non_existent_policy')
            
            self.assertIsNone(result)
    
    def test_get_policy_with_default(self):
        """Test getting policy with default value"""
        default_policy = {
            'min_length': 6,
            'require_uppercase': False,
            'require_lowercase': False
        }
        
        with patch('api.security.models.SecurityPolicy.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.first.return_value = None
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_policy(
                self.user.id,
                'non_existent_policy',
                default_policy
            )
            
            self.assertEqual(result, default_policy)
    
    def test_set_policy(self):
        """Test setting security policy"""
        policy_data = {
            'min_length': 12,
            'require_uppercase': True,
            'require_lowercase': True,
            'require_numbers': True,
            'require_special_chars': True,
            'prevent_reuse': True,
            'reuse_limit': 10,
            'max_age_days': 90
        }
        
        with patch('api.security.models.SecurityPolicy.objects.update_or_create') as mock_update_create:
            mock_policy = MagicMock()
            mock_policy.id = 'policy-id'
            mock_update_create.return_value = (mock_policy, True)
            
            result = self.service.set_policy(
                self.user.id,
                'password_policy',
                policy_data
            )
            
            self.assertEqual(result, mock_policy)
            mock_update_create.assert_called_once()
            
            # Check call arguments
            call_args = mock_update_create.call_args[1]
            self.assertEqual(call_args['defaults']['user'], self.user)
            self.assertEqual(call_args['defaults']['policy_key'], 'password_policy')
            self.assertEqual(json.loads(call_args['defaults']['policy_value']), policy_data)
    
    def test_set_policy_with_metadata(self):
        """Test setting security policy with metadata"""
        policy_data = {
            'min_length': 12,
            'require_uppercase': True
        }
        metadata = {
            'created_by': self.staff_user.id,
            'reason': 'Security enhancement',
            'version': '2.0'
        }
        
        with patch('api.security.models.SecurityPolicy.objects.update_or_create') as mock_update_create:
            mock_policy = MagicMock()
            mock_policy.id = 'policy-id'
            mock_update_create.return_value = (mock_policy, True)
            
            result = self.service.set_policy(
                self.user.id,
                'password_policy',
                policy_data,
                metadata=metadata
            )
            
            self.assertEqual(result, mock_policy)
            call_args = mock_update_create.call_args[1]
            self.assertIn('metadata', call_args['defaults'])
    
    def test_update_policy(self):
        """Test updating security policy"""
        existing_policy = SecurityPolicyFactory(
            user=self.user,
            policy_key='password_policy',
            policy_value=json.dumps({'min_length': 8})
        )
        
        updated_data = {
            'min_length': 12,
            'require_uppercase': True,
            'require_lowercase': True
        }
        
        with patch.object(existing_policy, 'save') as mock_save:
            with patch.object(self.service, '_clear_policy_cache') as mock_clear:
                mock_clear.return_value = True
                
                result = self.service.update_policy(
                    existing_policy.id,
                    updated_data
                )
                
                self.assertEqual(result, existing_policy)
                mock_save.assert_called_once()
                mock_clear.assert_called_once()
    
    def test_update_policy_not_found(self):
        """Test updating non-existent policy"""
        with patch('api.security.models.SecurityPolicy.objects.get') as mock_get:
            mock_get.side_effect = SecurityPolicy.DoesNotExist()
            
            result = self.service.update_policy(
                'non-existent-id',
                {'min_length': 12}
            )
            
            self.assertIsNone(result)
    
    def test_delete_policy(self):
        """Test deleting security policy"""
        existing_policy = SecurityPolicyFactory(
            user=self.user,
            policy_key='password_policy'
        )
        
        with patch.object(existing_policy, 'delete') as mock_delete:
            with patch.object(self.service, '_clear_policy_cache') as mock_clear:
                mock_clear.return_value = True
                
                result = self.service.delete_policy(existing_policy.id)
                
                self.assertTrue(result)
                mock_delete.assert_called_once()
                mock_clear.assert_called_once()
    
    def test_delete_policy_not_found(self):
        """Test deleting non-existent policy"""
        with patch('api.security.models.SecurityPolicy.objects.get') as mock_get:
            mock_get.side_effect = SecurityPolicy.DoesNotExist()
            
            result = self.service.delete_policy('non-existent-id')
            
            self.assertFalse(result)
    
    def test_get_all_user_policies(self):
        """Test getting all user policies"""
        with patch('api.security.models.SecurityPolicy.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 3
            mock_queryset.order_by.return_value = [
                SecurityPolicyFactory(user=self.user),
                SecurityPolicyFactory(user=self.user)
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_all_user_policies(self.user.id)
            
            self.assertEqual(result['count'], 3)
            self.assertEqual(len(result['policies']), 2)
            mock_filter.assert_called_once_with(user=self.user)
    
    def test_get_all_user_policies_include_inactive(self):
        """Test getting all user policies including inactive"""
        with patch('api.security.models.SecurityPolicy.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 5
            mock_queryset.order_by.return_value = [MagicMock() for _ in range(3)]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_all_user_policies(
                self.user.id,
                include_inactive=True
            )
            
            self.assertEqual(result['count'], 5)
            self.assertEqual(len(result['policies']), 3)
    
    def test_get_policy_by_type(self):
        """Test getting policies by type"""
        with patch('api.security.models.SecurityPolicy.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 2
            mock_queryset.order_by.return_value = [
                SecurityPolicyFactory(user=self.user, policy_key='password_policy'),
                SecurityPolicyFactory(user=self.user, policy_key='session_policy')
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_policy_by_type(self.user.id, 'password')
            
            self.assertEqual(result['count'], 2)
            self.assertEqual(len(result['policies']), 2)
    
    def test_validate_policy_data(self):
        """Test validating policy data"""
        valid_policy = {
            'min_length': 8,
            'require_uppercase': True,
            'require_lowercase': True,
            'require_numbers': True,
            'require_special_chars': True
        }
        
        result = self.service.validate_policy_data(valid_policy, 'password_policy')
        
        self.assertTrue(result['valid'])
        self.assertNotIn('errors', result)
    
    def test_validate_policy_data_invalid(self):
        """Test validating invalid policy data"""
        invalid_policy = {
            'min_length': -1,  # Invalid
            'require_uppercase': 'not_boolean',  # Invalid type
            'require_lowercase': True
        }
        
        result = self.service.validate_policy_data(invalid_policy, 'password_policy')
        
        self.assertFalse(result['valid'])
        self.assertIn('errors', result)
        self.assertGreater(len(result['errors']), 0)
    
    def test_validate_policy_data_missing_required(self):
        """Test validating policy data with missing required fields"""
        incomplete_policy = {
            'require_uppercase': True,
            'require_lowercase': True
            # Missing required fields
        }
        
        result = self.service.validate_policy_data(incomplete_policy, 'password_policy')
        
        self.assertFalse(result['valid'])
        self.assertIn('errors', result)
    
    def test_get_default_policy_template(self):
        """Test getting default policy template"""
        template = self.service.get_default_policy_template('password_policy')
        
        self.assertIn('min_length', template)
        self.assertIn('require_uppercase', template)
        self.assertIn('require_lowercase', template)
        self.assertIn('require_numbers', template)
        self.assertIn('require_special_chars', template)
    
    def test_get_default_policy_template_unknown_type(self):
        """Test getting default policy template for unknown type"""
        template = self.service.get_default_policy_template('unknown_policy')
        
        self.assertIsInstance(template, dict)
        self.assertGreater(len(template), 0)
    
    def test_apply_policy_template(self):
        """Test applying policy template"""
        with patch.object(self.service, 'set_policy') as mock_set:
            mock_set.return_value = MagicMock()
            
            result = self.service.apply_policy_template(
                self.user.id,
                'password_policy'
            )
            
            mock_set.assert_called_once()
            self.assertIsNotNone(result)
    
    def test_apply_policy_template_with_customization(self):
        """Test applying policy template with customization"""
        customizations = {
            'min_length': 12,
            'require_special_chars': False
        }
        
        with patch.object(self.service, 'set_policy') as mock_set:
            mock_set.return_value = MagicMock()
            
            result = self.service.apply_policy_template(
                self.user.id,
                'password_policy',
                customizations=customizations
            )
            
            mock_set.assert_called_once()
            
            # Check that customizations were applied
            call_args = mock_set.call_args[0]
            policy_data = call_args[2]
            self.assertEqual(policy_data['min_length'], 12)
            self.assertFalse(policy_data['require_special_chars'])
    
    def test_get_policy_compliance_status(self):
        """Test getting policy compliance status"""
        with patch.object(self.service, '_check_policy_compliance') as mock_compliance:
            mock_compliance.return_value = {
                'compliant': True,
                'compliance_score': 95.0,
                'violations': [],
                'recommendations': []
            }
            
            result = self.service.get_policy_compliance_status(self.user.id)
            
            self.assertTrue(result['compliant'])
            self.assertEqual(result['compliance_score'], 95.0)
    
    def test_check_policy_compliance(self):
        """Test checking policy compliance"""
        compliance = self.service._check_policy_compliance(self.user.id)
        
        self.assertIn('compliant', compliance)
        self.assertIn('compliance_score', compliance)
        self.assertIn('violations', compliance)
        self.assertIn('recommendations', compliance)
    
    def test_get_policy_violations(self):
        """Test getting policy violations"""
        with patch.object(self.service, '_analyze_policy_violations') as mock_violations:
            mock_violations.return_value = [
                {
                    'policy_type': 'password_policy',
                    'violation_type': 'password_too_short',
                    'severity': 'medium',
                    'affected_users': 25,
                    'description': 'Password does not meet minimum length requirement'
                },
                {
                    'policy_type': 'session_policy',
                    'violation_type': 'session_timeout_exceeded',
                    'severity': 'low',
                    'affected_users': 10,
                    'description': 'Session timeout exceeds policy limits'
                }
            ]
            
            result = self.service.get_policy_violations()
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['policy_type'], 'password_policy')
            self.assertEqual(result[0]['severity'], 'medium')
    
    def test_analyze_policy_violations(self):
        """Test analyzing policy violations"""
        violations = self.service._analyze_policy_violations()
        
        self.assertIsInstance(violations, list)
        
        for violation in violations:
            self.assertIn('policy_type', violation)
            self.assertIn('violation_type', violation)
            self.assertIn('severity', violation)
            self.assertIn('affected_users', violation)
            self.assertIn('description', violation)
    
    def test_get_policy_effectiveness_metrics(self):
        """Test getting policy effectiveness metrics"""
        with patch.object(self.service, '_calculate_policy_effectiveness') as mock_effectiveness:
            mock_effectiveness.return_value = {
                'overall_effectiveness': 85.5,
                'policy_breakdown': {
                    'password_policy': 90.0,
                    'session_policy': 80.0,
                    'access_policy': 85.0
                },
                'trend_data': [
                    {'date': '2023-01-01', 'effectiveness': 83.0},
                    {'date': '2023-01-02', 'effectiveness': 85.5}
                ],
                'improvement_areas': [
                    'Session timeout enforcement',
                    'Access control monitoring'
                ]
            }
            
            result = self.service.get_policy_effectiveness_metrics(days=30)
            
            self.assertEqual(result['overall_effectiveness'], 85.5)
            self.assertEqual(result['policy_breakdown']['password_policy'], 90.0)
            self.assertIn('trend_data', result)
    
    def test_calculate_policy_effectiveness(self):
        """Test calculating policy effectiveness"""
        effectiveness = self.service._calculate_policy_effectiveness(days=30)
        
        self.assertIn('overall_effectiveness', effectiveness)
        self.assertIn('policy_breakdown', effectiveness)
        self.assertIn('trend_data', effectiveness)
        self.assertIn('improvement_areas', effectiveness)
    
    def test_get_policy_recommendations(self):
        """Test getting policy recommendations"""
        with patch.object(self.service, '_generate_policy_recommendations') as mock_recommendations:
            mock_recommendations.return_value = [
                {
                    'policy_type': 'password_policy',
                    'recommendation': 'Increase minimum password length to 12 characters',
                    'priority': 'high',
                    'impact': 'Significant improvement in password security',
                    'implementation_effort': 'medium'
                },
                {
                    'policy_type': 'session_policy',
                    'recommendation': 'Reduce session timeout to 30 minutes',
                    'priority': 'medium',
                    'impact': 'Reduced risk from session hijacking',
                    'implementation_effort': 'low'
                }
            ]
            
            result = self.service.get_policy_recommendations()
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['policy_type'], 'password_policy')
            self.assertEqual(result[0]['priority'], 'high')
    
    def test_generate_policy_recommendations(self):
        """Test generating policy recommendations"""
        recommendations = self.service._generate_policy_recommendations()
        
        self.assertIsInstance(recommendations, list)
        
        for recommendation in recommendations:
            self.assertIn('policy_type', recommendation)
            self.assertIn('recommendation', recommendation)
            self.assertIn('priority', recommendation)
            self.assertIn('impact', recommendation)
            self.assertIn('implementation_effort', recommendation)
    
    def test_enforce_policy(self):
        """Test enforcing policy"""
        policy_data = {
            'min_length': 8,
            'require_uppercase': True,
            'require_lowercase': True
        }
        
        user_data = {
            'password': 'weak',
            'session_duration': 3600
        }
        
        with patch.object(self.service, '_check_policy_enforcement') as mock_enforcement:
            mock_enforcement.return_value = {
                'compliant': False,
                'violations': [
                    {
                        'policy_rule': 'min_length',
                        'current_value': 4,
                        'required_value': 8,
                        'message': 'Password too short'
                    }
                ],
                'actions': [
                    {
                        'type': 'reject',
                        'message': 'Password does not meet policy requirements'
                    }
                ]
            }
            
            result = self.service.enforce_policy(
                self.user.id,
                'password_policy',
                policy_data,
                user_data
            )
            
            self.assertFalse(result['compliant'])
            self.assertEqual(len(result['violations']), 1)
    
    def test_check_policy_enforcement(self):
        """Test checking policy enforcement"""
        policy_data = {
            'min_length': 8,
            'require_uppercase': True
        }
        user_data = {'password': 'StrongPassword123!'}
        
        enforcement = self.service._check_policy_enforcement(
            self.user.id,
            'password_policy',
            policy_data,
            user_data
        )
        
        self.assertIn('compliant', enforcement)
        self.assertIn('violations', enforcement)
        self.assertIn('actions', enforcement)
    
    def test_get_policy_audit_log(self):
        """Test getting policy audit log"""
        with patch('api.security.models.PolicyAuditLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 10
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_policy_audit_log(
                self.user.id,
                days=30
            )
            
            self.assertEqual(result['count'], 10)
            self.assertEqual(len(result['audit_entries']), 2)
    
    def test_create_policy_audit_log(self):
        """Test creating policy audit log entry"""
        with patch('api.security.models.PolicyAuditLog.objects.create') as mock_create:
            mock_log = MagicMock()
            mock_log.id = 'audit-log-id'
            mock_create.return_value = mock_log
            
            result = self.service.create_policy_audit_log(
                self.user.id,
                'password_policy',
                'policy_updated',
                {'old_min_length': 8, 'new_min_length': 12},
                self.staff_user
            )
            
            self.assertEqual(result, mock_log)
            mock_create.assert_called_once()
    
    def test_get_policy_statistics(self):
        """Test getting policy statistics"""
        with patch.object(self.service, '_calculate_policy_statistics') as mock_stats:
            mock_stats.return_value = {
                'total_policies': 150,
                'active_policies': 120,
                'policy_types': {
                    'password_policy': 50,
                    'session_policy': 40,
                    'access_policy': 30,
                    'privacy_policy': 30
                },
                'compliance_rate': 85.5,
                'average_effectiveness': 82.0,
                'recent_changes': 15
            }
            
            result = self.service.get_policy_statistics()
            
            self.assertEqual(result['total_policies'], 150)
            self.assertEqual(result['active_policies'], 120)
            self.assertEqual(result['compliance_rate'], 85.5)
    
    def test_calculate_policy_statistics(self):
        """Test calculating policy statistics"""
        stats = self.service._calculate_policy_statistics()
        
        self.assertIn('total_policies', stats)
        self.assertIn('active_policies', stats)
        self.assertIn('policy_types', stats)
        self.assertIn('compliance_rate', stats)
        self.assertIn('average_effectiveness', stats)
    
    def test_export_policies(self):
        """Test exporting policies"""
        with patch('api.security.models.SecurityPolicy.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.values.return_value = [
                {
                    'id': 'policy-1',
                    'user_id': self.user.id,
                    'policy_key': 'password_policy',
                    'policy_value': '{"min_length": 8}',
                    'is_active': True,
                    'created_at': timezone.now()
                },
                {
                    'id': 'policy-2',
                    'user_id': self.user.id,
                    'policy_key': 'session_policy',
                    'policy_value': '{"timeout": 3600}',
                    'is_active': True,
                    'created_at': timezone.now()
                }
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.export_policies(
                user_id=self.user.id,
                format='json'
            )
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['policy_key'], 'password_policy')
            self.assertEqual(result[1]['policy_key'], 'session_policy')
    
    def test_export_policies_csv(self):
        """Test exporting policies in CSV format"""
        with patch('api.security.models.SecurityPolicy.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.values.return_value = [
                {
                    'id': 'policy-1',
                    'user_id': self.user.id,
                    'policy_key': 'password_policy',
                    'policy_value': '{"min_length": 8}',
                    'is_active': True
                }
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.export_policies(
                user_id=self.user.id,
                format='csv'
            )
            
            self.assertIn('policy_key', result)
            self.assertIn('password_policy', result)
    
    def test_import_policies(self):
        """Test importing policies"""
        import_data = [
            {
                'policy_key': 'password_policy',
                'policy_value': {
                    'min_length': 12,
                    'require_uppercase': True,
                    'require_lowercase': True
                }
            },
            {
                'policy_key': 'session_policy',
                'policy_value': {
                    'timeout': 1800,
                    'max_concurrent_sessions': 3
                }
            }
        ]
        
        with patch.object(self.service, '_import_policy_entry') as mock_import:
            mock_import.return_value = MagicMock()
            
            result = self.service.import_policies(
                self.user.id,
                import_data
            )
            
            self.assertEqual(result['imported_count'], 2)
            self.assertEqual(result['failed_count'], 0)
            self.assertEqual(mock_import.call_count, 2)
    
    def test_import_policies_with_errors(self):
        """Test importing policies with validation errors"""
        import_data = [
            {
                'policy_key': '',  # Invalid - empty
                'policy_value': {'min_length': 8}
            },
            {
                'policy_key': 'valid_policy',
                'policy_value': {'timeout': 1800}
            }
        ]
        
        with patch.object(self.service, '_import_policy_entry') as mock_import:
            mock_import.return_value = MagicMock()
            
            result = self.service.import_policies(
                self.user.id,
                import_data
            )
            
            self.assertEqual(result['imported_count'], 1)
            self.assertEqual(result['failed_count'], 1)
            self.assertIn('errors', result)
    
    def test_import_policy_entry(self):
        """Test importing individual policy entry"""
        import_data = {
            'policy_key': 'password_policy',
            'policy_value': {
                'min_length': 12,
                'require_uppercase': True
            }
        }
        
        with patch.object(self.service, 'set_policy') as mock_set:
            mock_set.return_value = MagicMock()
            
            result = self.service._import_policy_entry(
                self.user,
                import_data
            )
            
            mock_set.assert_called_once()
            self.assertIsNotNone(result)
    
    def test_validate_import_data(self):
        """Test validating import data"""
        valid_data = [
            {
                'policy_key': 'password_policy',
                'policy_value': {'min_length': 8}
            },
            {
                'policy_key': 'session_policy',
                'policy_value': {'timeout': 3600}
            }
        ]
        
        result = self.service.validate_import_data(valid_data)
        
        self.assertTrue(result['valid'])
        self.assertNotIn('errors', result)
    
    def test_validate_import_data_invalid(self):
        """Test validating invalid import data"""
        invalid_data = [
            {
                'policy_key': '',  # Empty
                'policy_value': {'min_length': 8}
            },
            {
                'policy_key': 'session_policy',
                'policy_value': 'invalid_json'  # Invalid JSON
            }
        ]
        
        result = self.service.validate_import_data(invalid_data)
        
        self.assertFalse(result['valid'])
        self.assertIn('errors', result)
        self.assertGreater(len(result['errors']), 0)
    
    def test_get_policy_change_history(self):
        """Test getting policy change history"""
        with patch('api.security.models.PolicyAuditLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 5
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_policy_change_history(
                self.user.id,
                'password_policy'
            )
            
            self.assertEqual(result['count'], 5)
            self.assertEqual(len(result['changes']), 2)
    
    def test_rollback_policy(self):
        """Test rolling back policy to previous version"""
        with patch.object(self.service, '_get_policy_version') as mock_version:
            mock_version.return_value = {
                'policy_value': '{"min_length": 8, "require_uppercase": true}',
                'created_at': timezone.now() - timedelta(days=1),
                'version': 1
            }
            
            with patch.object(self.service, 'set_policy') as mock_set:
                mock_set.return_value = MagicMock()
                
                result = self.service.rollback_policy(
                    self.user.id,
                    'password_policy',
                    version=1
                )
                
                self.assertIsNotNone(result)
                mock_set.assert_called_once()
    
    def test_get_policy_version(self):
        """Test getting specific policy version"""
        with patch('api.security.models.PolicyAuditLog.objects.filter') as mock_filter:
            mock_log = MagicMock()
            mock_log.policy_value = '{"min_length": 8, "require_uppercase": true}'
            mock_log.created_at = timezone.now() - timedelta(days=1)
            mock_log.version = 1
            mock_queryset = MagicMock()
            mock_queryset.first.return_value = mock_log
            mock_filter.return_value = mock_queryset
            
            result = self.service._get_policy_version(
                self.user.id,
                'password_policy',
                version=1
            )
            
            self.assertEqual(result['version'], 1)
            self.assertIsNotNone(result['policy_value'])
    
    def test_get_policy_versions(self):
        """Test getting all policy versions"""
        with patch('api.security.models.PolicyAuditLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 3
            mock_queryset.order_by.return_value = [
                MagicMock(version=3, created_at=timezone.now()),
                MagicMock(version=2, created_at=timezone.now() - timedelta(days=1)),
                MagicMock(version=1, created_at=timezone.now() - timedelta(days=2))
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_policy_versions(
                self.user.id,
                'password_policy'
            )
            
            self.assertEqual(result['count'], 3)
            self.assertEqual(len(result['versions']), 3)
            self.assertEqual(result['versions'][0]['version'], 3)
    
    def test_compare_policy_versions(self):
        """Test comparing policy versions"""
        with patch.object(self.service, '_get_policy_version') as mock_get_version:
            mock_get_version.side_effect = [
                {
                    'policy_value': '{"min_length": 12, "require_uppercase": true}',
                    'version': 2
                },
                {
                    'policy_value': '{"min_length": 8, "require_uppercase": true}',
                    'version': 1
                }
            ]
            
            result = self.service.compare_policy_versions(
                self.user.id,
                'password_policy',
                version1=2,
                version2=1
            )
            
            self.assertIn('version1', result)
            self.assertIn('version2', result)
            self.assertIn('differences', result)
    
    def test_get_policy_compliance_trends(self):
        """Test getting policy compliance trends"""
        with patch.object(self.service, '_calculate_compliance_trends') as mock_trends:
            mock_trends.return_value = [
                {
                    'date': '2023-01-01',
                    'compliance_rate': 82.0,
                    'total_policies': 145,
                    'compliant_policies': 119
                },
                {
                    'date': '2023-01-02',
                    'compliance_rate': 85.5,
                    'total_policies': 148,
                    'compliant_policies': 127
                }
            ]
            
            result = self.service.get_policy_compliance_trends(days=30)
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['compliance_rate'], 82.0)
            self.assertEqual(result[1]['compliance_rate'], 85.5)
    
    def test_calculate_compliance_trends(self):
        """Test calculating compliance trends"""
        trends = self.service._calculate_compliance_trends(days=30)
        
        self.assertIsInstance(trends, list)
        
        for trend in trends:
            self.assertIn('date', trend)
            self.assertIn('compliance_rate', trend)
            self.assertIn('total_policies', trend)
            self.assertIn('compliant_policies', trend)
    
    def test_get_policy_effectiveness_by_type(self):
        """Test getting policy effectiveness by type"""
        with patch.object(self.service, '_calculate_effectiveness_by_type') as mock_effectiveness:
            mock_effectiveness.return_value = {
                'password_policy': {
                    'effectiveness_score': 90.0,
                    'compliance_rate': 92.0,
                    'violation_rate': 8.0,
                    'trend': 'improving'
                },
                'session_policy': {
                    'effectiveness_score': 75.0,
                    'compliance_rate': 80.0,
                    'violation_rate': 20.0,
                    'trend': 'stable'
                }
            }
            
            result = self.service.get_policy_effectiveness_by_type()
            
            self.assertEqual(result['password_policy']['effectiveness_score'], 90.0)
            self.assertEqual(result['session_policy']['compliance_rate'], 80.0)
    
    def test_calculate_effectiveness_by_type(self):
        """Test calculating effectiveness by type"""
        effectiveness = self.service._calculate_effectiveness_by_type()
        
        self.assertIsInstance(effectiveness, dict)
        
        for policy_type, metrics in effectiveness.items():
            self.assertIn('effectiveness_score', metrics)
            self.assertIn('compliance_rate', metrics)
            self.assertIn('violation_rate', metrics)
            self.assertIn('trend', metrics)
    
    def test_get_policy_benchmarking(self):
        """Test getting policy benchmarking"""
        with patch.object(self.service, '_benchmark_policies') as mock_benchmark:
            mock_benchmark.return_value = {
                'industry_average': {
                    'password_policy_effectiveness': 75.0,
                    'session_policy_effectiveness': 70.0,
                    'access_policy_effectiveness': 80.0
                },
                'your_metrics': {
                    'password_policy_effectiveness': 90.0,
                    'session_policy_effectiveness': 75.0,
                    'access_policy_effectiveness': 85.0
                },
                'comparison': {
                    'password_policy': 'above_average',
                    'session_policy': 'average',
                    'access_policy': 'above_average'
                },
                'percentile_rank': 80,
                'recommendations': [
                    'Maintain strong password policies',
                    'Improve session policy enforcement'
                ]
            }
            
            result = self.service.get_policy_benchmarking()
            
            self.assertEqual(result['percentile_rank'], 80)
            self.assertEqual(result['comparison']['password_policy'], 'above_average')
    
    def test_benchmark_policies(self):
        """Test benchmarking policies"""
        benchmark = self.service._benchmark_policies()
        
        self.assertIn('industry_average', benchmark)
        self.assertIn('your_metrics', benchmark)
        self.assertIn('comparison', benchmark)
        self.assertIn('percentile_rank', benchmark)
    
    def test_get_policy_optimization_suggestions(self):
        """Test getting policy optimization suggestions"""
        with patch.object(self.service, '_generate_optimization_suggestions') as mock_suggestions:
            mock_suggestions.return_value = [
                {
                    'policy_type': 'password_policy',
                    'current_effectiveness': 90.0,
                    'target_effectiveness': 95.0,
                    'optimization_actions': [
                        'Increase password complexity requirements',
                        'Implement regular password expiration'
                    ],
                    'expected_impact': '5% improvement in security',
                    'implementation_effort': 'medium',
                    'priority': 'high'
                }
            ]
            
            result = self.service.get_policy_optimization_suggestions()
            
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['policy_type'], 'password_policy')
            self.assertEqual(result[0]['priority'], 'high')
    
    def test_generate_optimization_suggestions(self):
        """Test generating optimization suggestions"""
        suggestions = self.service._generate_optimization_suggestions()
        
        self.assertIsInstance(suggestions, list)
        
        for suggestion in suggestions:
            self.assertIn('policy_type', suggestion)
            self.assertIn('current_effectiveness', suggestion)
            self.assertIn('target_effectiveness', suggestion)
            self.assertIn('optimization_actions', suggestion)
            self.assertIn('expected_impact', suggestion)
            self.assertIn('implementation_effort', suggestion)
            self.assertIn('priority', suggestion)
    
    def test_get_policy_forecasting(self):
        """Test getting policy forecasting"""
        with patch.object(self.service, '_forecast_policy_trends') as mock_forecast:
            mock_forecast.return_value = {
                'forecast_period': '30 days',
                'predicted_compliance_rate': 88.5,
                'predicted_effectiveness': 85.0,
                'confidence_interval': [85.0, 92.0],
                'trend_direction': 'improving',
                'key_factors': [
                    'New policy implementations',
                    'User education programs'
                ],
                'recommendations': [
                    'Continue current policy direction',
                    'Monitor emerging security threats'
                ]
            }
            
            result = self.service.get_policy_forecasting(days=30)
            
            self.assertEqual(result['predicted_compliance_rate'], 88.5)
            self.assertEqual(result['trend_direction'], 'improving')
            self.assertIn('confidence_interval', result)
    
    def test_forecast_policy_trends(self):
        """Test forecasting policy trends"""
        forecast = self.service._forecast_policy_trends(days=30)
        
        self.assertIn('forecast_period', forecast)
        self.assertIn('predicted_compliance_rate', forecast)
        self.assertIn('predicted_effectiveness', forecast)
        self.assertIn('confidence_interval', forecast)
        self.assertIn('trend_direction', forecast)
    
    def test_get_policy_impact_analysis(self):
        """Test getting policy impact analysis"""
        with patch.object(self.service, '_analyze_policy_impact') as mock_analysis:
            mock_analysis.return_value = {
                'security_incidents_reduction': 25.5,
                'compliance_improvement': 15.0,
                'user_satisfaction': 80.0,
                'operational_impact': 'low',
                'cost_benefit_ratio': 3.5,
                'key_metrics': {
                    'incident_reduction_rate': 25.5,
                    'compliance_increase': 15.0,
                    'user_adoption_rate': 85.0
                },
                'recommendations': [
                    'Continue policy enforcement',
                    'Monitor user feedback'
                ]
            }
            
            result = self.service.get_policy_impact_analysis(days=90)
            
            self.assertEqual(result['security_incidents_reduction'], 25.5)
            self.assertEqual(result['compliance_improvement'], 15.0)
            self.assertEqual(result['cost_benefit_ratio'], 3.5)
    
    def test_analyze_policy_impact(self):
        """Test analyzing policy impact"""
        analysis = self.service._analyze_policy_impact(days=90)
        
        self.assertIn('security_incidents_reduction', analysis)
        self.assertIn('compliance_improvement', analysis)
        self.assertIn('user_satisfaction', analysis)
        self.assertIn('operational_impact', analysis)
        self.assertIn('cost_benefit_ratio', analysis)
    
    def test_get_policy_user_feedback(self):
        """Test getting policy user feedback"""
        with patch('api.security.models.PolicyFeedback.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 25
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_policy_user_feedback(
                policy_type='password_policy'
            )
            
            self.assertEqual(result['count'], 25)
            self.assertEqual(len(result['feedback']), 2)
    
    def test_create_policy_feedback(self):
        """Test creating policy feedback"""
        feedback_data = {
            'policy_type': 'password_policy',
            'rating': 4,
            'comments': 'Policy is reasonable but could be more flexible',
            'suggestions': 'Allow longer passwords with fewer restrictions'
        }
        
        with patch('api.security.models.PolicyFeedback.objects.create') as mock_create:
            mock_feedback = MagicMock()
            mock_feedback.id = 'feedback-id'
            mock_create.return_value = mock_feedback
            
            result = self.service.create_policy_feedback(
                self.user.id,
                feedback_data
            )
            
            self.assertEqual(result, mock_feedback)
            mock_create.assert_called_once()
    
    def test_get_policy_training_status(self):
        """Test getting policy training status"""
        with patch('api.security.models.PolicyTraining.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 15
            mock_queryset.filter.return_value.count.return_value = 10
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_policy_training_status(self.user.id)
            
            self.assertEqual(result['total_trainings'], 15)
            self.assertEqual(result['completed_trainings'], 10)
            self.assertEqual(result['completion_rate'], 66.7)
    
    def test_assign_policy_training(self):
        """Test assigning policy training"""
        training_data = {
            'policy_type': 'password_policy',
            'training_type': 'mandatory',
            'due_date': timezone.now() + timedelta(days=30),
            'content': 'Password security best practices'
        }
        
        with patch('api.security.models.PolicyTraining.objects.create') as mock_create:
            mock_training = MagicMock()
            mock_training.id = 'training-id'
            mock_create.return_value = mock_training
            
            result = self.service.assign_policy_training(
                self.user.id,
                training_data
            )
            
            self.assertEqual(result, mock_training)
            mock_create.assert_called_once()
    
    def test_get_policy_automation_rules(self):
        """Test getting policy automation rules"""
        with patch('api.security.models.PolicyAutomationRule.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 5
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_policy_automation_rules()
            
            self.assertEqual(result['count'], 5)
            self.assertEqual(len(result['rules']), 2)
    
    def test_create_policy_automation_rule(self):
        """Test creating policy automation rule"""
        rule_data = {
            'name': 'Password Expiration Notification',
            'policy_type': 'password_policy',
            'trigger_condition': 'password_age > 80 days',
            'action': 'send_notification',
            'is_active': True
        }
        
        with patch('api.security.models.PolicyAutomationRule.objects.create') as mock_create:
            mock_rule = MagicMock()
            mock_rule.id = 'rule-id'
            mock_create.return_value = mock_rule
            
            result = self.service.create_policy_automation_rule(rule_data)
            
            self.assertEqual(result, mock_rule)
            mock_create.assert_called_once()
    
    def test_execute_policy_automation_rules(self):
        """Test executing policy automation rules"""
        with patch.object(self.service, '_evaluate_automation_rules') as mock_evaluate:
            mock_evaluate.return_value = [
                {
                    'rule_id': 'rule-1',
                    'rule_name': 'Password Expiration Notification',
                    'matched_users': [self.user],
                    'actions': ['send_notification']
                }
            ]
            
            result = self.service.execute_policy_automation_rules()
            
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['rule_name'], 'Password Expiration Notification')
    
    def test_evaluate_automation_rules(self):
        """Test evaluating automation rules"""
        with patch('api.security.models.PolicyAutomationRule.objects.filter') as mock_filter:
            mock_rule = MagicMock()
            mock_rule.trigger_condition = 'password_age > 80 days'
            mock_rule.action = 'send_notification'
            mock_rule.is_active = True
            mock_filter.return_value = [mock_rule]
            
            result = self.service._evaluate_automation_rules()
            
            self.assertIsInstance(result, list)
    
    def test_get_policy_compliance_dashboard(self):
        """Test getting policy compliance dashboard"""
        with patch.object(self.service, '_build_compliance_dashboard') as mock_dashboard:
            mock_dashboard.return_value = {
                'overview': {
                    'total_policies': 150,
                    'compliant_policies': 127,
                    'compliance_rate': 84.7,
                    'high_priority_violations': 5
                },
                'metrics': {
                    'policy_type_distribution': {
                        'password_policy': 50,
                        'session_policy': 40,
                        'access_policy': 30,
                        'privacy_policy': 30
                    },
                    'compliance_trends': [
                        {'date': '2023-01-01', 'rate': 82.0},
                        {'date': '2023-01-02', 'rate': 84.7}
                    ]
                },
                'alerts': [
                    {
                        'type': 'high_violation_rate',
                        'message': 'Session policy violations increased by 20%',
                        'severity': 'warning'
                    }
                ]
            }
            
            result = self.service.get_policy_compliance_dashboard()
            
            self.assertEqual(result['overview']['total_policies'], 150)
            self.assertEqual(result['overview']['compliance_rate'], 84.7)
            self.assertIn('metrics', result)
            self.assertIn('alerts', result)
    
    def test_build_compliance_dashboard(self):
        """Test building compliance dashboard"""
        dashboard = self.service._build_compliance_dashboard()
        
        self.assertIn('overview', dashboard)
        self.assertIn('metrics', dashboard)
        self.assertIn('alerts', dashboard)
        
        self.assertIn('total_policies', dashboard['overview'])
        self.assertIn('compliant_policies', dashboard['overview'])
        self.assertIn('compliance_rate', dashboard['overview'])
    
    def test_export_policy_compliance_report(self):
        """Test exporting policy compliance report"""
        with patch.object(self.service, '_generate_compliance_report') as mock_report:
            mock_report.return_value = {
                'executive_summary': {
                    'total_policies': 150,
                    'compliance_rate': 84.7,
                    'high_priority_violations': 5,
                    'risk_level': 'medium'
                },
                'detailed_analysis': {
                    'policy_type_compliance': {
                        'password_policy': 90.0,
                        'session_policy': 75.0,
                        'access_policy': 88.0
                    },
                    'violation_analysis': {
                        'total_violations': 23,
                        'violation_types': {}
                    }
                },
                'recommendations': [
                    'Strengthen session policy enforcement',
                    'Increase policy training frequency'
                ]
            }
            
            result = self.service.export_policy_compliance_report(format='json')
            
            self.assertEqual(result['executive_summary']['total_policies'], 150)
            self.assertEqual(result['executive_summary']['compliance_rate'], 84.7)
            self.assertIn('detailed_analysis', result)
            self.assertIn('recommendations', result)
    
    def test_generate_compliance_report(self):
        """Test generating compliance report"""
        report = self.service._generate_compliance_report()
        
        self.assertIn('executive_summary', report)
        self.assertIn('detailed_analysis', report)
        self.assertIn('recommendations', report)
        
        self.assertIn('total_policies', report['executive_summary'])
        self.assertIn('compliance_rate', report['executive_summary'])
    
    def test_get_policy_change_impact_assessment(self):
        """Test getting policy change impact assessment"""
        proposed_change = {
            'policy_type': 'password_policy',
            'current_value': {'min_length': 8},
            'proposed_value': {'min_length': 12},
            'change_reason': 'Enhanced security requirements'
        }
        
        with patch.object(self.service, '_assess_policy_change_impact') as mock_assess:
            mock_assess.return_value = {
                'impact_level': 'medium',
                'affected_users': 150,
                'implementation_effort': 'medium',
                'expected_benefits': [
                    '25% improvement in password security',
                    'Reduced risk from weak passwords'
                ],
                'potential_challenges': [
                    'User resistance to longer passwords',
                    'Increased support requests'
                ],
                'recommendation': 'Implement with gradual rollout'
            }
            
            result = self.service.get_policy_change_impact_assessment(proposed_change)
            
            self.assertEqual(result['impact_level'], 'medium')
            self.assertEqual(result['affected_users'], 150)
            self.assertIn('expected_benefits', result)
            self.assertIn('potential_challenges', result)
    
    def test_assess_policy_change_impact(self):
        """Test assessing policy change impact"""
        proposed_change = {
            'policy_type': 'password_policy',
            'current_value': {'min_length': 8},
            'proposed_value': {'min_length': 12}
        }
        
        assessment = self.service._assess_policy_change_impact(proposed_change)
        
        self.assertIn('impact_level', assessment)
        self.assertIn('affected_users', assessment)
        self.assertIn('implementation_effort', assessment)
        self.assertIn('expected_benefits', assessment)
        self.assertIn('potential_challenges', assessment)
    
    def test_get_policy_user_segmentation(self):
        """Test getting policy user segmentation"""
        with patch.object(self.service, '_analyze_user_policy_segments') as mock_segments:
            mock_segments.return_value = {
                'segments': [
                    {
                        'segment_name': 'high_compliance',
                        'user_count': 750,
                        'percentage': 75.0,
                        'characteristics': [
                            'High policy compliance rate',
                            'Regular policy training completion',
                            'Low violation history'
                        ]
                    },
                    {
                        'segment_name': 'medium_compliance',
                        'user_count': 200,
                        'percentage': 20.0,
                        'characteristics': [
                            'Moderate compliance rate',
                            'Occasional policy violations',
                            'Partial training completion'
                        ]
                    },
                    {
                        'segment_name': 'low_compliance',
                        'user_count': 50,
                        'percentage': 5.0,
                        'characteristics': [
                            'Low compliance rate',
                            'Frequent policy violations',
                            'Minimal training engagement'
                        ]
                    }
                ],
                'recommendations': [
                    'Target low compliance segment with additional training',
                    'Maintain engagement with high compliance segment'
                ]
            }
            
            result = self.service.get_policy_user_segmentation()
            
            self.assertEqual(len(result['segments']), 3)
            self.assertEqual(result['segments'][0]['segment_name'], 'high_compliance')
            self.assertEqual(result['segments'][0]['user_count'], 750)
    
    def test_analyze_user_policy_segments(self):
        """Test analyzing user policy segments"""
        segments = self.service._analyze_user_policy_segments()
        
        self.assertIn('segments', segments)
        self.assertIn('recommendations', segments)
        
        for segment in segments['segments']:
            self.assertIn('segment_name', segment)
            self.assertIn('user_count', segment)
            self.assertIn('percentage', segment)
            self.assertIn('characteristics', segment)
    
    def test_get_policy_effectiveness_correlation(self):
        """Test getting policy effectiveness correlation"""
        with patch.object(self.service, '_analyze_policy_correlations') as mock_correlations:
            mock_correlations.return_value = {
                'correlations': [
                    {
                        'policy_type': 'password_policy',
                        'correlated_metric': 'security_incidents',
                        'correlation_coefficient': -0.75,
                        'significance': 'high',
                        'interpretation': 'Stronger password policies correlate with fewer security incidents'
                    },
                    {
                        'policy_type': 'session_policy',
                        'correlated_metric': 'unauthorized_access',
                        'correlation_coefficient': -0.60,
                        'significance': 'medium',
                        'interpretation': 'Stricter session policies correlate with reduced unauthorized access'
                    }
                ],
                'insights': [
                    'Password policies have the strongest impact on security outcomes',
                    'Session policies show moderate effectiveness'
                ]
            }
            
            result = self.service.get_policy_effectiveness_correlation()
            
            self.assertEqual(len(result['correlations']), 2)
            self.assertEqual(result['correlations'][0]['policy_type'], 'password_policy')
            self.assertEqual(result['correlations'][0]['correlation_coefficient'], -0.75)
    
    def test_analyze_policy_correlations(self):
        """Test analyzing policy correlations"""
        correlations = self.service._analyze_policy_correlations()
        
        self.assertIn('correlations', correlations)
        self.assertIn('insights', correlations)
        
        for correlation in correlations['correlations']:
            self.assertIn('policy_type', correlation)
            self.assertIn('correlated_metric', correlation)
            self.assertIn('correlation_coefficient', correlation)
            self.assertIn('significance', correlation)
            self.assertIn('interpretation', correlation)