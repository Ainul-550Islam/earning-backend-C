"""
data_bridge.py – Data Bridge implementation for postback module.

Provides comprehensive data bridging functionality including:
- Data source abstraction
- Data transformation and mapping
- Data synchronization
- Data consistency management
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import threading
import queue
import json

from django.utils import timezone
from django.core.cache import cache
from django.db import transaction, connection

from api.postback.INTEGRATION_SYSTEM.integ_constants import IntegrationType, IntegrationProtocol
from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException
from api.postback.INTEGRATION_SYSTEM.BRIDGE_BUS.transformer import DataTransformer

logger = logging.getLogger(__name__)


class DataSourceType(Enum):
    """Data source type enumeration."""
    DATABASE = "database"
    API = "api"
    FILE = "file"
    MESSAGE_QUEUE = "message_queue"
    CACHE = "cache"
    MEMORY = "memory"
    WEBHOOK = "webhook"
    STREAM = "stream"


class DataSyncMode(Enum):
    """Data synchronization mode enumeration."""
    ONE_WAY = "one_way"
    TWO_WAY = "two_way"
    BROADCAST = "broadcast"
    AGGREGATE = "aggregate"


class DataConsistencyLevel(Enum):
    """Data consistency level enumeration."""
    EVENTUAL = "eventual"
    STRONG = "strong"
    WEAK = "weak"
    READ_YOUR_WRITES = "read_your_writes"


@dataclass
class DataBridgeConfig:
    """Data bridge configuration."""
    name: str
    source_type: DataSourceType
    target_type: DataSourceType
    source_config: Dict[str, Any]
    target_config: Dict[str, Any]
    sync_mode: DataSyncMode = DataSyncMode.ONE_WAY
    consistency_level: DataConsistencyLevel = DataConsistencyLevel.EVENTUAL
    transformation_config: Dict[str, Any] = field(default_factory=dict)
    filter_config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    batch_size: int = 100
    sync_interval: int = 60  # seconds
    retry_attempts: int = 3
    retry_delay: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataRecord:
    """Data record structure."""
    id: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=timezone.now)
    source: str = ""
    target: str = ""
    sync_status: str = "pending"
    error_message: str = ""
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'target': self.target,
            'sync_status': self.sync_status,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
        }


class DataSource(ABC):
    """
    Abstract base class for data sources.
    
    Provides common interface for different data sources.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get('name', 'unnamed')
        self.type = config.get('type')
        self.logger = logging.getLogger(f"data_source.{self.name}")
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to data source."""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from data source."""
        pass
    
    @abstractmethod
    def read(self, query: Dict[str, Any] = None) -> List[DataRecord]:
        """Read data from source."""
        pass
    
    @abstractmethod
    def write(self, records: List[DataRecord]) -> bool:
        """Write data to source."""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        pass


class DatabaseDataSource(DataSource):
    """Database data source implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        config['type'] = DataSourceType.DATABASE
        super().__init__(config)
        self.table_name = config.get('table_name')
        self.connection_string = config.get('connection_string')
    
    def connect(self) -> bool:
        """Connect to database."""
        try:
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            self.logger.info(f"Connected to database: {self.table_name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {str(e)}")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from database."""
        # Django manages connections automatically
        self.logger.info(f"Disconnected from database: {self.table_name}")
        return True
    
    def read(self, query: Dict[str, Any] = None) -> List[DataRecord]:
        """Read data from database."""
        query = query or {}
        records = []
        
        try:
            with connection.cursor() as cursor:
                # Build SQL query based on query parameters
                sql = f"SELECT * FROM {self.table_name}"
                params = []
                
                if 'conditions' in query:
                    conditions = query['conditions']
                    where_clauses = []
                    for field, value in conditions.items():
                        where_clauses.append(f"{field} = %s")
                        params.append(value)
                    
                    if where_clauses:
                        sql += f" WHERE {' AND '.join(where_clauses)}"
                
                if 'limit' in query:
                    sql += f" LIMIT {query['limit']}"
                
                cursor.execute(sql, params)
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                
                for row in rows:
                    record_data = dict(zip(columns, row))
                    record = DataRecord(
                        id=str(record_data.get('id', '')),
                        data=record_data,
                        source='database'
                    )
                    records.append(record)
        
        except Exception as e:
            self.logger.error(f"Error reading from database: {str(e)}")
        
        return records
    
    def write(self, records: List[DataRecord]) -> bool:
        """Write data to database."""
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    for record in records:
                        data = record.data
                        columns = list(data.keys())
                        values = list(data.values())
                        
                        # Build INSERT or UPDATE query
                        if 'id' in data:
                            # Update existing record
                            set_clauses = [f"{col} = %s" for col in columns if col != 'id']
                            sql = f"UPDATE {self.table_name} SET {', '.join(set_clauses)} WHERE id = %s"
                            update_values = [data[col] for col in columns if col != 'id']
                            update_values.append(data['id'])
                            cursor.execute(sql, update_values)
                        else:
                            # Insert new record
                            sql = f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})"
                            cursor.execute(sql, values)
            
            self.logger.info(f"Wrote {len(records)} records to database")
            return True
        
        except Exception as e:
            self.logger.error(f"Error writing to database: {str(e)}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            return {
                'status': 'healthy',
                'connection': 'active',
                'table': self.table_name,
            }
        
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
            }


