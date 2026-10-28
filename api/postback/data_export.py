"""
data_export.py – Data export system for postback module.

Provides comprehensive data export functionality including:
- Multiple export formats (CSV, Excel, JSON, XML)
- Data filtering and pagination
- Export job management
- Export scheduling and automation
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable, Type
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import io
import csv
import json
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
import tempfile
import os

from django.utils import timezone
from django.core.cache import cache
from django.db import models
from django.http import HttpResponse
from django.conf import settings

from .background_jobs import job_scheduler, JobType, JobPriority
from .integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)


class ExportFormat(Enum):
    """Export format enumeration."""
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    XML = "xml"
    PDF = "pdf"


class ExportStatus(Enum):
    """Export status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExportField:
    """Export field configuration."""
    name: str
    label: str
    field_type: str = "string"
    format_func: Optional[Callable] = None
    default_value: Any = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'label': self.label,
            'field_type': self.field_type,
            'default_value': self.default_value,
        }


@dataclass
class ExportConfig:
    """Export configuration."""
    name: str
    format: ExportFormat
    fields: List[ExportField]
    filters: Dict[str, Any] = field(default_factory=dict)
    ordering: List[str] = field(default_factory=list)
    limit: Optional[int] = None
    offset: int = 0
    include_headers: bool = True
    encoding: str = "utf-8"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'format': self.format.value,
            'fields': [field.to_dict() for field in self.fields],
            'filters': self.filters,
            'ordering': self.ordering,
            'limit': self.limit,
            'offset': self.offset,
            'include_headers': self.include_headers,
            'encoding': self.encoding,
            'date_format': self.date_format,
            'metadata': self.metadata,
        }


@dataclass
class ExportJob:
    """Export job data structure."""
    id: str
    config: ExportConfig
    status: ExportStatus = ExportStatus.PENDING
    created_at: datetime = field(default_factory=timezone.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    file_path: Optional[str] = None
    file_size: int = 0
    record_count: int = 0
    error_message: Optional[str] = None
    progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'config': self.config.to_dict(),
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'record_count': self.record_count,
            'error_message': self.error_message,
            'progress': self.progress,
            'metadata': self.metadata,
        }


