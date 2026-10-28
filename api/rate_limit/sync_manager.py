# api/rate_limit/sync_manager.py
"""
Data conflict resolver and synchronization manager for rate limit module.

Provides conflict detection, resolution, and data synchronization capabilities.
"""

import logging
from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.contrib.auth import get_user_model
import hashlib
import json

from api.rate_limit.integ_exceptions import IntegrationError

logger = logging.getLogger(__name__)
User = get_user_model()


class ConflictType:
    """Conflict type constants."""
    
    VERSION_CONFLICT = 'version_conflict'
    DATA_CONFLICT = 'data_conflict'
    DUPLICATE_CONFLICT = 'duplicate_conflict'
    REFERENCE_CONFLICT = 'reference_conflict'
    BUSINESS_RULE_CONFLICT = 'business_rule_conflict'
    PERMISSION_CONFLICT = 'permission_conflict'
    
    CHOICES = [
        (VERSION_CONFLICT, 'Version Conflict'),
        (DATA_CONFLICT, 'Data Conflict'),
        (DUPLICATE_CONFLICT, 'Duplicate Conflict'),
        (REFERENCE_CONFLICT, 'Reference Conflict'),
        (BUSINESS_RULE_CONFLICT, 'Business Rule Conflict'),
        (PERMISSION_CONFLICT, 'Permission Conflict'),
    ]


class ConflictResolution:
    """Conflict resolution strategy constants."""
    
    MANUAL = 'manual'
    AUTO_MERGE = 'auto_merge'
    LAST_WRITER_WINS = 'last_writer_wins'
    FIRST_WRITER_WINS = 'first_writer_wins'
    HIGHEST_PRIORITY = 'highest_priority'
    LOWEST_PRIORITY = 'lowest_priority'
    TIMESTAMP_BASED = 'timestamp_based'
    CUSTOM = 'custom'
    
    CHOICES = [
        (MANUAL, 'Manual Resolution'),
        (AUTO_MERGE, 'Auto Merge'),
        (LAST_WRITER_WINS, 'Last Writer Wins'),
        (FIRST_WRITER_WINS, 'First Writer Wins'),
        (HIGHEST_PRIORITY, 'Highest Priority'),
        (LOWEST_PRIORITY, 'Lowest Priority'),
        (TIMESTAMP_BASED, 'Timestamp Based'),
        (CUSTOM, 'Custom Resolution'),
    ]