class APIDataSource(DataSource):
    """API data source implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        config['type'] = DataSourceType.API
        super().__init__(config)
        self.base_url = config.get('base_url')
        self.headers = config.get('headers', {})
        self.auth = config.get('auth', {})
    
    def connect(self) -> bool:
        """Connect to API."""
        try:
            import requests
            
            # Test API connection
            response = requests.get(f"{self.base_url}/health", headers=self.headers, timeout=10)
            response.raise_for_status()
            
            self.logger.info(f"Connected to API: {self.base_url}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to connect to API: {str(e)}")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from API."""
        self.logger.info(f"Disconnected from API: {self.base_url}")
        return True
    
    def read(self, query: Dict[str, Any] = None) -> List[DataRecord]:
        """Read data from API."""
        query = query or {}
        records = []
        
        try:
            import requests
            
            # Build API request
            endpoint = query.get('endpoint', '')
            url = f"{self.base_url}/{endpoint}"
            params = query.get('params', {})
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Handle different response formats
            if isinstance(data, list):
                for item in data:
                    record = DataRecord(
                        id=str(item.get('id', '')),
                        data=item,
                        source='api'
                    )
                    records.append(record)
            elif isinstance(data, dict):
                if 'data' in data:
                    for item in data['data']:
                        record = DataRecord(
                            id=str(item.get('id', '')),
                            data=item,
                            source='api'
                        )
                        records.append(record)
                else:
                    record = DataRecord(
                        id=str(data.get('id', '')),
                        data=data,
                        source='api'
                    )
                    records.append(record)
        
        except Exception as e:
            self.logger.error(f"Error reading from API: {str(e)}")
        
        return records
    
    def write(self, records: List[DataRecord]) -> bool:
        """Write data to API."""
        try:
            import requests
            
            for record in records:
                endpoint = record.data.get('endpoint', '')
                url = f"{self.base_url}/{endpoint}"
                
                response = requests.post(url, json=record.data, headers=self.headers, timeout=30)
                response.raise_for_status()
            
            self.logger.info(f"Wrote {len(records)} records to API")
            return True
        
        except Exception as e:
            self.logger.error(f"Error writing to API: {str(e)}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        try:
            import requests
            
            response = requests.get(f"{self.base_url}/health", headers=self.headers, timeout=10)
            response.raise_for_status()
            
            return {
                'status': 'healthy',
                'connection': 'active',
                'base_url': self.base_url,
            }
        
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
            }


