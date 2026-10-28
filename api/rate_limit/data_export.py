# api/rate_limit/data_export.py
"""
Data export system for rate limit module.

Provides comprehensive data export capabilities in multiple formats.
"""

import logging
import csv
import io
import json
import zipfile
from typing import Dict, Any, List, Optional, Union, BinaryIO
from datetime import datetime, timedelta
from django.utils import timezone
from django.http import HttpResponse
from django.core.cache import cache
from django.db.models import QuerySet
import pandas as pd

from api.rate_limit.models import (
    RateLimitLog, RateLimitConfig, UserRateLimitProfile, 
    AbuseReport, IPBlockList, RateLimitInsight, RateLimitException
)
from api.rate_limit.repositories import RepositoryFactory
from api.rate_limit.analytics import AnalyticsEngine
from api.rate_limit.encryption import DataProtectionManager

logger = logging.getLogger(__name__)


class ExportFormat:
    """Enumeration of export formats."""
    
    CSV = 'csv'
    JSON = 'json'
    EXCEL = 'excel'
    XML = 'xml'
    PDF = 'pdf'
    
    CHOICES = [
        (CSV, 'CSV'),
        (JSON, 'JSON'),
        (EXCEL, 'Excel'),
        (XML, 'XML'),
        (PDF, 'PDF'),
    ]


class ExportProcessor:
    """Base class for export processors."""
    
    def __init__(self, format_type: str):
        self.format_type = format_type
        self.data_protection = DataProtectionManager()
    
    def process(self, queryset: QuerySet, fields: List[str] = None, 
                 include_metadata: bool = True) -> Union[str, bytes]:
        """
        Process export data.
        
        Args:
            queryset: Django QuerySet
            fields: Fields to include
            include_metadata: Whether to include metadata
            
        Returns:
            Processed data
        """
        raise NotImplementedError("Subclasses must implement process()")
    
    def get_content_type(self) -> str:
        """Get content type for the export format."""
        content_types = {
            ExportFormat.CSV: 'text/csv',
            ExportFormat.JSON: 'application/json',
            ExportFormat.EXCEL: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            ExportFormat.XML: 'application/xml',
            ExportFormat.PDF: 'application/pdf'
        }
        return content_types.get(self.format_type, 'application/octet-stream')
    
    def get_file_extension(self) -> str:
        """Get file extension for the export format."""
        extensions = {
            ExportFormat.CSV: '.csv',
            ExportFormat.JSON: '.json',
            ExportFormat.EXCEL: '.xlsx',
            ExportFormat.XML: '.xml',
            ExportFormat.PDF: '.pdf'
        }
        return extensions.get(self.format_type, '.txt')


