"""
interactors.py – Interactor pattern implementation for postback module.

Provides comprehensive interactor functionality including:
- Business logic coordination
- Service orchestration
- Data transformation
- Response formatting
"""
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .repositories import get_postback_log_repository, get_postback_insight_repository, get_network_config_repository
from .services import receive_postback
from .exceptions import PostbackException

logger = logging.getLogger(__name__)
User = get_user_model()


class BaseInteractor:
    """
    Base interactor class.
    
    Provides common interactor functionality that can be
    extended for specific business logic coordination.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.errors = []
        self.warnings = []
        self.result_data = {}
    
    def add_error(self, error: str):
        """Add error message."""
        self.errors.append(error)
        self.logger.error(error)
    
    def add_warning(self, warning: str):
        """Add warning message."""
        self.warnings.append(warning)
        self.logger.warning(warning)
    
    def add_result_data(self, key: str, value: Any):
        """Add result data."""
        self.result_data[key] = value
    
    def has_errors(self) -> bool:
        """Check if there are errors."""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if there are warnings."""
        return len(self.warnings) > 0
    
    def get_result(self) -> Dict[str, Any]:
        """Get interactor result."""
        return {
            'success': not self.has_errors(),
            'errors': self.errors,
            'warnings': self.warnings,
            'data': self.result_data,
            'timestamp': timezone.now().isoformat(),
        }