class FileDataSource(DataSource):
    """File data source implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        config['type'] = DataSourceType.FILE
        super().__init__(config)
        self.file_path = config.get('file_path')
        self.file_format = config.get('format', 'json')
    
    def connect(self) -> bool:
        """Connect to file."""
        try:
            import os
            if os.path.exists(self.file_path):
                self.logger.info(f"Connected to file: {self.file_path}")
                return True
            else:
                self.logger.error(f"File not found: {self.file_path}")
                return False
        
        except Exception as e:
            self.logger.error(f"Failed to connect to file: {str(e)}")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from file."""
        self.logger.info(f"Disconnected from file: {self.file_path}")
        return True
    
    def read(self, query: Dict[str, Any] = None) -> List[DataRecord]:
        """Read data from file."""
        records = []
        
        try:
            with open(self.file_path, 'r') as f:
                if self.file_format == 'json':
                    data = json.load(f)
                    
                    if isinstance(data, list):
                        for item in data:
                            record = DataRecord(
                                id=str(item.get('id', '')),
                                data=item,
                                source='file'
                            )
                            records.append(record)
                    elif isinstance(data, dict):
                        record = DataRecord(
                            id=str(data.get('id', '')),
                            data=data,
                            source='file'
                        )
                        records.append(record)
                
                elif self.file_format == 'csv':
                    import csv
                    reader = csv.DictReader(f)
                    for row in reader:
                        record = DataRecord(
                            id=str(row.get('id', '')),
                            data=row,
                            source='file'
                        )
                        records.append(record)
        
        except Exception as e:
            self.logger.error(f"Error reading from file: {str(e)}")
        
        return records
    
    def write(self, records: List[DataRecord]) -> bool:
        """Write data to file."""
        try:
            with open(self.file_path, 'w') as f:
                if self.file_format == 'json':
                    data = [record.data for record in records]
                    json.dump(data, f, indent=2)
                
                elif self.file_format == 'csv':
                    import csv
                    if records:
                        writer = csv.DictWriter(f, fieldnames=records[0].data.keys())
                        writer.writeheader()
                        for record in records:
                            writer.writerow(record.data)
            
            self.logger.info(f"Wrote {len(records)} records to file")
            return True
        
        except Exception as e:
            self.logger.error(f"Error writing to file: {str(e)}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        try:
            import os
            if os.path.exists(self.file_path):
                return {
                    'status': 'healthy',
                    'file_exists': True,
                    'file_path': self.file_path,
                }
            else:
                return {
                    'status': 'unhealthy',
                    'error': 'File not found',
                }
        
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
            }


