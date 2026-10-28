"""
📊 Backup Analytics Module

This module provides comprehensive analytics and reporting capabilities for the backup system.
It includes performance metrics, trend analysis, predictive analytics, and various reporting
formats to help monitor and optimize backup operations.

Features:
- Backup performance analytics
- Storage usage analytics
- Success/failure rate tracking
- Trend analysis and forecasting
- Predictive analytics
- Custom report generation
- Dashboard metrics
- Alert analytics
"""

import logging
import datetime
import json
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
from collections import defaultdict, Counter
import statistics
from django.db.models import Q, Count, Avg, Sum, Max, Min, F, ExpressionWrapper, FloatField
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, Extract
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

# Import backup models
from .models import (
    Backup, BackupSchedule, BackupRestoration, BackupLog, BackupVerification,
    BackupAlert, BackupStorageLocation, RetentionPolicy, BackupNotificationConfig
)

# Import utilities
from .utils import FileUtils, TimeUtils, BackupUtils

logger = logging.getLogger(__name__)


class AnalyticsPeriod(Enum):
    """Enumeration of analytics periods."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class ReportFormat(Enum):
    """Enumeration of report formats."""
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"
    HTML = "html"


class MetricType(Enum):
    """Enumeration of metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    PERCENTAGE = "percentage"
    AVERAGE = "average"
    TREND = "trend"


@dataclass
class MetricDefinition:
    """Definition of an analytics metric."""
    name: str
    metric_type: MetricType
    description: str
    unit: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    calculation_method: Optional[str] = None


@dataclass
class MetricValue:
    """Value of an analytics metric."""
    metric_name: str
    value: Union[int, float, Decimal, str]
    timestamp: datetime.datetime
    period: AnalyticsPeriod
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalyticsReport:
    """Analytics report data structure."""
    report_id: str
    title: str
    description: str
    period: AnalyticsPeriod
    start_date: datetime.datetime
    end_date: datetime.datetime
    metrics: List[MetricValue] = field(default_factory=list)
    charts: List[Dict[str, Any]] = field(default_factory=list)
    summaries: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime.datetime = field(default_factory=timezone.now)


