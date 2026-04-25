"""Data Bridge System

This module provides data bridge functionality for integration system
with comprehensive data transformation and synchronization capabilities.
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from abc import ABC, abstractmethod
from django.utils import timezone
from django.conf import settings
from django.db import transaction

from .integ_constants import BridgeType, HealthStatus, SyncStatus
from .integ_exceptions import BridgeError
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class BaseDataBridge(ABC):
    """
    Abstract base class for data bridge components.
    Defines the interface that all data bridges must implement.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the data bridge."""
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.monitor = PerformanceMonitor()
        
        # Load configuration
        self._load_configuration()
        
        # Initialize bridge
        self._initialize_bridge()
    
    def _load_configuration(self):
        """Load bridge configuration."""
        try:
            self.enabled = self.config.get('enabled', True)
            self.timeout = self.config.get('timeout', 30)
            self.batch_size = self.config.get('batch_size', 100)
            self.enable_compression = self.config.get('enable_compression', False)
            self.enable_encryption = self.config.get('enable_encryption', False)
            
        except Exception as e:
            self.logger.error(f"Error loading bridge configuration: {str(e)}")
            self.enabled = True
            self.timeout = 30
            self.batch_size = 100
            self.enable_compression = False
            self.enable_encryption = False
    
    @abstractmethod
    def _initialize_bridge(self):
        """Initialize the bridge."""
        pass
    
    @abstractmethod
    def transfer_data(self, data: Dict[str, Any], source: str, destination: str) -> bool:
        """
        Transfer data from source to destination.
        
        Args:
            data: Data to transfer
            source: Source identifier
            destination: Destination identifier
            
        Returns:
            True if transfer successful
        """
        pass
    
    @abstractmethod
    def sync_data(self, source: str, destination: str, sync_type: str = 'full') -> Dict[str, Any]:
        """
        Synchronize data between source and destination.
        
        Args:
            source: Source identifier
            destination: Destination identifier
            sync_type: Type of synchronization (full, incremental, delta)
            
        Returns:
            Synchronization result
        """
        pass
    
    @abstractmethod
    def get_bridge_info(self) -> Dict[str, Any]:
        """
        Get bridge information.
        
        Returns:
            Bridge information
        """
        pass
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of bridge.
        
        Returns:
            Health check results
        """
        try:
            return {
                'status': HealthStatus.HEALTHY,
                'enabled': self.enabled,
                'timeout': self.timeout,
                'batch_size': self.batch_size,
                'enable_compression': self.enable_compression,
                'enable_encryption': self.enable_encryption,
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'status': HealthStatus.UNHEALTHY,
                'error': str(e),
                'checked_at': timezone.now().isoformat()
            }


