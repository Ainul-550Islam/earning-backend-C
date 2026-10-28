"""
Security Data Export Module
Export functionality for security data
"""

import logging
import csv
import json
import io
import xlsxwriter
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.db.models import QuerySet
from django.core.serializers.json import DjangoJSONEncoder

from .models import SecurityLog, SecurityIncident, ThreatIntelligence, UserBan, DeviceInfo
from .selectors import SecurityLogSelector, SecurityIncidentSelector, ThreatIntelligenceSelector
from .utils import SecurityUtils
from .helpers import TimeHelper
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass



User = get_user_model()
logger = logging.getLogger('security.data_export')


class ExportFormat:
    """Export format types"""
    CSV = 'csv'
    JSON = 'json'
    EXCEL = 'excel'
    PDF = 'pdf'


class ExportStatus:
    """Export status"""
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class SecurityDataExporter:
    """Base security data exporter"""
    
    def __init__(self):
        self.max_records = 10000  # Maximum records per export
        self.chunk_size = 1000  # Records per chunk for large exports
    
    def export_security_logs(self, format_type: str, filters: Dict[str, Any] = None,
                           start_date: datetime = None, end_date: datetime = None) -> HttpResponse:
        """Export security logs"""
        queryset = self._get_filtered_security_logs(filters, start_date, end_date)
        
        if format_type == ExportFormat.CSV:
            return self._export_logs_csv(queryset)
        elif format_type == ExportFormat.JSON:
            return self._export_logs_json(queryset)
        elif format_type == ExportFormat.EXCEL:
            return self._export_logs_excel(queryset)
        elif format_type == ExportFormat.PDF:
            return self._export_logs_pdf(queryset)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
    
    def export_incidents(self, format_type: str, filters: Dict[str, Any] = None,
                        start_date: datetime = None, end_date: datetime = None) -> HttpResponse:
        """Export security incidents"""
        queryset = self._get_filtered_incidents(filters, start_date, end_date)
        
        if format_type == ExportFormat.CSV:
            return self._export_incidents_csv(queryset)
        elif format_type == ExportFormat.JSON:
            return self._export_incidents_json(queryset)
        elif format_type == ExportFormat.EXCEL:
            return self._export_incidents_excel(queryset)
        elif format_type == ExportFormat.PDF:
            return self._export_incidents_pdf(queryset)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
    
    def export_threat_intelligence(self, format_type: str, filters: Dict[str, Any] = None) -> HttpResponse:
        """Export threat intelligence"""
        queryset = self._get_filtered_threat_intelligence(filters)
        
        if format_type == ExportFormat.CSV:
            return self._export_threats_csv(queryset)
        elif format_type == ExportFormat.JSON:
            return self._export_threats_json(queryset)
        elif format_type == ExportFormat.EXCEL:
            return self._export_threats_excel(queryset)
        elif format_type == ExportFormat.PDF:
            return self._export_threats_pdf(queryset)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
    
    def export_user_activity(self, user_id: Union[int, str], format_type: str,
                           start_date: datetime = None, end_date: datetime = None) -> HttpResponse:
        """Export user activity"""
        queryset = self._get_user_activity(user_id, start_date, end_date)
        
        if format_type == ExportFormat.CSV:
            return self._export_user_activity_csv(queryset, user_id)
        elif format_type == ExportFormat.JSON:
            return self._export_user_activity_json(queryset, user_id)
        elif format_type == ExportFormat.EXCEL:
            return self._export_user_activity_excel(queryset, user_id)
        elif format_type == ExportFormat.PDF:
            return self._export_user_activity_pdf(queryset, user_id)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
    
    def export_compliance_report(self, format_type: str, days: int = 30) -> HttpResponse:
        """Export compliance report"""
        if format_type == ExportFormat.PDF:
            return self._export_compliance_pdf(days)
        elif format_type == ExportFormat.EXCEL:
            return self._export_compliance_excel(days)
        elif format_type == ExportFormat.JSON:
            return self._export_compliance_json(days)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
    
    def _get_filtered_security_logs(self, filters: Dict[str, Any] = None,
                                  start_date: datetime = None, end_date: datetime = None) -> QuerySet:
        """Get filtered security logs"""
        queryset = SecurityLog.objects.all()
        
        if filters:
            log_selector = SecurityLogSelector(queryset)
            
            if 'security_type' in filters:
                queryset = log_selector.filter_by_security_type(filters['security_type'])
            
            if 'severity' in filters:
                queryset = log_selector.filter_by_severity(filters['severity'])
            
            if 'user_id' in filters:
                queryset = log_selector.filter_by_user(filters['user_id'])
            
            if 'ip_address' in filters:
                queryset = log_selector.filter_by_ip_address(filters['ip_address'])
            
            if 'risk_score_min' in filters and 'risk_score_max' in filters:
                queryset = queryset.filter(
                    risk_score__gte=filters['risk_score_min'],
                    risk_score__lte=filters['risk_score_max']
                )
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Limit records
        return queryset[:self.max_records]
    
    def _get_filtered_incidents(self, filters: Dict[str, Any] = None,
                             start_date: datetime = None, end_date: datetime = None) -> QuerySet:
        """Get filtered incidents"""
        queryset = SecurityIncident.objects.all()
        
        if filters:
            incident_selector = SecurityIncidentSelector(queryset)
            
            if 'status' in filters:
                if filters['status'] == 'open':
                    queryset = incident_selector.filter_open()
                elif filters['status'] == 'resolved':
                    queryset = incident_selector.filter_resolved()
            
            if 'priority' in filters:
                queryset = incident_selector.filter_by_priority(filters['priority'])
            
            if 'incident_type' in filters:
                queryset = queryset.filter(incident_type=filters['incident_type'])
            
            if 'assigned_to' in filters:
                queryset = incident_selector.filter_by_assigned_user(filters['assigned_to'])
        
        if start_date:
            queryset = queryset.filter(opened_at__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(opened_at__lte=end_date)
        
        return queryset[:self.max_records]
    
    def _get_filtered_threat_intelligence(self, filters: Dict[str, Any] = None) -> QuerySet:
        """Get filtered threat intelligence"""
        queryset = ThreatIntelligence.objects.all()
        
        if filters:
            threat_selector = ThreatIntelligenceSelector(queryset)
            
            if 'is_active' in filters:
                if filters['is_active']:
                    queryset = threat_selector.filter_active()
                else:
                    queryset = threat_selector.filter_expired()
            
            if 'threat_type' in filters:
                queryset = threat_selector.filter_by_threat_type(filters['threat_type'])
            
            if 'severity' in filters:
                queryset = threat_selector.filter_by_severity(filters['severity'])
            
            if 'source' in filters:
                queryset = threat_selector.filter_by_source(filters['source'])
            
            if 'confidence_min' in filters and 'confidence_max' in filters:
                queryset = queryset.filter(
                    confidence__gte=filters['confidence_min'],
                    confidence__lte=filters['confidence_max']
                )
        
        return queryset[:self.max_records]
    
    def _get_user_activity(self, user_id: Union[int, str], start_date: datetime = None,
                          end_date: datetime = None) -> QuerySet:
        """Get user activity"""
        queryset = SecurityLog.objects.filter(user_id=user_id)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset[:self.max_records]
    
    def _export_logs_csv(self, queryset: QuerySet) -> HttpResponse:
        """Export logs to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="security_logs_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        
        # Header
        writer.writerow([
            'ID', 'User', 'Security Type', 'Severity', 'IP Address',
            'Description', 'Created At', 'Risk Score', 'Response Time (ms)'
        ])
        
        # Data rows
        for log in queryset:
            writer.writerow([
                log.id,
                log.user.username if log.user else 'Anonymous',
                log.security_type,
                log.severity,
                log.ip_address,
                log.description,
                log.created_at.isoformat(),
                log.risk_score or '',
                log.response_time_ms or ''
            ])
        
        return response
    
    def _export_logs_json(self, queryset: QuerySet) -> HttpResponse:
        """Export logs to JSON"""
        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="security_logs_{timezone.now().strftime("%Y%m%d")}.json"'
        
        logs_data = []
        for log in queryset:
            logs_data.append({
                'id': str(log.id),
                'user': log.user.username if log.user else None,
                'security_type': log.security_type,
                'severity': log.severity,
                'ip_address': log.ip_address,
                'description': log.description,
                'created_at': log.created_at.isoformat(),
                'risk_score': log.risk_score,
                'response_time_ms': log.response_time_ms,
                'metadata': log.metadata
            })
        
        json.dump(logs_data, response, cls=DjangoJSONEncoder, indent=2)
        return response
    
    def _export_logs_excel(self, queryset: QuerySet) -> HttpResponse:
        """Export logs to Excel"""
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="security_logs_{timezone.now().strftime("%Y%m%d")}.xlsx"'
        
        # Create Excel workbook
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        # Add worksheet
        worksheet = workbook.add_worksheet('Security Logs')
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'border': 1
        })
        
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss'})
        
        # Header
        headers = [
            'ID', 'User', 'Security Type', 'Severity', 'IP Address',
            'Description', 'Created At', 'Risk Score', 'Response Time (ms)'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
            worksheet.set_column(col, col, 20)  # Set column width
        
        # Data rows
        for row, log in enumerate(queryset, 1):
            worksheet.write(row, 0, str(log.id))
            worksheet.write(row, 1, log.user.username if log.user else 'Anonymous')
            worksheet.write(row, 2, log.security_type)
            worksheet.write(row, 3, log.severity)
            worksheet.write(row, 4, log.ip_address)
            worksheet.write(row, 5, log.description)
            worksheet.write(row, 6, log.created_at.isoformat(), date_format)
            worksheet.write(row, 7, log.risk_score or '')
            worksheet.write(row, 8, log.response_time_ms or '')
        
        workbook.close()
        output.seek(0)
        
        response.write(output.getvalue())
        return response
    
    def _export_logs_pdf(self, queryset: QuerySet) -> HttpResponse:
        """Export logs to PDF"""
        # This would require a PDF library like ReportLab
        # For now, return a simple text-based PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="security_logs_{timezone.now().strftime("%Y%m%d")}.pdf"'
        
        # Simple PDF content (in production, use proper PDF library)
        pdf_content = f"""
        Security Logs Report
        Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
        Total Records: {queryset.count()}
        
        """
        
        for log in queryset[:100]:  # Limit to 100 for PDF
            pdf_content += f"""
        {log.created_at.strftime('%Y-%m-%d %H:%M:%S')} - {log.security_type} - {log.severity}
        User: {log.user.username if log.user else 'Anonymous'}
        IP: {log.ip_address}
        Description: {log.description}
        Risk Score: {log.risk_score or 'N/A'}
        
        """
        
        response.write(pdf_content.encode())
        return response
    
    def _export_incidents_csv(self, queryset: QuerySet) -> HttpResponse:
        """Export incidents to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="security_incidents_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        
        # Header
        writer.writerow([
            'ID', 'Title', 'Incident Type', 'Severity', 'Priority', 'Status',
            'User', 'Assigned To', 'Opened At', 'Resolved At', 'Description'
        ])
        
        # Data rows
        for incident in queryset:
            writer.writerow([
                incident.id,
                incident.title,
                incident.incident_type,
                incident.severity,
                incident.priority,
                incident.status,
                incident.user.username if incident.user else 'Anonymous',
                incident.assigned_to.username if incident.assigned_to else 'Unassigned',
                incident.opened_at.isoformat(),
                incident.resolved_at.isoformat() if incident.resolved_at else '',
                incident.description
            ])
        
        return response
    
    def _export_incidents_json(self, queryset: QuerySet) -> HttpResponse:
        """Export incidents to JSON"""
        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="security_incidents_{timezone.now().strftime("%Y%m%d")}.json"'
        
        incidents_data = []
        for incident in queryset:
            incidents_data.append({
                'id': str(incident.id),
                'title': incident.title,
                'incident_type': incident.incident_type,
                'severity': incident.severity,
                'priority': incident.priority,
                'status': incident.status,
                'user': incident.user.username if incident.user else None,
                'assigned_to': incident.assigned_to.username if incident.assigned_to else None,
                'opened_at': incident.opened_at.isoformat(),
                'resolved_at': incident.resolved_at.isoformat() if incident.resolved_at else None,
                'description': incident.description,
                'affected_systems': incident.affected_systems,
                'resolution_notes': incident.resolution_notes
            })
        
        json.dump(incidents_data, response, cls=DjangoJSONEncoder, indent=2)
        return response
    
    def _export_incidents_excel(self, queryset: QuerySet) -> HttpResponse:
        """Export incidents to Excel"""
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="security_incidents_{timezone.now().strftime("%Y%m%d")}.xlsx"'
        
        # Create Excel workbook
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        # Add worksheet
        worksheet = workbook.add_worksheet('Security Incidents')
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'border': 1
        })
        
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss'})
        
        # Header
        headers = [
            'ID', 'Title', 'Incident Type', 'Severity', 'Priority', 'Status',
            'User', 'Assigned To', 'Opened At', 'Resolved At', 'Description'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
            worksheet.set_column(col, col, 20)  # Set column width
        
        # Data rows
        for row, incident in enumerate(queryset, 1):
            worksheet.write(row, 0, str(incident.id))
            worksheet.write(row, 1, incident.title)
            worksheet.write(row, 2, incident.incident_type)
            worksheet.write(row, 3, incident.severity)
            worksheet.write(row, 4, incident.priority)
            worksheet.write(row, 5, incident.status)
            worksheet.write(row, 6, incident.user.username if incident.user else 'Anonymous')
            worksheet.write(row, 7, incident.assigned_to.username if incident.assigned_to else 'Unassigned')
            worksheet.write(row, 8, incident.opened_at.isoformat(), date_format)
            worksheet.write(row, 9, incident.resolved_at.isoformat() if incident.resolved_at else '', date_format)
            worksheet.write(row, 10, incident.description)
        
        workbook.close()
        output.seek(0)
        
        response.write(output.getvalue())
        return response
    
    def _export_incidents_pdf(self, queryset: QuerySet) -> HttpResponse:
        """Export incidents to PDF"""
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="security_incidents_{timezone.now().strftime("%Y%m%d")}.pdf"'
        
        pdf_content = f"""
        Security Incidents Report
        Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
        Total Records: {queryset.count()}
        
        """
        
        for incident in queryset[:50]:  # Limit to 50 for PDF
            pdf_content += f"""
        {incident.title} ({incident.incident_type})
        Severity: {incident.severity} | Priority: {incident.priority} | Status: {incident.status}
        Opened: {incident.opened_at.strftime('%Y-%m-%d %H:%M:%S')}
        Assigned To: {incident.assigned_to.username if incident.assigned_to else 'Unassigned'}
        Description: {incident.description}
        
        """
        
        response.write(pdf_content.encode())
        return response
    
    def _export_threats_csv(self, queryset: QuerySet) -> HttpResponse:
        """Export threats to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="threat_intelligence_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        
        # Header
        writer.writerow([
            'ID', 'Threat Type', 'Indicator Type', 'Indicator', 'Severity',
            'Confidence', 'Source', 'Created At', 'Expires At', 'Description'
        ])
        
        # Data rows
        for threat in queryset:
            writer.writerow([
                threat.id,
                threat.threat_type,
                threat.indicator_type,
                threat.indicator,
                threat.severity,
                threat.confidence,
                threat.source,
                threat.created_at.isoformat(),
                threat.expires_at.isoformat() if threat.expires_at else '',
                threat.description
            ])
        
        return response
    
    def _export_threats_json(self, queryset: QuerySet) -> HttpResponse:
        """Export threats to JSON"""
        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="threat_intelligence_{timezone.now().strftime("%Y%m%d")}.json"'
        
        threats_data = []
        for threat in queryset:
            threats_data.append({
                'id': str(threat.id),
                'threat_type': threat.threat_type,
                'indicator_type': threat.indicator_type,
                'indicator': threat.indicator,
                'severity': threat.severity,
                'confidence': threat.confidence,
                'source': threat.source,
                'created_at': threat.created_at.isoformat(),
                'expires_at': threat.expires_at.isoformat() if threat.expires_at else None,
                'description': threat.description,
                'ip_range': threat.ip_range
            })
        
        json.dump(threats_data, response, cls=DjangoJSONEncoder, indent=2)
        return response
    
    def _export_threats_excel(self, queryset: QuerySet) -> HttpResponse:
        """Export threats to Excel"""
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="threat_intelligence_{timezone.now().strftime("%Y%m%d")}.xlsx"'
        
        # Create Excel workbook
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        # Add worksheet
        worksheet = workbook.add_worksheet('Threat Intelligence')
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'border': 1
        })
        
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss'})
        
        # Header
        headers = [
            'ID', 'Threat Type', 'Indicator Type', 'Indicator', 'Severity',
            'Confidence', 'Source', 'Created At', 'Expires At', 'Description'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
            worksheet.set_column(col, col, 20)  # Set column width
        
        # Data rows
        for row, threat in enumerate(queryset, 1):
            worksheet.write(row, 0, str(threat.id))
            worksheet.write(row, 1, threat.threat_type)
            worksheet.write(row, 2, threat.indicator_type)
            worksheet.write(row, 3, threat.indicator)
            worksheet.write(row, 4, threat.severity)
            worksheet.write(row, 5, threat.confidence)
            worksheet.write(row, 6, threat.source)
            worksheet.write(row, 7, threat.created_at.isoformat(), date_format)
            worksheet.write(row, 8, threat.expires_at.isoformat() if threat.expires_at else '', date_format)
            worksheet.write(row, 9, threat.description)
        
        workbook.close()
        output.seek(0)
        
        response.write(output.getvalue())
        return response
    
    def _export_threats_pdf(self, queryset: QuerySet) -> HttpResponse:
        """Export threats to PDF"""
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="threat_intelligence_{timezone.now().strftime("%Y%m%d")}.pdf"'
        
        pdf_content = f"""
        Threat Intelligence Report
        Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
        Total Records: {queryset.count()}
        
        """
        
        for threat in queryset[:50]:  # Limit to 50 for PDF
            pdf_content += f"""
        {threat.threat_type} ({threat.indicator_type})
        Indicator: {threat.indicator}
        Severity: {threat.severity} | Confidence: {threat.confidence}
        Source: {threat.source}
        Created: {threat.created_at.strftime('%Y-%m-%d %H:%M:%S')}
        Expires: {threat.expires_at.strftime('%Y-%m-%d %H:%M:%S') if threat.expires_at else 'Never'}
        Description: {threat.description}
        
        """
        
        response.write(pdf_content.encode())
        return response
    
    def _export_user_activity_csv(self, queryset: QuerySet, user_id: Union[int, str]) -> HttpResponse:
        """Export user activity to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="user_activity_{user_id}_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        
        # Header
        writer.writerow([
            'ID', 'Security Type', 'Severity', 'IP Address',
            'Description', 'Created At', 'Risk Score', 'Response Time (ms)'
        ])
        
        # Data rows
        for log in queryset:
            writer.writerow([
                log.id,
                log.security_type,
                log.severity,
                log.ip_address,
                log.description,
                log.created_at.isoformat(),
                log.risk_score or '',
                log.response_time_ms or ''
            ])
        
        return response
    
    def _export_user_activity_json(self, queryset: QuerySet, user_id: Union[int, str]) -> HttpResponse:
        """Export user activity to JSON"""
        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="user_activity_{user_id}_{timezone.now().strftime("%Y%m%d")}.json"'
        
        logs_data = []
        for log in queryset:
            logs_data.append({
                'id': str(log.id),
                'security_type': log.security_type,
                'severity': log.severity,
                'ip_address': log.ip_address,
                'description': log.description,
                'created_at': log.created_at.isoformat(),
                'risk_score': log.risk_score,
                'response_time_ms': log.response_time_ms,
                'metadata': log.metadata
            })
        
        json.dump(logs_data, response, cls=DjangoJSONEncoder, indent=2)
        return response
    
    def _export_user_activity_excel(self, queryset: QuerySet, user_id: Union[int, str]) -> HttpResponse:
        """Export user activity to Excel"""
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="user_activity_{user_id}_{timezone.now().strftime("%Y%m%d")}.xlsx"'
        
        # Create Excel workbook
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        # Add worksheet
        worksheet = workbook.add_worksheet('User Activity')
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'border': 1
        })
        
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss'})
        
        # Header
        headers = [
            'ID', 'Security Type', 'Severity', 'IP Address',
            'Description', 'Created At', 'Risk Score', 'Response Time (ms)'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
            worksheet.set_column(col, col, 20)  # Set column width
        
        # Data rows
        for row, log in enumerate(queryset, 1):
            worksheet.write(row, 0, str(log.id))
            worksheet.write(row, 1, log.security_type)
            worksheet.write(row, 2, log.severity)
            worksheet.write(row, 3, log.ip_address)
            worksheet.write(row, 4, log.description)
            worksheet.write(row, 5, log.created_at.isoformat(), date_format)
            worksheet.write(row, 6, log.risk_score or '')
            worksheet.write(row, 7, log.response_time_ms or '')
        
        workbook.close()
        output.seek(0)
        
        response.write(output.getvalue())
        return response
    
    def _export_user_activity_pdf(self, queryset: QuerySet, user_id: Union[int, str]) -> HttpResponse:
        """Export user activity to PDF"""
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="user_activity_{user_id}_{timezone.now().strftime("%Y%m%d")}.pdf"'
        
        pdf_content = f"""
        User Activity Report - User {user_id}
        Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
        Total Records: {queryset.count()}
        
        """
        
        for log in queryset[:100]:  # Limit to 100 for PDF
            pdf_content += f"""
        {log.created_at.strftime('%Y-%m-%d %H:%M:%S')} - {log.security_type} - {log.severity}
        IP: {log.ip_address}
        Description: {log.description}
        Risk Score: {log.risk_score or 'N/A'}
        
        """
        
        response.write(pdf_content.encode())
        return response
    
    def _export_compliance_json(self, days: int) -> HttpResponse:
        """Export compliance report to JSON"""
        from .analytics import security_analytics
        
        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="compliance_report_{timezone.now().strftime("%Y%m%d")}.json"'
        
        # Get compliance analytics
        compliance_data = security_analytics.get_compliance_analytics(days)
        
        json.dump(compliance_data, response, cls=DjangoJSONEncoder, indent=2)
        return response
    
    def _export_compliance_excel(self, days: int) -> HttpResponse:
        """Export compliance report to Excel"""
        from .analytics import security_analytics
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="compliance_report_{timezone.now().strftime("%Y%m%d")}.xlsx"'
        
        # Get compliance analytics
        compliance_data = security_analytics.get_compliance_analytics(days)
        
        # Create Excel workbook
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        # Overview worksheet
        worksheet = workbook.add_worksheet('Compliance Overview')
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'border': 1
        })
        
        # Header
        headers = ['Metric', 'Score', 'Grade']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
            worksheet.set_column(col, col, 20)
        
        # Data
        row = 1
        worksheet.write(row, 0, 'Overall Compliance Score')
        worksheet.write(row, 1, compliance_data['overall_compliance_score'])
        worksheet.write(row, 2, compliance_data['compliance_grade'])
        
        row += 1
        worksheet.write(row, 0, 'Period (days)')
        worksheet.write(row, 1, compliance_data['period_days'])
        
        # Compliance metrics
        row += 2
        worksheet.write(row, 0, 'Compliance Metrics', None, header_format)
        row += 1
        
        for metric, score in compliance_data['compliance_metrics'].items():
            worksheet.write(row, 0, metric.replace('_', ' ').title())
            worksheet.write(row, 1, score)
            row += 1
        
        # Violations
        row += 1
        worksheet.write(row, 0, 'Violations', None, header_format)
        row += 1
        
        for violation in compliance_data['violations']:
            worksheet.write(row, 0, violation['type'])
            worksheet.write(row, 1, violation['count'])
            worksheet.write(row, 2, violation['severity'])
            row += 1
        
        workbook.close()
        output.seek(0)
        
        response.write(output.getvalue())
        return response
    
    def _export_compliance_pdf(self, days: int) -> HttpResponse:
        """Export compliance report to PDF"""
        from .analytics import security_analytics
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="compliance_report_{timezone.now().strftime("%Y%m%d")}.pdf"'
        
        # Get compliance analytics
        compliance_data = security_analytics.get_compliance_analytics(days)
        
        pdf_content = f"""
        Compliance Report
        Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
        Period: {days} days
        Overall Score: {compliance_data['overall_compliance_score']:.2f}%
        Grade: {compliance_data['compliance_grade']}
        
        Compliance Metrics:
        """
        
        for metric, score in compliance_data['compliance_metrics'].items():
            pdf_content += f"""
        {metric.replace('_', ' ').title()}: {score:.2f}%
        """
        
        if compliance_data['violations']:
            pdf_content += """
        
        Violations:
        """
            for violation in compliance_data['violations']:
                pdf_content += f"""
        - {violation['type']}: {violation['count']} ({violation['severity']})
        """
        
        response.write(pdf_content.encode())
        return response


# Global exporter instance
security_data_exporter = SecurityDataExporter()


# Export classes and utilities
__all__ = [
    'ExportFormat',
    'ExportStatus',
    'SecurityDataExporter',
    'security_data_exporter'
]