class CSVExportProcessor(ExportProcessor):
    """CSV export processor."""
    
    def __init__(self):
        super().__init__(ExportFormat.CSV)
    
    def process(self, queryset: QuerySet, fields: List[str] = None, 
                 include_metadata: bool = True) -> str:
        """Process data to CSV format."""
        try:
            output = io.StringIO()
            
            # Get field names
            if not fields:
                fields = self._get_model_fields(queryset.model)
            
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            
            # Write data rows
            for obj in queryset:
                row_data = self._serialize_object(obj, fields)
                
                # Apply data protection if needed
                if include_metadata:
                    row_data = self._apply_protection(row_data)
                
                writer.writerow(row_data)
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"CSV export failed: {str(e)}")
            raise
    
    def _get_model_fields(self, model) -> List[str]:
        """Get model field names."""
        return [field.name for field in model._meta.fields]
    
    def _serialize_object(self, obj, fields: List[str]) -> Dict[str, Any]:
        """Serialize object to dictionary."""
        data = {}
        
        for field in fields:
            value = getattr(obj, field, None)
            
            if value is not None:
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif hasattr(value, '__dict__'):
                    value = str(value)
                elif hasattr(value, 'id'):
                    value = value.id if hasattr(value, 'id') else str(value)
                
            data[field] = value
        
        return data
    
    def _apply_protection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply data protection to sensitive fields."""
        sensitive_fields = ['ip_address', 'user_agent', 'email', 'phone']
        
        for field in sensitive_fields:
            if field in data and data[field]:
                # Hash sensitive fields
                data[field] = self.data_protection.encryption_manager.generate_hash(
                    str(data[field])
                )
        
        return data


class JSONExportProcessor(ExportProcessor):
    """JSON export processor."""
    
    def __init__(self):
        super().__init__(ExportFormat.JSON)
    
    def process(self, queryset: QuerySet, fields: List[str] = None, 
                 include_metadata: bool = True) -> str:
        """Process data to JSON format."""
        try:
            # Get field names
            if not fields:
                fields = self._get_model_fields(queryset.model)
            
            # Serialize all objects
            data = []
            for obj in queryset:
                obj_data = self._serialize_object(obj, fields)
                
                # Apply data protection if needed
                if include_metadata:
                    obj_data = self._apply_protection(obj_data)
                
                data.append(obj_data)
            
            # Create export metadata
            export_data = {
                'export_metadata': {
                    'format': self.format_type,
                    'exported_at': timezone.now().isoformat(),
                    'record_count': len(data),
                    'model': queryset.model.__name__,
                    'fields': fields
                },
                'data': data
            }
            
            return json.dumps(export_data, cls=CustomJSONEncoder, indent=2)
            
        except Exception as e:
            logger.error(f"JSON export failed: {str(e)}")
            raise
    
    def _get_model_fields(self, model) -> List[str]:
        """Get model field names."""
        return [field.name for field in model._meta.fields]
    
    def _serialize_object(self, obj, fields: List[str]) -> Dict[str, Any]:
        """Serialize object to dictionary."""
        data = {}
        
        for field in fields:
            value = getattr(obj, field, None)
            
            if value is not None:
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif hasattr(value, '__dict__'):
                    value = str(value)
                elif hasattr(value, 'id'):
                    value = value.id if hasattr(value, 'id') else str(value)
                
            data[field] = value
        
        return data
    
    def _apply_protection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply data protection to sensitive fields."""
        sensitive_fields = ['ip_address', 'user_agent', 'email', 'phone']
        
        for field in sensitive_fields:
            if field in data and data[field]:
                # Hash sensitive fields
                data[field] = self.data_protection.encryption_manager.generate_hash(
                    str(data[field])
                )
        
        return data


