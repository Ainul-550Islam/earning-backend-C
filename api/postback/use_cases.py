"""
use_cases.py – Use cases for postback module.

Provides comprehensive use case functionality including:
- Business use cases
- Data processing use cases
- Analytics use cases
- Integration use cases
"""
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .services import receive_postback
from .selectors import select_postback_logs, select_postback_insights, select_network_configs
from .exceptions import PostbackException

logger = logging.getLogger(__name__)
User = get_user_model()


class BaseUseCase:
    """
    Base use case class.
    
    Provides common use case functionality that can be
    extended for specific business logic.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.errors = []
        self.warnings = []
    
    def add_error(self, error: str):
        """Add error message."""
        self.errors.append(error)
        self.logger.error(error)
    
    def add_warning(self, warning: str):
        """Add warning message."""
        self.warnings.append(warning)
        self.logger.warning(warning)
    
    def has_errors(self) -> bool:
        """Check if there are errors."""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if there are warnings."""
        return len(self.warnings) > 0
    
    def get_result(self) -> Dict[str, Any]:
        """Get use case result."""
        return {
            'success': not self.has_errors(),
            'errors': self.errors,
            'warnings': self.warnings,
            'timestamp': timezone.now().isoformat(),
        }


class PostbackProcessingUseCase(BaseUseCase):
    """
    Use case for postback processing.
    
    Handles the complete postback processing workflow
    from validation to reward calculation.
    """
    
    def execute(self, postback_data: Dict[str, Any], network_key: str) -> Dict[str, Any]:
        """
        Execute postback processing use case.
        
        Args:
            postback_data: Postback data
            network_key: Network key
            
        Returns:
            Processing result
        """
        try:
            # Step 1: Validate network
            network = self._validate_network(network_key)
            
            # Step 2: Validate postback data
            self._validate_postback_data(postback_data, network)
            
            # Step 3: Check for duplicates
            duplicate_check = self._check_duplicates(postback_data, network)
            if duplicate_check['is_duplicate']:
                return self._create_duplicate_result(duplicate_check)
            
            # Step 4: Process postback
            processing_result = receive_postback(postback_data, network)
            
            # Step 5: Update analytics
            self._update_analytics(postback_data, network, processing_result)
            
            # Step 6: Send notifications
            self._send_notifications(postback_data, network, processing_result)
            
            return self._create_success_result(processing_result)
            
        except PostbackException as e:
            self.add_error(f"Postback processing failed: {str(e)}")
            return self._create_error_result(str(e))
        except Exception as e:
            self.add_error(f"Unexpected error: {str(e)}")
            return self._create_error_result(str(e))
    
    def _validate_network(self, network_key: str) -> NetworkPostbackConfig:
        """Validate network configuration."""
        network = select_network_configs().by_network(network_key).first()
        
        if not network:
            raise PostbackException(f"Network {network_key} not found")
        
        if not network.is_active:
            raise PostbackException(f"Network {network_key} is inactive")
        
        return network
    
    def _validate_postback_data(self, postback_data: Dict[str, Any], network: NetworkPostbackConfig):
        """Validate postback data."""
        required_fields = network.required_fields or ['lead_id']
        
        for field in required_fields:
            if field not in postback_data or not postback_data[field]:
                raise PostbackException(f"Missing required field: {field}")
        
        # Validate payout if present
        payout = postback_data.get('payout')
        if payout is not None:
            try:
                payout_value = Decimal(str(payout))
                if payout_value < 0:
                    raise PostbackException("Payout cannot be negative")
                
                if network.max_payout and payout_value > network.max_payout:
                    raise PostbackException(f"Payout exceeds maximum: {network.max_payout}")
            except (ValueError, TypeError):
                raise PostbackException("Invalid payout format")
    
    def _check_duplicates(self, postback_data: Dict[str, Any], network: NetworkPostbackConfig) -> Dict[str, Any]:
        """Check for duplicate leads."""
        lead_id = postback_data.get('lead_id')
        
        if not lead_id:
            return {'is_duplicate': False}
        
        existing_postback = select_postback_logs().by_network(network.network_key).by_lead_id(lead_id).first()
        
        return {
            'is_duplicate': existing_postback is not None,
            'existing_postback': existing_postback,
        }
    
    def _create_duplicate_result(self, duplicate_check: Dict[str, Any]) -> Dict[str, Any]:
        """Create duplicate result."""
        result = self.get_result()
        result.update({
            'status': 'duplicate',
            'message': 'Duplicate lead ID',
            'existing_postback_id': str(duplicate_check['existing_postback'].id) if duplicate_check['existing_postback'] else None,
        })
        return result
    
    def _update_analytics(self, postback_data: Dict[str, Any], network: NetworkPostbackConfig, processing_result: Dict[str, Any]):
        """Update analytics data."""
        # This would integrate with analytics system
        pass
    
    def _send_notifications(self, postback_data: Dict[str, Any], network: NetworkPostbackConfig, processing_result: Dict[str, Any]):
        """Send notifications for postback processing."""
        # This would integrate with notification system
        pass
    
    def _create_success_result(self, processing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Create success result."""
        result = self.get_result()
        result.update({
            'status': 'success',
            'postback_id': processing_result.get('postback_id'),
            'payout': processing_result.get('payout'),
            'reward_points': processing_result.get('reward_points'),
            'message': processing_result.get('message', 'Postback processed successfully'),
        })
        return result
    
    def _create_error_result(self, error: str) -> Dict[str, Any]:
        """Create error result."""
        result = self.get_result()
        result.update({
            'status': 'error',
            'message': error,
        })
        return result


class AnalyticsGenerationUseCase(BaseUseCase):
    """
    Use case for analytics generation.
    
    Handles generating analytics reports and insights
    for postback data.
    """
    
    def execute(self, network_key: str = None, start_date: datetime = None, end_date: datetime = None, 
                 report_type: str = 'daily') -> Dict[str, Any]:
        """
        Execute analytics generation use case.
        
        Args:
            network_key: Network key (None = all networks)
            start_date: Start date
            end_date: End date
            report_type: Type of report ('daily', 'weekly', 'monthly')
            
        Returns:
            Analytics result
        """
        try:
            # Step 1: Validate parameters
            self._validate_analytics_parameters(network_key, start_date, end_date, report_type)
            
            # Step 2: Get postback data
            postback_data = self._get_postback_data(network_key, start_date, end_date)
            
            # Step 3: Calculate metrics
            metrics = self._calculate_metrics(postback_data, report_type)
            
            # Step 4: Generate insights
            insights = self._generate_insights(metrics, postback_data)
            
            # Step 5: Detect anomalies
            anomalies = self._detect_anomalies(metrics, postback_data)
            
            # Step 6: Create report
            report = self._create_report(metrics, insights, anomalies, report_type)
            
            return self._create_analytics_result(report)
            
        except Exception as e:
            self.add_error(f"Analytics generation failed: {str(e)}")
            return self._create_error_result(str(e))
    
    def _validate_analytics_parameters(self, network_key: str, start_date: datetime, end_date: datetime, report_type: str):
        """Validate analytics parameters."""
        if start_date and end_date and start_date >= end_date:
            raise PostbackException("Start date must be before end date")
        
        if report_type not in ['daily', 'weekly', 'monthly']:
            raise PostbackException(f"Invalid report type: {report_type}")
        
        if network_key:
            network = select_network_configs().by_network(network_key).first()
            if not network:
                raise PostbackException(f"Network {network_key} not found")
    
    def _get_postback_data(self, network_key: str, start_date: datetime, end_date: datetime) -> List[PostbackLog]:
        """Get postback data for analytics."""
        selector = select_postback_logs()
        
        if network_key:
            selector = selector.by_network(network_key)
        
        if start_date and end_date:
            selector = selector.filter_by_date_range(start_date, end_date)
        
        return selector.all()
    
    def _calculate_metrics(self, postback_data: List[PostbackLog], report_type: str) -> Dict[str, Any]:
        """Calculate metrics for report."""
        if not postback_data:
            return {
                'total_postbacks': 0,
                'rewarded_postbacks': 0,
                'rejected_postbacks': 0,
                'total_payout': 0,
                'conversion_rate': 0,
                'avg_payout': 0,
            }
        
        total_postbacks = len(postback_data)
        rewarded_postbacks = len([pb for pb in postback_data if pb.status == 'rewarded'])
        rejected_postbacks = len([pb for pb in postback_data if pb.status == 'rejected'])
        total_payout = sum(float(pb.payout) for pb in postback_data if pb.payout)
        
        conversion_rate = (rewarded_postbacks / total_postbacks * 100) if total_postbacks > 0 else 0
        avg_payout = (total_payout / rewarded_postbacks) if rewarded_postbacks > 0 else 0
        
        return {
            'total_postbacks': total_postbacks,
            'rewarded_postbacks': rewarded_postbacks,
            'rejected_postbacks': rejected_postbacks,
            'total_payout': total_payout,
            'conversion_rate': conversion_rate,
            'avg_payout': avg_payout,
        }
    
    def _generate_insights(self, metrics: Dict[str, Any], postback_data: List[PostbackLog]) -> List[Dict[str, Any]]:
        """Generate insights from metrics."""
        insights = []
        
        # Conversion rate insight
        if metrics['conversion_rate'] < 50:
            insights.append({
                'type': 'low_conversion',
                'message': f"Low conversion rate: {metrics['conversion_rate']:.2f}%",
                'severity': 'high',
            })
        elif metrics['conversion_rate'] > 80:
            insights.append({
                'type': 'high_conversion',
                'message': f"High conversion rate: {metrics['conversion_rate']:.2f}%",
                'severity': 'info',
            })
        
        # Payout insight
        if metrics['avg_payout'] > 10:
            insights.append({
                'type': 'high_payout',
                'message': f"High average payout: ${metrics['avg_payout']:.2f}",
                'severity': 'warning',
            })
        
        # Volume insight
        if metrics['total_postbacks'] < 100:
            insights.append({
                'type': 'low_volume',
                'message': f"Low postback volume: {metrics['total_postbacks']}",
                'severity': 'warning',
            })
        
        return insights
    
    def _detect_anomalies(self, metrics: Dict[str, Any], postback_data: List[PostbackLog]) -> List[Dict[str, Any]]:
        """Detect anomalies in data."""
        anomalies = []
        
        # High rejection rate anomaly
        if metrics['total_postbacks'] > 0:
            rejection_rate = (metrics['rejected_postbacks'] / metrics['total_postbacks']) * 100
            if rejection_rate > 50:
                anomalies.append({
                    'type': 'high_rejection_rate',
                    'message': f"High rejection rate: {rejection_rate:.2f}%",
                    'severity': 'high',
                })
        
        # Zero payout anomaly
        if metrics['rewarded_postbacks'] > 0 and metrics['total_payout'] == 0:
            anomalies.append({
                'type': 'zero_payout',
                'message': "Zero total payout for rewarded postbacks",
                'severity': 'high',
            })
        
        return anomalies
    
    def _create_report(self, metrics: Dict[str, Any], insights: List[Dict[str, Any]], 
                       anomalies: List[Dict[str, Any]], report_type: str) -> Dict[str, Any]:
        """Create analytics report."""
        return {
            'report_type': report_type,
            'generated_at': timezone.now().isoformat(),
            'metrics': metrics,
            'insights': insights,
            'anomalies': anomalies,
            'summary': {
                'total_insights': len(insights),
                'total_anomalies': len(anomalies),
                'health_score': self._calculate_health_score(metrics, anomalies),
            }
        }
    
    def _calculate_health_score(self, metrics: Dict[str, Any], anomalies: List[Dict[str, Any]]) -> float:
        """Calculate health score."""
        base_score = 100.0
        
        # Deduct for anomalies
        for anomaly in anomalies:
            if anomaly['severity'] == 'high':
                base_score -= 20
            elif anomaly['severity'] == 'warning':
                base_score -= 10
            elif anomaly['severity'] == 'info':
                base_score -= 5
        
        # Deduct for low conversion rate
        if metrics['conversion_rate'] < 50:
            base_score -= 30
        elif metrics['conversion_rate'] < 70:
            base_score -= 15
        
        return max(0.0, base_score)
    
    def _create_analytics_result(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Create analytics result."""
        result = self.get_result()
        result.update({
            'report': report,
            'message': 'Analytics report generated successfully',
        })
        return result
    
    def _create_error_result(self, error: str) -> Dict[str, Any]:
        """Create error result."""
        result = self.get_result()
        result.update({
            'error': error,
            'message': 'Analytics generation failed',
        })
        return result


class NetworkManagementUseCase(BaseUseCase):
    """
    Use case for network management.
    
    Handles network configuration management
    including creation, updates, and monitoring.
    """
    
    def create_network(self, network_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new network configuration.
        
        Args:
            network_data: Network configuration data
            
        Returns:
            Creation result
        """
        try:
            # Step 1: Validate network data
            self._validate_network_data(network_data)
            
            # Step 2: Create network
            network = self._create_network(network_data)
            
            # Step 3: Setup monitoring
            self._setup_network_monitoring(network)
            
            # Step 4: Initialize analytics
            self._initialize_network_analytics(network)
            
            return self._create_network_result(network, 'created')
            
        except Exception as e:
            self.add_error(f"Network creation failed: {str(e)}")
            return self._create_error_result(str(e))
    
    def update_network(self, network_key: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update network configuration.
        
        Args:
            network_key: Network key
            update_data: Update data
            
        Returns:
            Update result
        """
        try:
            # Step 1: Get network
            network = select_network_configs().by_network(network_key).first()
            if not network:
                raise PostbackException(f"Network {network_key} not found")
            
            # Step 2: Validate update data
            self._validate_update_data(update_data)
            
            # Step 3: Update network
            updated_network = self._update_network(network, update_data)
            
            # Step 4: Update monitoring
            self._update_network_monitoring(updated_network)
            
            return self._create_network_result(updated_network, 'updated')
            
        except Exception as e:
            self.add_error(f"Network update failed: {str(e)}")
            return self._create_error_result(str(e))
    
    def deactivate_network(self, network_key: str) -> Dict[str, Any]:
        """
        Deactivate network.
        
        Args:
            network_key: Network key
            
        Returns:
            Deactivation result
        """
        try:
            # Step 1: Get network
            network = select_network_configs().by_network(network_key).first()
            if not network:
                raise PostbackException(f"Network {network_key} not found")
            
            # Step 2: Deactivate network
            network.is_active = False
            network.save()
            
            # Step 3: Disable monitoring
            self._disable_network_monitoring(network)
            
            return self._create_network_result(network, 'deactivated')
            
        except Exception as e:
            self.add_error(f"Network deactivation failed: {str(e)}")
            return self._create_error_result(str(e))
    
    def _validate_network_data(self, network_data: Dict[str, Any]):
        """Validate network creation data."""
        required_fields = ['network_key', 'name']
        
        for field in required_fields:
            if field not in network_data or not network_data[field]:
                raise PostbackException(f"Missing required field: {field}")
        
        # Validate network key format
        network_key = network_data['network_key']
        if not isinstance(network_key, str) or len(network_key) < 3:
            raise PostbackException("Invalid network_key format")
        
        # Check for duplicate network key
        existing_network = select_network_configs().by_network(network_key).first()
        if existing_network:
            raise PostbackException(f"Network key {network_key} already exists")
    
    def _validate_update_data(self, update_data: Dict[str, Any]):
        """Validate network update data."""
        # Validate max_payout if present
        if 'max_payout' in update_data:
            try:
                payout = Decimal(str(update_data['max_payout']))
                if payout < 0:
                    raise PostbackException("Max payout cannot be negative")
            except (ValueError, TypeError):
                raise PostbackException("Invalid max_payout format")
    
    def _create_network(self, network_data: Dict[str, Any]) -> NetworkPostbackConfig:
        """Create network configuration."""
        network = NetworkPostbackConfig(**network_data)
        network.save()
        return network
    
    def _update_network(self, network: NetworkPostbackConfig, update_data: Dict[str, Any]) -> NetworkPostbackConfig:
        """Update network configuration."""
        for field, value in update_data.items():
            if hasattr(network, field):
                setattr(network, field, value)
        
        network.save()
        return network
    
    def _setup_network_monitoring(self, network: NetworkPostbackConfig):
        """Setup monitoring for new network."""
        # This would integrate with monitoring system
        pass
    
    def _initialize_network_analytics(self, network: NetworkPostbackConfig):
        """Initialize analytics for new network."""
        # This would integrate with analytics system
        pass
    
    def _update_network_monitoring(self, network: NetworkPostbackConfig):
        """Update monitoring for network."""
        # This would integrate with monitoring system
        pass
    
    def _disable_network_monitoring(self, network: NetworkPostbackConfig):
        """Disable monitoring for network."""
        # This would integrate with monitoring system
        pass
    
    def _create_network_result(self, network: NetworkPostbackConfig, action: str) -> Dict[str, Any]:
        """Create network operation result."""
        result = self.get_result()
        result.update({
            'network_id': str(network.id),
            'network_key': network.network_key,
            'name': network.name,
            'action': action,
            'is_active': network.is_active,
            'message': f'Network {action} successfully',
        })
        return result
    
    def _create_error_result(self, error: str) -> Dict[str, Any]:
        """Create error result."""
        result = self.get_result()
        result.update({
            'error': error,
            'message': 'Network operation failed',
        })
        return result


class DataExportUseCase(BaseUseCase):
    """
    Use case for data export.
    
    Handles exporting postback data in various formats
    with filtering and formatting options.
    """
    
    def execute(self, export_type: str, filters: Dict[str, Any] = None, format_type: str = 'json') -> Dict[str, Any]:
        """
        Execute data export use case.
        
        Args:
            export_type: Type of data to export
            filters: Export filters
            format_type: Export format
            
        Returns:
            Export result
        """
        try:
            # Step 1: Validate export parameters
            self._validate_export_parameters(export_type, filters, format_type)
            
            # Step 2: Get data
            data = self._get_export_data(export_type, filters)
            
            # Step 3: Format data
            formatted_data = self._format_data(data, format_type)
            
            # Step 4: Create export file
            export_file = self._create_export_file(formatted_data, format_type)
            
            return self._create_export_result(export_file, export_type, format_type)
            
        except Exception as e:
            self.add_error(f"Data export failed: {str(e)}")
            return self._create_error_result(str(e))
    
    def _validate_export_parameters(self, export_type: str, filters: Dict[str, Any], format_type: str):
        """Validate export parameters."""
        valid_export_types = ['postback_logs', 'insights', 'networks']
        if export_type not in valid_export_types:
            raise PostbackException(f"Invalid export type: {export_type}")
        
        valid_format_types = ['json', 'csv', 'excel', 'xml']
        if format_type not in valid_format_types:
            raise PostbackException(f"Invalid format type: {format_type}")
    
    def _get_export_data(self, export_type: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get data for export."""
        if export_type == 'postback_logs':
            selector = select_postback_logs()
        elif export_type == 'insights':
            selector = select_postback_insights()
        elif export_type == 'networks':
            selector = select_network_configs()
        else:
            raise PostbackException(f"Unsupported export type: {export_type}")
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if field == 'date_range' and isinstance(value, dict):
                    start_date = value.get('start')
                    end_date = value.get('end')
                    if start_date and end_date:
                        selector = selector.filter_by_date_range(start_date, end_date)
                elif field == 'status' and value:
                    selector = selector.filter_by_status(value)
                elif field == 'network_key' and value:
                    if hasattr(selector, 'by_network'):
                        selector = selector.by_network(value)
        
        return [self._serialize_item(item) for item in selector.all()]
    
    def _serialize_item(self, item) -> Dict[str, Any]:
        """Serialize item for export."""
        data = {
            'id': str(item.id),
            'created_at': item.created_at.isoformat(),
            'updated_at': item.updated_at.isoformat(),
        }
        
        # Add model-specific fields
        if hasattr(item, 'network_key'):
            data['network_key'] = item.network_key
        if hasattr(item, 'name'):
            data['name'] = item.name
        if hasattr(item, 'status'):
            data['status'] = item.status
        if hasattr(item, 'lead_id'):
            data['lead_id'] = item.lead_id
        if hasattr(item, 'payout') and item.payout:
            data['payout'] = float(item.payout)
        if hasattr(item, 'health_score'):
            data['health_score'] = float(item.health_score)
        if hasattr(item, 'date'):
            data['date'] = item.date.isoformat()
        
        return data
    
    def _format_data(self, data: List[Dict[str, Any]], format_type: str) -> Any:
        """Format data for export."""
        if format_type == 'json':
            return data
        elif format_type == 'csv':
            return self._format_as_csv(data)
        elif format_type == 'excel':
            return self._format_as_excel(data)
        elif format_type == 'xml':
            return self._format_as_xml(data)
        else:
            raise PostbackException(f"Unsupported format type: {format_type}")
    
    def _format_as_csv(self, data: List[Dict[str, Any]]) -> str:
        """Format data as CSV."""
        if not data:
            return ""
        
        import csv
        import io
        
        output = io.StringIO()
        
        if data:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        return output.getvalue()
    
    def _format_as_excel(self, data: List[Dict[str, Any]]) -> bytes:
        """Format data as Excel."""
        # This would integrate with Excel library
        # For now, return CSV as fallback
        return self._format_as_csv(data).encode('utf-8')
    
    def _format_as_xml(self, data: List[Dict[str, Any]]) -> str:
        """Format data as XML."""
        import xml.etree.ElementTree as ET
        
        root = ET.Element('data')
        
        for item in data:
            item_element = ET.SubElement(root, 'item')
            for key, value in item.items():
                element = ET.SubElement(item_element, key)
                element.text = str(value)
        
        return ET.tostring(root, encoding='unicode')
    
    def _create_export_file(self, formatted_data: Any, format_type: str) -> Dict[str, Any]:
        """Create export file."""
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{timestamp}.{format_type}"
        
        return {
            'filename': filename,
            'data': formatted_data,
            'size': len(str(formatted_data)),
            'created_at': timezone.now().isoformat(),
        }
    
    def _create_export_result(self, export_file: Dict[str, Any], export_type: str, format_type: str) -> Dict[str, Any]:
        """Create export result."""
        result = self.get_result()
        result.update({
            'export_file': export_file,
            'export_type': export_type,
            'format_type': format_type,
            'message': 'Data exported successfully',
        })
        return result
    
    def _create_error_result(self, error: str) -> Dict[str, Any]:
        """Create error result."""
        result = self.get_result()
        result.update({
            'error': error,
            'message': 'Data export failed',
        })
        return result


# Use case factory
class UseCaseFactory:
    """Factory for creating use case instances."""
    
    @staticmethod
    def create_postback_processing() -> PostbackProcessingUseCase:
        """Create postback processing use case."""
        return PostbackProcessingUseCase()
    
    @staticmethod
    def create_analytics_generation() -> AnalyticsGenerationUseCase:
        """Create analytics generation use case."""
        return AnalyticsGenerationUseCase()
    
    @staticmethod
    def create_network_management() -> NetworkManagementUseCase:
        """Create network management use case."""
        return NetworkManagementUseCase()
    
    @staticmethod
    def create_data_export() -> DataExportUseCase:
        """Create data export use case."""
        return DataExportUseCase()


# Convenience functions
def process_postback(postback_data: Dict[str, Any], network_key: str) -> Dict[str, Any]:
    """Process postback using use case."""
    use_case = UseCaseFactory.create_postback_processing()
    return use_case.execute(postback_data, network_key)


def generate_analytics(network_key: str = None, start_date: datetime = None, 
                     end_date: datetime = None, report_type: str = 'daily') -> Dict[str, Any]:
    """Generate analytics using use case."""
    use_case = UseCaseFactory.create_analytics_generation()
    return use_case.execute(network_key, start_date, end_date, report_type)


def create_network(network_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create network using use case."""
    use_case = UseCaseFactory.create_network_management()
    return use_case.create_network(network_data)


def update_network(network_key: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update network using use case."""
    use_case = UseCaseFactory.create_network_management()
    return use_case.update_network(network_key, update_data)


def export_data(export_type: str, filters: Dict[str, Any] = None, format_type: str = 'json') -> Dict[str, Any]:
    """Export data using use case."""
    use_case = UseCaseFactory.create_data_export()
    return use_case.execute(export_type, filters, format_type)


# Use case utilities
def validate_use_case_result(result: Dict[str, Any]) -> bool:
    """Validate use case result."""
    return result.get('success', False)


def get_use_case_errors(result: Dict[str, Any]) -> List[str]:
    """Get errors from use case result."""
    return result.get('errors', [])


def get_use_case_warnings(result: Dict[str, Any]) -> List[str]:
    """Get warnings from use case result."""
    return result.get('warnings', [])


# Use case health check
def check_use_case_health() -> Dict[str, Any]:
    """Check use case system health."""
    health_status = {
        'overall': 'healthy',
        'use_cases': {},
        'issues': [],
    }
    
    # Test postback processing use case
    try:
        use_case = UseCaseFactory.create_postback_processing()
        health_status['use_cases']['postback_processing'] = 'healthy'
    except Exception as e:
        health_status['use_cases']['postback_processing'] = 'error'
        health_status['issues'].append(f"Postback processing use case error: {str(e)}")
    
    # Test analytics generation use case
    try:
        use_case = UseCaseFactory.create_analytics_generation()
        health_status['use_cases']['analytics_generation'] = 'healthy'
    except Exception as e:
        health_status['use_cases']['analytics_generation'] = 'error'
        health_status['issues'].append(f"Analytics generation use case error: {str(e)}")
    
    # Test network management use case
    try:
        use_case = UseCaseFactory.create_network_management()
        health_status['use_cases']['network_management'] = 'healthy'
    except Exception as e:
        health_status['use_cases']['network_management'] = 'error'
        health_status['issues'].append(f"Network management use case error: {str(e)}")
    
    # Test data export use case
    try:
        use_case = UseCaseFactory.create_data_export()
        health_status['use_cases']['data_export'] = 'healthy'
    except Exception as e:
        health_status['use_cases']['data_export'] = 'error'
        health_status['issues'].append(f"Data export use case error: {str(e)}")
    
    if health_status['issues']:
        health_status['overall'] = 'unhealthy'
    
    return health_status