class DataBridge:
    """
    Data bridge implementation.
    
    Handles data synchronization between different
    data sources with transformation and filtering.
    """
    
    def __init__(self, config: DataBridgeConfig):
        self.config = config
        self.name = config.name
        self.source_type = config.source_type
        self.target_type = config.target_type
        self.sync_mode = config.sync_mode
        self.consistency_level = config.consistency_level
        self.enabled = config.enabled
        self.batch_size = config.batch_size
        self.sync_interval = config.sync_interval
        
        # Initialize data sources
        self.source = self._create_data_source(config.source_config, config.source_type)
        self.target = self._create_data_source(config.target_config, config.target_type)
        
        # Initialize transformer
        self.transformer = DataTransformer(config.transformation_config)
        
        # Statistics
        self.total_synced = 0
        self.total_failed = 0
        self.last_sync_time = None
        self.error_count = 0
        self.last_error = ""
        
        self.logger = logging.getLogger(f"data_bridge.{self.name}")
    
    def _create_data_source(self, config: Dict[str, Any], source_type: DataSourceType) -> DataSource:
        """Create data source based on type."""
        if source_type == DataSourceType.DATABASE:
            return DatabaseDataSource(config)
        elif source_type == DataSourceType.API:
            return APIDataSource(config)
        elif source_type == DataSourceType.FILE:
            return FileDataSource(config)
        else:
            raise IntegrationException(f"Unsupported data source type: {source_type}")
    
    def start(self) -> bool:
        """Start data bridge."""
        try:
            # Connect to data sources
            if not self.source.connect():
                raise IntegrationException("Failed to connect to source")
            
            if not self.target.connect():
                raise IntegrationException("Failed to connect to target")
            
            self.enabled = True
            self.logger.info(f"Data bridge started: {self.name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to start data bridge: {str(e)}")
            return False
    
    def stop(self) -> bool:
        """Stop data bridge."""
        try:
            # Disconnect from data sources
            self.source.disconnect()
            self.target.disconnect()
            
            self.enabled = False
            self.logger.info(f"Data bridge stopped: {self.name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to stop data bridge: {str(e)}")
            return False
    
    def sync_data(self, query: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Synchronize data between sources.
        
        Args:
            query: Query parameters
            
        Returns:
            Sync result
        """
        if not self.enabled:
            return {'success': False, 'error': 'Data bridge is not enabled'}
        
        try:
            # Read data from source
            source_records = self.source.read(query)
            
            # Apply filters
            filtered_records = self._apply_filters(source_records)
            
            # Apply transformations
            transformed_records = self._apply_transformations(filtered_records)
            
            # Write to target
            success = self.target.write(transformed_records)
            
            if success:
                self.total_synced += len(transformed_records)
                self.last_sync_time = timezone.now()
                self.logger.info(f"Synced {len(transformed_records)} records")
                
                return {
                    'success': True,
                    'synced_count': len(transformed_records),
                    'source_count': len(source_records),
                    'filtered_count': len(filtered_records),
                }
            else:
                self.total_failed += len(transformed_records)
                return {'success': False, 'error': 'Failed to write to target'}
        
        except Exception as e:
            self.error_count += 1
            self.last_error = str(e)
            self.logger.error(f"Error syncing data: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _apply_filters(self, records: List[DataRecord]) -> List[DataRecord]:
        """Apply filters to records."""
        filter_config = self.config.filter_config
        
        if not filter_config:
            return records
        
        filtered_records = []
        
        for record in records:
            include = True
            
            # Apply field filters
            if 'field_filters' in filter_config:
                for field, filter_config in filter_config['field_filters'].items():
                    if field in record.data:
                        value = record.data[field]
                        
                        if 'equals' in filter_config and value != filter_config['equals']:
                            include = False
                        elif 'not_equals' in filter_config and value == filter_config['not_equals']:
                            include = False
                        elif 'in' in filter_config and value not in filter_config['in']:
                            include = False
                        elif 'not_in' in filter_config and value in filter_config['not_in']:
                            include = False
            
            if include:
                filtered_records.append(record)
        
        return filtered_records
    
    def _apply_transformations(self, records: List[DataRecord]) -> List[DataRecord]:
        """Apply transformations to records."""
        transformed_records = []
        
        for record in records:
            try:
                # Transform data
                transformed_data = self.transformer.transform_request(record.data)
                
                # Create new record with transformed data
                transformed_record = DataRecord(
                    id=record.id,
                    data=transformed_data,
                    timestamp=record.timestamp,
                    source=record.source,
                    target=self.target_type.value
                )
                
                transformed_records.append(transformed_record)
            
            except Exception as e:
                self.logger.error(f"Error transforming record {record.id}: {str(e)}")
                # Keep original record if transformation fails
                transformed_records.append(record)
        
        return transformed_records
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        source_health = self.source.health_check()
        target_health = self.target.health_check()
        
        overall_health = 'healthy'
        if source_health['status'] != 'healthy' or target_health['status'] != 'healthy':
            overall_health = 'unhealthy'
        
        return {
            'overall': overall_health,
            'enabled': self.enabled,
            'source': source_health,
            'target': target_health,
            'statistics': {
                'total_synced': self.total_synced,
                'total_failed': self.total_failed,
                'error_count': self.error_count,
                'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
                'last_error': self.last_error,
            }
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        return {
            'name': self.name,
            'source_type': self.source_type.value,
            'target_type': self.target_type.value,
            'sync_mode': self.sync_mode.value,
            'consistency_level': self.consistency_level.value,
            'enabled': self.enabled,
            'total_synced': self.total_synced,
            'total_failed': self.total_failed,
            'error_count': self.error_count,
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'last_error': self.last_error,
        }


class DataBridgeManager:
    """
    Manager for data bridges.
    
    Handles bridge registration, lifecycle management,
    and monitoring.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.bridges: Dict[str, DataBridge] = {}
        self._setup_default_bridges()
    
    def _setup_default_bridges(self):
        """Setup default data bridges."""
        # Default bridges would be configured here
        pass
    
    def register_bridge(self, config: DataBridgeConfig) -> bool:
        """
        Register data bridge.
        
        Args:
            config: Bridge configuration
            
        Returns:
            True if registered successfully
        """
        try:
            bridge = DataBridge(config)
            self.bridges[config.name] = bridge
            self.logger.info(f"Data bridge registered: {config.name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to register bridge {config.name}: {str(e)}")
            return False
    
    def unregister_bridge(self, name: str) -> bool:
        """
        Unregister data bridge.
        
        Args:
            name: Bridge name
            
        Returns:
            True if unregistered successfully
        """
        if name in self.bridges:
            bridge = self.bridges[name]
            bridge.stop()
            del self.bridges[name]
            self.logger.info(f"Data bridge unregistered: {name}")
            return True
        return False
    
    def get_bridge(self, name: str) -> Optional[DataBridge]:
        """
        Get bridge by name.
        
        Args:
            name: Bridge name
            
        Returns:
            Bridge or None
        """
        return self.bridges.get(name)
    
    def start_bridge(self, name: str) -> bool:
        """
        Start bridge.
        
        Args:
            name: Bridge name
            
        Returns:
            True if started successfully
        """
        bridge = self.get_bridge(name)
        if bridge:
            return bridge.start()
        return False
    
    def stop_bridge(self, name: str) -> bool:
        """
        Stop bridge.
        
        Args:
            name: Bridge name
            
        Returns:
            True if stopped successfully
        """
        bridge = self.get_bridge(name)
        if bridge:
            return bridge.stop()
        return False
    
    def sync_bridge(self, name: str, query: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Sync data for bridge.
        
        Args:
            name: Bridge name
            query: Query parameters
            
        Returns:
            Sync result
        """
        bridge = self.get_bridge(name)
        if bridge:
            return bridge.sync_data(query)
        return {'success': False, 'error': 'Bridge not found'}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        stats = {
            'total_bridges': len(self.bridges),
            'active_bridges': len([b for b in self.bridges.values() if b.enabled]),
            'bridge_details': {},
            'source_types': {},
            'target_types': {},
        }
        
        for name, bridge in self.bridges.items():
            stats['bridge_details'][name] = bridge.get_statistics()
            
            source_type = bridge.source_type.value
            stats['source_types'][source_type] = stats['source_types'].get(source_type, 0) + 1
            
            target_type = bridge.target_type.value
            stats['target_types'][target_type] = stats['target_types'].get(target_type, 0) + 1
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all bridges."""
        health_status = {
            'overall': 'healthy',
            'total_bridges': len(self.bridges),
            'healthy_bridges': 0,
            'unhealthy_bridges': 0,
            'bridge_health': {},
            'issues': [],
        }
        
        for name, bridge in self.bridges.items():
            try:
                bridge_health = bridge.health_check()
                health_status['bridge_health'][name] = bridge_health
                
                if bridge_health['overall'] == 'healthy':
                    health_status['healthy_bridges'] += 1
                else:
                    health_status['unhealthy_bridges'] += 1
                    health_status['issues'].append(f"Bridge {name} is unhealthy")
            
            except Exception as e:
                health_status['unhealthy_bridges'] += 1
                health_status['issues'].append(f"Error checking bridge {name}: {str(e)}")
        
        if health_status['issues']:
            health_status['overall'] = 'unhealthy'
        
        return health_status


# Global data bridge manager instance
data_bridge_manager = DataBridgeManager()


# Convenience functions
def register_data_bridge(config: DataBridgeConfig) -> bool:
    """Register data bridge."""
    return data_bridge_manager.register_bridge(config)


def sync_data_bridge(name: str, query: Dict[str, Any] = None) -> Dict[str, Any]:
    """Sync data bridge."""
    return data_bridge_manager.sync_bridge(name, query)


def get_data_bridge_statistics() -> Dict[str, Any]:
    """Get data bridge statistics."""
    return data_bridge_manager.get_statistics()


def perform_data_bridge_health_check() -> Dict[str, Any]:
    """Perform data bridge health check."""
    return data_bridge_manager.health_check()
