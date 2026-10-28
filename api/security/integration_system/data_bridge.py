"""
Data Bridge Module
Bridge for data synchronization between systems
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_handler import BaseIntegrationHandler
from .integ_constants import *
from .transformer import transformer_registry
from .circuit_breaker import circuit_breaker_protected

User = get_user_model()
logger = logging.getLogger('security.integration.data_bridge')


class DataBridge(BaseIntegrationHandler):
    """Data bridge for synchronizing data between systems"""
    
    def __init__(self):
        super().__init__("data_bridge")
        self.data_sources = {}
        self.data_targets = {}
        self.sync_rules = {}
        self.sync_jobs = {}
        self.conflict_resolution = 'manual'  # manual, auto_source, auto_target, auto_merge
        self.batch_size = 100
        self.sync_interval = 300  # 5 minutes
        self.max_retries = 3
        self.retry_delay = 10  # seconds
    
    def configure(self, config: Dict[str, Any]):
        """Configure data bridge"""
        super().configure(config)
        
        self.data_sources = config.get('data_sources', {})
        self.data_targets = config.get('data_targets', {})
        self.sync_rules = config.get('sync_rules', {})
        self.conflict_resolution = config.get('conflict_resolution', 'manual')
        self.batch_size = config.get('batch_size', 100)
        self.sync_interval = config.get('sync_interval', 300)
        self.max_retries = config.get('max_retries', 3)
        self.retry_delay = config.get('retry_delay', 10)
    
    def initialize(self) -> bool:
        """Initialize data bridge"""
        try:
            # Validate data sources and targets
            if not self._validate_data_config():
                return False
            
            # Initialize sync jobs
            self._initialize_sync_jobs()
            
            self.initialized = True
            self.health_status = 'healthy'
            return True
            
        except Exception as e:
            logger.error(f"Error initializing data bridge: {e}")
            self.health_status = 'unhealthy'
            return False
    
    def handle(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data bridge event"""
        try:
            sync_type = event_data.get('sync_type', 'manual')
            data_type = event_data.get('data_type')
            
            if sync_type == 'manual':
                return self._perform_manual_sync(event_data)
            elif sync_type == 'scheduled':
                return self._perform_scheduled_sync(event_data)
            elif sync_type == 'real_time':
                return self._perform_real_time_sync(event_data)
            else:
                return {
                    'status': 'error',
                    'message': f'Unknown sync type: {sync_type}'
                }
                
        except Exception as e:
            logger.error(f"Error handling data bridge event: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _validate_data_config(self) -> bool:
        """Validate data source and target configuration"""
        # Validate data sources
        for source_name, source_config in self.data_sources.items():
            if not self._validate_data_source_config(source_config):
                logger.error(f"Invalid data source configuration: {source_name}")
                return False
        
        # Validate data targets
        for target_name, target_config in self.data_targets.items():
            if not self._validate_data_target_config(target_config):
                logger.error(f"Invalid data target configuration: {target_name}")
                return False
        
        return True
    
    def _validate_data_source_config(self, config: Dict[str, Any]) -> bool:
        """Validate data source configuration"""
        required_fields = ['type', 'connection']
        
        for field in required_fields:
            if field not in config:
                return False
        
        # Validate type
        valid_types = ['database', 'api', 'file', 'message_queue']
        if config['type'] not in valid_types:
            return False
        
        return True
    
    def _validate_data_target_config(self, config: Dict[str, Any]) -> bool:
        """Validate data target configuration"""
        required_fields = ['type', 'connection']
        
        for field in required_fields:
            if field not in config:
                return False
        
        # Validate type
        valid_types = ['database', 'api', 'file', 'message_queue']
        if config['type'] not in valid_types:
            return False
        
        return True
    
    def _initialize_sync_jobs(self):
        """Initialize synchronization jobs"""
        for rule_name, rule_config in self.sync_rules.items():
            job = {
                'name': rule_name,
                'source': rule_config['source'],
                'target': rule_config['target'],
                'data_type': rule_config['data_type'],
                'sync_direction': rule_config.get('direction', 'bidirectional'),
                'transformer': rule_config.get('transformer'),
                'filter': rule_config.get('filter'),
                'schedule': rule_config.get('schedule', 'manual'),
                'last_sync': None,
                'status': 'idle',
                'statistics': {
                    'syncs': 0,
                    'successes': 0,
                    'failures': 0,
                    'records_synced': 0,
                    'conflicts': 0
                }
            }
            
            self.sync_jobs[rule_name] = job
    
    def _perform_manual_sync(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform manual synchronization"""
        rule_name = event_data.get('rule_name')
        
        if not rule_name or rule_name not in self.sync_jobs:
            return {
                'status': 'error',
                'message': f'Sync rule not found: {rule_name}'
            }
        
        return self._execute_sync_job(rule_name)
    
    def _perform_scheduled_sync(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform scheduled synchronization"""
        data_type = event_data.get('data_type')
        
        results = []
        for rule_name, job in self.sync_jobs.items():
            if job['data_type'] == data_type and job['schedule'] == 'scheduled':
                result = self._execute_sync_job(rule_name)
                results.append(result)
        
        return {
            'status': 'success',
            'syncs_performed': len(results),
            'results': results
        }
    
    def _perform_real_time_sync(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform real-time synchronization"""
        # Find applicable sync rules
        applicable_rules = []
        
        for rule_name, job in self.sync_jobs.items():
            if job['schedule'] == 'real_time':
                # Check if event matches rule
                if self._event_matches_rule(event_data, job):
                    applicable_rules.append(rule_name)
        
        results = []
        for rule_name in applicable_rules:
            result = self._execute_sync_job(rule_name, event_data)
            results.append(result)
        
        return {
            'status': 'success',
            'syncs_performed': len(results),
            'results': results
        }
    
    def _event_matches_rule(self, event_data: Dict[str, Any], job: Dict[str, Any]) -> bool:
        """Check if event matches sync rule"""
        # Check data type
        if event_data.get('data_type') != job['data_type']:
            return False
        
        # Check filter if exists
        filter_config = job.get('filter')
        if filter_config:
            for field, value in filter_config.items():
                if event_data.get(field) != value:
                    return False
        
        return True
    
    @circuit_breaker_protected('data_sync')
    def _execute_sync_job(self, rule_name: str, event_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute synchronization job"""
        job = self.sync_jobs[rule_name]
        
        try:
            job['status'] = 'running'
            job['statistics']['syncs'] += 1
            
            # Get data from source
            source_data = self._get_source_data(job['source'], job, event_data)
            
            if not source_data:
                return {
                    'status': 'success',
                    'message': 'No data to sync',
                    'rule_name': rule_name
                }
            
            # Transform data if transformer specified
            if job.get('transformer'):
                source_data = self._transform_data(source_data, job['transformer'])
            
            # Sync data to target
            sync_result = self._sync_to_target(job['target'], job, source_data)
            
            # Update job statistics
            if sync_result['success']:
                job['statistics']['successes'] += 1
                job['statistics']['records_synced'] += sync_result.get('records_synced', 0)
                job['last_sync'] = timezone.now()
                job['status'] = 'success'
            else:
                job['statistics']['failures'] += 1
                job['status'] = 'failed'
            
            return {
                'status': sync_result['success'],
                'rule_name': rule_name,
                'records_synced': sync_result.get('records_synced', 0),
                'conflicts': sync_result.get('conflicts', 0),
                'message': sync_result.get('message', 'Sync completed')
            }
            
        except Exception as e:
            job['statistics']['failures'] += 1
            job['status'] = 'error'
            logger.error(f"Error executing sync job {rule_name}: {e}")
            
            return {
                'status': 'error',
                'rule_name': rule_name,
                'message': str(e)
            }
    
    def _get_source_data(self, source_name: str, job: Dict[str, Any], 
                         event_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get data from source"""
        source_config = self.data_sources[source_name]
        source_type = source_config['type']
        
        if source_type == 'database':
            return self._get_database_data(source_config, job, event_data)
        elif source_type == 'api':
            return self._get_api_data(source_config, job, event_data)
        elif source_type == 'file':
            return self._get_file_data(source_config, job, event_data)
        elif source_type == 'message_queue':
            return self._get_message_queue_data(source_config, job, event_data)
        else:
            raise ValueError(f"Unsupported source type: {source_type}")
    
    def _get_database_data(self, config: Dict[str, Any], job: Dict[str, Any], 
                          event_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get data from database source"""
        from django.db import connections
        
        connection_name = config['connection']
        table = config['table']
        query = config.get('query', f"SELECT * FROM {table}")
        
        # Add last sync condition
        if job['last_sync']:
            query += f" WHERE updated_at > '{job['last_sync'].isoformat()}'"
        
        # Add event-specific conditions
        if event_data:
            conditions = []
            for field, value in event_data.items():
                if field in ['id', 'user_id']:
                    conditions.append(f"{field} = '{value}'")
            
            if conditions:
                where_clause = " AND " if 'WHERE' in query else " WHERE "
                query += where_clause + " AND ".join(conditions)
        
        # Execute query
        with connections[connection_name].cursor() as cursor:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            data = []
            for row in rows:
                row_dict = dict(zip(columns, row))
                data.append(row_dict)
            
            return data
    
    def _get_api_data(self, config: Dict[str, Any], job: Dict[str, Any], 
                      event_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get data from API source"""
        import requests
        
        url = config['url']
        headers = config.get('headers', {})
        params = config.get('params', {})
        
        # Add last sync parameter
        if job['last_sync']:
            params['updated_since'] = job['last_sync'].isoformat()
        
        # Add event-specific parameters
        if event_data:
            params.update(event_data)
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Ensure data is a list
        if isinstance(data, dict):
            data = [data]
        
        return data
    
    def _get_file_data(self, config: Dict[str, Any], job: Dict[str, Any], 
                       event_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get data from file source"""
        import json
        import csv
        import os
        
        file_path = config['path']
        file_format = config.get('format', 'json')
        
        if not os.path.exists(file_path):
            return []
        
        data = []
        
        if file_format == 'json':
            with open(file_path, 'r') as f:
                data = json.load(f)
        elif file_format == 'csv':
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                data = list(reader)
        else:
            raise ValueError(f"Unsupported file format: {file_format}")
        
        # Filter by last sync time
        if job['last_sync']:
            filtered_data = []
            for item in data:
                item_time = item.get('updated_at') or item.get('created_at')
                if item_time:
                    try:
                        item_dt = datetime.fromisoformat(item_time.replace('Z', '+00:00'))
                        if item_dt > job['last_sync']:
                            filtered_data.append(item)
                    except ValueError:
                        pass
            data = filtered_data
        
        return data
    
    def _get_message_queue_data(self, config: Dict[str, Any], job: Dict[str, Any], 
                               event_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get data from message queue source"""
        # This would implement message queue data retrieval
        # For now, return empty list
        return []
    
    def _transform_data(self, data: List[Dict[str, Any]], transformer_name: str) -> List[Dict[str, Any]]:
        """Transform data using specified transformer"""
        transformer = transformer_registry.get_transformer(transformer_name)
        
        if not transformer:
            logger.warning(f"Transformer not found: {transformer_name}")
            return data
        
        transformed_data = []
        for item in data:
            try:
                transformed_item = transformer.transform(item)
                transformed_data.append(transformed_item)
            except Exception as e:
                logger.error(f"Error transforming item: {e}")
                transformed_data.append(item)  # Use original item on error
        
        return transformed_data
    
    def _sync_to_target(self, target_name: str, job: Dict[str, Any], 
                        data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Sync data to target"""
        target_config = self.data_targets[target_name]
        target_type = target_config['type']
        
        if target_type == 'database':
            return self._sync_to_database(target_config, job, data)
        elif target_type == 'api':
            return self._sync_to_api(target_config, job, data)
        elif target_type == 'file':
            return self._sync_to_file(target_config, job, data)
        elif target_type == 'message_queue':
            return self._sync_to_message_queue(target_config, job, data)
        else:
            raise ValueError(f"Unsupported target type: {target_type}")
    
    def _sync_to_database(self, config: Dict[str, Any], job: Dict[str, Any], 
                          data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Sync data to database target"""
        from django.db import connections
        
        connection_name = config['connection']
        table = config['table']
        key_field = config.get('key_field', 'id')
        
        records_synced = 0
        conflicts = 0
        
        with connections[connection_name].cursor() as cursor:
            for item in data:
                try:
                    # Check if record exists
                    key_value = item.get(key_field)
                    if not key_value:
                        continue
                    
                    cursor.execute(f"SELECT * FROM {table} WHERE {key_field} = %s", [key_value])
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Handle conflict
                        if self.conflict_resolution == 'auto_source':
                            # Update with source data
                            self._update_database_record(cursor, table, item, key_field)
                            records_synced += 1
                        elif self.conflict_resolution == 'auto_target':
                            # Keep target data
                            conflicts += 1
                        elif self.conflict_resolution == 'auto_merge':
                            # Merge data
                            merged_item = self._merge_data(existing, item)
                            self._update_database_record(cursor, table, merged_item, key_field)
                            records_synced += 1
                        else:  # manual
                            conflicts += 1
                    else:
                        # Insert new record
                        self._insert_database_record(cursor, table, item)
                        records_synced += 1
                
                except Exception as e:
                    logger.error(f"Error syncing record to database: {e}")
        
        return {
            'success': True,
            'records_synced': records_synced,
            'conflicts': conflicts
        }
    
    def _sync_to_api(self, config: Dict[str, Any], job: Dict[str, Any], 
                     data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Sync data to API target"""
        import requests
        
        url = config['url']
        headers = config.get('headers', {})
        method = config.get('method', 'POST')
        
        records_synced = 0
        conflicts = 0
        
        for item in data:
            try:
                if method == 'POST':
                    response = requests.post(url, json=item, headers=headers, timeout=30)
                elif method == 'PUT':
                    key_field = config.get('key_field', 'id')
                    key_value = item.get(key_field)
                    if key_value:
                        response = requests.put(f"{url}{key_value}/", json=item, headers=headers, timeout=30)
                    else:
                        response = requests.post(url, json=item, headers=headers, timeout=30)
                
                if response.status_code in [200, 201]:
                    records_synced += 1
                elif response.status_code == 409:
                    conflicts += 1
                else:
                    logger.warning(f"API sync error: {response.status_code}")
            
            except Exception as e:
                logger.error(f"Error syncing record to API: {e}")
        
        return {
            'success': True,
            'records_synced': records_synced,
            'conflicts': conflicts
        }
    
    def _sync_to_file(self, config: Dict[str, Any], job: Dict[str, Any], 
                      data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Sync data to file target"""
        import json
        import csv
        import os
        
        file_path = config['path']
        file_format = config.get('format', 'json')
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        records_synced = len(data)
        
        if file_format == 'json':
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        elif file_format == 'csv':
            if data:
                with open(file_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
        else:
            raise ValueError(f"Unsupported file format: {file_format}")
        
        return {
            'success': True,
            'records_synced': records_synced,
            'conflicts': 0
        }
    
    def _sync_to_message_queue(self, config: Dict[str, Any], job: Dict[str, Any], 
                               data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Sync data to message queue target"""
        # This would implement message queue data synchronization
        # For now, return success
        return {
            'success': True,
            'records_synced': len(data),
            'conflicts': 0
        }
    
    def _update_database_record(self, cursor, table: str, item: Dict[str, Any], key_field: str):
        """Update database record"""
        set_clause = []
        values = []
        
        for field, value in item.items():
            if field != key_field:
                set_clause.append(f"{field} = %s")
                values.append(value)
        
        values.append(item[key_field])
        
        query = f"UPDATE {table} SET {', '.join(set_clause)} WHERE {key_field} = %s"
        cursor.execute(query, values)
    
    def _insert_database_record(self, cursor, table: str, item: Dict[str, Any]):
        """Insert database record"""
        fields = list(item.keys())
        placeholders = ['%s'] * len(fields)
        values = list(item.values())
        
        query = f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
        cursor.execute(query, values)
    
    def _merge_data(self, existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """Merge existing and new data"""
        merged = existing.copy()
        
        for key, value in new.items():
            # Prefer new data for timestamps and updated fields
            if key in ['updated_at', 'modified_at', 'last_updated']:
                merged[key] = value
            else:
                # Keep existing if new is empty
                if value not in [None, '', []]:
                    merged[key] = value
        
        return merged
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get synchronization status"""
        return {
            'total_jobs': len(self.sync_jobs),
            'running_jobs': len([j for j in self.sync_jobs.values() if j['status'] == 'running']),
            'failed_jobs': len([j for j in self.sync_jobs.values() if j['status'] == 'failed']),
            'jobs': {
                name: {
                    'status': job['status'],
                    'last_sync': job['last_sync'].isoformat() if job['last_sync'] else None,
                    'statistics': job['statistics']
                }
                for name, job in self.sync_jobs.items()
            }
        }
    
    def add_sync_rule(self, rule_name: str, source: str, target: str, data_type: str, **kwargs):
        """Add synchronization rule"""
        rule_config = {
            'source': source,
            'target': target,
            'data_type': data_type,
            'direction': kwargs.get('direction', 'bidirectional'),
            'transformer': kwargs.get('transformer'),
            'filter': kwargs.get('filter'),
            'schedule': kwargs.get('schedule', 'manual')
        }
        
        job = {
            'name': rule_name,
            **rule_config,
            'last_sync': None,
            'status': 'idle',
            'statistics': {
                'syncs': 0,
                'successes': 0,
                'failures': 0,
                'records_synced': 0,
                'conflicts': 0
            }
        }
        
        self.sync_rules[rule_name] = rule_config
        self.sync_jobs[rule_name] = job
        
        logger.info(f"Added sync rule: {rule_name}")
    
    def remove_sync_rule(self, rule_name: str):
        """Remove synchronization rule"""
        if rule_name in self.sync_rules:
            del self.sync_rules[rule_name]
        
        if rule_name in self.sync_jobs:
            del self.sync_jobs[rule_name]
        
        logger.info(f"Removed sync rule: {rule_name}")
    
    def cleanup(self):
        """Clean up data bridge"""
        self.sync_jobs.clear()
        self.sync_rules.clear()
        super().cleanup()


# Export symbols
__all__ = [
    'DataBridge'
]