class ExcelExportProcessor(ExportProcessor):
    """Excel export processor."""
    
    def __init__(self):
        super().__init__(ExportFormat.EXCEL)
    
    def process(self, queryset: QuerySet, fields: List[str] = None, 
                 include_metadata: bool = True) -> bytes:
        """Process data to Excel format."""
        try:
            # Get field names
            if not fields:
                fields = self._get_model_fields(queryset.model)
            
            # Convert to DataFrame
            data = []
            for obj in queryset:
                obj_data = self._serialize_object(obj, fields)
                
                # Apply data protection if needed
                if include_metadata:
                    obj_data = self._apply_protection(obj_data)
                
                data.append(obj_data)
            
            df = pd.DataFrame(data)
            
            # Create Excel file
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Write main data
                df.to_excel(writer, sheet_name='Data', index=False)
                
                # Add metadata sheet
                if include_metadata:
                    metadata = {
                        'Export Format': self.format_type,
                        'Exported At': timezone.now().isoformat(),
                        'Record Count': len(data),
                        'Model': queryset.model.__name__,
                        'Fields': ', '.join(fields)
                    }
                    
                    metadata_df = pd.DataFrame(list(metadata.items()), 
                                               columns=['Property', 'Value'])
                    metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Excel export failed: {str(e)}")
            raise
    
    def _get_model_fields(self, model) -> List[str]:
        """Get model field names."""
        return [field.name for field in model._meta.fields]
    
    def _serialize_object(self, obj, fields: List[str]) -> Dict[str, Any]:
        """Serialize object to dictionary."""
        data = {}
        
        for field in fields:
            value = getattr(obj, field, None)
            
            if value is not None:
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif hasattr(value, '__dict__'):
                    value = str(value)
                elif hasattr(value, 'id'):
                    value = value.id if hasattr(value, 'id') else str(value)
                
            data[field] = value
        
        return data
    
    def _apply_protection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply data protection to sensitive fields."""
        sensitive_fields = ['ip_address', 'user_agent', 'email', 'phone']
        
        for field in sensitive_fields:
            if field in data and data[field]:
                # Hash sensitive fields
                data[field] = self.data_protection.encryption_manager.generate_hash(
                    str(data[field])
                )
        
        return data


class XMLExportProcessor(ExportProcessor):
    """XML export processor."""
    
    def __init__(self):
        super().__init__(ExportFormat.XML)
    
    def process(self, queryset: QuerySet, fields: List[str] = None, 
                 include_metadata: bool = True) -> str:
        """Process data to XML format."""
        try:
            # Get field names
            if not fields:
                fields = self._get_model_fields(queryset.model)
            
            # Create XML structure
            xml_data = {
                'export_metadata': {
                    'format': self.format_type,
                    'exported_at': timezone.now().isoformat(),
                    'record_count': queryset.count(),
                    'model': queryset.model.__name__,
                    'fields': fields
                },
                'records': []
            }
            
            # Serialize all objects
            for obj in queryset:
                obj_data = self._serialize_object(obj, fields)
                
                # Apply data protection if needed
                if include_metadata:
                    obj_data = self._apply_protection(obj_data)
                
                xml_data['records'].append(obj_data)
            
            # Convert to XML
            return self._dict_to_xml(xml_data, 'export')
            
        except Exception as e:
            logger.error(f"XML export failed: {str(e)}")
            raise
    
    def _get_model_fields(self, model) -> List[str]:
        """Get model field names."""
        return [field.name for field in model._meta.fields]
    
    def _serialize_object(self, obj, fields: List[str]) -> Dict[str, Any]:
        """Serialize object to dictionary."""
        data = {}
        
        for field in fields:
            value = getattr(obj, field, None)
            
            if value is not None:
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif hasattr(value, '__dict__'):
                    value = str(value)
                elif hasattr(value, 'id'):
                    value = value.id if hasattr(value, 'id') else str(value)
                
            data[field] = value
        
        return data
    
    def _apply_protection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply data protection to sensitive fields."""
        sensitive_fields = ['ip_address', 'user_agent', 'email', 'phone']
        
        for field in sensitive_fields:
            if field in data and data[field]:
                # Hash sensitive fields
                data[field] = self.data_protection.encryption_manager.generate_hash(
                    str(data[field])
                )
        
        return data
    
    def _dict_to_xml(self, data: Dict[str, Any], root_name: str) -> str:
        """Convert dictionary to XML string."""
        def dict_to_xml_recursive(d, root):
            xml = f"<{root}>"
            for key, value in d.items():
                if isinstance(value, dict):
                    xml += dict_to_xml_recursive(value, key)
                elif isinstance(value, list):
                    for item in value:
                        xml += dict_to_xml_recursive(item, key)
                else:
                    xml += f"<{key}>{str(value)}</{key}>"
            xml += f"</{root}>"
            return xml
        
        return dict_to_xml_recursive(data, root_name)