class DatabaseBridge(BaseDataBridge):
    """
    Database bridge for data synchronization.
    Handles database-to-database data transfer and synchronization.
    """
    
    def _initialize_bridge(self):
        """Initialize the database bridge."""
        try:
            self.source_config = self.config.get('source', {})
            self.destination_config = self.config.get('destination', {})
            self.mappings = self.config.get('mappings', {})
            
            # Initialize database connections
            self._initialize_connections()
            
            self.logger.info("Database bridge initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing database bridge: {str(e)}")
            raise
    
    def _initialize_connections(self):
        """Initialize database connections."""
        try:
            from django.db import connections
            
            # Source connection
            self.source_connection = connections[self.source_config.get('connection', 'default')]
            
            # Destination connection
            self.destination_connection = connections[self.destination_config.get('connection', 'default')]
            
        except Exception as e:
            self.logger.error(f"Error initializing connections: {str(e)}")
            raise
    
    def transfer_data(self, data: Dict[str, Any], source: str, destination: str) -> bool:
        """
        Transfer data from source to destination.
        
        Args:
            data: Data to transfer
            source: Source table/collection
            destination: Destination table/collection
            
        Returns:
            True if transfer successful
        """
        try:
            with self.monitor.measure_bridge('database') as measurement:
                # Validate data
                if not self._validate_data(data):
                    raise BridgeError("Invalid data for transfer")
                
                # Apply transformations
                transformed_data = self._transform_data(data, source, destination)
                
                # Transfer to destination
                success = self._insert_data(transformed_data, destination)
                
                if success:
                    self.logger.info(f"Data transferred from {source} to {destination}")
                
                return success
                
        except Exception as e:
            self.logger.error(f"Error transferring data: {str(e)}")
            return False
    
    def sync_data(self, source: str, destination: str, sync_type: str = 'full') -> Dict[str, Any]:
        """
        Synchronize data between source and destination.
        
        Args:
            source: Source table/collection
            destination: Destination table/collection
            sync_type: Type of synchronization
            
        Returns:
            Synchronization result
        """
        try:
            with self.monitor.measure_bridge('database_sync') as measurement:
                result = {
                    'sync_type': sync_type,
                    'source': source,
                    'destination': destination,
                    'started_at': timezone.now().isoformat(),
                    'records_processed': 0,
                    'records_synced': 0,
                    'records_failed': 0,
                    'errors': []
                }
                
                if sync_type == 'full':
                    result = self._full_sync(source, destination, result)
                elif sync_type == 'incremental':
                    result = self._incremental_sync(source, destination, result)
                elif sync_type == 'delta':
                    result = self._delta_sync(source, destination, result)
                else:
                    raise BridgeError(f"Unknown sync type: {sync_type}")
                
                result['completed_at'] = timezone.now().isoformat()
                result['success'] = result['records_failed'] == 0
                
                return result
                
        except Exception as e:
            self.logger.error(f"Error syncing data: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'sync_type': sync_type,
                'source': source,
                'destination': destination
            }
    
    def _validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate data for transfer."""
        try:
            if not isinstance(data, dict):
                return False
            
            if not data:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating data: {str(e)}")
            return False
    
    def _transform_data(self, data: Dict[str, Any], source: str, destination: str) -> Dict[str, Any]:
        """Transform data according to mappings."""
        try:
            mapping_key = f"{source}->{destination}"
            
            if mapping_key in self.mappings:
                mapping = self.mappings[mapping_key]
                transformed_data = {}
                
                for source_field, dest_field in mapping.items():
                    if source_field in data:
                        transformed_data[dest_field] = data[source_field]
                
                return transformed_data
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error transforming data: {str(e)}")
            return data
    
    def _insert_data(self, data: Dict[str, Any], destination: str) -> bool:
        """Insert data into destination."""
        try:
            # This would integrate with your database layer
            # For now, just log the operation
            self.logger.debug(f"Inserting data into {destination}: {data}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error inserting data: {str(e)}")
            return False
    
    def _full_sync(self, source: str, destination: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Perform full synchronization."""
        try:
            # Get all records from source
            source_records = self._get_all_records(source)
            
            for record in source_records:
                try:
                    # Transform and insert
                    transformed_record = self._transform_data(record, source, destination)
                    
                    if self._insert_data(transformed_record, destination):
                        result['records_synced'] += 1
                    else:
                        result['records_failed'] += 1
                    
                    result['records_processed'] += 1
                    
                except Exception as e:
                    result['records_failed'] += 1
                    result['errors'].append(str(e))
                    continue
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in full sync: {str(e)}")
            result['errors'].append(str(e))
            return result
    
    def _incremental_sync(self, source: str, destination: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Perform incremental synchronization."""
        try:
            # Get last sync timestamp
            last_sync = self._get_last_sync_timestamp(source, destination)
            
            # Get records since last sync
            source_records = self._get_records_since(source, last_sync)
            
            for record in source_records:
                try:
                    # Transform and insert
                    transformed_record = self._transform_data(record, source, destination)
                    
                    if self._insert_data(transformed_record, destination):
                        result['records_synced'] += 1
                    else:
                        result['records_failed'] += 1
                    
                    result['records_processed'] += 1
                    
                except Exception as e:
                    result['records_failed'] += 1
                    result['errors'].append(str(e))
                    continue
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in incremental sync: {str(e)}")
            result['errors'].append(str(e))
            return result
    
    def _delta_sync(self, source: str, destination: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Perform delta synchronization."""
        try:
            # Get source and destination records
            source_records = self._get_all_records(source)
            dest_records = self._get_all_records(destination)
            
            # Find differences
            source_keys = {self._get_record_key(r) for r in source_records}
            dest_keys = {self._get_record_key(r) for r in dest_records}
            
            # Records to add (in source but not in destination)
            records_to_add = [r for r in source_records if self._get_record_key(r) not in dest_keys]
            
            # Records to update (in both but different)
            records_to_update = []
            for record in source_records:
                key = self._get_record_key(record)
                if key in dest_keys:
                    dest_record = self._get_record_by_key(dest_records, key)
                    if self._records_differ(record, dest_record):
                        records_to_update.append(record)
            
            # Process additions
            for record in records_to_add:
                try:
                    transformed_record = self._transform_data(record, source, destination)
                    
                    if self._insert_data(transformed_record, destination):
                        result['records_synced'] += 1
                    else:
                        result['records_failed'] += 1
                    
                    result['records_processed'] += 1
                    
                except Exception as e:
                    result['records_failed'] += 1
                    result['errors'].append(str(e))
                    continue
            
            # Process updates
            for record in records_to_update:
                try:
                    transformed_record = self._transform_data(record, source, destination)
                    
                    if self._update_data(transformed_record, destination):
                        result['records_synced'] += 1
                    else:
                        result['records_failed'] += 1
                    
                    result['records_processed'] += 1
                    
                except Exception as e:
                    result['records_failed'] += 1
                    result['errors'].append(str(e))
                    continue
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in delta sync: {str(e)}")
            result['errors'].append(str(e))
            return result
    
    def _get_all_records(self, source: str) -> List[Dict[str, Any]]:
        """Get all records from source."""
        try:
            # This would integrate with your database layer
            # For now, return empty list
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting records from {source}: {str(e)}")
            return []
    
    def _get_records_since(self, source: str, timestamp: timezone.datetime) -> List[Dict[str, Any]]:
        """Get records since timestamp."""
        try:
            # This would integrate with your database layer
            # For now, return empty list
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting records since {timestamp}: {str(e)}")
            return []
    
    def _get_last_sync_timestamp(self, source: str, destination: str) -> timezone.datetime:
        """Get last synchronization timestamp."""
        try:
            # This would integrate with your sync tracking system
            # For now, return a default timestamp
            return timezone.now() - timezone.timedelta(days=1)
            
        except Exception as e:
            self.logger.error(f"Error getting last sync timestamp: {str(e)}")
            return timezone.now() - timezone.timedelta(days=1)
    
    def _get_record_key(self, record: Dict[str, Any]) -> str:
        """Get unique key for record."""
        try:
            # Use ID field or create composite key
            if 'id' in record:
                return str(record['id'])
            else:
                # Create composite key from all fields
                return str(hash(str(sorted(record.items()))))
                
        except Exception as e:
            self.logger.error(f"Error getting record key: {str(e)}")
            return str(hash(str(record)))
    
    def _get_record_by_key(self, records: List[Dict[str, Any]], key: str) -> Optional[Dict[str, Any]]:
        """Get record by key."""
        try:
            for record in records:
                if self._get_record_key(record) == key:
                    return record
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting record by key: {str(e)}")
            return None
    
    def _records_differ(self, record1: Dict[str, Any], record2: Dict[str, Any]) -> bool:
        """Check if records differ."""
        try:
            # Compare all fields except timestamps
            fields1 = {k: v for k, v in record1.items() if k not in ['created_at', 'updated_at']}
            fields2 = {k: v for k, v in record2.items() if k not in ['created_at', 'updated_at']}
            
            return fields1 != fields2
            
        except Exception as e:
            self.logger.error(f"Error comparing records: {str(e)}")
            return True
    
    def _update_data(self, data: Dict[str, Any], destination: str) -> bool:
        """Update data in destination."""
        try:
            # This would integrate with your database layer
            # For now, just log the operation
            self.logger.debug(f"Updating data in {destination}: {data}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating data: {str(e)}")
            return False
    
    def get_bridge_info(self) -> Dict[str, Any]:
        """
        Get database bridge information.
        
        Returns:
            Bridge information
        """
        return {
            'type': BridgeType.DATA_PIPE,
            'name': 'DatabaseBridge',
            'description': 'Bridge for database synchronization',
            'version': '1.0.0',
            'supported_sync_types': ['full', 'incremental', 'delta'],
            'mappings_count': len(self.mappings),
            'enabled': self.enabled,
            'config': self.config
        }


class FileBridge(BaseDataBridge):
    """
    File bridge for data synchronization.
    Handles file-to-file and file-to-database data transfer.
    """
    
    def _initialize_bridge(self):
        """Initialize the file bridge."""
        try:
            self.file_formats = self.config.get('file_formats', ['json', 'csv', 'xml'])
            self.encoding = self.config.get('encoding', 'utf-8')
            self.delimiter = self.config.get('delimiter', ',')
            
            self.logger.info("File bridge initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing file bridge: {str(e)}")
            raise
    
    def transfer_data(self, data: Dict[str, Any], source: str, destination: str) -> bool:
        """
        Transfer data from source file to destination.
        
        Args:
            data: Data to transfer
            source: Source file path
            destination: Destination file path
            
        Returns:
            True if transfer successful
        """
        try:
            with self.monitor.measure_bridge('file') as measurement:
                # Read source file
                source_data = self._read_file(source)
                
                # Merge with provided data
                if isinstance(source_data, list):
                    source_data.append(data)
                else:
                    source_data = [source_data, data]
                
                # Write to destination
                success = self._write_file(destination, source_data)
                
                if success:
                    self.logger.info(f"Data transferred from {source} to {destination}")
                
                return success
                
        except Exception as e:
            self.logger.error(f"Error transferring data: {str(e)}")
            return False
    
    def sync_data(self, source: str, destination: str, sync_type: str = 'full') -> Dict[str, Any]:
        """
        Synchronize data between source and destination files.
        
        Args:
            source: Source file path
            destination: Destination file path
            sync_type: Type of synchronization
            
        Returns:
            Synchronization result
        """
        try:
            with self.monitor.measure_bridge('file_sync') as measurement:
                result = {
                    'sync_type': sync_type,
                    'source': source,
                    'destination': destination,
                    'started_at': timezone.now().isoformat(),
                    'records_processed': 0,
                    'records_synced': 0,
                    'records_failed': 0,
                    'errors': []
                }
                
                # Read source file
                source_data = self._read_file(source)
                
                # Read destination file (if exists)
                try:
                    dest_data = self._read_file(destination)
                except FileNotFoundError:
                    dest_data = []
                
                if sync_type == 'full':
                    result = self._full_file_sync(source_data, dest_data, destination, result)
                elif sync_type == 'incremental':
                    result = self._incremental_file_sync(source_data, dest_data, destination, result)
                else:
                    raise BridgeError(f"Unknown sync type: {sync_type}")
                
                result['completed_at'] = timezone.now().isoformat()
                result['success'] = result['records_failed'] == 0
                
                return result
                
        except Exception as e:
            self.logger.error(f"Error syncing files: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'sync_type': sync_type,
                'source': source,
                'destination': destination
            }
    
    def _read_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Read data from file."""
        try:
            import json
            import csv
            
            file_ext = file_path.split('.')[-1].lower()
            
            if file_ext == 'json':
                with open(file_path, 'r', encoding=self.encoding) as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else [data]
            elif file_ext == 'csv':
                data = []
                with open(file_path, 'r', encoding=self.encoding) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        data.append(dict(row))
                return data
            else:
                raise BridgeError(f"Unsupported file format: {file_ext}")
                
        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {str(e)}")
            raise
    
    def _write_file(self, file_path: str, data: List[Dict[str, Any]]) -> bool:
        """Write data to file."""
        try:
            import json
            import csv
            
            file_ext = file_path.split('.')[-1].lower()
            
            if file_ext == 'json':
                with open(file_path, 'w', encoding=self.encoding) as f:
                    json.dump(data, f, indent=2, default=str)
            elif file_ext == 'csv':
                if data:
                    with open(file_path, 'w', encoding=self.encoding, newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=data[0].keys())
                        writer.writeheader()
                        writer.writerows(data)
            else:
                raise BridgeError(f"Unsupported file format: {file_ext}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error writing file {file_path}: {str(e)}")
            return False
    
    def _full_file_sync(self, source_data: List[Dict[str, Any]], dest_data: List[Dict[str, Any]], destination: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Perform full file synchronization."""
        try:
            # Write all source data to destination
            if self._write_file(destination, source_data):
                result['records_synced'] = len(source_data)
            else:
                result['records_failed'] = len(source_data)
            
            result['records_processed'] = len(source_data)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in full file sync: {str(e)}")
            result['errors'].append(str(e))
            return result
    
    def _incremental_file_sync(self, source_data: List[Dict[str, Any]], dest_data: List[Dict[str, Any]], destination: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Perform incremental file synchronization."""
        try:
            # Find new records (in source but not in destination)
            dest_keys = {self._get_record_key(r) for r in dest_data}
            new_records = [r for r in source_data if self._get_record_key(r) not in dest_keys]
            
            # Append new records to destination
            combined_data = dest_data + new_records
            
            if self._write_file(destination, combined_data):
                result['records_synced'] = len(new_records)
            else:
                result['records_failed'] = len(new_records)
            
            result['records_processed'] = len(new_records)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in incremental file sync: {str(e)}")
            result['errors'].append(str(e))
            return result
    
    def _get_record_key(self, record: Dict[str, Any]) -> str:
        """Get unique key for record."""
        try:
            if 'id' in record:
                return str(record['id'])
            else:
                return str(hash(str(sorted(record.items()))))
                
        except Exception as e:
            self.logger.error(f"Error getting record key: {str(e)}")
            return str(hash(str(record)))
    
    def get_bridge_info(self) -> Dict[str, Any]:
        """
        Get file bridge information.
        
        Returns:
            Bridge information
        """
        return {
            'type': BridgeType.DATA_PIPE,
            'name': 'FileBridge',
            'description': 'Bridge for file synchronization',
            'version': '1.0.0',
            'supported_formats': self.file_formats,
            'encoding': self.encoding,
            'delimiter': self.delimiter,
            'enabled': self.enabled,
            'config': self.config
        }


class DataBridgeManager:
    """
    Main data bridge manager for integration system.
    Coordinates multiple data bridges and provides unified interface.
    """
    
    def __init__(self):
        """Initialize the data bridge manager."""
        self.logger = logger
        self.bridges = {}
        self.monitor = PerformanceMonitor()
        
        # Load configuration
        self._load_configuration()
        
        # Initialize bridges
        self._initialize_bridges()
    
    def _load_configuration(self):
        """Load bridge configuration from settings."""
        try:
            self.config = getattr(settings, 'WEBHOOK_DATA_BRIDGE_CONFIG', {})
            self.enabled_bridges = self.config.get('enabled_bridges', ['database', 'file'])
            
            self.logger.info("Data bridge configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading data bridge configuration: {str(e)}")
            self.config = {}
            self.enabled_bridges = ['database', 'file']
    
    def _initialize_bridges(self):
        """Initialize enabled bridges."""
        try:
            # Initialize database bridge
            if 'database' in self.enabled_bridges:
                database_config = self.config.get('database', {})
                self.bridges['database'] = DatabaseBridge(database_config)
            
            # Initialize file bridge
            if 'file' in self.enabled_bridges:
                file_config = self.config.get('file', {})
                self.bridges['file'] = FileBridge(file_config)
            
            self.logger.info(f"Initialized {len(self.bridges)} data bridges")
            
        except Exception as e:
            self.logger.error(f"Error initializing data bridges: {str(e)}")
    
    def transfer_data(self, bridge_type: str, data: Dict[str, Any], source: str, destination: str) -> bool:
        """
        Transfer data using specified bridge.
        
        Args:
            bridge_type: Type of bridge to use
            data: Data to transfer
            source: Source identifier
            destination: Destination identifier
            
        Returns:
            True if transfer successful
        """
        try:
            if bridge_type not in self.bridges:
                raise BridgeError(f"Bridge {bridge_type} not found")
            
            bridge = self.bridges[bridge_type]
            return bridge.transfer_data(data, source, destination)
            
        except Exception as e:
            self.logger.error(f"Error transferring data with {bridge_type}: {str(e)}")
            return False
    
    def sync_data(self, bridge_type: str, source: str, destination: str, sync_type: str = 'full') -> Dict[str, Any]:
        """
        Synchronize data using specified bridge.
        
        Args:
            bridge_type: Type of bridge to use
            source: Source identifier
            destination: Destination identifier
            sync_type: Type of synchronization
            
        Returns:
            Synchronization result
        """
        try:
            if bridge_type not in self.bridges:
                raise BridgeError(f"Bridge {bridge_type} not found")
            
            bridge = self.bridges[bridge_type]
            return bridge.sync_data(source, destination, sync_type)
            
        except Exception as e:
            self.logger.error(f"Error syncing data with {bridge_type}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'bridge_type': bridge_type,
                'source': source,
                'destination': destination,
                'sync_type': sync_type
            }
    
    def get_bridge_status(self, bridge_type: str = None) -> Dict[str, Any]:
        """
        Get bridge status.
        
        Args:
            bridge_type: Optional specific bridge type
            
        Returns:
            Bridge status information
        """
        try:
            if bridge_type:
                if bridge_type in self.bridges:
                    return self.bridges[bridge_type].health_check()
                else:
                    return {'error': f'Bridge {bridge_type} not found'}
            else:
                return {
                    'total_bridges': len(self.bridges),
                    'enabled_bridges': self.enabled_bridges,
                    'bridges': {
                        name: bridge.health_check()
                        for name, bridge in self.bridges.items()
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Error getting bridge status: {str(e)}")
            return {'error': str(e)}
    
    def register_bridge(self, bridge_type: str, bridge: BaseDataBridge) -> bool:
        """
        Register a custom bridge.
        
        Args:
            bridge_type: Type of bridge
            bridge: Bridge instance
            
        Returns:
            True if registration successful
        """
        try:
            if not isinstance(bridge, BaseDataBridge):
                raise BridgeError("Bridge must inherit from BaseDataBridge")
            
            self.bridges[bridge_type] = bridge
            self.logger.info(f"Bridge {bridge_type} registered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering bridge {bridge_type}: {str(e)}")
            return False
    
    def unregister_bridge(self, bridge_type: str) -> bool:
        """
        Unregister a bridge.
        
        Args:
            bridge_type: Type of bridge to unregister
            
        Returns:
            True if unregistration successful
        """
        try:
            if bridge_type in self.bridges:
                del self.bridges[bridge_type]
                self.logger.info(f"Bridge {bridge_type} unregistered successfully")
                return True
            else:
                self.logger.warning(f"Bridge {bridge_type} not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error unregistering bridge {bridge_type}: {str(e)}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of bridge system.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                'overall': HealthStatus.HEALTHY,
                'components': {},
                'checks': []
            }
            
            # Check bridges
            for bridge_type, bridge in self.bridges.items():
                bridge_health = bridge.health_check()
                health_status['components'][bridge_type] = bridge_health
                
                if bridge_health['status'] != HealthStatus.HEALTHY:
                    health_status['overall'] = HealthStatus.UNHEALTHY
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'overall': HealthStatus.UNHEALTHY,
                'error': str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get bridge system status.
        
        Returns:
            System status
        """
        try:
            return {
                'data_bridge_manager': {
                    'status': 'running',
                    'total_bridges': len(self.bridges),
                    'enabled_bridges': self.enabled_bridges,
                    'uptime': self.monitor.get_uptime(),
                    'performance_metrics': self.monitor.get_system_metrics()
                },
                'bridges': {
                    name: bridge.get_bridge_info()
                    for name, bridge in self.bridges.items()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting bridge status: {str(e)}")
            return {'error': str(e)}