class DataExporter:
    """
    Data exporter for various formats.
    
    Handles data export with different formats
    and configurations.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.export_jobs: Dict[str, ExportJob] = {}
        self.temp_dir = getattr(settings, 'EXPORT_TEMP_DIR', '/tmp/exports')
        self.max_file_size = getattr(settings, 'EXPORT_MAX_FILE_SIZE', 100 * 1024 * 1024)  # 100MB
        
        # Ensure temp directory exists
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def create_export_job(self, config: ExportConfig) -> ExportJob:
        """
        Create export job.
        
        Args:
            config: Export configuration
            
        Returns:
            Export job
        """
        import uuid
        
        job = ExportJob(
            id=f"export_{uuid.uuid4().hex[:12]}",
            config=config
        )
        
        self.export_jobs[job.id] = job
        self.logger.info(f"Export job created: {job.id}")
        
        return job
    
    def export_data(self, queryset: models.QuerySet, config: ExportConfig) -> str:
        """
        Export data immediately.
        
        Args:
            queryset: Django queryset
            config: Export configuration
            
        Returns:
            File path
        """
        try:
            # Apply filters
            filtered_queryset = self._apply_filters(queryset, config.filters)
            
            # Apply ordering
            if config.ordering:
                filtered_queryset = filtered_queryset.order_by(*config.ordering)
            
            # Apply limit and offset
            if config.offset:
                filtered_queryset = filtered_queryset[config.offset:]
            
            if config.limit:
                filtered_queryset = filtered_queryset[:config.limit]
            
            # Export based on format
            if config.format == ExportFormat.CSV:
                return self._export_csv(filtered_queryset, config)
            elif config.format == ExportFormat.EXCEL:
                return self._export_excel(filtered_queryset, config)
            elif config.format == ExportFormat.JSON:
                return self._export_json(filtered_queryset, config)
            elif config.format == ExportFormat.XML:
                return self._export_xml(filtered_queryset, config)
            elif config.format == ExportFormat.PDF:
                return self._export_pdf(filtered_queryset, config)
            else:
                raise IntegrationException(f"Unsupported export format: {config.format}")
        
        except Exception as e:
            self.logger.error(f"Export failed: {str(e)}")
            raise IntegrationException(f"Export failed: {str(e)}")
    
    def export_async(self, queryset: models.QuerySet, config: ExportConfig) -> str:
        """
        Export data asynchronously.
        
        Args:
            queryset: Django queryset
            config: Export configuration
            
        Returns:
            Export job ID
        """
        # Create export job
        job = self.create_export_job(config)
        
        # Submit background job
        job_id = job_scheduler.submit_job(
            name=f"Export {config.name}",
            function=self._export_async_worker,
            job_type=JobType.DATA_EXPORT,
            priority=JobPriority.NORMAL,
            args=[queryset, job]
        )
        
        return job_id
    
    def _export_async_worker(self, queryset: models.QuerySet, job: ExportJob):
        """Background worker for async export."""
        try:
            # Update job status
            job.status = ExportStatus.PROCESSING
            job.started_at = timezone.now()
            
            # Export data
            file_path = self.export_data(queryset, job.config)
            
            # Update job with results
            job.status = ExportStatus.COMPLETED
            job.completed_at = timezone.now()
            job.file_path = file_path
            job.file_size = os.path.getsize(file_path)
            job.progress = 100.0
            
            self.logger.info(f"Export completed: {job.id}")
        
        except Exception as e:
            # Update job with error
            job.status = ExportStatus.FAILED
            job.completed_at = timezone.now()
            job.error_message = str(e)
            
            self.logger.error(f"Export failed: {job.id} - {str(e)}")
    
    def _apply_filters(self, queryset: models.QuerySet, filters: Dict[str, Any]) -> models.QuerySet:
        """Apply filters to queryset."""
        filtered_queryset = queryset
        
        for field, value in filters.items():
            if isinstance(value, dict):
                # Handle complex filters
                if 'gt' in value:
                    filtered_queryset = filtered_queryset.filter(**{f"{field}__gt": value['gt']})
                if 'lt' in value:
                    filtered_queryset = filtered_queryset.filter(**{f"{field}__lt": value['lt']})
                if 'gte' in value:
                    filtered_queryset = filtered_queryset.filter(**{f"{field}__gte": value['gte']})
                if 'lte' in value:
                    filtered_queryset = filtered_queryset.filter(**{f"{field}__lte": value['lte']})
                if 'in' in value:
                    filtered_queryset = filtered_queryset.filter(**{f"{field}__in": value['in']})
                if 'contains' in value:
                    filtered_queryset = filtered_queryset.filter(**{f"{field}__contains": value['contains']})
                if 'icontains' in value:
                    filtered_queryset = filtered_queryset.filter(**{f"{field}__icontains": value['icontains']})
            else:
                # Simple filter
                filtered_queryset = filtered_queryset.filter(**{field: value})
        
        return filtered_queryset
    
    def _export_csv(self, queryset: models.QuerySet, config: ExportConfig) -> str:
        """Export to CSV format."""
        # Create temporary file
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{config.name}_{timestamp}.csv"
        file_path = os.path.join(self.temp_dir, filename)
        
        with open(file_path, 'w', newline='', encoding=config.encoding) as csvfile:
            writer = csv.writer(csvfile)
            
            # Write headers
            if config.include_headers:
                headers = [field.label for field in config.fields]
                writer.writerow(headers)
            
            # Write data rows
            record_count = 0
            for obj in queryset:
                row = []
                for field in config.fields:
                    value = self._get_field_value(obj, field, config)
                    row.append(value)
                
                writer.writerow(row)
                record_count += 1
                
                # Check file size
                if os.path.getsize(file_path) > self.max_file_size:
                    raise IntegrationException("Export file size exceeded limit")
        
        self.logger.info(f"CSV export completed: {file_path} ({record_count} records)")
        return file_path
    
    def _export_excel(self, queryset: models.QuerySet, config: ExportConfig) -> str:
        """Export to Excel format."""
        try:
            import pandas as pd
        except ImportError:
            raise IntegrationException("pandas is required for Excel export")
        
        # Create temporary file
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{config.name}_{timestamp}.xlsx"
        file_path = os.path.join(self.temp_dir, filename)
        
        # Prepare data
        data = []
        for obj in queryset:
            row = {}
            for field in config.fields:
                value = self._get_field_value(obj, field, config)
                row[field.label] = value
            data.append(row)
            
            # Check file size estimate
            if len(data) * 100 > self.max_file_size:  # Rough estimate
                raise IntegrationException("Export file size exceeded limit")
        
        # Create DataFrame and export
        df = pd.DataFrame(data)
        
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=config.name)
        
        self.logger.info(f"Excel export completed: {file_path} ({len(data)} records)")
        return file_path
    
    def _export_json(self, queryset: models.QuerySet, config: ExportConfig) -> str:
        """Export to JSON format."""
        # Create temporary file
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{config.name}_{timestamp}.json"
        file_path = os.path.join(self.temp_dir, filename)
        
        # Prepare data
        data = {
            'metadata': {
                'exported_at': timezone.now().isoformat(),
                'record_count': queryset.count(),
                'format': config.format.value,
                'fields': [field.to_dict() for field in config.fields],
            },
            'data': []
        }
        
        for obj in queryset:
            record = {}
            for field in config.fields:
                value = self._get_field_value(obj, field, config)
                record[field.name] = value
            data['data'].append(record)
            
            # Check file size
            if len(json.dumps(data)) > self.max_file_size:
                raise IntegrationException("Export file size exceeded limit")
        
        # Write JSON file
        with open(file_path, 'w', encoding=config.encoding) as jsonfile:
            json.dump(data, jsonfile, indent=2, default=str, ensure_ascii=False)
        
        self.logger.info(f"JSON export completed: {file_path} ({len(data['data'])} records)")
        return file_path
    
    def _export_xml(self, queryset: models.QuerySet, config: ExportConfig) -> str:
        """Export to XML format."""
        # Create temporary file
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{config.name}_{timestamp}.xml"
        file_path = os.path.join(self.temp_dir, filename)
        
        # Create root element
        root = ET.Element('data')
        
        # Add metadata
        metadata = ET.SubElement(root, 'metadata')
        ET.SubElement(metadata, 'exported_at').text = timezone.now().isoformat()
        ET.SubElement(metadata, 'record_count').text = str(queryset.count())
        ET.SubElement(metadata, 'format').text = config.format.value
        
        # Add data records
        records_element = ET.SubElement(root, 'records')
        record_count = 0
        
        for obj in queryset:
            record_element = ET.SubElement(records_element, 'record')
            
            for field in config.fields:
                value = self._get_field_value(obj, field, config)
                field_element = ET.SubElement(record_element, field.name)
                field_element.text = str(value) if value is not None else ''
            
            record_count += 1
            
            # Check file size
            if len(ET.tostring(root)) > self.max_file_size:
                raise IntegrationException("Export file size exceeded limit")
        
        # Write XML file
        tree = ET.ElementTree(root)
        tree.write(file_path, encoding=config.encoding, xml_declaration=True)
        
        self.logger.info(f"XML export completed: {file_path} ({record_count} records)")
        return file_path
    
    def _export_pdf(self, queryset: models.QuerySet, config: ExportConfig) -> str:
        """Export to PDF format."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
        except ImportError:
            raise IntegrationException("reportlab is required for PDF export")
        
        # Create temporary file
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{config.name}_{timestamp}.pdf"
        file_path = os.path.join(self.temp_dir, filename)
        
        # Create PDF document
        doc = SimpleDocTemplate(file_path, pagesize=landscape(letter))
        styles = getSampleStyleSheet()
        story = []
        
        # Add title
        title = Paragraph(config.name, styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Prepare table data
        headers = [field.label for field in config.fields] if config.include_headers else []
        data = []
        
        for obj in queryset:
            row = []
            for field in config.fields:
                value = self._get_field_value(obj, field, config)
                row.append(str(value) if value is not None else '')
            data.append(row)
            
            # Check file size estimate
            if len(data) * 100 > self.max_file_size:
                raise IntegrationException("Export file size exceeded limit")
        
        # Create table
        if headers:
            table_data = [headers] + data
        else:
            table_data = data
        
        table = Table(table_data)
        
        # Add table style
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        table.setStyle(style)
        
        story.append(table)
        
        # Build PDF
        doc.build(story)
        
        self.logger.info(f"PDF export completed: {file_path} ({len(data)} records)")
        return file_path
    
    def _get_field_value(self, obj: models.Model, field: ExportField, config: ExportConfig) -> Any:
        """Get field value from object."""
        # Navigate nested fields
        value = obj
        for part in field.name.split('.'):
            if hasattr(value, part):
                value = getattr(value, part)
            else:
                value = None
                break
        
        # Apply format function
        if field.format_func and value is not None:
            try:
                value = field.format_func(value)
            except Exception as e:
                self.logger.warning(f"Format function failed for field {field.name}: {str(e)}")
        
        # Format dates
        if isinstance(value, datetime):
            value = value.strftime(config.date_format)
        elif value is None:
            value = field.default_value if field.default_value is not None else ''
        
        return value
    
    def get_export_job(self, job_id: str) -> Optional[ExportJob]:
        """Get export job by ID."""
        return self.export_jobs.get(job_id)
    
    def get_export_jobs(self, status: ExportStatus = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get export jobs."""
        jobs = list(self.export_jobs.values())
        
        if status:
            jobs = [job for job in jobs if job.status == status]
        
        # Sort by created time
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        return [job.to_dict() for job in jobs[:limit]]
    
    def download_file(self, file_path: str) -> HttpResponse:
        """Create HTTP response for file download."""
        if not os.path.exists(file_path):
            raise IntegrationException("Export file not found")
        
        # Get file info
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        # Create response
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = file_size
            return response
    
    def cleanup_old_files(self, days: int = 7) -> int:
        """Clean up old export files."""
        cutoff_time = timezone.now() - timedelta(days=days)
        cleaned_count = 0
        
        for filename in os.listdir(self.temp_dir):
            file_path = os.path.join(self.temp_dir, filename)
            
            if os.path.isfile(file_path):
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_time < cutoff_time:
                    try:
                        os.remove(file_path)
                        cleaned_count += 1
                    except Exception as e:
                        self.logger.error(f"Failed to remove file {file_path}: {str(e)}")
        
        self.logger.info(f"Cleaned up {cleaned_count} old export files")
        return cleaned_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get export statistics."""
        total_jobs = len(self.export_jobs)
        
        # Count by status
        status_counts = {}
        for job in self.export_jobs.values():
            status = job.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Count by format
        format_counts = {}
        for job in self.export_jobs.values():
            format_type = job.config.format.value
            format_counts[format_type] = format_counts.get(format_type, 0) + 1
        
        return {
            'total_jobs': total_jobs,
            'status_counts': status_counts,
            'format_counts': format_counts,
            'temp_directory': self.temp_dir,
            'max_file_size': self.max_file_size,
        }


# Global data exporter instance
data_exporter = DataExporter()


# Convenience functions
def create_export_config(name: str, format: ExportFormat, fields: List[ExportField],
                        filters: Dict[str, Any] = None, ordering: List[str] = None,
                        limit: int = None, include_headers: bool = True) -> ExportConfig:
    """Create export configuration."""
    return ExportConfig(
        name=name,
        format=format,
        fields=fields,
        filters=filters or {},
        ordering=ordering or [],
        limit=limit,
        include_headers=include_headers
    )


def export_data(queryset: models.QuerySet, config: ExportConfig) -> str:
    """Export data immediately."""
    return data_exporter.export_data(queryset, config)


def export_data_async(queryset: models.QuerySet, config: ExportConfig) -> str:
    """Export data asynchronously."""
    return data_exporter.export_async(queryset, config)


def get_export_job(job_id: str) -> Optional[ExportJob]:
    """Get export job."""
    return data_exporter.get_export_job(job_id)


def download_export_file(file_path: str) -> HttpResponse:
    """Download export file."""
    return data_exporter.download_file(file_path)


def get_export_statistics() -> Dict[str, Any]:
    """Get export statistics."""
    return data_exporter.get_statistics()