class PDFExportProcessor(ExportProcessor):
    """PDF export processor."""
    
    def __init__(self):
        super().__init__(ExportFormat.PDF)
    
    def process(self, queryset: QuerySet, fields: List[str] = None, 
                 include_metadata: bool = True) -> bytes:
        """Process data to PDF format."""
        try:
            # For PDF export, we'll create a simple text-based PDF
            # In production, you'd use a proper PDF library like ReportLab
            
            # Get field names
            if not fields:
                fields = self._get_model_fields(queryset.model)
            
            # Create simple text content
            content = []
            
            # Add header
            content.append(f"Rate Limit Data Export")
            content.append(f"Format: {self.format_type}")
            content.append(f"Exported At: {timezone.now().isoformat()}")
            content.append(f"Model: {queryset.model.__name__}")
            content.append(f"Record Count: {queryset.count()}")
            content.append("")
            
            # Add headers
            content.append("\t".join(fields))
            content.append("-" * 100)
            
            # Add data rows
            for obj in queryset:
                obj_data = self._serialize_object(obj, fields)
                
                # Apply data protection if needed
                if include_metadata:
                    obj_data = self._apply_protection(obj_data)
                
                row = []
                for field in fields:
                    value = obj_data.get(field, '')
                    row.append(str(value))
                
                content.append("\t".join(row))
            
            # Convert to bytes (simplified approach)
            text_content = "\n".join(content)
            return text_content.encode('utf-8')
            
        except Exception as e:
            logger.error(f"PDF export failed: {str(e)}")
            raise
    
    def _get_model_fields(self, model) -> List[str]:
        """Get model field names."""
        return [field.name for field in model._meta.fields]
    
    def _serialize_object(self, obj, fields: List[str]) -> Dict[str, Any]:
        """Serialize object to dictionary."""
        data = {}
        
        for field in fields:
            value = getattr(obj, field, None)
            
            if value is not None:
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif hasattr(value, '__dict__'):
                    value = str(value)
                elif hasattr(value, 'id'):
                    value = value.id if hasattr(value, 'id') else str(value)
                
            data[field] = value
        
        return data
    
    def _apply_protection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply data protection to sensitive fields."""
        sensitive_fields = ['ip_address', 'user_agent', 'email', 'phone']
        
        for field in sensitive_fields:
            if field in data and data[field]:
                # Hash sensitive fields
                data[field] = self.data_protection.encryption_manager.generate_hash(
                    str(data[field])
                )
        
        return data


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for special types."""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)


