"""
Reporting System for alerts app - Advanced reporting and analytics
"""
from typing import Dict, List, Any, Optional, Union
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import connection, models
from django.db.models.functions import TruncDate, TruncHour
import logging
import json
import time
import io
import uuid
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Report type enumeration"""
    ALERT_SUMMARY = "alert_summary"
    INCIDENT_REPORT = "incident_report"
    PERFORMANCE_METRICS = "performance_metrics"
    USER_ACTIVITY = "user_activity"
    SYSTEM_HEALTH = "system_health"
    COMPLIANCE_REPORT = "compliance_report"
    TREND_ANALYSIS = "trend_analysis"
    CUSTOM_REPORT = "custom_report"


class ReportFormat(Enum):
    """Report format enumeration"""
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    EXCEL = "excel"
    HTML = "html"


class ReportSchedule(Enum):
    """Report schedule enumeration"""
    ON_DEMAND = "on_demand"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class Report:
    """Represents a report"""
    
    def __init__(self, report_type: ReportType, title: str, description: str = None):
        self.id = str(uuid.uuid4())
        self.report_type = report_type
        self.title = title
        self.description = description
        self.created_at = timezone.now()
        self.generated_at = None
        self.data = None
        self.metadata = {}
        self.filters = {}
        self.format = ReportFormat.JSON
        self.schedule = ReportSchedule.ON_DEMAND
        self.is_template = False
        
    def generate(self, data: Dict[str, Any], format: ReportFormat = None) -> Dict[str, Any]:
        """Generate report with data"""
        try:
            self.data = data
            self.generated_at = timezone.now()
            self.format = format or self.format
            
            # Format data based on format type
            formatted_data = self._format_data(data, self.format)
            
            return {
                'success': True,
                'report_id': self.id,
                'formatted_data': formatted_data,
                'format': self.format.value,
                'generated_at': self.generated_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating report {self.id}: {e}")
            return {
                'success': False,
                'error': 'Operation failed',
                'report_id': self.id
            }
    
    def _format_data(self, data: Dict[str, Any], format: ReportFormat) -> Any:
        """Format data based on report format"""
        if format == ReportFormat.JSON:
            return json.dumps(data, default=str, indent=2)
        elif format == ReportFormat.CSV:
            return self._format_as_csv(data)
        elif format == ReportFormat.HTML:
            return self._format_as_html(data)
        elif format == ReportFormat.EXCEL:
            return self._format_as_excel(data)
        elif format == ReportFormat.PDF:
            return self._format_as_pdf(data)
        else:
            return data
    
    def _format_as_csv(self, data: Dict[str, Any]) -> str:
        """Format data as CSV"""
        try:
            import csv
            from io import StringIO
            
            output = StringIO()
            writer = csv.writer(output)
            
            # Handle different data structures
            if isinstance(data, list):
                if data and isinstance(data[0], dict):
                    # List of dictionaries
                    headers = list(data[0].keys())
                    writer.writerow(headers)
                    for row in data:
                        writer.writerow([row.get(h, '') for h in headers])
                else:
                    # List of values
                    writer.writerow(['value'])
                    for row in data:
                        writer.writerow([row])
            elif isinstance(data, dict):
                # Dictionary
                writer.writerow(['key', 'value'])
                for key, value in data.items():
                    writer.writerow([key, str(value)])
            else:
                # Single value
                writer.writerow(['value'])
                writer.writerow([str(data)])
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"CSV formatting error: {e}")
            return str(data)
    
    def _format_as_html(self, data: Dict[str, Any]) -> str:
        """Format data as HTML"""
        try:
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>{title}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    .summary {{ background-color: #f9f9f9; padding: 15px; margin-bottom: 20px; }}
                </style>
            </head>
            <body>
                <h1>{title}</h1>
                {description}
                <div class="summary">
                    <h2>Summary</h2>
                    <p>Generated on: {generated_at}</p>
                    <p>Report type: {report_type}</p>
                </div>
                <h2>Data</h2>
                {data_content}
            </body>
            </html>
            """
            
            # Format data content
            data_content = self._format_data_for_html(data)
            
            return html_template.format(
                title=self.title,
                description=f"<p>{self.description}</p>" if self.description else "",
                generated_at=self.generated_at.strftime('%Y-%m-%d %H:%M:%S') if self.generated_at else "",
                report_type=self.report_type.value,
                data_content=data_content
            )
            
        except Exception as e:
            logger.error(f"HTML formatting error: {e}")
            return f"<pre>{json.dumps(data, default=str, indent=2)}</pre>"
    
    def _format_data_for_html(self, data: Any) -> str:
        """Format data for HTML display"""
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                # List of dictionaries
                headers = list(data[0].keys())
                rows = []
                for item in data:
                    row = "<tr>"
                    for header in headers:
                        row += f"<td>{str(item.get(header, ''))}</td>"
                    row += "</tr>"
                    rows.append(row)
                
                header_row = "<tr>" + "".join([f"<th>{h}</th>" for h in headers]) + "</tr>"
                
                return f"""
                <table>
                    {header_row}
                    {''.join(rows)}
                </table>
                """
            else:
                # List of values
                rows = "".join([f"<tr><td>{str(item)}</td></tr>" for item in data])
                return f"<table><tr><th>Value</th></tr>{rows}</table>"
        
        elif isinstance(data, dict):
            # Dictionary
            rows = []
            for key, value in data.items():
                rows.append(f"<tr><td><strong>{key}</strong></td><td>{str(value)}</td></tr>")
            
            return f"<table><tr><th>Key</th><th>Value</th></tr>{''.join(rows)}</table>"
        
        else:
            # Single value
            return f"<table><tr><th>Value</th></tr><tr><td>{str(data)}</td></tr></table>"
    
    def _format_as_excel(self, data: Dict[str, Any]) -> bytes:
        """Format data as Excel"""
        try:
            import openpyxl
            from openpyxl import Workbook
            from io import BytesIO
            
            wb = Workbook()
            ws = wb.active
            ws.title = self.title
            
            if isinstance(data, list):
                if data and isinstance(data[0], dict):
                    # List of dictionaries
                    headers = list(data[0].keys())
                    ws.append(headers)
                    
                    for row in data:
                        ws.append([row.get(h, '') for h in headers])
                else:
                    # List of values
                    ws.append(['Value'])
                    for item in data:
                        ws.append([item])
            elif isinstance(data, dict):
                # Dictionary
                ws.append(['Key', 'Value'])
                for key, value in data.items():
                    ws.append([key, str(value)])
            else:
                # Single value
                ws.append(['Value'])
                ws.append([str(data)])
            
            # Save to bytes
            output = BytesIO()
            wb.save(output)
            return output.getvalue()
            
        except ImportError:
            logger.error("openpyxl not available, falling back to CSV")
            return self._format_as_csv(data).encode('utf-8')
        except Exception as e:
            logger.error(f"Excel formatting error: {e}")
            return str(data).encode('utf-8')
    
    def _format_as_pdf(self, data: Dict[str, Any]) -> bytes:
        """Format data as PDF"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from io import BytesIO
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            
            # Build story
            story = []
            
            # Title
            title_style = styles['Title']
            story.append(Paragraph(self.title, title_style))
            story.append(Spacer(1, 12))
            
            # Description
            if self.description:
                normal_style = styles['Normal']
                story.append(Paragraph(self.description, normal_style))
                story.append(Spacer(1, 12))
            
            # Data
            if isinstance(data, list):
                if data and isinstance(data[0], dict):
                    # List of dictionaries
                    headers = list(data[0].keys())
                    table_data = [headers] + [[str(item.get(h, '')) for h in headers] for item in data]
                    
                    table = Table(table_data)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 14),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 12),
                    ]))
                    
                    story.append(table)
                else:
                    # List of values
                    for item in data:
                        story.append(Paragraph(str(item), styles['Normal']))
                        story.append(Spacer(1, 6))
            
            elif isinstance(data, dict):
                # Dictionary
                for key, value in data.items():
                    story.append(Paragraph(f"<b>{key}:</b> {str(value)}", styles['Normal']))
                    story.append(Spacer(1, 6))
            
            else:
                # Single value
                story.append(Paragraph(str(data), styles['Normal']))
            
            # Build PDF
            doc.build(story)
            return buffer.getvalue()
            
        except ImportError:
            logger.error("reportlab not available, falling back to HTML")
            return self._format_as_html(data).encode('utf-8')
        except Exception as e:
            logger.error(f"PDF formatting error: {e}")
            return str(data).encode('utf-8')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'report_type': self.report_type.value,
            'title': self.title,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'format': self.format.value,
            'schedule': self.schedule.value,
            'is_template': self.is_template,
            'metadata': self.metadata,
            'filters': self.filters,
            'has_data': self.data is not None
        }


class ReportGenerator:
    """Report generation engine"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', True)
        self.default_format = ReportFormat(config.get('default_format', 'json'))
        self.cache_timeout = config.get('cache_timeout', 300)  # 5 minutes
        
    def generate_alert_summary_report(self, start_date: datetime, end_date: datetime,
                                   filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate alert summary report"""
        try:
            from .models import AlertLog, AlertRule
            
            # Base queryset
            queryset = AlertLog.objects.filter(
                triggered_at__gte=start_date,
                triggered_at__lte=end_date
            )
            
            # Apply filters
            if filters:
                if 'severity' in filters:
                    queryset = queryset.filter(severity__in=filters['severity'])
                
                if 'alert_type' in filters:
                    queryset = queryset.filter(alert_rule__alert_type=filters['alert_type'])
                
                if 'user_id' in filters:
                    queryset = queryset.filter(user_id=filters['user_id'])
                
                if 'tenant_id' in filters:
                    queryset = queryset.filter(tenant_id=filters['tenant_id'])
            
            # Get summary data
            total_alerts = queryset.count()
            resolved_alerts = queryset.filter(is_resolved=True).count()
            unresolved_alerts = total_alerts - resolved_alerts
            
            # Severity breakdown
            severity_breakdown = queryset.values('severity').annotate(
                count=models.Count('severity')
            ).order_by('severity')
            
            # Alert type breakdown
            type_breakdown = queryset.values('alert_rule__alert_type').annotate(
                count=models.Count('alert_rule__alert_type')
            ).order_by('-count')[:10]  # Top 10
            
            # Daily trend
            daily_trend = queryset.annotate(
                date=TruncDate('triggered_at')
            ).values('date').annotate(
                count=models.Count('id')
            ).order_by('date')
            
            # Resolution time statistics
            resolved_queryset = queryset.filter(is_resolved=True)
            avg_resolution_time = resolved_queryset.aggregate(
                avg_time=models.Avg(models.F('resolved_at') - models.F('triggered_at'))
            )['avg_time']
            
            data = {
                'summary': {
                    'total_alerts': total_alerts,
                    'resolved_alerts': resolved_alerts,
                    'unresolved_alerts': unresolved_alerts,
                    'resolution_rate': (resolved_alerts / total_alerts * 100) if total_alerts > 0 else 0,
                    'avg_resolution_time_hours': avg_resolution_time.total_seconds() / 3600 if avg_resolution_time else 0
                },
                'severity_breakdown': list(severity_breakdown),
                'type_breakdown': list(type_breakdown),
                'daily_trend': list(daily_trend),
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'filters': filters or {}
            }
            
            return {
                'success': True,
                'data': data,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating alert summary report: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def generate_performance_metrics_report(self, start_date: datetime, end_date: datetime,
                                        filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate performance metrics report"""
        try:
            from .models import SystemMetrics
            
            # Base queryset
            queryset = SystemMetrics.objects.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date
            )
            
            # Apply filters
            if filters:
                if 'metric_type' in filters:
                    queryset = queryset.filter(metric_type=filters['metric_type'])
                
                if 'source' in filters:
                    queryset = queryset.filter(source=filters['source'])
            
            # Get metrics data
            metrics_data = queryset.order_by('timestamp')
            
            # Calculate statistics
            if metrics_data.exists():
                metric_types = metrics_data.values('metric_type').distinct()
                
                type_stats = {}
                for metric_type in metric_types:
                    type_queryset = metrics_data.filter(metric_type=metric_type['metric_type'])
                    
                    values = type_queryset.values_list('value', flat=True)
                    if values:
                        type_stats[metric_type['metric_type']] = {
                            'min': min(values),
                            'max': max(values),
                            'avg': sum(values) / len(values),
                            'count': len(values),
                            'latest': values[-1]
                        }
            
            # Performance trends
            performance_trends = metrics_data.annotate(
                hour=TruncHour('timestamp')
            ).values('hour').annotate(
                avg_value=models.Avg('value'),
                count=models.Count('id')
            ).order_by('hour')
            
            data = {
                'performance_summary': type_stats or {},
                'performance_trends': list(performance_trends),
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'filters': filters or {}
            }
            
            return {
                'success': True,
                'data': data,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating performance metrics report: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def generate_user_activity_report(self, start_date: datetime, end_date: datetime,
                                 filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate user activity report"""
        try:
            from .models import AlertLog
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            
            # Base queryset
            queryset = AlertLog.objects.filter(
                triggered_at__gte=start_date,
                triggered_at__lte=end_date
            )
            
            # Apply filters
            if filters:
                if 'user_id' in filters:
                    queryset = queryset.filter(user_id=filters['user_id'])
                
                if 'tenant_id' in filters:
                    queryset = queryset.filter(tenant_id=filters['tenant_id'])
            
            # User activity breakdown
            user_activity = queryset.values('user_id').annotate(
                alert_count=models.Count('id'),
                resolved_count=models.Count('id', filter=models.Q(is_resolved=True))
            ).order_by('-alert_count')[:20]  # Top 20 users
            
            # Get user details
            user_ids = [activity['user_id'] for activity in user_activity]
            users = User.objects.filter(id__in=user_ids)
            user_dict = {user.id: user for user in users}
            
            # Enrich user activity
            enriched_activity = []
            for activity in user_activity:
                user = user_dict.get(activity['user_id'])
                enriched_activity.append({
                    'user_id': activity['user_id'],
                    'username': user.username if user else 'Unknown',
                    'email': user.email if user else '',
                    'alert_count': activity['alert_count'],
                    'resolved_count': activity['resolved_count'],
                    'resolution_rate': (activity['resolved_count'] / activity['alert_count'] * 100) if activity['alert_count'] > 0 else 0
                })
            
            # Daily activity trend
            daily_activity = queryset.annotate(
                date=TruncDate('triggered_at')
            ).values('date').annotate(
                alert_count=models.Count('id'),
                unique_users=models.Count('user_id', distinct=True)
            ).order_by('date')
            
            data = {
                'user_activity': enriched_activity,
                'daily_trend': list(daily_activity),
                'summary': {
                    'total_users': len(user_ids),
                    'total_alerts': queryset.count(),
                    'avg_alerts_per_user': queryset.count() / len(user_ids) if user_ids else 0
                },
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'filters': filters or {}
            }
            
            return {
                'success': True,
                'data': data,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating user activity report: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def generate_system_health_report(self, start_date: datetime, end_date: datetime,
                                   filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate system health report"""
        try:
            from .health_check import get_health_check_manager
            
            health_manager = get_health_check_manager()
            if not health_manager:
                return {
                    'success': False,
                    'error': 'Health check manager not available'
                }
            
            # Get health check results
            health_status = health_manager.get_manager_status()
            
            # Get historical health data
            # This would typically come from a health metrics table
            # For now, use current status
            health_trends = []
            current_time = timezone.now()
            
            # Generate sample trend data
            for i in range(24):  # Last 24 hours
                timestamp = current_time - timedelta(hours=i)
                health_trends.append({
                    'timestamp': timestamp.isoformat(),
                    'overall_health': 'healthy',  # This would be calculated from historical data
                    'critical_components': 0,
                    'warning_components': 0
                })
            
            data = {
                'current_status': health_status,
                'health_trends': health_trends,
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'filters': filters or {}
            }
            
            return {
                'success': True,
                'data': data,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating system health report: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }


class ReportManager:
    """Main report management system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', True)
        self.generator = ReportGenerator(config.get('generator', {}))
        self.reports = {}
        self.templates = {}
        self.scheduled_reports = {}
        
        # Initialize templates
        self._initialize_templates()
        
    def _initialize_templates(self):
        """Initialize report templates"""
        template_configs = self.config.get('templates', {})
        
        for template_name, template_config in template_configs.items():
            report = Report(
                report_type=ReportType(template_config.get('type', 'custom_report')),
                title=template_config.get('title', template_name),
                description=template_config.get('description')
            )
            report.is_template = True
            report.format = ReportFormat(template_config.get('format', 'json'))
            report.schedule = ReportSchedule(template_config.get('schedule', 'on_demand'))
            report.metadata = template_config.get('metadata', {})
            report.filters = template_config.get('filters', {})
            
            self.templates[template_name] = report
            logger.info(f"Initialized report template: {template_name}")
    
    def create_report(self, report_type: ReportType, title: str, 
                    description: str = None, format: ReportFormat = None) -> Report:
        """Create a new report"""
        report = Report(report_type, title, description)
        report.format = format or self.generator.default_format
        
        self.reports[report.id] = report
        return report
    
    def generate_report(self, report_id: str, start_date: datetime = None, 
                      end_date: datetime = None, filters: Dict[str, Any] = None,
                      format: ReportFormat = None) -> Dict[str, Any]:
        """Generate a specific report"""
        report = self.reports.get(report_id)
        if not report:
            return {
                'success': False,
                'error': f'Report {report_id} not found'
            }
        
        # Set default dates if not provided
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)  # Default to last 30 days
        
        if not end_date:
            end_date = timezone.now()
        
        # Generate report data based on type
        if report.report_type == ReportType.ALERT_SUMMARY:
            result = self.generator.generate_alert_summary_report(start_date, end_date, filters)
        elif report.report_type == ReportType.PERFORMANCE_METRICS:
            result = self.generator.generate_performance_metrics_report(start_date, end_date, filters)
        elif report.report_type == ReportType.USER_ACTIVITY:
            result = self.generator.generate_user_activity_report(start_date, end_date, filters)
        elif report.report_type == ReportType.SYSTEM_HEALTH:
            result = self.generator.generate_system_health_report(start_date, end_date, filters)
        else:
            result = {
                'success': False,
                'error': f'Report type {report.report_type.value} not supported'
            }
        
        # Format the report
        if result['success']:
            formatted_result = report.generate(result['data'], format or report.format)
            result.update(formatted_result)
        
        return result
    
    def get_report(self, report_id: str) -> Optional[Report]:
        """Get report by ID"""
        return self.reports.get(report_id)
    
    def get_template(self, template_name: str) -> Optional[Report]:
        """Get report template by name"""
        return self.templates.get(template_name)
    
    def list_reports(self) -> List[Dict[str, Any]]:
        """List all reports"""
        reports = []
        
        for report in self.reports.values():
            reports.append(report.to_dict())
        
        for template in self.templates.values():
            reports.append(template.to_dict())
        
        return sorted(reports, key=lambda x: x['created_at'], reverse=True)
    
    def delete_report(self, report_id: str) -> bool:
        """Delete a report"""
        if report_id in self.reports:
            del self.reports[report_id]
            logger.info(f"Deleted report {report_id}")
            return True
        return False
    
    def get_manager_status(self) -> Dict[str, Any]:
        """Get report manager status"""
        return {
            'enabled': self.enabled,
            'total_reports': len(self.reports),
            'total_templates': len(self.templates),
            'default_format': self.generator.default_format,
            'cache_timeout': self.generator.cache_timeout,
            'report_types': [rt.value for rt in ReportType],
            'available_formats': [rf.value for rf in ReportFormat],
            'available_schedules': [rs.value for rs in ReportSchedule],
            'timestamp': timezone.now().isoformat()
        }


# Global report manager
report_manager = None


def get_report_manager() -> Optional[ReportManager]:
    """Get the global report manager"""
    return report_manager


def initialize_report_manager():
    """Initialize report manager from settings"""
    from django.conf import settings
    
    global report_manager
    
    config = getattr(settings, 'REPORT_MANAGER_CONFIG', {
        'enabled': True,
        'default_format': 'json',
        'cache_timeout': 300,
        'generator': {
            'enabled': True
        },
        'templates': {
            'daily_alert_summary': {
                'type': 'alert_summary',
                'title': 'Daily Alert Summary',
                'description': 'Summary of all alerts generated in the last 24 hours',
                'format': 'json',
                'schedule': 'daily'
            },
            'weekly_performance': {
                'type': 'performance_metrics',
                'title': 'Weekly Performance Report',
                'description': 'System performance metrics for the last week',
                'format': 'excel',
                'schedule': 'weekly'
            },
            'monthly_user_activity': {
                'type': 'user_activity',
                'title': 'Monthly User Activity',
                'description': 'User activity and alert statistics for the last month',
                'format': 'pdf',
                'schedule': 'monthly'
            }
        }
    })
    
    try:
        report_manager = ReportManager(config)
        logger.info("Report manager initialized")
    except Exception as e:
        logger.error(f"Error initializing report manager: {e}")


# Initialize on module import
try:
    initialize_report_manager()
except Exception as e:
    logger.error(f"Error initializing report manager: {e}")
