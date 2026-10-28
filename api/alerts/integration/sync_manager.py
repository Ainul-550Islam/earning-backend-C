"""
Integration Sync Manager - Data conflict resolver for integration system
Provides safe data synchronization with existing alerts architecture
"""
import logging
import json
import hashlib
import time
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timezone
from django.utils import timezone as django_tz
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q

# Absolute imports to prevent ModuleNotFoundError
from api.alerts.models import AlertLog, AlertRule, Notification
from api.alerts.validators import validate_alert_rule_condition, validate_threshold_value
from api.alerts.integration.integ_handler import integration_handler
from api.alerts.integration.integ_adapter import integration_adapter
from api.alerts.integration.integ_registry import integration_registry
from api.alerts.integration.integ_constants import (
    CACHE_KEYS,
    CACHE_TIMEOUTS
)

logger = logging.getLogger(__name__)


class SyncConflict:
    """
    Represents a synchronization conflict
    """
    
    def __init__(self, conflict_type: str, entity_id: str, entity_type: str, 
                 source_data: Dict[str, Any], target_data: Dict[str, Any], 
                 conflicts: List[str]):
        self.conflict_type = conflict_type
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.source_data = source_data
        self.target_data = target_data
        self.conflicts = conflicts
        self.timestamp = django_tz.now().isoformat()
        self.resolved = False
        self.resolution_strategy = None
        self.resolution_data = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        """
        return {
            'conflict_type': self.conflict_type,
            'entity_id': self.entity_id,
            'entity_type': self.entity_type,
            'source_data': self.source_data,
            'target_data': self.target_data,
            'conflicts': self.conflicts,
            'timestamp': self.timestamp,
            'resolved': self.resolved,
            'resolution_strategy': self.resolution_strategy,
            'resolution_data': self.resolution_data
        }


class IntegrationSyncManager:
    """
    Synchronization manager for integration system
    Maintains existing data integrity and resolves conflicts
    """
    
    def __init__(self):
        self.sync_strategies = {}
        self.conflicts = []
        self.sync_stats = {
            'total_syncs': 0,
            'successful_syncs': 0,
            'failed_syncs': 0,
            'conflicts_resolved': 0,
            'conflicts_unresolved': 0,
            'last_sync': None
        }
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        """
        Register default conflict resolution strategies
        """
        self.sync_strategies = {
            'source_wins': self._source_wins_strategy,
            'target_wins': self._target_wins_strategy,
            'merge': self._merge_strategy,
            'timestamp_based': self._timestamp_based_strategy,
            'manual': self._manual_strategy
        }
    
    def sync_integration_data(self, source_system: str, target_system: str, 
                            data: Union[Dict[str, Any], List[Dict[str, Any]]], 
                            strategy: str = 'merge') -> Dict[str, Any]:
        """
        Synchronize integration data between systems
        Validates data using existing validators
        """
        try:
            self.sync_stats['total_syncs'] += 1
            self.sync_stats['last_sync'] = django_tz.now().isoformat()
            
            # Handle batch data
            if isinstance(data, list):
                return self._sync_batch_data(source_system, target_system, data, strategy)
            else:
                return self._sync_single_data(source_system, target_system, data, strategy)
                
        except Exception as e:
            logger.error(f"Error syncing integration data: {e}")
            self.sync_stats['failed_syncs'] += 1
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _sync_single_data(self, source_system: str, target_system: str, 
                         data: Dict[str, Any], strategy: str) -> Dict[str, Any]:
        """
        Synchronize single data item
        """
        try:
            # Validate source data
            validation_result = self._validate_sync_data(data)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': 'Data validation failed',
                    'validation_errors': validation_result['errors']
                }
            
            # Generate entity identifier
            entity_id = self._generate_entity_id(data)
            entity_type = self._determine_entity_type(data)
            
            # Check for existing data
            existing_data = self._get_existing_data(entity_id, entity_type)
            
            if existing_data:
                # Check for conflicts
                conflicts = self._detect_conflicts(data, existing_data)
                
                if conflicts:
                    # Resolve conflicts
                    resolution = self._resolve_conflicts(
                        data, existing_data, conflicts, strategy, entity_id, entity_type
                    )
                    
                    if resolution['success']:
                        # Apply resolution
                        result = self._apply_sync_resolution(
                            source_system, target_system, resolution['resolved_data']
                        )
                        
                        if result['success']:
                            self.sync_stats['successful_syncs'] += 1
                            self.sync_stats['conflicts_resolved'] += 1
                        else:
                            self.sync_stats['failed_syncs'] += 1
                            self.sync_stats['conflicts_unresolved'] += 1
                        
                        return result
                    else:
                        self.sync_stats['failed_syncs'] += 1
                        self.sync_stats['conflicts_unresolved'] += 1
                        return resolution
                else:
                    # No conflicts, proceed with sync
                    result = self._apply_sync_resolution(source_system, target_system, data)
                    
                    if result['success']:
                        self.sync_stats['successful_syncs'] += 1
                    else:
                        self.sync_stats['failed_syncs'] += 1
                    
                    return result
            else:
                # New data, proceed with sync
                result = self._apply_sync_resolution(source_system, target_system, data)
                
                if result['success']:
                    self.sync_stats['successful_syncs'] += 1
                else:
                    self.sync_stats['failed_syncs'] += 1
                
                return result
                
        except Exception as e:
            logger.error(f"Error syncing single data: {e}")
            self.sync_stats['failed_syncs'] += 1
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _sync_batch_data(self, source_system: str, target_system: str, 
                        data_list: List[Dict[str, Any]], strategy: str) -> Dict[str, Any]:
        """
        Synchronize batch data
        """
        try:
            results = []
            successful_count = 0
            failed_count = 0
            conflicts_count = 0
            
            for data in data_list:
                result = self._sync_single_data(source_system, target_system, data, strategy)
                results.append(result)
                
                if result.get('success', False):
                    successful_count += 1
                else:
                    failed_count += 1
                
                if 'conflicts' in result:
                    conflicts_count += len(result['conflicts'])
            
            return {
                'success': True,
                'batch_results': {
                    'total_items': len(data_list),
                    'successful_items': successful_count,
                    'failed_items': failed_count,
                    'conflicts_found': conflicts_count,
                    'success_rate': (successful_count / len(data_list)) * 100,
                    'results': results
                }
            }
            
        except Exception as e:
            logger.error(f"Error syncing batch data: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _validate_sync_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate synchronization data using existing validators
        """
        try:
            errors = []
            
            # Validate alert-related data
            if 'condition' in data:
                condition_validation = validate_alert_rule_condition(data['condition'])
                if not condition_validation['valid']:
                    errors.extend(condition_validation['errors'])
            
            if 'threshold' in data:
                threshold_validation = validate_threshold_value(data['threshold'])
                if not threshold_validation['valid']:
                    errors.extend(threshold_validation['errors'])
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating sync data: {e}")
            return {
                'valid': False,
                'errors': ['Validation error']
            }
    
    def _generate_entity_id(self, data: Dict[str, Any]) -> str:
        """
        Generate unique entity identifier
        """
        try:
            # Use existing ID if available
            if 'id' in data:
                return str(data['id'])
            
            # Generate hash-based ID
            entity_data = {
                'title': data.get('title', ''),
                'integration_type': data.get('integration_type', ''),
                'channel': data.get('channel', '')
            }
            
            data_string = json.dumps(entity_data, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(data_string.encode('utf-8')).hexdigest()[:16]
            
        except Exception as e:
            logger.error(f"Error generating entity ID: {e}")
            return f"unknown_{int(time.time())}"
    
    def _determine_entity_type(self, data: Dict[str, Any]) -> str:
        """
        Determine entity type from data
        """
        if 'integration_type' in data:
            return f"integration_{data['integration_type']}"
        elif 'channel' in data:
            return f"channel_{data['channel']}"
        elif 'alert_rule_id' in data:
            return 'alert_rule'
        elif 'alert_id' in data:
            return 'alert'
        else:
            return 'unknown'
    
    def _get_existing_data(self, entity_id: str, entity_type: str) -> Optional[Dict[str, Any]]:
        """
        Get existing data for entity
        """
        try:
            # Try to get from registry first
            integration = integration_registry.get_integration(entity_id)
            if integration:
                return integration
            
            # Try to get from database based on entity type
            if entity_type == 'alert_rule':
                try:
                    rule = AlertRule.objects.get(id=entity_id)
                    return {
                        'id': rule.id,
                        'title': rule.name,
                        'condition': rule.condition,
                        'threshold_value': rule.threshold_value,
                        'is_active': rule.is_active
                    }
                except AlertRule.DoesNotExist:
                    pass
            
            elif entity_type == 'alert':
                try:
                    alert = AlertLog.objects.get(id=entity_id)
                    return {
                        'id': alert.id,
                        'title': alert.title,
                        'severity': alert.severity,
                        'message': alert.message,
                        'is_resolved': alert.is_resolved
                    }
                except AlertLog.DoesNotExist:
                    pass
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting existing data: {e}")
            return None
    
    def _detect_conflicts(self, source_data: Dict[str, Any], target_data: Dict[str, Any]) -> List[str]:
        """
        Detect conflicts between source and target data
        """
        try:
            conflicts = []
            
            # Check for field conflicts
            all_fields = set(source_data.keys()) | set(target_data.keys())
            
            for field in all_fields:
                source_value = source_data.get(field)
                target_value = target_data.get(field)
                
                if source_value != target_value:
                    conflicts.append(f"Field '{field}' differs: source={source_value}, target={target_value}")
            
            return conflicts
            
        except Exception as e:
            logger.error(f"Error detecting conflicts: {e}")
            return [f"Conflict detection error: {str(e)}"]
    
    def _resolve_conflicts(self, source_data: Dict[str, Any], target_data: Dict[str, Any], 
                          conflicts: List[str], strategy: str, entity_id: str, 
                          entity_type: str) -> Dict[str, Any]:
        """
        Resolve conflicts using specified strategy
        """
        try:
            # Create conflict object
            conflict = SyncConflict(
                conflict_type='data_conflict',
                entity_id=entity_id,
                entity_type=entity_type,
                source_data=source_data,
                target_data=target_data,
                conflicts=conflicts
            )
            
            # Get resolution strategy
            resolution_func = self.sync_strategies.get(strategy, self._merge_strategy)
            
            # Apply strategy
            resolved_data = resolution_func(source_data, target_data, conflicts)
            
            if resolved_data:
                conflict.resolved = True
                conflict.resolution_strategy = strategy
                conflict.resolution_data = resolved_data
                
                # Store conflict for tracking
                self.conflicts.append(conflict)
                
                return {
                    'success': True,
                    'resolved_data': resolved_data,
                    'conflict': conflict.to_dict()
                }
            else:
                return {
                    'success': False,
                    'error': 'Conflict resolution failed',
                    'conflict': conflict.to_dict()
                }
                
        except Exception as e:
            logger.error(f"Error resolving conflicts: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _source_wins_strategy(self, source_data: Dict[str, Any], target_data: Dict[str, Any], 
                             conflicts: List[str]) -> Dict[str, Any]:
        """
        Source wins strategy - use source data for all conflicts
        """
        return source_data.copy()
    
    def _target_wins_strategy(self, source_data: Dict[str, Any], target_data: Dict[str, Any], 
                             conflicts: List[str]) -> Dict[str, Any]:
        """
        Target wins strategy - use target data for all conflicts
        """
        return target_data.copy()
    
    def _merge_strategy(self, source_data: Dict[str, Any], target_data: Dict[str, Any], 
                       conflicts: List[str]) -> Dict[str, Any]:
        """
        Merge strategy - intelligently merge data
        """
        try:
            merged = target_data.copy()
            
            # For each conflict, try intelligent merging
            for conflict in conflicts:
                if "Field '" in conflict:
                    field = conflict.split("'")[1]
                    
                    # Merge based on field type
                    if field in ['updated_at', 'last_modified', 'timestamp']:
                        # Use most recent timestamp
                        source_time = source_data.get(field)
                        target_time = target_data.get(field)
                        
                        if source_time and target_time:
                            try:
                                source_dt = datetime.fromisoformat(source_time.replace('Z', '+00:00'))
                                target_dt = datetime.fromisoformat(target_time.replace('Z', '+00:00'))
                                
                                if source_dt > target_dt:
                                    merged[field] = source_time
                            except ValueError:
                                # Fallback to source
                                merged[field] = source_time
                        else:
                            merged[field] = source_time or target_time
                    
                    elif field in ['tags', 'labels', 'metadata']:
                        # Merge arrays/dictionaries
                        source_value = source_data.get(field, {})
                        target_value = target_data.get(field, {})
                        
                        if isinstance(source_value, dict) and isinstance(target_value, dict):
                            merged[field] = {**target_value, **source_value}
                        else:
                            merged[field] = source_value
                    
                    else:
                        # Default to source
                        merged[field] = source_data.get(field)
            
            return merged
            
        except Exception as e:
            logger.error(f"Error in merge strategy: {e}")
            return source_data.copy()
    
    def _timestamp_based_strategy(self, source_data: Dict[str, Any], target_data: Dict[str, Any], 
                                 conflicts: List[str]) -> Dict[str, Any]:
        """
        Timestamp-based strategy - use data with most recent timestamp
        """
        try:
            source_time = source_data.get('timestamp') or source_data.get('updated_at')
            target_time = target_data.get('timestamp') or target_data.get('updated_at')
            
            if source_time and target_time:
                try:
                    source_dt = datetime.fromisoformat(source_time.replace('Z', '+00:00'))
                    target_dt = datetime.fromisoformat(target_time.replace('Z', '+00:00'))
                    
                    if source_dt > target_dt:
                        return source_data.copy()
                    else:
                        return target_data.copy()
                except ValueError:
                    # Fallback to source
                    return source_data.copy()
            else:
                # Fallback to merge strategy
                return self._merge_strategy(source_data, target_data, conflicts)
                
        except Exception as e:
            logger.error(f"Error in timestamp-based strategy: {e}")
            return self._merge_strategy(source_data, target_data, conflicts)
    
    def _manual_strategy(self, source_data: Dict[str, Any], target_data: Dict[str, Any], 
                        conflicts: List[str]) -> Dict[str, Any]:
        """
        Manual strategy - requires manual resolution
        """
        # Store conflict for manual resolution
        return None
    
    def _apply_sync_resolution(self, source_system: str, target_system: str, 
                             resolved_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply synchronization resolution
        """
        try:
            # Update integration registry
            entity_id = self._generate_entity_id(resolved_data)
            
            # Record the sync on the target integration if it is registered. The registry
            # holds integrations (name, class, config), not synced entities, so the old
            # register_integration(integration_id=..., integration_type=...) call could
            # never succeed (wrong signature).
            from django.utils import timezone as _tz
            if integration_registry.get_integration(target_system):
                integration_registry.update_integration_config(target_system, {
                    'last_synced_entity': entity_id,
                    'last_synced_at': _tz.now().isoformat(),
                })
            
            # Update database if needed
            if 'alert_rule_id' in resolved_data:
                self._update_alert_rule(resolved_data)
            elif 'alert_id' in resolved_data:
                self._update_alert_log(resolved_data)
            
            return {
                'success': True,
                'message': f'Synchronization applied successfully for {entity_id}',
                'entity_id': entity_id
            }
            
        except Exception as e:
            logger.error(f"Error applying sync resolution: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def _update_alert_rule(self, data: Dict[str, Any]):
        """
        Update alert rule in database
        """
        try:
            rule_id = data.get('alert_rule_id')
            if rule_id:
                rule = AlertRule.objects.get(id=rule_id)
                
                if 'title' in data:
                    rule.name = data['title']
                if 'condition' in data:
                    rule.condition = data['condition']
                if 'threshold_value' in data:
                    rule.threshold_value = data['threshold_value']
                if 'is_active' in data:
                    rule.is_active = data['is_active']
                
                rule.save()
                
        except Exception as e:
            logger.error(f"Error updating alert rule: {e}")
    
    def _update_alert_log(self, data: Dict[str, Any]):
        """
        Update alert log in database
        """
        try:
            alert_id = data.get('alert_id')
            if alert_id:
                alert = AlertLog.objects.get(id=alert_id)
                
                if 'title' in data:
                    alert.title = data['title']
                if 'severity' in data:
                    alert.severity = data['severity']
                if 'message' in data:
                    alert.message = data['message']
                if 'is_resolved' in data:
                    alert.is_resolved = data['is_resolved']
                
                alert.save()
                
        except Exception as e:
            logger.error(f"Error updating alert log: {e}")
    
    def register_sync_strategy(self, name: str, strategy_func: Callable):
        """
        Register custom synchronization strategy
        """
        self.sync_strategies[name] = strategy_func
        logger.info(f"Registered sync strategy: {name}")
    
    def get_conflicts(self, resolved: bool = None) -> List[Dict[str, Any]]:
        """
        Get synchronization conflicts
        """
        try:
            conflicts = [conflict.to_dict() for conflict in self.conflicts]
            
            if resolved is not None:
                conflicts = [c for c in conflicts if c['resolved'] == resolved]
            
            return conflicts
            
        except Exception as e:
            logger.error(f"Error getting conflicts: {e}")
            return []
    
    def get_sync_statistics(self) -> Dict[str, Any]:
        """
        Get synchronization statistics
        """
        try:
            total_syncs = self.sync_stats['total_syncs']
            successful_syncs = self.sync_stats['successful_syncs']
            
            success_rate = (successful_syncs / max(total_syncs, 1)) * 100
            
            return {
                'total_syncs': total_syncs,
                'successful_syncs': successful_syncs,
                'failed_syncs': self.sync_stats['failed_syncs'],
                'conflicts_resolved': self.sync_stats['conflicts_resolved'],
                'conflicts_unresolved': self.sync_stats['conflicts_unresolved'],
                'success_rate': success_rate,
                'last_sync': self.sync_stats['last_sync'],
                'registered_strategies': list(self.sync_strategies.keys()),
                'total_conflicts': len(self.conflicts),
                'timestamp': django_tz.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting sync statistics: {e}")
            return {
                'error': 'Operation failed',
                'timestamp': django_tz.now().isoformat()
            }


# Global sync manager instance
integration_sync_manager = IntegrationSyncManager()


# Utility functions
def sync_integration_data(source_system: str, target_system: str, 
                        data: Union[Dict[str, Any], List[Dict[str, Any]]], 
                        strategy: str = 'merge') -> Dict[str, Any]:
    """
    Synchronize integration data
    """
    return integration_sync_manager.sync_integration_data(source_system, target_system, data, strategy)


def get_sync_conflicts(resolved: bool = None) -> List[Dict[str, Any]]:
    """
    Get synchronization conflicts
    """
    return integration_sync_manager.get_conflicts(resolved)


def get_sync_statistics() -> Dict[str, Any]:
    """
    Get synchronization statistics
    """
    return integration_sync_manager.get_sync_statistics()
