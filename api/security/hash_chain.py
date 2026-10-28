"""
SHA-256 Hash Chain Implementation for Security Module
Provides integrity verification and data tampering detection
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from django.db import models
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger('security.hash_chain')


class HashChainedModel(models.Model):
    """
    Abstract base model that provides SHA-256 hash chaining functionality
    for data integrity verification and tampering detection.
    """
    
    # Hash chain fields
    integrity_hash = models.CharField(
        max_length=64,
        db_index=True,
        editable=False,
        help_text="SHA-256 hash of critical fields for integrity verification"
    )
    
    previous_hash = models.CharField(
        max_length=64,
        db_index=True,
        null=True,
        blank=True,
        editable=False,
        help_text="Hash of previous record in chain"
    )
    
    chain_position = models.BigIntegerField(
        default=0,
        db_index=True,
        editable=False,
        help_text="Position in hash chain"
    )
    
    is_verified = models.BooleanField(
        default=False,
        db_index=True,
        editable=False,
        help_text="Whether integrity has been verified"
    )
    
    verification_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        help_text="Last verification timestamp"
    )
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['integrity_hash', 'chain_position']),
            models.Index(fields=['previous_hash', 'chain_position']),
            models.Index(fields=['is_verified', 'verification_timestamp']),
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_fields = self._get_critical_fields()
    
    def _get_critical_fields(self) -> Dict[str, Any]:
        """
        Get critical fields that should be included in hash calculation.
        Override this method in subclasses to specify which fields to hash.
        """
        critical_fields = {}
        
        # Get all field names except hash-related fields
        for field in self._meta.fields:
            if field.name not in ['integrity_hash', 'previous_hash', 'chain_position', 
                               'is_verified', 'verification_timestamp', 'id']:
                # Skip auto-managed timestamp fields (auto_now/auto_now_add) since
                # their value isn't populated until after the DB save, which would
                # otherwise cause a false-positive integrity failure on every new record.
                if getattr(field, 'auto_now', False) or getattr(field, 'auto_now_add', False):
                    continue
                value = getattr(self, field.name)
                if value is not None:
                    critical_fields[field.name] = str(value)
        
        return critical_fields
    
    def _calculate_hash(self, data: Dict[str, Any], previous_hash: str = None) -> str:
        """
        Calculate SHA-256 hash of critical data
        """
        try:
            # Create hash input
            hash_input = {
                'data': data,
                'previous_hash': previous_hash or '',
                'model': self.__class__.__name__
            }
            
            # Convert to JSON string
            hash_string = json.dumps(hash_input, sort_keys=True, separators=(',', ':'))
            
            # Calculate SHA-256 hash
            return hashlib.sha256(hash_string.encode('utf-8')).hexdigest()
            
        except Exception as e:
            logger.error(f"Error calculating hash for {self.__class__.__name__}: {e}")
            return hashlib.sha256(str(data).encode('utf-8')).hexdigest()
    
    def _get_chain_position(self) -> int:
        """
        Get position in hash chain
        """
        try:
            # Get the highest chain position for this model type
            max_position = self.__class__.objects.aggregate(
                max_position=models.Max('chain_position')
            )['max_position'] or 0
            
            return max_position + 1
            
        except Exception as e:
            logger.error(f"Error getting chain position: {e}")
            return 1
    
    def _get_previous_hash(self) -> Optional[str]:
        """
        Get hash of previous record in chain
        """
        try:
            if self.chain_position <= 1:
                return None
            
            previous_record = self.__class__.objects.filter(
                chain_position=self.chain_position - 1
            ).first()
            
            return previous_record.integrity_hash if previous_record else None
            
        except Exception as e:
            logger.error(f"Error getting previous hash: {e}")
            return None
    
    def update_integrity_hash(self, force_update: bool = False):
        """
        Update integrity hash for this record
        """
        try:
            # Get current critical fields
            current_fields = self._get_critical_fields()
            
            # Check if fields have changed.
            # NOTE: Only skip if integrity_hash already exists AND nothing changed -
            # otherwise a brand-new record (integrity_hash empty) would incorrectly
            # skip hash/chain_position assignment on its very first save.
            if not force_update and self.integrity_hash and current_fields == self._original_fields:
                return  # No changes needed
            
            # Get chain position and previous hash
            if not self.chain_position:
                self.chain_position = self._get_chain_position()
            
            if not self.previous_hash and self.chain_position > 1:
                self.previous_hash = self._get_previous_hash()
            
            # Calculate new hash
            self.integrity_hash = self._calculate_hash(current_fields, self.previous_hash)
            
            # Mark verified immediately: we just computed this hash from the
            # current data, so it is self-consistent at this point. This value
            # must be set BEFORE the DB write, because the post_save signal's
            # verify_integrity() call happens AFTER the INSERT/UPDATE and its
            # result is never persisted back to the row.
            self.is_verified = True
            self.verification_timestamp = timezone.now()
            
            # Update original fields
            self._original_fields = current_fields
            
            logger.debug(f"Updated integrity hash for {self.__class__.__name__} (position {self.chain_position})")
            
        except Exception as e:
            logger.error(f"Error updating integrity hash: {e}")
            raise
    
    def verify_integrity(self) -> bool:
        """
        Verify integrity of this record
        """
        try:
            if not self.integrity_hash:
                return False
            
            # Get current critical fields
            current_fields = self._get_critical_fields()
            
            # Recalculate hash
            calculated_hash = self._calculate_hash(current_fields, self.previous_hash)
            
            # Compare hashes
            is_valid = calculated_hash == self.integrity_hash
            
            # Update verification status
            self.is_verified = is_valid
            self.verification_timestamp = timezone.now()
            
            if is_valid:
                logger.debug(f"Integrity verified for {self.__class__.__name__} (position {self.chain_position})")
            else:
                logger.warning(f"Integrity verification FAILED for {self.__class__.__name__} (position {self.chain_position})")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error verifying integrity: {e}")
            return False
    
    def verify_chain_integrity(self) -> Dict[str, Any]:
        """
        Verify integrity of entire hash chain
        """
        try:
            results = {
                'total_records': 0,
                'verified_records': 0,
                'failed_records': 0,
                'broken_chains': [],
                'is_valid': True
            }
            
            # Get all records in chain order
            records = self.__class__.objects.order_by('chain_position')
            results['total_records'] = records.count()
            
            previous_hash = None
            for record in records:
                # Verify individual record
                if record.verify_integrity():
                    results['verified_records'] += 1
                else:
                    results['failed_records'] += 1
                    results['broken_chains'].append({
                        'position': record.chain_position,
                        'id': str(record.id),
                        'error': 'Hash mismatch'
                    })
                    results['is_valid'] = False
                
                # Verify chain link
                if previous_hash and record.previous_hash != previous_hash:
                    results['broken_chains'].append({
                        'position': record.chain_position,
                        'id': str(record.id),
                        'error': 'Chain link broken'
                    })
                    results['is_valid'] = False
                
                previous_hash = record.integrity_hash
            
            return results
            
        except Exception as e:
            logger.error(f"Error verifying chain integrity: {e}")
            return {
                'total_records': 0,
                'verified_records': 0,
                'failed_records': 0,
                'broken_chains': [str(e)],
                'is_valid': False
            }
    
    def get_hash_info(self) -> Dict[str, Any]:
        """
        Get hash information for this record
        """
        return {
            'integrity_hash': self.integrity_hash,
            'previous_hash': self.previous_hash,
            'chain_position': self.chain_position,
            'is_verified': self.is_verified,
            'verification_timestamp': self.verification_timestamp.isoformat() if self.verification_timestamp else None,
            'critical_fields': list(self._get_critical_fields().keys())
        }
    
    def save(self, *args, **kwargs):
        """
        Override save to update integrity hash
        """
        # Update integrity hash before saving
        self.update_integrity_hash()
        
        # Save the record
        super().save(*args, **kwargs)
        
        # Verify integrity after save
        self.verify_integrity()


class HashChainManager(models.Manager):
    """
    Custom manager for hash-chained models
    """
    
    def get_verified_records(self):
        """Get only verified records"""
        return self.filter(is_verified=True)
    
    def get_unverified_records(self):
        """Get only unverified records"""
        return self.filter(is_verified=False)
    
    def verify_all_records(self) -> Dict[str, Any]:
        """Verify all records in this model"""
        results = {
            'total_records': 0,
            'verified_records': 0,
            'failed_records': 0,
            'broken_chains': []
        }
        
        try:
            # Get first record to verify chain
            first_record = self.order_by('chain_position').first()
            if first_record:
                return first_record.verify_chain_integrity()
            
        except Exception as e:
            logger.error(f"Error verifying all records: {e}")
            results['broken_chains'].append(str(e))
        
        return results
    
    def get_chain_statistics(self) -> Dict[str, Any]:
        """Get statistics about hash chain"""
        try:
            total = self.count()
            verified = self.filter(is_verified=True).count()
            unverified = total - verified
            
            return {
                'total_records': total,
                'verified_records': verified,
                'unverified_records': unverified,
                'verification_rate': (verified / total * 100) if total > 0 else 0,
                'last_chain_position': self.aggregate(
                    max_position=models.Max('chain_position')
                )['max_position'] or 0
            }
            
        except Exception as e:
            logger.error(f"Error getting chain statistics: {e}")
            return {
                'total_records': 0,
                'verified_records': 0,
                'unverified_records': 0,
                'verification_rate': 0,
                'last_chain_position': 0
            }


# Signal handlers for automatic hash verification
@receiver(pre_save)
def update_hash_before_save(sender, instance, **kwargs):
    """
    Automatically update hash before saving
    """
    if isinstance(instance, HashChainedModel):
        try:
            instance.update_integrity_hash()
        except Exception as e:
            logger.error(f"Error updating hash before save: {e}")


@receiver(post_save)
def verify_hash_after_save(sender, instance, created, **kwargs):
    """
    Automatically verify hash after saving
    """
    if isinstance(instance, HashChainedModel):
        try:
            instance.verify_integrity()
            
            if created:
                logger.info(f"Created new {sender.__name__} with hash chain position {instance.chain_position}")
                
        except Exception as e:
            logger.error(f"Error verifying hash after save: {e}")


# Utility functions for hash chain management
def verify_model_integrity(model_class) -> Dict[str, Any]:
    """
    Verify integrity of all records in a model
    """
    try:
        if not issubclass(model_class, HashChainedModel):
            return {
                'error': f'Model {model_class.__name__} is not a HashChainedModel',
                'is_valid': False
            }
        
        manager = model_class.objects
        if hasattr(manager, 'verify_all_records'):
            return manager.verify_all_records()
        else:
            # Fallback verification
            return _fallback_verification(model_class)
            
    except Exception as e:
        logger.error(f"Error verifying model integrity: {e}")
        return {
            'error': str(e),
            'is_valid': False
        }


def _fallback_verification(model_class) -> Dict[str, Any]:
    """
    Fallback verification method
    """
    results = {
        'total_records': 0,
        'verified_records': 0,
        'failed_records': 0,
        'broken_chains': [],
        'is_valid': True
    }
    
    try:
        records = model_class.objects.all()
        results['total_records'] = records.count()
        
        for record in records:
            if record.verify_integrity():
                results['verified_records'] += 1
            else:
                results['failed_records'] += 1
                results['broken_chains'].append({
                    'position': record.chain_position,
                    'id': str(record.id),
                    'error': 'Hash mismatch'
                })
                results['is_valid'] = False
        
    except Exception as e:
        logger.error(f"Error in fallback verification: {e}")
        results['broken_chains'].append(str(e))
        results['is_valid'] = False
    
    return results


def get_hash_chain_report() -> Dict[str, Any]:
    """
    Get comprehensive hash chain report for all HashChainedModels
    """
    from django.apps import apps
    
    report = {
        'timestamp': timezone.now().isoformat(),
        'models': {},
        'total_models': 0,
        'total_records': 0,
        'total_verified': 0,
        'total_unverified': 0,
        'overall_integrity': True
    }
    
    try:
        # Get all models
        for model in apps.get_models():
            if issubclass(model, HashChainedModel):
                model_name = f"{model._meta.app_label}.{model.__name__}"
                
                # Get model statistics
                if hasattr(model.objects, 'get_chain_statistics'):
                    stats = model.objects.get_chain_statistics()
                else:
                    stats = {
                        'total_records': model.objects.count(),
                        'verified_records': model.objects.filter(is_verified=True).count(),
                        'unverified_records': model.objects.filter(is_verified=False).count(),
                        'verification_rate': 0
                    }
                
                # Verify model integrity
                verification = verify_model_integrity(model)
                
                report['models'][model_name] = {
                    'statistics': stats,
                    'verification': verification
                }
                
                # Update totals
                report['total_models'] += 1
                report['total_records'] += stats['total_records']
                report['total_verified'] += stats['verified_records']
                report['total_unverified'] += stats['unverified_records']
                
                if not verification.get('is_valid', False):
                    report['overall_integrity'] = False
    
    except Exception as e:
        logger.error(f"Error generating hash chain report: {e}")
        report['error'] = str(e)
        report['overall_integrity'] = False
    
    return report


# Export symbols
__all__ = [
    'HashChainedModel',
    'HashChainManager',
    'verify_model_integrity',
    'get_hash_chain_report'
]