class BackupAnalyticsEngine:
    """Main analytics engine for backup system."""
    
    def __init__(self):
        self.metric_definitions = self._initialize_metric_definitions()
        self.cache_timeout = getattr(settings, 'BACKUP_ANALYTICS_CACHE_TIMEOUT', 300)  # 5 minutes
    
    def _initialize_metric_definitions(self) -> Dict[str, MetricDefinition]:
        """Initialize metric definitions."""
        return {
            # Backup metrics
            'backup_count': MetricDefinition(
                name='backup_count',
                metric_type=MetricType.COUNTER,
                description='Total number of backups',
                unit='count'
            ),
            'backup_success_rate': MetricDefinition(
                name='backup_success_rate',
                metric_type=MetricType.PERCENTAGE,
                description='Backup success rate',
                unit='%'
            ),
            'backup_average_duration': MetricDefinition(
                name='backup_average_duration',
                metric_type=MetricType.AVERAGE,
                description='Average backup duration',
                unit='seconds'
            ),
            'backup_average_size': MetricDefinition(
                name='backup_average_size',
                metric_type=MetricType.AVERAGE,
                description='Average backup size',
                unit='bytes'
            ),
            'backup_total_size': MetricDefinition(
                name='backup_total_size',
                metric_type=MetricType.GAUGE,
                description='Total backup storage used',
                unit='bytes'
            ),
            'backup_failure_rate': MetricDefinition(
                name='backup_failure_rate',
                metric_type=MetricType.PERCENTAGE,
                description='Backup failure rate',
                unit='%'
            ),
            'backup_compression_ratio': MetricDefinition(
                name='backup_compression_ratio',
                metric_type=MetricType.AVERAGE,
                description='Average compression ratio',
                unit='%'
            ),
            'backup_verification_rate': MetricDefinition(
                name='backup_verification_rate',
                metric_type=MetricType.PERCENTAGE,
                description='Backup verification success rate',
                unit='%'
            ),
            
            # Storage metrics
            'storage_utilization': MetricDefinition(
                name='storage_utilization',
                metric_type=MetricType.PERCENTAGE,
                description='Storage utilization percentage',
                unit='%'
            ),
            'storage_growth_rate': MetricDefinition(
                name='storage_growth_rate',
                metric_type=MetricType.TREND,
                description='Storage growth rate',
                unit='%/day'
            ),
            'duplicate_backup_ratio': MetricDefinition(
                name='duplicate_backup_ratio',
                metric_type=MetricType.PERCENTAGE,
                description='Duplicate backup ratio',
                unit='%'
            ),
            
            # Performance metrics
            'backup_throughput': MetricDefinition(
                name='backup_throughput',
                metric_type=MetricType.AVERAGE,
                description='Backup throughput (bytes/second)',
                unit='bytes/sec'
            ),
            'restore_throughput': MetricDefinition(
                name='restore_throughput',
                metric_type=MetricType.AVERAGE,
                description='Restore throughput (bytes/second)',
                unit='bytes/sec'
            ),
            'database_backup_time': MetricDefinition(
                name='database_backup_time',
                metric_type=MetricType.AVERAGE,
                description='Average database backup time',
                unit='seconds'
            ),
            
            # Schedule metrics
            'schedule_adherence': MetricDefinition(
                name='schedule_adherence',
                metric_type=MetricType.PERCENTAGE,
                description='Schedule adherence rate',
                unit='%'
            ),
            'missed_schedules': MetricDefinition(
                name='missed_schedules',
                metric_type=MetricType.COUNTER,
                description='Number of missed schedules',
                unit='count'
            ),
            
            # Alert metrics
            'alert_count': MetricDefinition(
                name='alert_count',
                metric_type=MetricType.COUNTER,
                description='Number of alerts',
                unit='count'
            ),
            'critical_alert_rate': MetricDefinition(
                name='critical_alert_rate',
                metric_type=MetricType.PERCENTAGE,
                description='Critical alert rate',
                unit='%'
            ),
            'alert_resolution_time': MetricDefinition(
                name='alert_resolution_time',
                metric_type=MetricType.AVERAGE,
                description='Average alert resolution time',
                unit='seconds'
            ),
        }
    
    def calculate_metric(self, metric_name: str, period: AnalyticsPeriod,
                        start_date: datetime.datetime, end_date: datetime.datetime,
                        filters: Optional[Dict[str, Any]] = None) -> MetricValue:
        """Calculate a specific metric for the given period."""
        if metric_name not in self.metric_definitions:
            raise ValueError(f"Unknown metric: {metric_name}")
        
        metric_def = self.metric_definitions[metric_name]
        
        # Check cache first
        cache_key = f"backup_analytics_{metric_name}_{period.value}_{start_date.date()}_{end_date.date()}"
        cached_value = cache.get(cache_key)
        if cached_value:
            return cached_value
        
        # Calculate metric based on type
        if metric_name == 'backup_count':
            value = self._calculate_backup_count(start_date, end_date, filters)
        elif metric_name == 'backup_success_rate':
            value = self._calculate_backup_success_rate(start_date, end_date, filters)
        elif metric_name == 'backup_average_duration':
            value = self._calculate_backup_average_duration(start_date, end_date, filters)
        elif metric_name == 'backup_average_size':
            value = self._calculate_backup_average_size(start_date, end_date, filters)
        elif metric_name == 'backup_total_size':
            value = self._calculate_backup_total_size(start_date, end_date, filters)
        elif metric_name == 'backup_failure_rate':
            value = self._calculate_backup_failure_rate(start_date, end_date, filters)
        elif metric_name == 'backup_compression_ratio':
            value = self._calculate_backup_compression_ratio(start_date, end_date, filters)
        elif metric_name == 'backup_verification_rate':
            value = self._calculate_backup_verification_rate(start_date, end_date, filters)
        elif metric_name == 'storage_utilization':
            value = self._calculate_storage_utilization(start_date, end_date, filters)
        elif metric_name == 'storage_growth_rate':
            value = self._calculate_storage_growth_rate(start_date, end_date, filters)
        elif metric_name == 'duplicate_backup_ratio':
            value = self._calculate_duplicate_backup_ratio(start_date, end_date, filters)
        elif metric_name == 'backup_throughput':
            value = self._calculate_backup_throughput(start_date, end_date, filters)
        elif metric_name == 'restore_throughput':
            value = self._calculate_restore_throughput(start_date, end_date, filters)
        elif metric_name == 'database_backup_time':
            value = self._calculate_database_backup_time(start_date, end_date, filters)
        elif metric_name == 'schedule_adherence':
            value = self._calculate_schedule_adherence(start_date, end_date, filters)
        elif metric_name == 'missed_schedules':
            value = self._calculate_missed_schedules(start_date, end_date, filters)
        elif metric_name == 'alert_count':
            value = self._calculate_alert_count(start_date, end_date, filters)
        elif metric_name == 'critical_alert_rate':
            value = self._calculate_critical_alert_rate(start_date, end_date, filters)
        elif metric_name == 'alert_resolution_time':
            value = self._calculate_alert_resolution_time(start_date, end_date, filters)
        else:
            raise ValueError(f"Metric calculation not implemented: {metric_name}")
        
        metric_value = MetricValue(
            metric_name=metric_name,
            value=value,
            timestamp=timezone.now(),
            period=period,
            tags=filters or {}
        )
        
        # Cache the result
        cache.set(cache_key, metric_value, self.cache_timeout)
        
        return metric_value
    
    def _calculate_backup_count(self, start_date: datetime.datetime, end_date: datetime.datetime,
                               filters: Optional[Dict[str, Any]] = None) -> int:
        """Calculate total backup count."""
        queryset = Backup.objects.filter(created_at__range=(start_date, end_date))
        
        if filters:
            if 'backup_type' in filters:
                queryset = queryset.filter(backup_type=filters['backup_type'])
            if 'storage_type' in filters:
                queryset = queryset.filter(storage_type=filters['storage_type'])
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
        
        return queryset.count()
    
    def _calculate_backup_success_rate(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                      filters: Optional[Dict[str, Any]] = None) -> float:
        """Calculate backup success rate."""
        queryset = Backup.objects.filter(created_at__range=(start_date, end_date))
        
        if filters:
            if 'backup_type' in filters:
                queryset = queryset.filter(backup_type=filters['backup_type'])
            if 'storage_type' in filters:
                queryset = queryset.filter(storage_type=filters['storage_type'])
        
        total_count = queryset.count()
        if total_count == 0:
            return 0.0
        
        success_count = queryset.filter(status='completed').count()
        return round((success_count / total_count) * 100, 2)
    
    def _calculate_backup_average_duration(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                         filters: Optional[Dict[str, Any]] = None) -> float:
        """Calculate average backup duration."""
        queryset = Backup.objects.filter(
            created_at__range=(start_date, end_date),
            status='completed'
        ).exclude(duration__isnull=True)
        
        if filters:
            if 'backup_type' in filters:
                queryset = queryset.filter(backup_type=filters['backup_type'])
            if 'storage_type' in filters:
                queryset = queryset.filter(storage_type=filters['storage_type'])
        
        avg_duration = queryset.aggregate(avg_duration=Avg('duration'))['avg_duration']
        return float(avg_duration) if avg_duration else 0.0
    
    def _calculate_backup_average_size(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                     filters: Optional[Dict[str, Any]] = None) -> float:
        """Calculate average backup size."""
        queryset = Backup.objects.filter(
            created_at__range=(start_date, end_date),
            status='completed'
        ).exclude(file_size__isnull=True)
        
        if filters:
            if 'backup_type' in filters:
                queryset = queryset.filter(backup_type=filters['backup_type'])
            if 'storage_type' in filters:
                queryset = queryset.filter(storage_type=filters['storage_type'])
        
        avg_size = queryset.aggregate(avg_size=Avg('file_size'))['avg_size']
        return float(avg_size) if avg_size else 0.0
    
    def _calculate_backup_total_size(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                   filters: Optional[Dict[str, Any]] = None) -> int:
        """Calculate total backup storage used."""
        queryset = Backup.objects.filter(
            created_at__range=(start_date, end_date),
            status='completed'
        ).exclude(file_size__isnull=True)
        
        if filters:
            if 'backup_type' in filters:
                queryset = queryset.filter(backup_type=filters['backup_type'])
            if 'storage_type' in filters:
                queryset = queryset.filter(storage_type=filters['storage_type'])
        
        total_size = queryset.aggregate(total_size=Sum('file_size'))['total_size']
        return int(total_size) if total_size else 0
    
    def _calculate_backup_failure_rate(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                      filters: Optional[Dict[str, Any]] = None) -> float:
        """Calculate backup failure rate."""
        queryset = Backup.objects.filter(created_at__range=(start_date, end_date))
        
        if filters:
            if 'backup_type' in filters:
                queryset = queryset.filter(backup_type=filters['backup_type'])
            if 'storage_type' in filters:
                queryset = queryset.filter(storage_type=filters['storage_type'])
        
        total_count = queryset.count()
        if total_count == 0:
            return 0.0
        
        failure_count = queryset.filter(status='failed').count()
        return round((failure_count / total_count) * 100, 2)
    
    def _calculate_backup_compression_ratio(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                          filters: Optional[Dict[str, Any]] = None) -> float:
        """Calculate average compression ratio."""
        queryset = Backup.objects.filter(
            created_at__range=(start_date, end_date),
            status='completed',
            is_compressed=True
        ).exclude(
            Q(original_size__isnull=True) | Q(file_size__isnull=True)
        )
        
        if filters:
            if 'backup_type' in filters:
                queryset = queryset.filter(backup_type=filters['backup_type'])
            if 'storage_type' in filters:
                queryset = queryset.filter(storage_type=filters['storage_type'])
        
        ratios = []
        for backup in queryset:
            if backup.original_size and backup.file_size and backup.original_size > 0:
                ratio = ((backup.original_size - backup.file_size) / backup.original_size) * 100
                ratios.append(ratio)
        
        return round(statistics.mean(ratios), 2) if ratios else 0.0
    
    def _calculate_backup_verification_rate(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                           filters: Optional[Dict[str, Any]] = None) -> float:
        """Calculate backup verification success rate."""
        queryset = BackupVerification.objects.filter(
            verified_at__range=(start_date, end_date)
        )
        
        if filters:
            if 'verification_method' in filters:
                queryset = queryset.filter(verification_method=filters['verification_method'])
        
        total_count = queryset.count()
        if total_count == 0:
            return 0.0
        
        success_count = queryset.filter(is_valid=True).count()
        return round((success_count / total_count) * 100, 2)
    
    def _calculate_storage_utilization(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                     filters: Optional[Dict[str, Any]] = None) -> float:
        """Calculate storage utilization percentage."""
        locations = BackupStorageLocation.objects.filter(is_active=True)
        
        if filters and 'storage_type' in filters:
            locations = locations.filter(storage_type=filters['storage_type'])
        
        total_capacity = sum(loc.total_space or 0 for loc in locations)
        used_space = sum(loc.used_space or 0 for loc in locations)
        
        if total_capacity == 0:
            return 0.0
        
        return round((used_space / total_capacity) * 100, 2)
    
    def _calculate_storage_growth_rate(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                      filters: Optional[Dict[str, Any]] = None) -> float:
        """Calculate storage growth rate per day."""
        # Get size at start and end of period
        start_size = self._calculate_backup_total_size(
            start_date - datetime.timedelta(days=7), start_date, filters
        )
        end_size = self._calculate_backup_total_size(start_date, end_date, filters)
        
        if start_size == 0:
            return 0.0
        
        days = (end_date - start_date).days or 1
        growth_rate = ((end_size - start_size) / start_size) * 100
        return round(growth_rate / days, 2)
    
    def _calculate_duplicate_backup_ratio(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                         filters: Optional[Dict[str, Any]] = None) -> float:
        """Calculate duplicate backup ratio."""
        queryset = Backup.objects.filter(
            created_at__range=(start_date, end_date),
            status='completed'
        ).exclude(checksum__isnull=True)
        
        if filters:
            if 'backup_type' in filters:
                queryset = queryset.filter(backup_type=filters['backup_type'])
            if 'storage_type' in filters:
                queryset = queryset.filter(storage_type=filters['storage_type'])
        
        # Group by checksum
        checksum_counts = Counter(backup.checksum for backup in queryset)
        
        total_backups = len(checksum_counts)
        duplicate_backups = sum(count - 1 for count in checksum_counts.values() if count > 1)
        
        if total_backups == 0:
            return 0.0
        
        return round((duplicate_backups / total_backups) * 100, 2)
    
    def _calculate_backup_throughput(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                    filters: Optional[Dict[str, Any]] = None) -> float:
        """Calculate backup throughput (bytes/second)."""
        queryset = Backup.objects.filter(
            created_at__range=(start_date, end_date),
            status='completed'
        ).exclude(
            Q(file_size__isnull=True) | Q(duration__isnull=True)
        )
        
        if filters:
            if 'backup_type' in filters:
                queryset = queryset.filter(backup_type=filters['backup_type'])
            if 'storage_type' in filters:
                queryset = queryset.filter(storage_type=filters['storage_type'])
        
        throughputs = []
        for backup in queryset:
            if backup.file_size and backup.duration and backup.duration > 0:
                throughput = backup.file_size / backup.duration
                throughputs.append(throughput)
        
        return round(statistics.mean(throughputs), 2) if throughputs else 0.0
    
    def _calculate_restore_throughput(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                    filters: Optional[Dict[str, Any]] = None) -> float:
        """Calculate restore throughput (bytes/second)."""
        queryset = BackupRestoration.objects.filter(
            created_at__range=(start_date, end_date),
            status='completed'
        ).exclude(
            Q(bytes_restored__isnull=True) | Q(duration__isnull=True)
        )
        
        if filters:
            if 'restoration_type' in filters:
                queryset = queryset.filter(restoration_type=filters['restoration_type'])
        
        throughputs = []
        for restoration in queryset:
            if restoration.bytes_restored and restoration.duration and restoration.duration > 0:
                throughput = restoration.bytes_restored / restoration.duration
                throughputs.append(throughput)
        
        return round(statistics.mean(throughputs), 2) if throughputs else 0.0
    
    def _calculate_database_backup_time(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                       filters: Optional[Dict[str, Any]] = None) -> float:
        """Calculate average database backup time."""
        # Filter logs for database backup operations
        queryset = BackupLog.objects.filter(
            timestamp__range=(start_date, end_date),
            category='backup',
            action='start'
        ).filter(Q(message__icontains='database') | Q(message__icontains='dump'))
        
        if filters:
            if 'database_type' in filters:
                queryset = queryset.filter(message__icontains=filters['database_type'])
        
        # This is a simplified calculation - in practice, you'd correlate start/end logs
        return float(queryset.count()) * 60  # Placeholder: 60 seconds per backup
    
    def _calculate_schedule_adherence(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                    filters: Optional[Dict[str, Any]] = None) -> float:
        """Calculate schedule adherence rate."""
        queryset = BackupSchedule.objects.filter(is_active=True)
        
        if filters:
            if 'frequency' in filters:
                queryset = queryset.filter(frequency=filters['frequency'])
        
        total_schedules = queryset.count()
        if total_schedules == 0:
            return 0.0
        
        # Count schedules that ran on time (within 5 minutes tolerance)
        on_time_count = 0
        tolerance = datetime.timedelta(minutes=5)
        
        for schedule in queryset:
            next_run = schedule.next_run
            if next_run and start_date <= next_run <= end_date:
                # Check if backup was created within tolerance
                backup = Backup.objects.filter(
                    backup_schedule=schedule,
                    created_at__range=(next_run, next_run + tolerance)
                ).first()
                if backup:
                    on_time_count += 1
        
        return round((on_time_count / total_schedules) * 100, 2)
    
    def _calculate_missed_schedules(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                   filters: Optional[Dict[str, Any]] = None) -> int:
        """Calculate number of missed schedules."""
        queryset = BackupSchedule.objects.filter(is_active=True)
        
        if filters:
            if 'frequency' in filters:
                queryset = queryset.filter(frequency=filters['frequency'])
        
        missed_count = 0
        tolerance = datetime.timedelta(minutes=5)
        
        for schedule in queryset:
            next_run = schedule.next_run
            if next_run and start_date <= next_run <= end_date:
                # Check if backup was missed
                backup = Backup.objects.filter(
                    backup_schedule=schedule,
                    created_at__range=(next_run, next_run + tolerance)
                ).first()
                if not backup:
                    missed_count += 1
        
        return missed_count
    
    def _calculate_alert_count(self, start_date: datetime.datetime, end_date: datetime.datetime,
                             filters: Optional[Dict[str, Any]] = None) -> int:
        """Calculate number of alerts."""
        queryset = BackupAlert.objects.filter(created_at__range=(start_date, end_date))
        
        if filters:
            if 'alert_type' in filters:
                queryset = queryset.filter(alert_type=filters['alert_type'])
            if 'severity' in filters:
                queryset = queryset.filter(severity=filters['severity'])
        
        return queryset.count()
    
    def _calculate_critical_alert_rate(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                     filters: Optional[Dict[str, Any]] = None) -> float:
        """Calculate critical alert rate."""
        queryset = BackupAlert.objects.filter(created_at__range=(start_date, end_date))
        
        if filters:
            if 'alert_type' in filters:
                queryset = queryset.filter(alert_type=filters['alert_type'])
        
        total_count = queryset.count()
        if total_count == 0:
            return 0.0
        
        critical_count = queryset.filter(severity='critical').count()
        return round((critical_count / total_count) * 100, 2)
    
    def _calculate_alert_resolution_time(self, start_date: datetime.datetime, end_date: datetime.datetime,
                                        filters: Optional[Dict[str, Any]] = None) -> float:
        """Calculate average alert resolution time."""
        queryset = BackupAlert.objects.filter(
            created_at__range=(start_date, end_date),
            is_resolved=True
        ).exclude(resolved_at__isnull=True)
        
        if filters:
            if 'alert_type' in filters:
                queryset = queryset.filter(alert_type=filters['alert_type'])
            if 'severity' in filters:
                queryset = queryset.filter(severity=filters['severity'])
        
        resolution_times = []
        for alert in queryset:
            if alert.resolved_at:
                resolution_time = (alert.resolved_at - alert.created_at).total_seconds()
                resolution_times.append(resolution_time)
        
        return round(statistics.mean(resolution_times), 2) if resolution_times else 0.0
    
    def generate_report(self, report_type: str, period: AnalyticsPeriod,
                        start_date: datetime.datetime, end_date: datetime.datetime,
                        filters: Optional[Dict[str, Any]] = None,
                        format: ReportFormat = ReportFormat.JSON) -> AnalyticsReport:
        """Generate a comprehensive analytics report."""
        
        # Define report metrics based on type
        if report_type == 'backup_performance':
            metric_names = [
                'backup_count', 'backup_success_rate', 'backup_average_duration',
                'backup_average_size', 'backup_total_size', 'backup_failure_rate',
                'backup_compression_ratio', 'backup_verification_rate'
            ]
        elif report_type == 'storage_analysis':
            metric_names = [
                'storage_utilization', 'storage_growth_rate', 'duplicate_backup_ratio',
                'backup_total_size'
            ]
        elif report_type == 'performance_metrics':
            metric_names = [
                'backup_throughput', 'restore_throughput', 'database_backup_time'
            ]
        elif report_type == 'schedule_analysis':
            metric_names = [
                'schedule_adherence', 'missed_schedules'
            ]
        elif report_type == 'alert_analysis':
            metric_names = [
                'alert_count', 'critical_alert_rate', 'alert_resolution_time'
            ]
        elif report_type == 'comprehensive':
            # Include all metrics
            metric_names = list(self.metric_definitions.keys())
        else:
            raise ValueError(f"Unknown report type: {report_type}")
        
        # Calculate metrics
        metrics = []
        for metric_name in metric_names:
            try:
                metric_value = self.calculate_metric(metric_name, period, start_date, end_date, filters)
                metrics.append(metric_value)
            except Exception as e:
                logger.error(f"Failed to calculate metric {metric_name}: {e}")
        
        # Generate charts
        charts = self._generate_charts(metrics, period, start_date, end_date)
        
        # Generate summaries
        summaries = self._generate_summaries(metrics, report_type)
        
        # Create report
        report = AnalyticsReport(
            report_id=f"report_{report_type}_{period.value}_{int(timezone.now().timestamp())}",
            title=f"{report_type.replace('_', ' ').title()} Report",
            description=f"Analytics report for {report_type} from {start_date.date()} to {end_date.date()}",
            period=period,
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            charts=charts,
            summaries=summaries
        )
        
        return report
    
    def _generate_charts(self, metrics: List[MetricValue], period: AnalyticsPeriod,
                        start_date: datetime.datetime, end_date: datetime.datetime) -> List[Dict[str, Any]]:
        """Generate chart configurations for metrics."""
        charts = []
        
        for metric in metrics:
            chart_config = {
                'type': 'line',  # Default chart type
                'title': f"{metric.metric_name.replace('_', ' ').title()} Over Time",
                'metric_name': metric.metric_name,
                'period': period.value,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'unit': self.metric_definitions[metric.metric_name].unit,
                'data_points': []  # Would be populated with time series data
            }
            
            # Adjust chart type based on metric
            if metric.metric_name in ['backup_count', 'alert_count', 'missed_schedules']:
                chart_config['type'] = 'bar'
            elif metric.metric_name in ['backup_success_rate', 'storage_utilization']:
                chart_config['type'] = 'gauge'
            
            charts.append(chart_config)
        
        return charts
    
    def _generate_summaries(self, metrics: List[MetricValue], report_type: str) -> Dict[str, Any]:
        """Generate summary statistics and insights."""
        summaries = {
            'overall_health': 'good',
            'key_insights': [],
            'recommendations': [],
            'trends': {},
            'anomalies': []
        }
        
        # Analyze metrics for insights
        for metric in metrics:
            metric_def = self.metric_definitions[metric.metric_name]
            value = metric.value
            
            # Generate insights based on metric type and value
            if metric.metric_name == 'backup_success_rate':
                if value >= 95:
                    summaries['key_insights'].append(f"Excellent backup success rate: {value}%")
                elif value >= 90:
                    summaries['key_insights'].append(f"Good backup success rate: {value}%")
                else:
                    summaries['key_insights'].append(f"Backup success rate needs attention: {value}%")
                    summaries['recommendations'].append("Investigate backup failures and improve reliability")
                    summaries['overall_health'] = 'warning'
            
            elif metric.metric_name == 'storage_utilization':
                if value >= 90:
                    summaries['key_insights'].append(f"High storage utilization: {value}%")
                    summaries['recommendations'].append("Consider storage cleanup or expansion")
                    summaries['overall_health'] = 'critical'
                elif value >= 75:
                    summaries['key_insights'].append(f"Moderate storage utilization: {value}%")
                    summaries['recommendations'].append("Monitor storage growth and plan for expansion")
            
            elif metric.metric_name == 'backup_failure_rate':
                if value > 10:
                    summaries['key_insights'].append(f"High backup failure rate: {value}%")
                    summaries['recommendations'].append("Investigate and resolve backup failures")
                    summaries['overall_health'] = 'critical'
            
            elif metric.metric_name == 'duplicate_backup_ratio':
                if value > 20:
                    summaries['key_insights'].append(f"High duplicate backup ratio: {value}%")
                    summaries['recommendations'].append("Implement deduplication to reduce storage costs")
        
        return summaries
    
    def get_dashboard_metrics(self, period: AnalyticsPeriod = AnalyticsPeriod.DAILY) -> Dict[str, Any]:
        """Get metrics for dashboard display."""
        end_date = timezone.now()
        
        if period == AnalyticsPeriod.DAILY:
            start_date = end_date - datetime.timedelta(days=1)
        elif period == AnalyticsPeriod.WEEKLY:
            start_date = end_date - datetime.timedelta(weeks=1)
        elif period == AnalyticsPeriod.MONTHLY:
            start_date = end_date - datetime.timedelta(days=30)
        else:
            start_date = end_date - datetime.timedelta(days=1)
        
        # Key dashboard metrics
        dashboard_metrics = [
            'backup_count', 'backup_success_rate', 'storage_utilization',
            'backup_average_duration', 'alert_count', 'backup_total_size'
        ]
        
        metrics = {}
        for metric_name in dashboard_metrics:
            try:
                metric_value = self.calculate_metric(metric_name, period, start_date, end_date)
                metrics[metric_name] = {
                    'value': metric_value.value,
                    'unit': self.metric_definitions[metric_name].unit,
                    'trend': 'stable'  # Would calculate trend based on historical data
                }
            except Exception as e:
                logger.error(f"Failed to calculate dashboard metric {metric_name}: {e}")
                metrics[metric_name] = {
                    'value': 0,
                    'unit': self.metric_definitions[metric_name].unit,
                    'trend': 'unknown'
                }
        
        return {
            'period': period.value,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'metrics': metrics,
            'last_updated': timezone.now().isoformat()
        }
    
    def get_trend_analysis(self, metric_name: str, periods: int = 30) -> Dict[str, Any]:
        """Get trend analysis for a specific metric."""
        if metric_name not in self.metric_definitions:
            raise ValueError(f"Unknown metric: {metric_name}")
        
        end_date = timezone.now()
        trend_data = []
        
        for i in range(periods):
            period_end = end_date - datetime.timedelta(days=i)
            period_start = period_end - datetime.timedelta(days=1)
            
            try:
                metric_value = self.calculate_metric(
                    metric_name, AnalyticsPeriod.DAILY, period_start, period_end
                )
                trend_data.append({
                    'date': period_start.date().isoformat(),
                    'value': metric_value.value
                })
            except Exception as e:
                logger.error(f"Failed to calculate trend data for {metric_name} on {period_start.date()}: {e}")
        
        # Calculate trend statistics
        values = [point['value'] for point in trend_data if isinstance(point['value'], (int, float))]
        trend_stats = {}
        
        if values:
            trend_stats = {
                'average': statistics.mean(values),
                'median': statistics.median(values),
                'min': min(values),
                'max': max(values),
                'trend_direction': 'up' if values[-1] > values[0] else 'down' if values[-1] < values[0] else 'stable'
            }
        
        return {
            'metric_name': metric_name,
            'periods': periods,
            'data': trend_data,
            'statistics': trend_stats
        }


