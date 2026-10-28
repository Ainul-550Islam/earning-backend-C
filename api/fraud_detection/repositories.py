# =============================================================================
# fraud_detection/repositories.py
# =============================================================================
"""
Repository Layer for Fraud Detection System.

Implements Clean Architecture pattern with SHA-256 Hash Chaining
for all model operations to ensure data integrity and auditability.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, TypeVar, Generic

from django.db import models, transaction
from django.db.models import Q, F, Count, Avg, Max, Min, Sum, Prefetch
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

from api.fraud_detection.models import (
    FraudRule, FraudCase, FraudAlert, FraudCaseEvidence,
    FraudRiskProfile, DeviceFingerprint, FraudSuspiciousIP,
    FraudPattern
)
from api.fraud_detection.constants import HASH_ALGORITHM, HASH_LENGTH
from api.fraud_detection.exceptions import RepositoryError, IntegrityViolationError
from api.fraud_detection.encryption import generate_integrity_hash, verify_data_integrity


logger = logging.getLogger(__name__)

T = TypeVar('T', bound=models.Model)


class BaseRepository(Generic[T]):
    """
    Base repository with SHA-256 Hash Chaining for data integrity.
    
    All model operations include hash chaining to ensure data integrity
    and provide auditability for fraud detection operations.
    """
    
    def __init__(self, model_class: type[T]):
        """
        Initialize repository with model class.
        
        Args:
            model_class: Django model class to manage
        """
        self.model_class = model_class
        self.model_name = model_class.__name__.lower()
    
    def _generate_operation_hash(self, operation: str, data: Dict[str, Any], 
                                previous_hash: Optional[str] = None) -> str:
        """
        Generate SHA-256 hash for operation with chain linking.
        
        Args:
            operation: Operation type (create, update, delete)
            data: Operation data
            previous_hash: Previous hash in chain for chaining
            
        Returns:
            SHA-256 hash for operation
        """
        # Create comprehensive hash data with full audit trail
        hash_data = {
            'operation': operation,
            'model': self.model_name,
            'timestamp': timezone.now().isoformat(),
            'data': data,
            'previous_hash': previous_hash or 'genesis',
            'operation_id': f"{operation}_{self.model_name}_{timezone.now().timestamp()}"
        }
        
        # Generate hash with salt for additional security
        hash_string = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
        base_hash = hashlib.sha256(hash_string.encode('utf-8')).hexdigest()
        
        # Apply second round of hashing for chain integrity
        chain_data = f"{base_hash}{previous_hash or 'genesis'}{timezone.now().isoformat()}"
        return hashlib.sha256(chain_data.encode('utf-8')).hexdigest()
    
    def _verify_model_integrity(self, instance: T) -> bool:
        """
        Verify model instance integrity using stored hash.
        
        Args:
            instance: Model instance to verify
            
        Returns:
            True if integrity verified, False otherwise
        """
        if not hasattr(instance, 'integrity_hash'):
            return True  # Model doesn't support integrity checking
        
        # Get current data without hash field
        data = {}
        for field in instance._meta.fields:
            if field.name != 'integrity_hash':
                value = getattr(instance, field.name)
                if isinstance(value, (datetime, timezone.datetime)):
                    value = value.isoformat()
                elif hasattr(value, 'pk'):  # Foreign key
                    value = value.pk
                data[field.name] = value
        
        expected_hash = generate_integrity_hash(data)
        actual_hash = instance.integrity_hash
        
        return expected_hash == actual_hash
    
    def _update_integrity_hash(self, instance: T) -> None:
        """
        Update integrity hash for model instance.
        
        Args:
            instance: Model instance to update hash for
        """
        if not hasattr(instance, 'integrity_hash'):
            return  # Model doesn't support integrity checking
        
        # Get current data without hash field
        data = {}
        for field in instance._meta.fields:
            if field.name != 'integrity_hash':
                value = getattr(instance, field.name)
                if isinstance(value, (datetime, timezone.datetime)):
                    value = value.isoformat()
                elif hasattr(value, 'pk'):  # Foreign key
                    value = value.pk
                data[field.name] = value
        
        instance.integrity_hash = generate_integrity_hash(data)
    
    def create(self, **kwargs) -> T:
        """
        Create new model instance with integrity hash.
        
        Args:
            **kwargs: Model field values
            
        Returns:
            Created model instance
            
        Raises:
            RepositoryError: If creation fails
        """
        try:
            with transaction.atomic():
                # Generate operation hash
                operation_hash = self._generate_operation_hash('create', kwargs)
                
                # Create instance
                instance = self.model_class(**kwargs)
                
                # Update integrity hash if supported
                self._update_integrity_hash(instance)
                
                # Add operation hash to metadata if supported
                if hasattr(instance, 'metadata'):
                    if not instance.metadata:
                        instance.metadata = {}
                    instance.metadata['operation_hash'] = operation_hash
                
                instance.save()
                
                logger.info(f"Created {self.model_name} instance with hash: {operation_hash}")
                return instance
                
        except Exception as e:
            logger.error(f"Failed to create {self.model_name}: {e}")
            raise RepositoryError(f"Failed to create {self.model_name}: {e}")
    
    def get_by_id(self, instance_id: Union[int, str]) -> Optional[T]:
        """
        Get model instance by ID with integrity verification.
        
        Args:
            instance_id: Instance ID
            
        Returns:
            Model instance or None if not found
            
        Raises:
            IntegrityViolationError: If integrity verification fails
        """
        try:
            instance = self.model_class.objects.get(pk=instance_id)
            
            # Verify integrity
            if not self._verify_model_integrity(instance):
                logger.error(f"Integrity violation detected for {self.model_name} ID: {instance_id}")
                raise IntegrityViolationError(
                    f"Integrity violation detected for {self.model_name} ID: {instance_id}"
                )
            
            return instance
            
        except ObjectDoesNotExist:
            return None
        except Exception as e:
            if isinstance(e, IntegrityViolationError):
                raise
            logger.error(f"Failed to get {self.model_name} by ID: {e}")
            raise RepositoryError(f"Failed to get {self.model_name} by ID: {e}")
    
    def update(self, instance_id: Union[int, str], **kwargs) -> Optional[T]:
        """
        Update model instance with integrity hash update.
        
        Args:
            instance_id: Instance ID
            **kwargs: Fields to update
            
        Returns:
            Updated model instance or None if not found
            
        Raises:
            RepositoryError: If update fails
            IntegrityViolationError: If integrity verification fails
        """
        try:
            with transaction.atomic():
                instance = self.get_by_id(instance_id)
                if not instance:
                    return None
                
                # Get previous hash for chaining
                previous_hash = getattr(instance, 'integrity_hash', None)
                
                # Generate operation hash
                operation_hash = self._generate_operation_hash('update', kwargs, previous_hash)
                
                # Update instance
                for field, value in kwargs.items():
                    setattr(instance, field, value)
                
                # Update integrity hash
                self._update_integrity_hash(instance)
                
                # Add operation hash to metadata if supported
                if hasattr(instance, 'metadata'):
                    if not instance.metadata:
                        instance.metadata = {}
                    instance.metadata['operation_hash'] = operation_hash
                    instance.metadata['previous_hash'] = previous_hash
                
                instance.save()
                
                logger.info(f"Updated {self.model_name} instance with hash: {operation_hash}")
                return instance
                
        except Exception as e:
            if isinstance(e, (IntegrityViolationError, RepositoryError)):
                raise
            logger.error(f"Failed to update {self.model_name}: {e}")
            raise RepositoryError(f"Failed to update {self.model_name}: {e}")
    
    def delete(self, instance_id: Union[int, str]) -> bool:
        """
        Delete model instance with operation logging.
        
        Args:
            instance_id: Instance ID
            
        Returns:
            True if deleted, False if not found
            
        Raises:
            RepositoryError: If deletion fails
        """
        try:
            with transaction.atomic():
                instance = self.get_by_id(instance_id)
                if not instance:
                    return False
                
                # Get previous hash for chaining
                previous_hash = getattr(instance, 'integrity_hash', None)
                
                # Generate operation hash
                operation_hash = self._generate_operation_hash('delete', {'id': instance_id}, previous_hash)
                
                # Log deletion before actual deletion
                logger.info(f"Deleting {self.model_name} instance with hash: {operation_hash}")
                
                # Delete instance
                instance.delete()
                
                return True
                
        except Exception as e:
            if isinstance(e, (IntegrityViolationError, RepositoryError)):
                raise
            logger.error(f"Failed to delete {self.model_name}: {e}")
            raise RepositoryError(f"Failed to delete {self.model_name}: {e}")
    
    def list(self, filters: Optional[Dict[str, Any]] = None, 
             order_by: Optional[str] = None, limit: Optional[int] = None) -> List[T]:
        """
        List model instances with optional filtering and ordering.
        
        Args:
            filters: Filter criteria
            order_by: Ordering field
            limit: Maximum number of results
            
        Returns:
            List of model instances
        """
        try:
            queryset = self.model_class.objects.all()
            
            if filters:
                queryset = queryset.filter(**filters)
            
            if order_by:
                queryset = queryset.order_by(order_by)
            
            if limit:
                queryset = queryset[:limit]
            
            # Verify integrity for each instance
            verified_instances = []
            for instance in queryset:
                if self._verify_model_integrity(instance):
                    verified_instances.append(instance)
                else:
                    logger.warning(f"Skipping {self.model_name} instance due to integrity violation: {instance.pk}")
            
            return verified_instances
            
        except Exception as e:
            logger.error(f"Failed to list {self.model_name}: {e}")
            raise RepositoryError(f"Failed to list {self.model_name}: {e}")
    
    def bulk_create(self, instances_data: List[Dict[str, Any]]) -> List[T]:
        """
        Bulk create model instances with integrity hashes.
        
        Args:
            instances_data: List of instance data dictionaries
            
        Returns:
            List of created model instances
            
        Raises:
            RepositoryError: If bulk creation fails
        """
        try:
            with transaction.atomic():
                instances = []
                operation_hashes = []
                
                for data in instances_data:
                    # Generate operation hash
                    operation_hash = self._generate_operation_hash('bulk_create', data)
                    operation_hashes.append(operation_hash)
                    
                    # Create instance
                    instance = self.model_class(**data)
                    self._update_integrity_hash(instance)
                    
                    # Add operation hash to metadata if supported
                    if hasattr(instance, 'metadata'):
                        if not instance.metadata:
                            instance.metadata = {}
                        instance.metadata['operation_hash'] = operation_hash
                    
                    instances.append(instance)
                
                # Bulk create
                created_instances = self.model_class.objects.bulk_create(instances)
                
                logger.info(f"Bulk created {len(created_instances)} {self.model_name} instances")
                return created_instances
                
        except Exception as e:
            logger.error(f"Failed to bulk create {self.model_name}: {e}")
            raise RepositoryError(f"Failed to bulk create {self.model_name}: {e}")
    
    def bulk_update(self, instances_data: List[Dict[str, Any]], 
                    field_names: List[str]) -> int:
        """
        Bulk update model instances with integrity hash updates.
        
        Args:
            instances_data: List of instance data with IDs
            field_names: List of field names to update
            
        Returns:
            Number of updated instances
            
        Raises:
            RepositoryError: If bulk update fails
        """
        try:
            with transaction.atomic():
                instances = []
                
                for data in instances_data:
                    instance_id = data.get('id') or data.get('pk')
                    if not instance_id:
                        continue
                    
                    instance = self.get_by_id(instance_id)
                    if not instance:
                        continue
                    
                    # Update fields
                    for field in field_names:
                        if field in data:
                            setattr(instance, field, data[field])
                    
                    # Update integrity hash
                    self._update_integrity_hash(instance)
                    
                    instances.append(instance)
                
                # Bulk update
                updated_count = self.model_class.objects.bulk_update(instances, field_names + ['integrity_hash'])
                
                logger.info(f"Bulk updated {updated_count} {self.model_name} instances")
                return updated_count
                
        except Exception as e:
            logger.error(f"Failed to bulk update {self.model_name}: {e}")
            raise RepositoryError(f"Failed to bulk update {self.model_name}: {e}")


class FraudRuleRepository(BaseRepository[FraudRule]):
    """Repository for FraudRule model operations."""
    
    def __init__(self):
        super().__init__(FraudRule)
    
    def get_active_rules(self, rule_type: Optional[str] = None) -> List[FraudRule]:
        """
        Get all active fraud rules, optionally filtered by type.
        
        Args:
            rule_type: Optional rule type filter
            
        Returns:
            List of active fraud rules
        """
        filters = {'is_active': True}
        if rule_type:
            filters['rule_type'] = rule_type
        
        return self.list(filters=filters, order_by='-priority')
    
    def get_rules_by_severity(self, severity: str) -> List[FraudRule]:
        """
        Get fraud rules by severity level.
        
        Args:
            severity: Severity level
            
        Returns:
            List of fraud rules with specified severity
        """
        return self.list(filters={'severity': severity, 'is_active': True}, order_by='-priority')
    
    def get_rules_for_user(self, user_id: Union[int, str]) -> List[FraudRule]:
        """
        Get fraud rules applicable to specific user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of applicable fraud rules
        """
        return self.list(
            filters={'is_active': True, 'applicable_users__contains': str(user_id)},
            order_by='-priority'
        )


class FraudCaseRepository(BaseRepository[FraudCase]):
    """Repository for FraudCase model operations."""
    
    def __init__(self):
        super().__init__(FraudCase)
    
    def get_cases_by_status(self, status: str) -> List[FraudCase]:
        """
        Get fraud cases by status.
        
        Args:
            status: Case status
            
        Returns:
            List of fraud cases with specified status
        """
        return self.list(filters={'status': status}, order_by='-created_at')
    
    def get_cases_by_user(self, user_id: Union[int, str]) -> List[FraudCase]:
        """
        Get fraud cases for specific user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of fraud cases for user
        """
        return self.list(filters={'user_id': user_id}, order_by='-created_at')
    
    def get_high_risk_cases(self, min_risk_score: int = 80) -> List[FraudCase]:
        """
        Get high risk fraud cases.
        
        Args:
            min_risk_score: Minimum risk score threshold
            
        Returns:
            List of high risk fraud cases
        """
        return self.list(
            filters={'risk_score__gte': min_risk_score},
            order_by='-risk_score'
        )
    
    def get_open_cases_older_than(self, hours: int = 24) -> List[FraudCase]:
        """
        Get open cases older than specified hours.
        
        Args:
            hours: Hours threshold
            
        Returns:
            List of old open cases
        """
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.list(
            filters={
                'status__in': ['open', 'investigating'],
                'created_at__lt': cutoff_time
            },
            order_by='created_at'
        )


class FraudAlertRepository(BaseRepository[FraudAlert]):
    """Repository for FraudAlert model operations."""
    
    def __init__(self):
        super().__init__(FraudAlert)
    
    def get_alerts_by_type(self, alert_type: str) -> List[FraudAlert]:
        """
        Get fraud alerts by type.
        
        Args:
            alert_type: Alert type
            
        Returns:
            List of fraud alerts with specified type
        """
        return self.list(filters={'alert_type': alert_type}, order_by='-created_at')
    
    def get_unacknowledged_alerts(self) -> List[FraudAlert]:
        """
        Get unacknowledged fraud alerts.
        
        Returns:
            List of unacknowledged fraud alerts
        """
        return self.list(filters={'acknowledged': False}, order_by='-created_at')
    
    def get_alerts_for_user(self, user_id: Union[int, str]) -> List[FraudAlert]:
        """
        Get fraud alerts for specific user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of fraud alerts for user
        """
        return self.list(filters={'user_id': user_id}, order_by='-created_at')
    
    def get_recent_alerts(self, hours: int = 24) -> List[FraudAlert]:
        """
        Get recent fraud alerts within specified hours.
        
        Args:
            hours: Hours threshold
            
        Returns:
            List of recent fraud alerts
        """
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.list(filters={'created_at__gte': cutoff_time}, order_by='-created_at')


class FraudRiskProfileRepository(BaseRepository[FraudRiskProfile]):
    """Repository for FraudRiskProfile model operations."""
    
    def __init__(self):
        super().__init__(FraudRiskProfile)
    
    def get_profile_by_user(self, user_id: Union[int, str]) -> Optional[FraudRiskProfile]:
        """
        Get risk profile for specific user.
        
        Args:
            user_id: User ID
            
        Returns:
            User risk profile or None
        """
        try:
            return self.model_class.objects.get(user_id=user_id)
        except ObjectDoesNotExist:
            return None
    
    def get_high_risk_users(self, min_score: int = 70) -> List[FraudRiskProfile]:
        """
        Get users with high risk scores.
        
        Args:
            min_score: Minimum risk score
            
        Returns:
            List of high risk user profiles
        """
        return self.list(filters={'risk_score__gte': min_score}, order_by='-risk_score')
    
    def update_risk_score(self, user_id: Union[int, str], new_score: int, 
                         reason: Optional[str] = None) -> Optional[FraudRiskProfile]:
        """
        Update user risk score.
        
        Args:
            user_id: User ID
            new_score: New risk score
            reason: Update reason
            
        Returns:
            Updated risk profile or None
        """
        profile = self.get_profile_by_user(user_id)
        if not profile:
            # Create new profile
            return self.create(user_id=user_id, risk_score=new_score, update_reason=reason)
        
        return self.update(
            profile.pk,
            risk_score=new_score,
            update_reason=reason,
            last_updated=timezone.now()
        )


class DeviceFingerprintRepository(BaseRepository[DeviceFingerprint]):
    """Repository for DeviceFingerprint model operations."""
    
    def __init__(self):
        super().__init__(DeviceFingerprint)
    
    def get_fingerprint_by_hash(self, device_hash: str) -> Optional[DeviceFingerprint]:
        """
        Get device fingerprint by hash.
        
        Args:
            device_hash: Device fingerprint hash
            
        Returns:
            Device fingerprint or None
        """
        try:
            return self.model_class.objects.get(device_hash=device_hash)
        except ObjectDoesNotExist:
            return None
    
    def get_fingerprints_for_user(self, user_id: Union[int, str]) -> List[DeviceFingerprint]:
        """
        Get all device fingerprints for user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of device fingerprints for user
        """
        return self.list(filters={'user_id': user_id}, order_by='-last_seen')
    
    def get_suspicious_devices(self, min_user_count: int = 3) -> List[DeviceFingerprint]:
        """
        Get devices used by multiple users (potential fraud).
        
        Args:
            min_user_count: Minimum number of users
            
        Returns:
            List of suspicious device fingerprints
        """
        return self.list(
            filters={'user_count__gte': min_user_count},
            order_by='-user_count'
        )
    
    def update_device_usage(self, device_hash: str, user_id: Union[int, str]) -> DeviceFingerprint:
        """
        Update device usage statistics.
        
        Args:
            device_hash: Device fingerprint hash
            user_id: User ID
            
        Returns:
            Updated device fingerprint
        """
        fingerprint = self.get_fingerprint_by_hash(device_hash)
        if not fingerprint:
            # Create new fingerprint
            return self.create(
                device_hash=device_hash,
                user_id=user_id,
                user_count=1,
                first_seen=timezone.now(),
                last_seen=timezone.now()
            )
        
        # Update existing fingerprint
        new_user_count = fingerprint.user_count
        if fingerprint.user_id != user_id:
            new_user_count += 1
        
        return self.update(
            fingerprint.pk,
            user_id=user_id,
            user_count=new_user_count,
            last_seen=timezone.now()
        )


class FraudSuspiciousIPRepository(BaseRepository[FraudSuspiciousIP]):
    """Repository for FraudSuspiciousIP model operations."""
    
    def __init__(self):
        super().__init__(FraudSuspiciousIP)
    
    def get_suspicious_ip(self, ip_address: str) -> Optional[FraudSuspiciousIP]:
        """
        Get suspicious IP record.
        
        Args:
            ip_address: IP address
            
        Returns:
            Suspicious IP record or None
        """
        try:
            return self.model_class.objects.get(ip_address=ip_address)
        except ObjectDoesNotExist:
            return None
    
    def get_high_risk_ips(self, min_risk_score: int = 70) -> List[FraudSuspiciousIP]:
        """
        Get high risk IP addresses.
        
        Args:
            min_risk_score: Minimum risk score
            
        Returns:
            List of high risk IP addresses
        """
        return self.list(filters={'risk_score__gte': min_risk_score}, order_by='-risk_score')
    
    def update_ip_risk(self, ip_address: str, risk_score: int, 
                      reason: Optional[str] = None) -> FraudSuspiciousIP:
        """
        Update IP address risk score.
        
        Args:
            ip_address: IP address
            risk_score: New risk score
            reason: Update reason
            
        Returns:
            Updated suspicious IP record
        """
        suspicious_ip = self.get_suspicious_ip(ip_address)
        if not suspicious_ip:
            # Create new record
            return self.create(
                ip_address=ip_address,
                risk_score=risk_score,
                reason=reason,
                first_seen=timezone.now(),
                last_seen=timezone.now()
            )
        
        # Update existing record
        return self.update(
            suspicious_ip.pk,
            risk_score=risk_score,
            reason=reason,
            last_seen=timezone.now()
        )


# Repository instances for dependency injection
fraud_rule_repository = FraudRuleRepository()
fraud_case_repository = FraudCaseRepository()
fraud_alert_repository = FraudAlertRepository()
fraud_risk_profile_repository = FraudRiskProfileRepository()
fraud_device_fingerprint_repository = DeviceFingerprintRepository()
fraud_suspicious_ip_repository = FraudSuspiciousIPRepository()


def get_repository(model_name: str) -> BaseRepository:
    """
    Get repository instance by model name.
    
    Args:
        model_name: Model name (lowercase)
        
    Returns:
        Repository instance
        
    Raises:
        RepositoryError: If repository not found
    """
    repository_map = {
        'fraudrule': fraud_rule_repository,
        'fraudcase': fraud_case_repository,
        'fraudalert': fraud_alert_repository,
        'fraudriskprofile': fraud_risk_profile_repository,
        'frauddevicefingerprint': fraud_device_fingerprint_repository,
        'fraudsuspiciousip': fraud_suspicious_ip_repository,
    }
    
    repository = repository_map.get(model_name.lower())
    if not repository:
        raise RepositoryError(f"No repository found for model: {model_name}")
    
    return repository