class PostbackProcessingInteractor(BaseInteractor):
    """
    Interactor for postback processing.
    
    Coordinates the complete postback processing workflow
    between services and repositories.
    """
    
    def __init__(self):
        super().__init__()
        self.postback_repo = get_postback_log_repository()
        self.network_repo = get_network_config_repository()
        self.insight_repo = get_postback_insight_repository()
    
    def execute(self, postback_data: Dict[str, Any], network_key: str) -> Dict[str, Any]:
        """
        Execute postback processing interactor.
        
        Args:
            postback_data: Postback data
            network_key: Network key
            
        Returns:
            Processing result
        """
        try:
            # Step 1: Validate network
            network = self._validate_network(network_key)
            self.add_result_data('network', {
                'id': str(network.id),
                'network_key': network.network_key,
                'name': network.name,
            })
            
            # Step 2: Validate postback data
            self._validate_postback_data(postback_data, network)
            
            # Step 3: Check for duplicates
            duplicate_check = self._check_duplicates(postback_data, network)
            self.add_result_data('duplicate_check', duplicate_check)
            
            if duplicate_check['is_duplicate']:
                return self._create_duplicate_result(duplicate_check)
            
            # Step 4: Process postback
            processing_result = receive_postback(postback_data, network)
            self.add_result_data('processing_result', processing_result)
            
            # Step 5: Update analytics
            analytics_update = self._update_analytics(postback_data, network, processing_result)
            self.add_result_data('analytics_update', analytics_update)
            
            # Step 6: Send notifications
            notification_result = self._send_notifications(postback_data, network, processing_result)
            self.add_result_data('notification_result', notification_result)
            
            return self._create_success_result(processing_result)
            
        except PostbackException as e:
            self.add_error(f"Postback processing failed: {str(e)}")
            return self._create_error_result(str(e))
        except Exception as e:
            self.add_error(f"Unexpected error: {str(e)}")
            return self._create_error_result(str(e))
    
    def _validate_network(self, network_key: str) -> NetworkPostbackConfig:
        """Validate network configuration."""
        network = self.network_repo.by_network(network_key)
        
        if not network:
            raise PostbackException(f"Network {network_key} not found")
        
        network = network[0]  # Get first item from list
        
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
        
        existing_postbacks = self.postback_repo.by_lead_id(lead_id)
        existing_postback = None
        
        for pb in existing_postbacks:
            if pb.network.network_key == network.network_key:
                existing_postback = pb
                break
        
        return {
            'is_duplicate': existing_postback is not None,
            'existing_postback_id': str(existing_postback.id) if existing_postback else None,
        }
    
    def _update_analytics(self, postback_data: Dict[str, Any], network: NetworkPostbackConfig, processing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Update analytics data."""
        # This would integrate with analytics system
        return {
            'updated': True,
            'network_key': network.network_key,
            'postback_status': processing_result.get('status'),
        }
    
    def _send_notifications(self, postback_data: Dict[str, Any], network: NetworkPostbackConfig, processing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Send notifications for postback processing."""
        # This would integrate with notification system
        return {
            'sent': True,
            'notification_type': 'postback_processed',
            'recipients': ['admin'],
        }
    
    def _create_duplicate_result(self, duplicate_check: Dict[str, Any]) -> Dict[str, Any]:
        """Create duplicate result."""
        result = self.get_result()
        result['data']['status'] = 'duplicate'
        result['data']['message'] = 'Duplicate lead ID'
        result['data']['existing_postback_id'] = duplicate_check['existing_postback_id']
        return result
    
    def _create_success_result(self, processing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Create success result."""
        result = self.get_result()
        result['data']['status'] = 'success'
        result['data']['postback_id'] = processing_result.get('postback_id')
        result['data']['payout'] = processing_result.get('payout')
        result['data']['reward_points'] = processing_result.get('reward_points')
        result['data']['message'] = processing_result.get('message', 'Postback processed successfully')
        return result
    
    def _create_error_result(self, error: str) -> Dict[str, Any]:
        """Create error result."""
        result = self.get_result()
        result['data']['status'] = 'error'
        result['data']['message'] = error
        return result


class AnalyticsInteractor(BaseInteractor):
    """
    Interactor for analytics operations.
    
    Coordinates analytics data generation and reporting
    between repositories and services.
    """
    
    def __init__(self):
        super().__init__()
        self.postback_repo = get_postback_log_repository()
        self.insight_repo = get_postback_insight_repository()
        self.network_repo = get_network_config_repository()
    
    def generate_insights(self, network_key: str = None, date: datetime.date = None) -> Dict[str, Any]:
        """
        Generate insights for a specific date.
        
        Args:
            network_key: Network key (None = all networks)
            date: Date for insights (None = today)
            
        Returns:
            Insights generation result
        """
        try:
            # Step 1: Validate parameters
            target_date = date or timezone.now().date()
            
            # Step 2: Get postback data
            postback_data = self._get_postback_data_for_date(network_key, target_date)
            self.add_result_data('postback_data_count', len(postback_data))
            
            # Step 3: Calculate metrics
            metrics = self._calculate_metrics(postback_data)
            self.add_result_data('metrics', metrics)
            
            # Step 4: Generate insights
            insight = self._generate_insight(network_key, target_date, metrics)
            self.add_result_data('insight', insight)
            
            # Step 5: Detect anomalies
            anomalies = self._detect_anomalies(insight, metrics)
            self.add_result_data('anomalies', anomalies)
            
            return self._create_insights_result(insight, anomalies)
            
        except Exception as e:
            self.add_error(f"Insights generation failed: {str(e)}")
            return self._create_error_result(str(e))
    
    def get_analytics_report(self, network_key: str = None, start_date: datetime.date = None, 
                           end_date: datetime.date = None, report_type: str = 'summary') -> Dict[str, Any]:
        """
        Get analytics report.
        
        Args:
            network_key: Network key
            start_date: Start date
            end_date: End date
            report_type: Type of report
            
        Returns:
            Analytics report result
        """
        try:
            # Step 1: Validate parameters
            self._validate_report_parameters(network_key, start_date, end_date, report_type)
            
            # Step 2: Get insights data
            insights_data = self._get_insights_data(network_key, start_date, end_date)
            self.add_result_data('insights_count', len(insights_data))
            
            # Step 3: Generate report
            report = self._generate_report(insights_data, report_type)
            self.add_result_data('report', report)
            
            # Step 4: Add recommendations
            recommendations = self._generate_recommendations(report)
            self.add_result_data('recommendations', recommendations)
            
            return self._create_report_result(report, recommendations)
            
        except Exception as e:
            self.add_error(f"Analytics report failed: {str(e)}")
            return self._create_error_result(str(e))
    
    def _get_postback_data_for_date(self, network_key: str, date: datetime.date) -> List[PostbackLog]:
        """Get postback data for specific date."""
        start_datetime = datetime.combine(date, datetime.min.time())
        end_datetime = datetime.combine(date, datetime.max.time())
        
        postbacks = self.postback_repo.by_date_range(start_datetime, end_datetime)
        
        if network_key:
            postbacks = [pb for pb in postbacks if pb.network.network_key == network_key]
        
        return postbacks
    
    def _calculate_metrics(self, postback_data: List[PostbackLog]) -> Dict[str, Any]:
        """Calculate metrics from postback data."""
        if not postback_data:
            return {
                'total_postbacks': 0,
                'rewarded_postbacks': 0,
                'rejected_postbacks': 0,
                'failed_postbacks': 0,
                'total_payout': 0,
                'conversion_rate': 0,
                'avg_payout': 0,
            }
        
        total_postbacks = len(postback_data)
        rewarded_postbacks = len([pb for pb in postback_data if pb.status == 'rewarded'])
        rejected_postbacks = len([pb for pb in postback_data if pb.status == 'rejected'])
        failed_postbacks = len([pb for pb in postback_data if pb.status == 'failed'])
        total_payout = sum(float(pb.payout) for pb in postback_data if pb.payout)
        
        conversion_rate = (rewarded_postbacks / total_postbacks * 100) if total_postbacks > 0 else 0
        avg_payout = (total_payout / rewarded_postbacks) if rewarded_postbacks > 0 else 0
        
        return {
            'total_postbacks': total_postbacks,
            'rewarded_postbacks': rewarded_postbacks,
            'rejected_postbacks': rejected_postbacks,
            'failed_postbacks': failed_postbacks,
            'total_payout': total_payout,
            'conversion_rate': conversion_rate,
            'avg_payout': avg_payout,
        }
    
    def _generate_insight(self, network_key: str, date: datetime.date, metrics: Dict[str, Any]) -> PostbackInsight:
        """Generate insight from metrics."""
        if network_key:
            network = self.network_repo.by_network(network_key)
            if not network:
                raise PostbackException(f"Network {network_key} not found")
            network = network[0]
        else:
            # For all networks, create a summary insight
            network = None
        
        # Calculate health score
        health_score = self._calculate_health_score(metrics)
        
        # Detect anomalies
        anomaly_detected = self._detect_anomaly_flag(metrics)
        anomaly_details = self._get_anomaly_details(metrics) if anomaly_detected else {}
        
        # Create insight
        if network:
            # Update existing insight or create new one
            existing_insights = self.insight_repo.by_network(network_key)
            existing_insight = None
            
            for insight in existing_insights:
                if insight.date == date:
                    existing_insight = insight
                    break
            
            if existing_insight:
                # Update existing insight
                insight = self.insight_repo.update(existing_insight,
                    received_count=metrics['total_postbacks'],
                    rewarded_count=metrics['rewarded_postbacks'],
                    rejected_count=metrics['rejected_postbacks'],
                    total_payout=metrics['total_payout'],
                    health_score=health_score,
                    anomaly_detected=anomaly_detected,
                    anomaly_details=anomaly_details,
                )
            else:
                # Create new insight
                insight = self.insight_repo.create(
                    network=network,
                    date=date,
                    received_count=metrics['total_postbacks'],
                    rewarded_count=metrics['rewarded_postbacks'],
                    rejected_count=metrics['rejected_postbacks'],
                    total_payout=metrics['total_payout'],
                    health_score=health_score,
                    anomaly_detected=anomaly_detected,
                    anomaly_details=anomaly_details,
                )
        else:
            # Create summary insight (would need a different model or approach)
            insight = None
        
        return insight
    
    def _calculate_health_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate health score from metrics."""
        base_score = 100.0
        
        # Deduct for low conversion rate
        if metrics['conversion_rate'] < 50:
            base_score -= 30
        elif metrics['conversion_rate'] < 70:
            base_score -= 15
        
        # Deduct for high rejection rate
        if metrics['total_postbacks'] > 0:
            rejection_rate = (metrics['rejected_postbacks'] / metrics['total_postbacks']) * 100
            if rejection_rate > 50:
                base_score -= 30
            elif rejection_rate > 30:
                base_score -= 15
        
        # Deduct for zero payout
        if metrics['rewarded_postbacks'] > 0 and metrics['total_payout'] == 0:
            base_score -= 20
        
        return max(0.0, base_score)
    
    def _detect_anomaly_flag(self, metrics: Dict[str, Any]) -> bool:
        """Detect if there's an anomaly."""
        # High rejection rate anomaly
        if metrics['total_postbacks'] > 0:
            rejection_rate = (metrics['rejected_postbacks'] / metrics['total_postbacks']) * 100
            if rejection_rate > 50:
                return True
        
        # Zero payout anomaly
        if metrics['rewarded_postbacks'] > 0 and metrics['total_payout'] == 0:
            return True
        
        # Very low conversion rate
        if metrics['conversion_rate'] < 10:
            return True
        
        return False
    
    def _get_anomaly_details(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Get anomaly details."""
        anomalies = []
        
        if metrics['total_postbacks'] > 0:
            rejection_rate = (metrics['rejected_postbacks'] / metrics['total_postbacks']) * 100
            if rejection_rate > 50:
                anomalies.append({
                    'type': 'high_rejection_rate',
                    'value': rejection_rate,
                    'threshold': 50,
                })
        
        if metrics['conversion_rate'] < 10:
            anomalies.append({
                'type': 'low_conversion_rate',
                'value': metrics['conversion_rate'],
                'threshold': 10,
            })
        
        return {
            'anomalies': anomalies,
            'severity': 'high' if len(anomalies) > 1 else 'medium',
        }
    
    def _detect_anomalies(self, insight: PostbackInsight, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect anomalies in insight."""
        if not insight or not insight.anomaly_detected:
            return []
        
        return insight.anomaly_details.get('anomalies', [])
    
    def _validate_report_parameters(self, network_key: str, start_date: datetime.date, end_date: datetime.date, report_type: str):
        """Validate report parameters."""
        if start_date and end_date and start_date > end_date:
            raise PostbackException("Start date must be before end date")
        
        valid_report_types = ['summary', 'detailed', 'trends']
        if report_type not in valid_report_types:
            raise PostbackException(f"Invalid report type: {report_type}")
    
    def _get_insights_data(self, network_key: str, start_date: datetime.date, end_date: datetime.date) -> List[PostbackInsight]:
        """Get insights data for report."""
        if network_key:
            insights = self.insight_repo.by_network(network_key)
        else:
            insights = self.insight_repo.get_all()
        
        # Filter by date range
        if start_date:
            insights = [insight for insight in insights if insight.date >= start_date]
        if end_date:
            insights = [insight for insight in insights if insight.date <= end_date]
        
        return insights
    
    def _generate_report(self, insights_data: List[PostbackInsight], report_type: str) -> Dict[str, Any]:
        """Generate report from insights data."""
        if report_type == 'summary':
            return self._generate_summary_report(insights_data)
        elif report_type == 'detailed':
            return self._generate_detailed_report(insights_data)
        elif report_type == 'trends':
            return self._generate_trends_report(insights_data)
        else:
            raise PostbackException(f"Unsupported report type: {report_type}")
    
    def _generate_summary_report(self, insights_data: List[PostbackInsight]) -> Dict[str, Any]:
        """Generate summary report."""
        if not insights_data:
            return {
                'report_type': 'summary',
                'total_insights': 0,
                'avg_health_score': 0,
                'total_postbacks': 0,
                'total_payout': 0,
            }
        
        total_insights = len(insights_data)
        avg_health_score = sum(insight.health_score for insight in insights_data) / total_insights
        total_postbacks = sum(insight.received_count for insight in insights_data)
        total_payout = sum(insight.total_payout for insight in insights_data)
        anomaly_count = len([insight for insight in insights_data if insight.anomaly_detected])
        
        return {
            'report_type': 'summary',
            'total_insights': total_insights,
            'avg_health_score': avg_health_score,
            'total_postbacks': total_postbacks,
            'total_payout': total_payout,
            'anomaly_count': anomaly_count,
            'health_score_distribution': self.insight_repo.get_health_score_distribution(),
        }
    
    def _generate_detailed_report(self, insights_data: List[PostbackInsight]) -> Dict[str, Any]:
        """Generate detailed report."""
        return {
            'report_type': 'detailed',
            'insights': [
                {
                    'id': str(insight.id),
                    'network_key': insight.network.network_key,
                    'date': insight.date.isoformat(),
                    'health_score': float(insight.health_score),
                    'received_count': insight.received_count,
                    'rewarded_count': insight.rewarded_count,
                    'rejected_count': insight.rejected_count,
                    'total_payout': float(insight.total_payout),
                    'anomaly_detected': insight.anomaly_detected,
                    'anomaly_details': insight.anomaly_details,
                }
                for insight in insights_data
            ],
        }
    
    def _generate_trends_report(self, insights_data: List[PostbackInsight]) -> Dict[str, Any]:
        """Generate trends report."""
        # Sort insights by date
        sorted_insights = sorted(insights_data, key=lambda x: x.date)
        
        # Calculate trends
        health_scores = [float(insight.health_score) for insight in sorted_insights]
        postback_counts = [insight.received_count for insight in sorted_insights]
        
        return {
            'report_type': 'trends',
            'period': {
                'start': sorted_insights[0].date.isoformat() if sorted_insights else None,
                'end': sorted_insights[-1].date.isoformat() if sorted_insights else None,
            },
            'health_score_trend': health_scores,
            'postback_count_trend': postback_counts,
            'avg_health_score': sum(health_scores) / len(health_scores) if health_scores else 0,
            'total_postbacks': sum(postback_counts),
        }
    
    def _generate_recommendations(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate recommendations from report."""
        recommendations = []
        
        if report['report_type'] == 'summary':
            avg_health_score = report.get('avg_health_score', 0)
            
            if avg_health_score < 50:
                recommendations.append({
                    'type': 'health_improvement',
                    'priority': 'high',
                    'message': 'Overall health score is low. Review network performance.',
                })
            elif avg_health_score < 70:
                recommendations.append({
                    'type': 'health_monitoring',
                    'priority': 'medium',
                    'message': 'Health score could be improved. Monitor closely.',
                })
            
            anomaly_count = report.get('anomaly_count', 0)
            if anomaly_count > 0:
                recommendations.append({
                    'type': 'anomaly_investigation',
                    'priority': 'high',
                    'message': f'{anomaly_count} anomalies detected. Investigate immediately.',
                })
        
        return recommendations
    
    def _create_insights_result(self, insight: PostbackInsight, anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create insights result."""
        result = self.get_result()
        result['data']['status'] = 'success'
        result['data']['message'] = 'Insights generated successfully'
        result['data']['insight_id'] = str(insight.id) if insight else None
        result['data']['anomalies'] = anomalies
        return result
    
    def _create_report_result(self, report: Dict[str, Any], recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create report result."""
        result = self.get_result()
        result['data']['status'] = 'success'
        result['data']['message'] = 'Report generated successfully'
        result['data']['report'] = report
        result['data']['recommendations'] = recommendations
        return result
    
    def _create_error_result(self, error: str) -> Dict[str, Any]:
        """Create error result."""
        result = self.get_result()
        result['data']['status'] = 'error'
        result['data']['message'] = error
        return result


class NetworkManagementInteractor(BaseInteractor):
    """
    Interactor for network management operations.
    
    Coordinates network configuration management
    between repositories and services.
    """
    
    def __init__(self):
        super().__init__()
        self.network_repo = get_network_config_repository()
        self.postback_repo = get_postback_log_repository()
        self.insight_repo = get_postback_insight_repository()
    
    def create_network(self, network_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new network configuration.
        
        Args:
            network_data: Network configuration data
            
        Returns:
            Network creation result
        """
        try:
            # Step 1: Validate network data
            self._validate_network_data(network_data)
            
            # Step 2: Create network
            network = self.network_repo.create(**network_data)
            self.add_result_data('network', {
                'id': str(network.id),
                'network_key': network.network_key,
                'name': network.name,
            })
            
            # Step 3: Setup monitoring
            monitoring_result = self._setup_monitoring(network)
            self.add_result_data('monitoring_result', monitoring_result)
            
            # Step 4: Initialize analytics
            analytics_result = self._initialize_analytics(network)
            self.add_result_data('analytics_result', analytics_result)
            
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
            Network update result
        """
        try:
            # Step 1: Get network
            networks = self.network_repo.by_network(network_key)
            if not networks:
                raise PostbackException(f"Network {network_key} not found")
            
            network = networks[0]
            
            # Step 2: Validate update data
            self._validate_update_data(update_data)
            
            # Step 3: Update network
            updated_network = self.network_repo.update(network, **update_data)
            self.add_result_data('network', {
                'id': str(updated_network.id),
                'network_key': updated_network.network_key,
                'name': updated_network.name,
            })
            
            # Step 4: Update monitoring
            monitoring_result = self._update_monitoring(updated_network)
            self.add_result_data('monitoring_result', monitoring_result)
            
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
            Network deactivation result
        """
        try:
            # Step 1: Get network
            networks = self.network_repo.by_network(network_key)
            if not networks:
                raise PostbackException(f"Network {network_key} not found")
            
            network = networks[0]
            
            # Step 2: Deactivate network
            updated_network = self.network_repo.update(network, is_active=False)
            self.add_result_data('network', {
                'id': str(updated_network.id),
                'network_key': updated_network.network_key,
                'name': updated_network.name,
                'is_active': updated_network.is_active,
            })
            
            # Step 3: Disable monitoring
            monitoring_result = self._disable_monitoring(updated_network)
            self.add_result_data('monitoring_result', monitoring_result)
            
            return self._create_network_result(updated_network, 'deactivated')
            
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
        existing_networks = self.network_repo.by_network(network_key)
        if existing_networks:
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
    
    def _setup_monitoring(self, network: NetworkPostbackConfig) -> Dict[str, Any]:
        """Setup monitoring for new network."""
        # This would integrate with monitoring system
        return {
            'monitoring_enabled': True,
            'network_key': network.network_key,
            'setup_time': timezone.now().isoformat(),
        }
    
    def _initialize_analytics(self, network: NetworkPostbackConfig) -> Dict[str, Any]:
        """Initialize analytics for new network."""
        # This would integrate with analytics system
        return {
            'analytics_enabled': True,
            'network_key': network.network_key,
            'initialization_time': timezone.now().isoformat(),
        }
    
    def _update_monitoring(self, network: NetworkPostbackConfig) -> Dict[str, Any]:
        """Update monitoring for network."""
        # This would integrate with monitoring system
        return {
            'monitoring_updated': True,
            'network_key': network.network_key,
            'update_time': timezone.now().isoformat(),
        }
    
    def _disable_monitoring(self, network: NetworkPostbackConfig) -> Dict[str, Any]:
        """Disable monitoring for network."""
        # This would integrate with monitoring system
        return {
            'monitoring_disabled': True,
            'network_key': network.network_key,
            'disable_time': timezone.now().isoformat(),
        }
    
    def _create_network_result(self, network: NetworkPostbackConfig, action: str) -> Dict[str, Any]:
        """Create network operation result."""
        result = self.get_result()
        result['data']['status'] = 'success'
        result['data']['action'] = action
        result['data']['network_id'] = str(network.id)
        result['data']['network_key'] = network.network_key
        result['data']['name'] = network.name
        result['data']['is_active'] = network.is_active
        result['data']['message'] = f'Network {action} successfully'
        return result
    
    def _create_error_result(self, error: str) -> Dict[str, Any]:
        """Create error result."""
        result = self.get_result()
        result['data']['status'] = 'error'
        result['data']['message'] = error
        return result


# Interactor factory
class InteractorFactory:
    """Factory for creating interactor instances."""
    
    @staticmethod
    def create_postback_processing() -> PostbackProcessingInteractor:
        """Create postback processing interactor."""
        return PostbackProcessingInteractor()
    
    @staticmethod
    def create_analytics() -> AnalyticsInteractor:
        """Create analytics interactor."""
        return AnalyticsInteractor()
    
    @staticmethod
    def create_network_management() -> NetworkManagementInteractor:
        """Create network management interactor."""
        return NetworkManagementInteractor()


# Convenience functions
def process_postback(postback_data: Dict[str, Any], network_key: str) -> Dict[str, Any]:
    """Process postback using interactor."""
    interactor = InteractorFactory.create_postback_processing()
    return interactor.execute(postback_data, network_key)


def generate_insights(network_key: str = None, date: datetime.date = None) -> Dict[str, Any]:
    """Generate insights using interactor."""
    interactor = InteractorFactory.create_analytics()
    return interactor.generate_insights(network_key, date)


def get_analytics_report(network_key: str = None, start_date: datetime.date = None, 
                       end_date: datetime.date = None, report_type: str = 'summary') -> Dict[str, Any]:
    """Get analytics report using interactor."""
    interactor = InteractorFactory.create_analytics()
    return interactor.get_analytics_report(network_key, start_date, end_date, report_type)


def create_network(network_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create network using interactor."""
    interactor = InteractorFactory.create_network_management()
    return interactor.create_network(network_data)


def update_network(network_key: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update network using interactor."""
    interactor = InteractorFactory.create_network_management()
    return interactor.update_network(network_key, update_data)


def deactivate_network(network_key: str) -> Dict[str, Any]:
    """Deactivate network using interactor."""
    interactor = InteractorFactory.create_network_management()
    return interactor.deactivate_network(network_key)


# Interactor utilities
def validate_interactor_result(result: Dict[str, Any]) -> bool:
    """Validate interactor result."""
    return result.get('success', False)


def get_interactor_errors(result: Dict[str, Any]) -> List[str]:
    """Get errors from interactor result."""
    return result.get('errors', [])


def get_interactor_warnings(result: Dict[str, Any]) -> List[str]:
    """Get warnings from interactor result."""
    return result.get('warnings', [])


def get_interactor_data(result: Dict[str, Any]) -> Dict[str, Any]:
    """Get data from interactor result."""
    return result.get('data', {})


# Interactor health check
def check_interactor_health() -> Dict[str, Any]:
    """Check interactor system health."""
    health_status = {
        'overall': 'healthy',
        'interactors': {},
        'issues': [],
    }
    
    # Test postback processing interactor
    try:
        interactor = InteractorFactory.create_postback_processing()
        health_status['interactors']['postback_processing'] = 'healthy'
    except Exception as e:
        health_status['interactors']['postback_processing'] = 'error'
        health_status['issues'].append(f"Postback processing interactor error: {str(e)}")
    
    # Test analytics interactor
    try:
        interactor = InteractorFactory.create_analytics()
        health_status['interactors']['analytics'] = 'healthy'
    except Exception as e:
        health_status['interactors']['analytics'] = 'error'
        health_status['issues'].append(f"Analytics interactor error: {str(e)}")
    
    # Test network management interactor
    try:
        interactor = InteractorFactory.create_network_management()
        health_status['interactors']['network_management'] = 'healthy'
    except Exception as e:
        health_status['interactors']['network_management'] = 'error'
        health_status['issues'].append(f"Network management interactor error: {str(e)}")
    
    if health_status['issues']:
        health_status['overall'] = 'unhealthy'
    
    return health_status