# Global analytics engine instance
_analytics_engine: Optional[BackupAnalyticsEngine] = None


def get_analytics_engine() -> BackupAnalyticsEngine:
    """Get the global analytics engine instance."""
    global _analytics_engine
    if _analytics_engine is None:
        _analytics_engine = BackupAnalyticsEngine()
    return _analytics_engine


def calculate_metric(metric_name: str, period: AnalyticsPeriod,
                    start_date: datetime.datetime, end_date: datetime.datetime,
                    filters: Optional[Dict[str, Any]] = None) -> MetricValue:
    """Convenience function to calculate a metric."""
    engine = get_analytics_engine()
    return engine.calculate_metric(metric_name, period, start_date, end_date, filters)


def generate_report(report_type: str, period: AnalyticsPeriod,
                   start_date: datetime.datetime, end_date: datetime.datetime,
                   filters: Optional[Dict[str, Any]] = None,
                   format: ReportFormat = ReportFormat.JSON) -> AnalyticsReport:
    """Convenience function to generate a report."""
    engine = get_analytics_engine()
    return engine.generate_report(report_type, period, start_date, end_date, filters, format)


def get_dashboard_metrics(period: AnalyticsPeriod = AnalyticsPeriod.DAILY) -> Dict[str, Any]:
    """Convenience function to get dashboard metrics."""
    engine = get_analytics_engine()
    return engine.get_dashboard_metrics(period)


def get_trend_analysis(metric_name: str, periods: int = 30) -> Dict[str, Any]:
    """Convenience function to get trend analysis."""
    engine = get_analytics_engine()
    return engine.get_trend_analysis(metric_name, periods)
