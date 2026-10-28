"""
Sync Manager Module
Data conflict resolver and synchronization manager
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_exceptions import ConflictException, DataSyncException

User = get_user_model()
logger = logging.getLogger('security.integration.sync_manager')


class ConflictResolution:
    """Base conflict resolution strategy"""
    
    def __init__(self, name: str, priority: int = 5):
        self.name = name
        self.priority = priority  # Lower number = higher priority
        self.enabled = True
        self.description = ""
    
    def resolve_conflict(self, source_data: Dict[str, Any], target_data: Dict[str, Any],
                         conflict_info: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict - override in subclasses"""
        raise NotImplementedError("Subclasses must implement resolve_conflict method")
    
    def can_resolve(self, conflict_type: str) -> bool:
        """Check if strategy can resolve conflict type"""
        return True
    
    def enable(self):
        """Enable strategy"""
        self.enabled = True
    
    def disable(self):
        """Disable strategy"""
        self.enabled = False


class SourceWinsResolution(ConflictResolution):
    """Source data wins resolution"""
    
    def __init__(self):
        super().__init__("source_wins", priority=1)
        self.description = "Source data takes precedence over target data"
    
    def resolve_conflict(self, source_data: Dict[str, Any], target_data: Dict[str, Any],
                         conflict_info: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict by using source data"""
        return {
            'resolved_data': source_data,
            'resolution_strategy': 'source_wins',
            'conflicts_resolved': len(conflict_info.get('conflicting_fields', [])),
            'message': 'Source data used to resolve conflicts'
        }


class TargetWinsResolution(ConflictResolution):
    """Target data wins resolution"""
    
    def __init__(self):
        super().__init__("target_wins", priority=2)
        self.description = "Target data takes precedence over source data"
    
    def resolve_conflict(self, source_data: Dict[str, Any], target_data: Dict[str, Any],
                         conflict_info: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict by using target data"""
        return {
            'resolved_data': target_data,
            'resolution_strategy': 'target_wins',
            'conflicts_resolved': len(conflict_info.get('conflicting_fields', [])),
            'message': 'Target data used to resolve conflicts'
        }


class MergeResolution(ConflictResolution):
    """Merge data resolution"""
    
    def __init__(self):
        super().__init__("merge", priority=3)
        self.description = "Merge source and target data intelligently"
    
    def resolve_conflict(self, source_data: Dict[str, Any], target_data: Dict[str, Any],
                         conflict_info: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict by merging data"""
        resolved_data = {}
        conflicts_resolved = 0
        
        conflicting_fields = conflict_info.get('conflicting_fields', [])
        
        for field, source_value in source_data.items():
            target_value = target_data.get(field)
            
            if field in conflicting_fields:
                # Apply merge logic
                merged_value = self._merge_field_values(field, source_value, target_value)
                resolved_data[field] = merged_value
                conflicts_resolved += 1
            else:
                # No conflict, use source value
                resolved_data[field] = source_value
        
        # Add fields only in target
        for field, target_value in target_data.items():
            if field not in resolved_data:
                resolved_data[field] = target_value
        
        return {
            'resolved_data': resolved_data,
            'resolution_strategy': 'merge',
            'conflicts_resolved': conflicts_resolved,
            'message': f'Merged data with {conflicts_resolved} conflicts resolved'
        }
    
    def _merge_field_values(self, field: str, source_value: Any, target_value: Any) -> Any:
        """Merge individual field values"""
        # Timestamp fields - use most recent
        if field.endswith('_at') or field.endswith('time'):
            if isinstance(source_value, str) and isinstance(target_value, str):
                try:
                    source_dt = datetime.fromisoformat(source_value.replace('Z', '+00:00'))
                    target_dt = datetime.fromisoformat(target_value.replace('Z', '+00:00'))
                    return max(source_dt, target_dt).isoformat()
                except ValueError:
                    pass
        
        # Numeric fields - use max
        if isinstance(source_value, (int, float)) and isinstance(target_value, (int, float)):
            return max(source_value, target_value)
        
        # List fields - combine
        if isinstance(source_value, list) and isinstance(target_value, list):
            return list(set(source_value + target_value))
        
        # String fields - concatenate if different
        if isinstance(source_value, str) and isinstance(target_value, str):
            if source_value != target_value:
                return f"{source_value} | {target_value}"
        
        # Default - use source
        return source_value


class TimestampResolution(ConflictResolution):
    """Timestamp-based resolution"""
    
    def __init__(self):
        super().__init__("timestamp", priority=4)
        self.description = "Use most recent timestamp to resolve conflicts"
    
    def resolve_conflict(self, source_data: Dict[str, Any], target_data: Dict[str, Any],
                         conflict_info: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict based on timestamps"""
        resolved_data = {}
        conflicts_resolved = 0
        
        conflicting_fields = conflict_info.get('conflicting_fields', [])
        
        # Get timestamps
        source_timestamp = self._get_timestamp(source_data)
        target_timestamp = self._get_timestamp(target_data)
        
        # Determine which data is more recent
        use_source = source_timestamp >= target_timestamp if source_timestamp and target_timestamp else True
        
        for field, source_value in source_data.items():
            if field in conflicting_fields:
                # Use more recent data
                if use_source:
                    resolved_data[field] = source_value
                else:
                    resolved_data[field] = target_data.get(field, source_value)
                conflicts_resolved += 1
            else:
                resolved_data[field] = source_value
        
        # Add fields only in target
        for field, target_value in target_data.items():
            if field not in resolved_data:
                resolved_data[field] = target_value
        
        return {
            'resolved_data': resolved_data,
            'resolution_strategy': 'timestamp',
            'conflicts_resolved': conflicts_resolved,
            'message': f'Used {"source" if use_source else "target"} data based on timestamps'
        }
    
    def _get_timestamp(self, data: Dict[str, Any]) -> Optional[datetime]:
        """Get timestamp from data"""
        timestamp_fields = ['updated_at', 'modified_at', 'last_updated', 'timestamp']
        
        for field in timestamp_fields:
            if field in data:
                try:
                    return datetime.fromisoformat(data[field].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    pass
        
        return None


class ManualResolution(ConflictResolution):
    """Manual resolution requiring human intervention"""
    
    def __init__(self):
        super().__init__("manual", priority=10)
        self.description = "Requires manual conflict resolution"
    
    def resolve_conflict(self, source_data: Dict[str, Any], target_data: Dict[str, Any],
                         conflict_info: Dict[str, Any]) -> Dict[str, Any]:
        """Mark conflict for manual resolution"""
        # Create conflict record
        conflict_id = SecurityUtils.generate_uuid()
        
        SecurityLog.objects.create(
            security_type='sync_conflict',
            severity='warning',
            description=f"Sync conflict requiring manual resolution: {conflict_id}",
            metadata={
                'conflict_id': conflict_id,
                'conflicting_fields': conflict_info.get('conflicting_fields', []),
                'source_data': source_data,
                'target_data': target_data,
                'resolution_strategy': 'manual'
            }
        )
        
        return {
            'resolved_data': None,
            'resolution_strategy': 'manual',
            'conflicts_resolved': 0,
            'conflict_id': conflict_id,
            'message': 'Conflict flagged for manual resolution',
            'requires_manual_intervention': True
        }


class SyncManager:
    """Data synchronization manager with conflict resolution"""
    
    def __init__(self):
        self.resolution_strategies = []
        self.conflict_history = []
        self.max_history = 1000
        self.enabled = True
        self.default_strategy = 'merge'
        self.statistics = {
            'sync_operations': 0,
            'conflicts_detected': 0,
            'conflicts_resolved': 0,
            'manual_interventions': 0
        }
    
    def add_resolution_strategy(self, strategy: ConflictResolution):
        """Add conflict resolution strategy"""
        self.resolution_strategies.append(strategy)
        
        # Sort by priority
        self.resolution_strategies.sort(key=lambda s: s.priority)
        
        logger.info(f"Added conflict resolution strategy: {strategy.name}")
    
    def remove_resolution_strategy(self, strategy_name: str) -> bool:
        """Remove conflict resolution strategy"""
        for i, strategy in enumerate(self.resolution_strategies):
            if strategy.name == strategy_name:
                del self.resolution_strategies[i]
                logger.info(f"Removed conflict resolution strategy: {strategy_name}")
                return True
        return False
    
    def get_strategy(self, strategy_name: str) -> Optional[ConflictResolution]:
        """Get resolution strategy by name"""
        for strategy in self.resolution_strategies:
            if strategy.name == strategy_name:
                return strategy
        return None
    
    def detect_conflicts(self, source_data: Dict[str, Any], target_data: Dict[str, Any],
                         key_field: str = 'id') -> Dict[str, Any]:
        """Detect conflicts between source and target data"""
        conflicts = []
        
        # Find common fields
        common_fields = set(source_data.keys()) & set(target_data.keys())
        
        for field in common_fields:
            source_value = source_data[field]
            target_value = target_data[field]
            
            # Check for conflict
            if source_value != target_value:
                conflicts.append({
                    'field': field,
                    'source_value': source_value,
                    'target_value': target_value,
                    'conflict_type': self._determine_conflict_type(field, source_value, target_value)
                })
        
        return {
            'has_conflicts': len(conflicts) > 0,
            'conflict_count': len(conflicts),
            'conflicting_fields': [c['field'] for c in conflicts],
            'conflicts': conflicts,
            'key_field': key_field,
            'source_key': source_data.get(key_field),
            'target_key': target_data.get(key_field)
        }
    
    def _determine_conflict_type(self, field: str, source_value: Any, target_value: Any) -> str:
        """Determine conflict type"""
        if field.endswith('_at') or field.endswith('_time'):
            return 'timestamp'
        elif isinstance(source_value, (int, float)) and isinstance(target_value, (int, float)):
            return 'numeric'
        elif isinstance(source_value, str) and isinstance(target_value, str):
            return 'text'
        elif isinstance(source_value, bool) and isinstance(target_value, bool):
            return 'boolean'
        elif isinstance(source_value, list) and isinstance(target_value, list):
            return 'list'
        elif isinstance(source_value, dict) and isinstance(target_value, dict):
            return 'object'
        else:
            return 'unknown'
    
    def resolve_conflicts(self, source_data: Dict[str, Any], target_data: Dict[str, Any],
                          conflict_info: Dict[str, Any], strategy_name: str = None) -> Dict[str, Any]:
        """Resolve conflicts using specified strategy"""
        self.statistics['conflicts_detected'] += conflict_info['conflict_count']
        
        # Select strategy
        if strategy_name:
            strategy = self.get_strategy(strategy_name)
            if not strategy or not strategy.enabled:
                strategy = self._get_default_strategy(conflict_info)
        else:
            strategy = self._get_default_strategy(conflict_info)
        
        if not strategy:
            return {
                'success': False,
                'message': 'No suitable resolution strategy found'
            }
        
        try:
            result = strategy.resolve_conflict(source_data, target_data, conflict_info)
            
            if result.get('requires_manual_intervention'):
                self.statistics['manual_interventions'] += 1
            else:
                self.statistics['conflicts_resolved'] += result.get('conflicts_resolved', 0)
            
            # Record conflict resolution
            self._record_conflict_resolution(source_data, target_data, conflict_info, result)
            
            return {
                'success': True,
                'strategy_used': strategy.name,
                'result': result
            }
        
        except Exception as e:
            logger.error(f"Error resolving conflicts with strategy {strategy.name}: {e}")
            return {
                'success': False,
                'message': f'Error resolving conflicts: {str(e)}'
            }
    
    def _get_default_strategy(self, conflict_info: Dict[str, Any]) -> ConflictResolution:
        """Get default resolution strategy"""
        # Try to find strategy that can handle the conflict types
        conflict_types = set(c['conflict_type'] for c in conflict_info['conflicts'])
        
        for strategy in self.resolution_strategies:
            if strategy.enabled and strategy.can_resolve('any'):
                return strategy
        
        # Fallback to manual resolution
        return ManualResolution()
    
    def _record_conflict_resolution(self, source_data: Dict[str, Any], target_data: Dict[str, Any],
                                conflict_info: Dict[str, Any], resolution_result: Dict[str, Any]):
        """Record conflict resolution in history"""
        history_entry = {
            'timestamp': timezone.now(),
            'conflict_count': conflict_info['conflict_count'],
            'conflicting_fields': conflict_info['conflicting_fields'],
            'strategy_used': resolution_result.get('strategy_used'),
            'conflicts_resolved': resolution_result.get('conflicts_resolved', 0),
            'requires_manual_intervention': resolution_result.get('requires_manual_intervention', False),
            'resolution_data': resolution_result.get('resolved_data')
        }
        
        self.conflict_history.append(history_entry)
        
        # Maintain history size
        if len(self.conflict_history) > self.max_history:
            self.conflict_history.pop(0)
    
    def synchronize_data(self, source_system: str, target_system: str, data_items: List[Dict[str, Any]],
                        key_field: str = 'id', strategy_name: str = None) -> Dict[str, Any]:
        """Synchronize data between systems with conflict resolution"""
        if not self.enabled:
            return {
                'success': False,
                'message': 'Sync manager disabled'
            }
        
        self.statistics['sync_operations'] += 1
        
        results = {
            'success': True,
            'items_processed': 0,
            'items_synced': 0,
            'conflicts_detected': 0,
            'conflicts_resolved': 0,
            'manual_interventions': 0,
            'errors': []
        }
        
        for item in data_items:
            try:
                # Get corresponding data from target system
                target_data = self._get_target_data(target_system, item.get(key_field))
                
                if target_data:
                    # Detect conflicts
                    conflict_info = self.detect_conflicts(item, target_data, key_field)
                    
                    if conflict_info['has_conflicts']:
                        results['conflicts_detected'] += 1
                        
                        # Resolve conflicts
                        resolution_result = self.resolve_conflicts(
                            item, target_data, conflict_info, strategy_name
                        )
                        
                        if resolution_result['success']:
                            resolved_data = resolution_result['result'].get('resolved_data')
                            
                            if resolved_data:
                                # Update target system with resolved data
                                if self._update_target_data(target_system, resolved_data):
                                    results['items_synced'] += 1
                                    results['conflicts_resolved'] += resolution_result['result'].get('conflicts_resolved', 0)
                                    
                                    if resolution_result['result'].get('requires_manual_intervention'):
                                        results['manual_interventions'] += 1
                        else:
                            results['errors'].append(f"Failed to resolve conflicts for item {item.get(key_field)}")
                    else:
                        # No conflicts, update directly
                        if self._update_target_data(target_system, item):
                            results['items_synced'] += 1
                else:
                    # No existing data, create new
                    if self._create_target_data(target_system, item):
                        results['items_synced'] += 1
                
                results['items_processed'] += 1
            
            except Exception as e:
                logger.error(f"Error processing item {item.get(key_field)}: {e}")
                results['errors'].append(f"Error processing item {item.get(key_field)}: {str(e)}")
        
        return results
    
    def _get_target_data(self, target_system: str, key_value: Any) -> Optional[Dict[str, Any]]:
        """Get data from target system - override in subclasses"""
        # This would implement actual data retrieval
        # For now, return None (no existing data)
        return None
    
    def _update_target_data(self, target_system: str, data: Dict[str, Any]) -> bool:
        """Update data in target system - override in subclasses"""
        # This would implement actual data update
        # For now, return True (success)
        return True
    
    def _create_target_data(self, target_system: str, data: Dict[str, Any]) -> bool:
        """Create data in target system - override in subclasses"""
        # This would implement actual data creation
        # For now, return True (success)
        return True
    
    def get_conflict_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get conflict resolution history"""
        return self.conflict_history[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get synchronization statistics"""
        total_conflicts = self.statistics['conflicts_detected']
        resolution_rate = (
            (self.statistics['conflicts_resolved'] / total_conflicts * 100)
            if total_conflicts > 0 else 0
        )
        
        return {
            'enabled': self.enabled,
            'default_strategy': self.default_strategy,
            'total_strategies': len(self.resolution_strategies),
            'enabled_strategies': len([s for s in self.resolution_strategies if s.enabled]),
            'statistics': {
                **self.statistics,
                'resolution_rate': resolution_rate,
                'history_entries': len(self.conflict_history)
            }
        }
    
    def set_default_strategy(self, strategy_name: str):
        """Set default resolution strategy"""
        self.default_strategy = strategy_name
        logger.info(f"Set default resolution strategy to: {strategy_name}")
    
    def enable_all_strategies(self):
        """Enable all resolution strategies"""
        for strategy in self.resolution_strategies:
            strategy.enable()
    
    def disable_all_strategies(self):
        """Disable all resolution strategies"""
        for strategy in self.resolution_strategies:
            strategy.disable()
    
    def enable(self):
        """Enable sync manager"""
        self.enabled = True
        logger.info("Sync manager enabled")
    
    def disable(self):
        """Disable sync manager"""
        self.enabled = False
        logger.info("Sync manager disabled")
    
    def clear_history(self):
        """Clear conflict history"""
        self.conflict_history.clear()
        logger.info("Cleared conflict resolution history")


# Global sync manager
sync_manager = SyncManager()


# Create default resolution strategies
def create_default_resolution_strategies():
    """Create default conflict resolution strategies"""
    
    # Add default strategies
    sync_manager.add_resolution_strategy(SourceWinsResolution())
    sync_manager.add_resolution_strategy(TargetWinsResolution())
    sync_manager.add_resolution_strategy(MergeResolution())
    sync_manager.add_resolution_strategy(TimestampResolution())
    sync_manager.add_resolution_strategy(ManualResolution())
    
    # Set default strategy
    sync_manager.set_default_strategy('merge')
    
    logger.info("Created default conflict resolution strategies")


# Initialize default strategies
create_default_resolution_strategies()


# Export symbols
__all__ = [
    'ConflictResolution',
    'SourceWinsResolution',
    'TargetWinsResolution',
    'MergeResolution',
    'TimestampResolution',
    'ManualResolution',
    'SyncManager',
    'sync_manager',
    'create_default_resolution_strategies'
]