class Conflict:
    """Represents a data conflict."""
    
    def __init__(self, conflict_id: str, conflict_type: str, resource_type: str,
                 resource_id: str, conflicting_data: List[Dict[str, Any]],
                 resolution: str = ConflictResolution.MANUAL, description: str = '',
                 severity: str = 'medium', metadata: Dict[str, Any] = None):
        self.conflict_id = conflict_id
        self.conflict_type = conflict_type
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.conflicting_data = conflicting_data
        self.resolution = resolution
        self.description = description
        self.severity = severity
        self.metadata = metadata or {}
        self.created_at = timezone.now()
        self.resolved_at = None
        self.resolved_by = None
        self.resolution_data = None
        self.status = 'pending'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert conflict to dictionary."""
        return {
            'conflict_id': self.conflict_id,
            'conflict_type': self.conflict_type,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'conflicting_data': self.conflicting_data,
            'resolution': self.resolution,
            'description': self.description,
            'severity': self.severity,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by': self.resolved_by,
            'resolution_data': self.resolution_data,
            'status': self.status
        }
    
    def resolve(self, resolution_data: Dict[str, Any], resolved_by: int = None):
        """Mark conflict as resolved."""
        self.resolved_at = timezone.now()
        self.resolved_by = resolved_by
        self.resolution_data = resolution_data
        self.status = 'resolved'
    
    def get_hash(self) -> str:
        """Get hash of conflict for identification."""
        conflict_data = {
            'conflict_type': self.conflict_type,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'conflicting_data': sorted(self.conflicting_data, key=lambda x: str(x))
        }
        return hashlib.sha256(json.dumps(conflict_data, sort_keys=True).encode()).hexdigest()


class ConflictDetector:
    """Detects conflicts in data synchronization."""
    
    def __init__(self):
        self.detection_rules: Dict[str, Callable] = {}
        self._initialize_detection_rules()
    
    def _initialize_detection_rules(self):
        """Initialize default conflict detection rules."""
        self.detection_rules[ConflictType.VERSION_CONFLICT] = self._detect_version_conflict
        self.detection_rules[ConflictType.DATA_CONFLICT] = self._detect_data_conflict
        self.detection_rules[ConflictType.DUPLICATE_CONFLICT] = self._detect_duplicate_conflict
        self.detection_rules[ConflictType.REFERENCE_CONFLICT] = self._detect_reference_conflict
        self.detection_rules[ConflictType.BUSINESS_RULE_CONFLICT] = self._detect_business_rule_conflict
        self.detection_rules[ConflictType.PERMISSION_CONFLICT] = self._detect_permission_conflict
    
    def add_detection_rule(self, conflict_type: str, detector: Callable):
        """Add a conflict detection rule."""
        self.detection_rules[conflict_type] = detector
        logger.info(f"Added conflict detection rule: {conflict_type}")
    
    def detect_conflicts(self, resource_type: str, resource_id: str,
                        local_data: Dict[str, Any], remote_data: Dict[str, Any],
                        context: Dict[str, Any] = None) -> List[Conflict]:
        """
        Detect conflicts between local and remote data.
        
        Args:
            resource_type: Type of resource
            resource_id: Resource identifier
            local_data: Local data
            remote_data: Remote data
            context: Additional context
            
        Returns:
            List of detected conflicts
        """
        conflicts = []
        context = context or {}
        
        for conflict_type, detector in self.detection_rules.items():
            try:
                conflict = detector(resource_type, resource_id, local_data, remote_data, context)
                if conflict:
                    conflicts.append(conflict)
            except Exception as e:
                logger.error(f"Conflict detection failed for {conflict_type}: {str(e)}")
        
        return conflicts
    
    def _detect_version_conflict(self, resource_type: str, resource_id: str,
                               local_data: Dict[str, Any], remote_data: Dict[str, Any],
                               context: Dict[str, Any]) -> Optional[Conflict]:
        """Detect version conflicts."""
        local_version = local_data.get('version')
        remote_version = remote_data.get('version')
        
        if local_version and remote_version and local_version != remote_version:
            conflict_id = f"version_conflict_{resource_type}_{resource_id}_{timezone.now().timestamp()}"
            
            return Conflict(
                conflict_id=conflict_id,
                conflict_type=ConflictType.VERSION_CONFLICT,
                resource_type=resource_type,
                resource_id=resource_id,
                conflicting_data=[
                    {'source': 'local', 'version': local_version, 'data': local_data},
                    {'source': 'remote', 'version': remote_version, 'data': remote_data}
                ],
                resolution=ConflictResolution.TIMESTAMP_BASED,
                description=f"Version mismatch: local={local_version}, remote={remote_version}",
                severity='high'
            )
        
        return None
    
    def _detect_data_conflict(self, resource_type: str, resource_id: str,
                            local_data: Dict[str, Any], remote_data: Dict[str, Any],
                            context: Dict[str, Any]) -> Optional[Conflict]:
        """Detect data conflicts."""
        conflicts = []
        
        # Check for conflicting field values
        for field in set(local_data.keys()) & set(remote_data.keys()):
            if field in ['id', 'created_at', 'updated_at', 'version']:
                continue  # Skip metadata fields
            
            local_value = local_data[field]
            remote_value = remote_data[field]
            
            if local_value != remote_value:
                conflict_id = f"data_conflict_{resource_type}_{resource_id}_{field}_{timezone.now().timestamp()}"
                
                conflicts.append(Conflict(
                    conflict_id=conflict_id,
                    conflict_type=ConflictType.DATA_CONFLICT,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    conflicting_data=[
                        {'source': 'local', 'field': field, 'value': local_value},
                        {'source': 'remote', 'field': field, 'value': remote_value}
                    ],
                    resolution=ConflictResolution.LAST_WRITER_WINS,
                    description=f"Data conflict in field '{field}': local={local_value}, remote={remote_value}",
                    severity='medium'
                ))
        
        return conflicts[0] if conflicts else None
    
    def _detect_duplicate_conflict(self, resource_type: str, resource_id: str,
                                  local_data: Dict[str, Any], remote_data: Dict[str, Any],
                                  context: Dict[str, Any]) -> Optional[Conflict]:
        """Detect duplicate conflicts."""
        # Check if both records have the same identifier but different data
        local_identifier = local_data.get('identifier')
        remote_identifier = remote_data.get('identifier')
        
        if local_identifier and remote_identifier and local_identifier == remote_identifier:
            # Check if there are actual differences
            if local_data != remote_data:
                conflict_id = f"duplicate_conflict_{resource_type}_{resource_id}_{timezone.now().timestamp()}"
                
                return Conflict(
                    conflict_id=conflict_id,
                    conflict_type=ConflictType.DUPLICATE_CONFLICT,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    conflicting_data=[
                        {'source': 'local', 'data': local_data},
                        {'source': 'remote', 'data': remote_data}
                    ],
                    resolution=ConflictResolution.MANUAL,
                    description=f"Duplicate records with same identifier but different data",
                    severity='high'
                )
        
        return None
    
    def _detect_reference_conflict(self, resource_type: str, resource_id: str,
                                 local_data: Dict[str, Any], remote_data: Dict[str, Any],
                                 context: Dict[str, Any]) -> Optional[Conflict]:
        """Detect reference conflicts."""
        # Check for broken references
        local_references = local_data.get('references', [])
        remote_references = remote_data.get('references', [])
        
        if local_references != remote_references:
            conflict_id = f"reference_conflict_{resource_type}_{resource_id}_{timezone.now().timestamp()}"
            
            return Conflict(
                conflict_id=conflict_id,
                conflict_type=ConflictType.REFERENCE_CONFLICT,
                resource_type=resource_type,
                resource_id=resource_id,
                conflicting_data=[
                    {'source': 'local', 'references': local_references},
                    {'source': 'remote', 'references': remote_references}
                ],
                resolution=ConflictResolution.AUTO_MERGE,
                description="Reference data mismatch",
                severity='medium'
            )
        
        return None
    
    def _detect_business_rule_conflict(self, resource_type: str, resource_id: str,
                                      local_data: Dict[str, Any], remote_data: Dict[str, Any],
                                      context: Dict[str, Any]) -> Optional[Conflict]:
        """Detect business rule conflicts."""
        # Check rate limit specific business rules
        if resource_type == 'rate_limit_config':
            local_requests = local_data.get('requests_per_unit')
            remote_requests = remote_data.get('requests_per_unit')
            
            # Business rule: requests_per_unit should not exceed 10000
            max_requests = 10000
            
            if local_requests > max_requests or remote_requests > max_requests:
                conflict_id = f"business_rule_conflict_{resource_type}_{resource_id}_{timezone.now().timestamp()}"
                
                return Conflict(
                    conflict_id=conflict_id,
                    conflict_type=ConflictType.BUSINESS_RULE_CONFLICT,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    conflicting_data=[
                        {'source': 'local', 'requests_per_unit': local_requests},
                        {'source': 'remote', 'requests_per_unit': remote_requests}
                    ],
                    resolution=ConflictResolution.HIGHEST_PRIORITY,
                    description=f"Requests per unit exceeds business rule limit of {max_requests}",
                    severity='high'
                )
        
        return None
    
    def _detect_permission_conflict(self, resource_type: str, resource_id: str,
                                   local_data: Dict[str, Any], remote_data: Dict[str, Any],
                                   context: Dict[str, Any]) -> Optional[Conflict]:
        """Detect permission conflicts."""
        # Check if user has permission to modify this resource
        user_id = context.get('user_id')
        if not user_id:
            return None
        
        try:
            user = User.objects.get(id=user_id)
            
            # Check if user can modify rate limit configs
            if resource_type == 'rate_limit_config':
                if not (user.is_staff or user.groups.filter(name='rate_limit_managers').exists()):
                    conflict_id = f"permission_conflict_{resource_type}_{resource_id}_{timezone.now().timestamp()}"
                    
                    return Conflict(
                        conflict_id=conflict_id,
                        conflict_type=ConflictType.PERMISSION_CONFLICT,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        conflicting_data=[
                            {'source': 'permission_check', 'user_id': user_id, 'permission': False}
                        ],
                        resolution=ConflictResolution.MANUAL,
                        description=f"User {user_id} lacks permission to modify {resource_type}",
                        severity='high'
                    )
        
        except User.DoesNotExist:
            pass
        
        return None


class ConflictResolver:
    """Resolves detected conflicts."""
    
    def __init__(self):
        self.resolvers: Dict[str, Callable] = {}
        self._initialize_resolvers()
    
    def _initialize_resolvers(self):
        """Initialize default conflict resolvers."""
        self.resolvers[ConflictResolution.LAST_WRITER_WINS] = self._resolve_last_writer_wins
        self.resolvers[ConflictResolution.FIRST_WRITER_WINS] = self._resolve_first_writer_wins
        self.resolvers[ConflictResolution.HIGHEST_PRIORITY] = self._resolve_highest_priority
        self.resolvers[ConflictResolution.LOWEST_PRIORITY] = self._resolve_lowest_priority
        self.resolvers[ConflictResolution.TIMESTAMP_BASED] = self._resolve_timestamp_based
        self.resolvers[ConflictResolution.AUTO_MERGE] = self._resolve_auto_merge
    
    def add_resolver(self, resolution: str, resolver: Callable):
        """Add a conflict resolver."""
        self.resolvers[resolution] = resolver
        logger.info(f"Added conflict resolver: {resolution}")
    
    def resolve_conflict(self, conflict: Conflict, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Resolve a conflict using the specified resolution strategy.
        
        Args:
            conflict: Conflict to resolve
            context: Resolution context
            
        Returns:
            Resolution result
        """
        try:
            resolver = self.resolvers.get(conflict.resolution)
            
            if not resolver:
                return {
                    'success': False,
                    'error': f'No resolver found for resolution: {conflict.resolution}'
                }
            
            result = resolver(conflict, context or {})
            
            if result['success']:
                conflict.resolve(result['resolved_data'], context.get('resolved_by'))
            
            return result
            
        except Exception as e:
            logger.error(f"Conflict resolution failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _resolve_last_writer_wins(self, conflict: Conflict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict by keeping the last writer's data."""
        try:
            # Get the most recent data based on timestamp
            conflicting_data = conflict.conflicting_data
            
            if not conflicting_data:
                return {
                    'success': False,
                    'error': 'No conflicting data available'
                }
            
            # Find the data with the most recent timestamp
            latest_data = None
            latest_timestamp = None
            
            for data_item in conflicting_data:
                timestamp = data_item.get('timestamp')
                if timestamp:
                    if isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    
                    if latest_timestamp is None or timestamp > latest_timestamp:
                        latest_timestamp = timestamp
                        latest_data = data_item
                else:
                    # If no timestamp, assume it's the most recent
                    if latest_data is None:
                        latest_data = data_item
            
            if not latest_data:
                return {
                    'success': False,
                    'error': 'Unable to determine latest data'
                }
            
            resolved_data = latest_data.get('data', {})
            
            return {
                'success': True,
                'resolved_data': resolved_data,
                'resolution_strategy': ConflictResolution.LAST_WRITER_WINS,
                'selected_source': latest_data['source']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _resolve_first_writer_wins(self, conflict: Conflict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict by keeping the first writer's data."""
        try:
            conflicting_data = conflict.conflicting_data
            
            if not conflicting_data:
                return {
                    'success': False,
                    'error': 'No conflicting data available'
                }
            
            # Use the first data item
            first_data = conflicting_data[0]
            resolved_data = first_data.get('data', {})
            
            return {
                'success': True,
                'resolved_data': resolved_data,
                'resolution_strategy': ConflictResolution.FIRST_WRITER_WINS,
                'selected_source': first_data['source']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _resolve_highest_priority(self, conflict: Conflict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict by keeping the highest priority data."""
        try:
            conflicting_data = conflict.conflicting_data
            
            if not conflicting_data:
                return {
                    'success': False,
                    'error': 'No conflicting data available'
                }
            
            # Find data with highest priority
            highest_priority_data = None
            highest_priority = -1
            
            for data_item in conflicting_data:
                priority = data_item.get('priority', 0)
                if priority > highest_priority:
                    highest_priority = priority
                    highest_priority_data = data_item
            
            if not highest_priority_data:
                # Fallback to first data
                highest_priority_data = conflicting_data[0]
            
            resolved_data = highest_priority_data.get('data', {})
            
            return {
                'success': True,
                'resolved_data': resolved_data,
                'resolution_strategy': ConflictResolution.HIGHEST_PRIORITY,
                'selected_source': highest_priority_data['source']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _resolve_lowest_priority(self, conflict: Conflict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict by keeping the lowest priority data."""
        try:
            conflicting_data = conflict.conflicting_data
            
            if not conflicting_data:
                return {
                    'success': False,
                    'error': 'No conflicting data available'
                }
            
            # Find data with lowest priority
            lowest_priority_data = None
            lowest_priority = float('inf')
            
            for data_item in conflicting_data:
                priority = data_item.get('priority', 0)
                if priority < lowest_priority:
                    lowest_priority = priority
                    lowest_priority_data = data_item
            
            if not lowest_priority_data:
                # Fallback to first data
                lowest_priority_data = conflicting_data[0]
            
            resolved_data = lowest_priority_data.get('data', {})
            
            return {
                'success': True,
                'resolved_data': resolved_data,
                'resolution_strategy': ConflictResolution.LOWEST_PRIORITY,
                'selected_source': lowest_priority_data['source']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _resolve_timestamp_based(self, conflict: Conflict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict based on timestamp."""
        try:
            conflicting_data = conflict.conflicting_data
            
            if not conflicting_data:
                return {
                    'success': False,
                    'error': 'No conflicting data available'
                }
            
            # Find data with most recent timestamp
            latest_data = None
            latest_timestamp = None
            
            for data_item in conflicting_data:
                timestamp = data_item.get('timestamp')
                if timestamp:
                    if isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    
                    if latest_timestamp is None or timestamp > latest_timestamp:
                        latest_timestamp = timestamp
                        latest_data = data_item
            
            if not latest_data:
                return {
                    'success': False,
                    'error': 'Unable to determine latest timestamp'
                }
            
            resolved_data = latest_data.get('data', {})
            
            return {
                'success': True,
                'resolved_data': resolved_data,
                'resolution_strategy': ConflictResolution.TIMESTAMP_BASED,
                'selected_source': latest_data['source']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _resolve_auto_merge(self, conflict: Conflict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict by automatically merging data."""
        try:
            conflicting_data = conflict.conflicting_data
            
            if not conflicting_data:
                return {
                    'success': False,
                    'error': 'No conflicting data available'
                }
            
            # Merge all data sources
            merged_data = {}
            sources = []
            
            for data_item in conflicting_data:
                data = data_item.get('data', {})
                source = data_item.get('source', 'unknown')
                sources.append(source)
                
                # Merge fields
                for field, value in data.items():
                    if field not in merged_data:
                        merged_data[field] = value
                    elif isinstance(merged_data[field], list):
                        if isinstance(value, list):
                            merged_data[field].extend(value)
                        else:
                            merged_data[field].append(value)
                    else:
                        # Convert to list and merge
                        existing = merged_data[field]
                        merged_data[field] = [existing, value]
            
            return {
                'success': True,
                'resolved_data': merged_data,
                'resolution_strategy': ConflictResolution.AUTO_MERGE,
                'merged_sources': sources
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


class SyncManager:
    """
    Main synchronization and conflict management manager.
    """
    
    def __init__(self):
        self.conflict_detector = ConflictDetector()
        self.conflict_resolver = ConflictResolver()
        self.conflicts: Dict[str, Conflict] = {}
        self.sync_sessions: Dict[str, Dict[str, Any]] = {}
        self.max_conflicts = 10000
        self.conflict_resolution_strategies = {
            ConflictType.VERSION_CONFLICT: ConflictResolution.TIMESTAMP_BASED,
            ConflictType.DATA_CONFLICT: ConflictResolution.LAST_WRITER_WINS,
            ConflictType.DUPLICATE_CONFLICT: ConflictResolution.MANUAL,
            ConflictType.REFERENCE_CONFLICT: ConflictResolution.AUTO_MERGE,
            ConflictType.BUSINESS_RULE_CONFLICT: ConflictResolution.HIGHEST_PRIORITY,
            ConflictType.PERMISSION_CONFLICT: ConflictResolution.MANUAL
        }
    
    def synchronize_data(self, resource_type: str, resource_id: str,
                        local_data: Dict[str, Any], remote_data: Dict[str, Any],
                        context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Synchronize data between local and remote sources.
        
        Args:
            resource_type: Type of resource
            resource_id: Resource identifier
            local_data: Local data
            remote_data: Remote data
            context: Synchronization context
            
        Returns:
            Synchronization result
        """
        try:
            # Detect conflicts
            conflicts = self.conflict_detector.detect_conflicts(
                resource_type, resource_id, local_data, remote_data, context
            )
            
            if not conflicts:
                # No conflicts, merge data
                merged_data = self._merge_data(local_data, remote_data)
                
                return {
                    'success': True,
                    'conflicts': [],
                    'merged_data': merged_data,
                    'resolution_strategy': 'no_conflicts'
                }
            
            # Store conflicts
            for conflict in conflicts:
                self.conflicts[conflict.conflict_id] = conflict
            
            # Resolve conflicts
            resolved_data = local_data.copy()
            resolution_results = []
            
            for conflict in conflicts:
                # Get resolution strategy
                strategy = self.conflict_resolution_strategies.get(
                    conflict.conflict_type,
                    conflict.resolution
                )
                
                # Update conflict resolution strategy
                conflict.resolution = strategy
                
                # Resolve conflict
                result = self.conflict_resolver.resolve_conflict(conflict, context)
                resolution_results.append(result)
                
                if result['success']:
                    # Update resolved data
                    resolved_data.update(result['resolved_data'])
                else:
                    return {
                        'success': False,
                        'error': f"Conflict resolution failed: {result.get('error')}",
                        'conflicts': [c.to_dict() for c in conflicts],
                        'resolution_results': resolution_results
                    }
            
            return {
                'success': True,
                'conflicts': [c.to_dict() for c in conflicts],
                'merged_data': resolved_data,
                'resolution_results': resolution_results
            }
            
        except Exception as e:
            logger.error(f"Data synchronization failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _merge_data(self, local_data: Dict[str, Any], remote_data: Dict[str, Any]) -> Dict[str, Any]:
        """Merge local and remote data without conflicts."""
        merged = local_data.copy()
        
        # Add remote fields that don't exist in local
        for field, value in remote_data.items():
            if field not in merged:
                merged[field] = value
        
        return merged
    
    def get_conflict(self, conflict_id: str) -> Optional[Conflict]:
        """Get a specific conflict."""
        return self.conflicts.get(conflict_id)
    
    def get_conflicts(self, status: str = None, conflict_type: str = None,
                    severity: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get conflicts with filtering."""
        conflicts = list(self.conflicts.values())
        
        # Apply filters
        if status:
            conflicts = [c for c in conflicts if c.status == status]
        
        if conflict_type:
            conflicts = [c for c in conflicts if c.conflict_type == conflict_type]
        
        if severity:
            conflicts = [c for c in conflicts if c.severity == severity]
        
        # Sort by creation time (most recent first)
        conflicts.sort(key=lambda c: c.created_at, reverse=True)
        
        return [c.to_dict() for c in conflicts[:limit]]
    
    def resolve_conflict_manually(self, conflict_id: str, resolved_data: Dict[str, Any],
                               resolved_by: int = None) -> Dict[str, Any]:
        """Manually resolve a conflict."""
        conflict = self.conflicts.get(conflict_id)
        
        if not conflict:
            return {
                'success': False,
                'error': f'Conflict not found: {conflict_id}'
            }
        
        try:
            conflict.resolve(resolved_data, resolved_by)
            
            return {
                'success': True,
                'conflict_id': conflict_id,
                'resolved_at': conflict.resolved_at.isoformat(),
                'resolved_by': resolved_by
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def bulk_resolve_conflicts(self, conflict_ids: List[str], resolution: str,
                             context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Bulk resolve conflicts."""
        results = []
        
        for conflict_id in conflict_ids:
            conflict = self.conflicts.get(conflict_id)
            
            if not conflict:
                results.append({
                    'conflict_id': conflict_id,
                    'success': False,
                    'error': 'Conflict not found'
                })
                continue
            
            # Update resolution strategy
            conflict.resolution = resolution
            
            # Resolve conflict
            result = self.conflict_resolver.resolve_conflict(conflict, context)
            results.append({
                'conflict_id': conflict_id,
                'success': result['success'],
                'error': result.get('error')
            })
        
        success_count = len([r for r in results if r['success']])
        
        return {
            'success': True,
            'total_conflicts': len(conflict_ids),
            'resolved_count': success_count,
            'failed_count': len(conflict_ids) - success_count,
            'results': results
        }
    
    def get_sync_statistics(self) -> Dict[str, Any]:
        """Get synchronization statistics."""
        total_conflicts = len(self.conflicts)
        resolved_conflicts = len([c for c in self.conflicts.values() if c.status == 'resolved'])
        pending_conflicts = total_conflicts - resolved_conflicts
        
        # Conflict type distribution
        conflict_types = {}
        for conflict in self.conflicts.values():
            conflict_types[conflict.conflict_type] = conflict_types.get(conflict.conflict_type, 0) + 1
        
        # Severity distribution
        severity_distribution = {}
        for conflict in self.conflicts.values():
            severity_distribution[conflict.severity] = severity_distribution.get(conflict.severity, 0) + 1
        
        return {
            'total_conflicts': total_conflicts,
            'resolved_conflicts': resolved_conflicts,
            'pending_conflicts': pending_conflicts,
            'resolution_rate': (resolved_conflicts / max(total_conflicts, 1)) * 100,
            'conflict_types': conflict_types,
            'severity_distribution': severity_distribution,
            'resolution_strategies': self.conflict_resolution_strategies
        }
    
    def cleanup_resolved_conflicts(self, days: int = 30) -> Dict[str, Any]:
        """Clean up old resolved conflicts."""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            original_count = len(self.conflicts)
            
            # Remove resolved conflicts older than cutoff
            self.conflicts = {
                conflict_id: conflict
                for conflict_id, conflict in self.conflicts.items()
                if not (
                    conflict.status == 'resolved' and
                    conflict.resolved_at and
                    conflict.resolved_at < cutoff_date
                )
            }
            
            removed_count = original_count - len(self.conflicts)
            
            logger.info(f"Cleaned up {removed_count} resolved conflicts older than {days} days")
            
            return {
                'success': True,
                'removed_count': removed_count,
                'remaining_conflicts': len(self.conflicts),
                'cutoff_days': days
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup resolved conflicts: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Global sync manager instance
sync_manager = SyncManager()


# Export classes and functions
__all__ = [
    'ConflictType',
    'ConflictResolution',
    'Conflict',
    'ConflictDetector',
    'ConflictResolver',
    'SyncManager',
    'sync_manager'
]