class DataExporter:
    """
    Main data exporter class.
    """
    
    def __init__(self):
        self.repositories = RepositoryFactory.get_all_repositories()
        self.processors = {
            ExportFormat.CSV: CSVExportProcessor(),
            ExportFormat.JSON: JSONExportProcessor(),
            ExportFormat.EXCEL: ExcelExportProcessor(),
            ExportFormat.XML: XMLExportProcessor(),
            ExportFormat.PDF: PDFExportProcessor()
        }
    
    def export_rate_limit_logs(self, format_type: str = ExportFormat.CSV, 
                               days: int = 30, fields: List[str] = None,
                               include_metadata: bool = True) -> HttpResponse:
        """
        Export rate limit logs.
        
        Args:
            format_type: Export format
            days: Number of days to export
            fields: Fields to include
            include_metadata: Whether to include metadata
            
        Returns:
            HTTP response with exported data
        """
        try:
            # Get processor
            processor = self.processors.get(format_type)
            if not processor:
                raise ValueError(f"Unsupported export format: {format_type}")
            
            # Get queryset
            since_time = timezone.now() - timedelta(days=days)
            queryset = self.repositories['rate_limit_log'].model.objects.filter(
                timestamp__gte=since_time
            )
            
            # Process export
            data = processor.process(queryset, fields, include_metadata)
            
            # Create response
            response = HttpResponse(
                data,
                content_type=processor.get_content_type()
            )
            
            # Set headers
            filename = f"rate_limit_logs_{timezone.now().date()}{processor.get_file_extension()}"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
            
        except Exception as e:
            logger.error(f"Rate limit logs export failed: {str(e)}")
            raise
    
    def export_user_profiles(self, format_type: str = ExportFormat.CSV,
                             fields: List[str] = None,
                             include_metadata: bool = True) -> HttpResponse:
        """
        Export user rate limit profiles.
        
        Args:
            format_type: Export format
            fields: Fields to include
            include_metadata: Whether to include metadata
            
        Returns:
            HTTP response with exported data
        """
        try:
            # Get processor
            processor = self.processors.get(format_type)
            if not processor:
                raise ValueError(f"Unsupported export format: {format_type}")
            
            # Get queryset
            queryset = self.repositories['user_rate_limit_profile'].model.objects.all()
            
            # Process export
            data = processor.process(queryset, fields, include_metadata)
            
            # Create response
            response = HttpResponse(
                data,
                content_type=processor.get_content_type()
            )
            
            # Set headers
            filename = f"user_profiles_{timezone.now().date()}{processor.get_file_extension()}"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
            
        except Exception as e:
            logger.error(f"User profiles export failed: {str(e)}")
            raise
    
    def export_abuse_reports(self, format_type: str = ExportFormat.CSV,
                             days: int = 30, fields: List[str] = None,
                             include_metadata: bool = True) -> HttpResponse:
        """
        Export abuse reports.
        
        Args:
            format_type: Export format
            days: Number of days to export
            fields: Fields to include
            include_metadata: Whether to include metadata
            
        Returns:
            HTTP response with exported data
        """
        try:
            # Get processor
            processor = self.processors.get(format_type)
            if not processor:
                raise ValueError(f"Unsupported export format: {format_type}")
            
            # Get queryset
            since_time = timezone.now() - timedelta(days=days)
            queryset = self.repositories['abuse_report'].model.objects.filter(
                created_at__gte=since_time
            )
            
            # Process export
            data = processor.process(queryset, fields, include_metadata)
            
            # Create response
            response = HttpResponse(
                data,
                content_type=processor.get_content_type()
            )
            
            # Set headers
            filename = f"abuse_reports_{timezone.now().date()}{processor.get_file_extension()}"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
            
        except Exception as e:
            logger.error(f"Abuse reports export failed: {str(e)}")
            raise
    
    def export_ip_blocks(self, format_type: str = ExportFormat.CSV,
                         include_metadata: bool = True) -> HttpResponse:
        """
        Export IP blocks.
        
        Args:
            format_type: Export format
            include_metadata: Whether to include metadata
            
        Returns:
            HTTP response with exported data
        """
        try:
            # Get processor
            processor = self.processors.get(format_type)
            if not processor:
                raise ValueError(f"Unsupported export format: {format_type}")
            
            # Get queryset
            queryset = self.repositories['ip_block_list'].model.objects.all()
            
            # Process export
            data = processor.process(queryset, include_metadata=include_metadata)
            
            # Create response
            response = HttpResponse(
                data,
                content_type=processor.get_content_type()
            )
            
            # Set headers
            filename = f"ip_blocks_{timezone.now().date()}{processor.get_file_extension()}"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
            
        except Exception as e:
            logger.error(f"IP blocks export failed: {str(e)}")
            raise
    
    def export_analytics_data(self, analysis_type: str = 'overview',
                              format_type: str = ExportFormat.JSON,
                              days: int = 30) -> HttpResponse:
        """
        Export analytics data.
        
        Args:
            analysis_type: Type of analytics
            format_type: Export format
            days: Number of days to analyze
            
        Returns:
            HTTP response with exported data
        """
        try:
            # Get analytics engine
            analytics_engine = AnalyticsEngine()
            
            # Get analytics data
            if analysis_type == 'overview':
                data = analytics_engine.get_overview_statistics(days)
            elif analysis_type == 'time_series':
                data = analytics_engine.get_time_series_analysis(days)
            elif analysis_type == 'endpoint':
                data = analytics_engine.get_endpoint_analysis(days=days)
            elif analysis_type == 'user_behavior':
                data = analytics_engine.get_user_behavior_analysis(days=days)
            elif analysis_type == 'abuse_patterns':
                data = analytics_engine.get_abuse_pattern_analysis(days)
            elif analysis_type == 'performance':
                data = analytics_engine.get_performance_metrics(days * 24)
            else:
                raise ValueError(f"Unknown analysis type: {analysis_type}")
            
            # Create response
            response = HttpResponse(
                json.dumps(data, cls=CustomJSONEncoder, indent=2),
                content_type='application/json'
            )
            
            # Set headers
            filename = f"analytics_{analysis_type}_{timezone.now().date()}.json"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
            
        except Exception as e:
            logger.error(f"Analytics export failed: {str(e)}")
            raise
    
    def export_bulk_data(self, export_config: Dict[str, Any]) -> HttpResponse:
        """
        Export multiple data types in a single request.
        
        Args:
            export_config: Export configuration
            
        Returns:
            HTTP response with ZIP file containing all exports
        """
        try:
            # Create ZIP file in memory
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Export each configured data type
                for config in export_config.get('exports', []):
                    data_type = config.get('type')
                    format_type = config.get('format', ExportFormat.CSV)
                    filename = config.get('filename', f"{data_type}.{format_type}")
                    
                    # Get data
                    if data_type == 'logs':
                        response = self.export_rate_limit_logs(
                            format_type=format_type,
                            days=config.get('days', 30),
                            include_metadata=config.get('include_metadata', True)
                        )
                    elif data_type == 'profiles':
                        response = self.export_user_profiles(
                            format_type=format_type,
                            include_metadata=config.get('include_metadata', True)
                        )
                    elif data_type == 'abuse_reports':
                        response = self.export_abuse_reports(
                            format_type=format_type,
                            days=config.get('days', 30),
                            include_metadata=config.get('include_metadata', True)
                        )
                    elif data_type == 'ip_blocks':
                        response = self.export_ip_blocks(
                            format_type=format_type,
                            include_metadata=config.get('include_metadata', True)
                        )
                    else:
                        continue
                    
                    # Add to ZIP
                    zip_file.writestr(filename, response.content)
            
            # Create response
            zip_buffer.seek(0)
            response = HttpResponse(
                zip_buffer.getvalue(),
                content_type='application/zip'
            )
            
            # Set headers
            response['Content-Disposition'] = f'attachment; filename="rate_limit_export_{timezone.now().date()}.zip"'
            
            return response
            
        except Exception as e:
            logger.error(f"Bulk export failed: {str(e)}")
            raise
    
    def get_export_history(self) -> List[Dict[str, Any]]:
        """
        Get export history from cache.
        
        Returns:
            List of export history entries
        """
        try:
            # Get from cache
            history = cache.get('rate_limit_export_history', [])
            
            # Return recent exports (last 50)
            return history[-50:] if len(history) > 50 else history
            
        except Exception as e:
            logger.error(f"Failed to get export history: {str(e)}")
            return []
    
    def schedule_export(self, export_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Schedule an export job.
        
        Args:
            export_config: Export configuration
            
        Returns:
            Job information
        """
        try:
            from api.rate_limit.background_jobs import job_manager
            
            # Create export job
            job_name = f"export_{export_config.get('type', 'bulk')}"
            
            # Schedule the job
            from celery import current_app
            from api.rate_limit.background_jobs import run_background_job
            
            task = run_background_job.delay(job_name, export_config)
            
            return {
                'success': True,
                'job_id': task.id,
                'job_name': job_name,
                'status': 'scheduled'
            }
            
        except Exception as e:
            logger.error(f"Failed to schedule export: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Global data exporter instance
data_exporter = DataExporter()


# Export classes and functions
__all__ = [
    'ExportFormat',
    'ExportProcessor',
    'CSVExportProcessor',
    'JSONExportProcessor',
    'ExcelExportProcessor',
    'XMLExportProcessor',
    'PDFExportProcessor',
    'DataExporter',
    'data_exporter'
]
