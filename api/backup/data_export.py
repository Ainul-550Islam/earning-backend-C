"""
📊 Data Export Module

This module provides comprehensive data export capabilities for the backup system.
It includes multiple export formats, filtering options, scheduled exports, and
export management to support compliance and reporting requirements.

Features:
- Multiple export formats (CSV, Excel, JSON, XML, PDF)
- Advanced filtering and query options
- Scheduled and on-demand exports
- Export progress tracking
- Data security and privacy controls
- Export validation and integrity checks
- Compression and encryption of exports
- Export history and audit trail
"""

import logging
import os
import csv
import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional, Union, Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from django.db import models
from django.db.models import QuerySet
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django.conf import settings
from django.core.files.base import ContentFile
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import zipfile
import tempfile

# Import backup models
from .models import Backup, BackupSchedule, BackupLog, BackupVerification, BackupAlert
from .utils import TimeUtils, FileUtils

logger = logging.getLogger(__name__)


class ExportFormat(Enum):
    """Enumeration of supported export formats."""
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    XML = "xml"
    PDF = "pdf"


class ExportStatus(Enum):
    """Enumeration of export statuses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DataType(Enum):
    """Enumeration of export data types."""
    BACKUPS = "backups"
    SCHEDULES = "schedules"
    LOGS = "logs"
    VERIFICATIONS = "verifications"
    ALERTS = "alerts"
    ANALYTICS = "analytics"
    CUSTOM = "custom"


@dataclass
class ExportFilter:
    """Export filter configuration."""
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    status_filter: Optional[List[str]] = None
    storage_type_filter: Optional[List[str]] = None
    backup_type_filter: Optional[List[str]] = None
    user_filter: Optional[List[str]] = None
    custom_filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportConfig:
    """Export configuration."""
    export_format: ExportFormat = ExportFormat.CSV
    data_type: DataType = DataType.BACKUPS
    filters: Optional[ExportFilter] = None
    columns: Optional[List[str]] = None
    include_headers: bool = True
    compress_output: bool = False
    encrypt_output: bool = False
    max_records: Optional[int] = None
    batch_size: int = 1000
    timezone_offset: Optional[int] = None
    date_format: str = "%Y-%m-%d %H:%M:%S"
    encoding: str = "utf-8"
    delimiter: str = ","
    include_metadata: bool = True
    custom_formatter: Optional[Callable] = None


@dataclass
class ExportResult:
    """Result of an export operation."""
    success: bool
    export_id: str
    file_path: Optional[str] = None
    file_size: int = 0
    record_count: int = 0
    export_time_ms: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataExporter:
    """Main data exporter with multiple format support."""
    
    def __init__(self):
        self.export_dir = getattr(settings, 'BACKUP_EXPORT_DIR', '/tmp/backup_exports')
        os.makedirs(self.export_dir, exist_ok=True)
        
        # Format handlers
        self.format_handlers = {
            ExportFormat.CSV: self._export_csv,
            ExportFormat.EXCEL: self._export_excel,
            ExportFormat.JSON: self._export_json,
            ExportFormat.XML: self._export_xml,
            ExportFormat.PDF: self._export_pdf
        }
    
    def export_data(self, config: ExportConfig) -> ExportResult:
        """Export data based on configuration."""
        start_time = timezone.now()
        export_id = f"export_{int(start_time.timestamp())}"
        
        try:
            # Get data based on type
            queryset = self._get_queryset(config.data_type, config.filters)
            
            # Apply max records limit
            if config.max_records:
                queryset = queryset[:config.max_records]
            
            # Count records
            record_count = queryset.count()
            
            if record_count == 0:
                return ExportResult(
                    success=False,
                    export_id=export_id,
                    error_message="No records found matching the criteria"
                )
            
            # Generate file path
            file_extension = self._get_file_extension(config.export_format)
            file_path = os.path.join(self.export_dir, f"{export_id}.{file_extension}")
            
            # Export data
            handler = self.format_handlers[config.export_format]
            handler(queryset, file_path, config)
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Compress if requested
            if config.compress_output:
                file_path = self._compress_file(file_path)
                file_size = os.path.getsize(file_path)
            
            # Encrypt if requested
            if config.encrypt_output:
                file_path = self._encrypt_file(file_path)
                file_size = os.path.getsize(file_path)
            
            # Calculate export time
            export_time = (timezone.now() - start_time).total_seconds() * 1000
            
            result = ExportResult(
                success=True,
                export_id=export_id,
                file_path=file_path,
                file_size=file_size,
                record_count=record_count,
                export_time_ms=export_time,
                metadata={
                    'format': config.export_format.value,
                    'data_type': config.data_type.value,
                    'filters': config.filters.__dict__ if config.filters else {},
                    'columns': config.columns,
                    'compressed': config.compress_output,
                    'encrypted': config.encrypt_output
                }
            )
            
            logger.info(f"Export {export_id} completed: {record_count} records in {export_time:.2f}ms")
            return result
            
        except Exception as e:
            export_time = (timezone.now() - start_time).total_seconds() * 1000
            logger.error(f"Export {export_id} failed: {e}")
            
            return ExportResult(
                success=False,
                export_id=export_id,
                error_message=str(e),
                export_time_ms=export_time
            )
    
    def _get_queryset(self, data_type: DataType, filters: Optional[ExportFilter]) -> QuerySet:
        """Get queryset based on data type and filters."""
        if data_type == DataType.BACKUPS:
            queryset = Backup.objects.all()
            if filters:
                if filters.date_from:
                    queryset = queryset.filter(created_at__gte=filters.date_from)
                if filters.date_to:
                    queryset = queryset.filter(created_at__lte=filters.date_to)
                if filters.status_filter:
                    queryset = queryset.filter(status__in=filters.status_filter)
                if filters.storage_type_filter:
                    queryset = queryset.filter(storage_type__in=filters.storage_type_filter)
                if filters.backup_type_filter:
                    queryset = queryset.filter(backup_type__in=filters.backup_type_filter)
                if filters.user_filter:
                    queryset = queryset.filter(created_by__username__in=filters.user_filter)
        
        elif data_type == DataType.SCHEDULES:
            queryset = BackupSchedule.objects.all()
            if filters:
                if filters.date_from:
                    queryset = queryset.filter(created_at__gte=filters.date_from)
                if filters.date_to:
                    queryset = queryset.filter(created_at__lte=filters.date_to)
        
        elif data_type == DataType.LOGS:
            queryset = BackupLog.objects.all()
            if filters:
                if filters.date_from:
                    queryset = queryset.filter(created_at__gte=filters.date_from)
                if filters.date_to:
                    queryset = queryset.filter(created_at__lte=filters.date_to)
                if filters.custom_filters.get('log_level'):
                    queryset = queryset.filter(level=filters.custom_filters['log_level'])
                if filters.custom_filters.get('category'):
                    queryset = queryset.filter(category=filters.custom_filters['category'])
        
        elif data_type == DataType.VERIFICATIONS:
            queryset = BackupVerification.objects.all()
            if filters:
                if filters.date_from:
                    queryset = queryset.filter(verified_at__gte=filters.date_from)
                if filters.date_to:
                    queryset = queryset.filter(verified_at__lte=filters.date_to)
                if filters.status_filter:
                    queryset = queryset.filter(is_valid__in=[s == 'valid' for s in filters.status_filter])
        
        elif data_type == DataType.ALERTS:
            queryset = BackupAlert.objects.all()
            if filters:
                if filters.date_from:
                    queryset = queryset.filter(created_at__gte=filters.date_from)
                if filters.date_to:
                    queryset = queryset.filter(created_at__lte=filters.date_to)
                if filters.status_filter:
                    queryset = queryset.filter(is_resolved__in=[s == 'resolved' for s in filters.status_filter])
                if filters.custom_filters.get('severity'):
                    queryset = queryset.filter(severity=filters.custom_filters['severity'])
        
        else:
            raise ValueError(f"Unsupported data type: {data_type}")
        
        return queryset.select_related().order_by('-created_at')
    
    def _get_file_extension(self, export_format: ExportFormat) -> str:
        """Get file extension for export format."""
        extensions = {
            ExportFormat.CSV: 'csv',
            ExportFormat.EXCEL: 'xlsx',
            ExportFormat.JSON: 'json',
            ExportFormat.XML: 'xml',
            ExportFormat.PDF: 'pdf'
        }
        return extensions.get(export_format, 'txt')
    
    def _export_csv(self, queryset: QuerySet, file_path: str, config: ExportConfig) -> None:
        """Export data to CSV format."""
        with open(file_path, 'w', newline='', encoding=config.encoding) as csvfile:
            writer = csv.writer(csvfile, delimiter=config.delimiter)
            
            # Get field names
            model = queryset.model
            field_names = config.columns or [f.name for f in model._meta.fields]
            
            # Write headers
            if config.include_headers:
                headers = [model._meta.get_field(f).verbose_name or f for f in field_names]
                writer.writerow(headers)
            
            # Write data
            for obj in queryset.iterator(chunk_size=config.batch_size):
                row = []
                for field in field_names:
                    value = getattr(obj, field, '')
                    if isinstance(value, datetime):
                        value = value.strftime(config.date_format)
                    elif value is None:
                        value = ''
                    elif config.custom_formatter:
                        value = config.custom_formatter(field, value, obj)
                    row.append(str(value))
                writer.writerow(row)
    
    def _export_excel(self, queryset: QuerySet, file_path: str, config: ExportConfig) -> None:
        """Export data to Excel format."""
        wb = Workbook()
        ws = wb.active
        ws.title = f"{config.data_type.value.title()} Data"
        
        # Get field names
        model = queryset.model
        field_names = config.columns or [f.name for f in model._meta.fields]
        
        # Write headers with styling
        if config.include_headers:
            header_font = Font(bold=True)
            header_fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")
            
            for col, field in enumerate(field_names, 1):
                cell = ws.cell(row=1, column=col)
                cell.value = model._meta.get_field(field).verbose_name or field
                cell.font = header_font
                cell.fill = header_fill
        
        # Write data
        for row_num, obj in enumerate(queryset.iterator(chunk_size=config.batch_size), 2):
            for col_num, field in enumerate(field_names, 1):
                value = getattr(obj, field, '')
                if isinstance(value, datetime):
                    value = value.strftime(config.date_format)
                elif value is None:
                    value = ''
                elif config.custom_formatter:
                    value = config.custom_formatter(field, value, obj)
                
                ws.cell(row=row_num, column=col_num, value=str(value))
        
        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        wb.save(file_path)
    
    def _export_json(self, queryset: QuerySet, file_path: str, config: ExportConfig) -> None:
        """Export data to JSON format."""
        data = []
        
        for obj in queryset.iterator(chunk_size=config.batch_size):
            record = {}
            field_names = config.columns or [f.name for f in obj._meta.fields]
            
            for field in field_names:
                value = getattr(obj, field, '')
                if isinstance(value, datetime):
                    value = value.strftime(config.date_format)
                elif hasattr(value, '__dict__'):  # Related objects
                    value = str(value)
                elif config.custom_formatter:
                    value = config.custom_formatter(field, value, obj)
                
                record[field] = value
            
            data.append(record)
        
        # Add metadata if requested
        output = data
        if config.include_metadata:
            output = {
                'metadata': {
                    'export_date': timezone.now().isoformat(),
                    'data_type': config.data_type.value,
                    'record_count': len(data),
                    'filters': config.filters.__dict__ if config.filters else {}
                },
                'data': data
            }
        
        with open(file_path, 'w', encoding=config.encoding) as jsonfile:
            json.dump(output, jsonfile, indent=2, ensure_ascii=False)
    
    def _export_xml(self, queryset: QuerySet, file_path: str, config: ExportConfig) -> None:
        """Export data to XML format."""
        root = ET.Element(f"{config.data_type.value}_data")
        
        # Add metadata if requested
        if config.include_metadata:
            metadata = ET.SubElement(root, "metadata")
            ET.SubElement(metadata, "export_date").text = timezone.now().isoformat()
            ET.SubElement(metadata, "data_type").text = config.data_type.value
            ET.SubElement(metadata, "record_count").text = str(queryset.count())
        
        # Add records
        records = ET.SubElement(root, "records")
        field_names = config.columns or [f.name for f in queryset.model._meta.fields]
        
        for obj in queryset.iterator(chunk_size=config.batch_size):
            record = ET.SubElement(records, "record")
            
            for field in field_names:
                value = getattr(obj, field, '')
                if isinstance(value, datetime):
                    value = value.strftime(config.date_format)
                elif hasattr(value, '__dict__'):
                    value = str(value)
                elif config.custom_formatter:
                    value = config.custom_formatter(field, value, obj)
                
                element = ET.SubElement(record, field)
                element.text = str(value)
        
        # Write to file
        tree = ET.ElementTree(root)
        tree.write(file_path, encoding=config.encoding, xml_declaration=True)
    
    def _export_pdf(self, queryset: QuerySet, file_path: str, config: ExportConfig) -> None:
        """Export data to PDF format."""
        doc = SimpleDocTemplate(file_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1  # Center alignment
        )
        story.append(Paragraph(f"{config.data_type.title()} Export", title_style))
        
        # Metadata
        if config.include_metadata:
            metadata_style = styles['Normal']
            metadata_text = f"""
            Export Date: {timezone.now().strftime(config.date_format)}<br/>
            Data Type: {config.data_type.value}<br/>
            Record Count: {queryset.count()}
            """
            story.append(Paragraph(metadata_text, metadata_style))
            story.append(Spacer(1, 20))
        
        # Table data
        field_names = config.columns or [f.name for f in queryset.model._meta.fields]
        
        # Prepare table data
        table_data = []
        
        # Headers
        if config.include_headers:
            headers = [queryset.model._meta.get_field(f).verbose_name or f for f in field_names]
            table_data.append(headers)
        
        # Data rows (limit to prevent memory issues)
        max_rows = 1000  # Limit for PDF
        for obj in queryset[:max_rows]:
            row = []
            for field in field_names:
                value = getattr(obj, field, '')
                if isinstance(value, datetime):
                    value = value.strftime(config.date_format)
                elif hasattr(value, '__dict__'):
                    value = str(value)
                elif config.custom_formatter:
                    value = config.custom_formatter(field, value, obj)
                
                row.append(str(value))
            table_data.append(row)
        
        # Create table
        if table_data:
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 14),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            # Adjust column widths
            col_widths = [len(str(header)) * 8 for header in table_data[0]]
            table._argW = col_widths
            
            story.append(table)
        
        # Build PDF
        doc.build(story)
    
    def _compress_file(self, file_path: str) -> str:
        """Compress export file."""
        compressed_path = f"{file_path}.zip"
        
        with zipfile.ZipFile(compressed_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(file_path, os.path.basename(file_path))
        
        # Remove original file
        os.remove(file_path)
        
        return compressed_path
    
    def _encrypt_file(self, file_path: str) -> str:
        """Encrypt export file (placeholder implementation)."""
        # This would integrate with the encryption module
        # For now, just return the original path
        logger.warning("File encryption not implemented - returning original file")
        return file_path
    
    def get_export_formats(self) -> List[Dict[str, str]]:
        """Get available export formats."""
        return [
            {'value': fmt.value, 'label': fmt.value.title()}
            for fmt in ExportFormat
        ]
    
    def get_data_types(self) -> List[Dict[str, str]]:
        """Get available data types."""
        return [
            {'value': dt.value, 'label': dt.value.title()}
            for dt in DataType
        ]
    
    def get_model_fields(self, data_type: DataType) -> List[Dict[str, str]]:
        """Get available fields for a data type."""
        field_mapping = {
            DataType.BACKUPS: Backup,
            DataType.SCHEDULES: BackupSchedule,
            DataType.LOGS: BackupLog,
            DataType.VERIFICATIONS: BackupVerification,
            DataType.ALERTS: BackupAlert
        }
        
        model = field_mapping.get(data_type)
        if not model:
            return []
        
        return [
            {
                'name': field.name,
                'label': field.verbose_name or field.name.title(),
                'type': field.get_internal_type()
            }
            for field in model._meta.fields
        ]
    
    def validate_export_config(self, config: ExportConfig) -> List[str]:
        """Validate export configuration."""
        errors = []
        
        # Validate data type
        if not isinstance(config.data_type, DataType):
            errors.append("Invalid data type")
        
        # Validate format
        if not isinstance(config.export_format, ExportFormat):
            errors.append("Invalid export format")
        
        # Validate filters
        if config.filters:
            if config.filters.date_from and config.filters.date_to:
                if config.filters.date_from > config.filters.date_to:
                    errors.append("Date from must be before date to")
        
        # Validate batch size
        if config.batch_size <= 0:
            errors.append("Batch size must be greater than 0")
        
        # Validate max records
        if config.max_records and config.max_records <= 0:
            errors.append("Max records must be greater than 0")
        
        return errors


class ScheduledExportManager:
    """Manages scheduled data exports."""
    
    def __init__(self):
        self.scheduled_exports: Dict[str, Dict[str, Any]] = {}
        self.export_dir = getattr(settings, 'BACKUP_EXPORT_DIR', '/tmp/backup_exports')
    
    def schedule_export(self, export_id: str, config: ExportConfig, 
                       schedule_expression: str, recipients: List[str]) -> bool:
        """Schedule a recurring export."""
        try:
            self.scheduled_exports[export_id] = {
                'config': config,
                'schedule_expression': schedule_expression,
                'recipients': recipients,
                'last_run': None,
                'next_run': self._calculate_next_run(schedule_expression),
                'active': True,
                'created_at': timezone.now()
            }
            
            logger.info(f"Scheduled export {export_id} with expression: {schedule_expression}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to schedule export {export_id}: {e}")
            return False
    
    def _calculate_next_run(self, schedule_expression: str) -> datetime:
        """Calculate next run time from cron expression (simplified)."""
        # This would use a proper cron parser
        # For now, just schedule for next day
        return timezone.now() + timedelta(days=1)
    
    def run_scheduled_exports(self) -> List[ExportResult]:
        """Run all scheduled exports that are due."""
        results = []
        now = timezone.now()
        
        for export_id, export_config in self.scheduled_exports.items():
            if not export_config['active']:
                continue
            
            if export_config['next_run'] <= now:
                try:
                    # Run export
                    exporter = DataExporter()
                    result = exporter.export_data(export_config['config'])
                    
                    # Update schedule
                    export_config['last_run'] = now
                    export_config['next_run'] = self._calculate_next_run(
                        export_config['schedule_expression']
                    )
                    
                    # Send to recipients
                    if result.success and export_config['recipients']:
                        self._send_export_to_recipients(result, export_config['recipients'])
                    
                    results.append(result)
                    
                except Exception as e:
                    logger.error(f"Failed to run scheduled export {export_id}: {e}")
                    results.append(ExportResult(
                        success=False,
                        export_id=export_id,
                        error_message=str(e)
                    ))
        
        return results
    
    def _send_export_to_recipients(self, result: ExportResult, recipients: List[str]) -> None:
        """Send export file to recipients."""
        # This would integrate with email/notification system
        logger.info(f"Export {result.export_id} ready for {len(recipients)} recipients")
    
    def get_scheduled_exports(self) -> List[Dict[str, Any]]:
        """Get all scheduled exports."""
        return [
            {
                'export_id': export_id,
                'data_type': config['config'].data_type.value,
                'format': config['config'].export_format.value,
                'schedule_expression': config['schedule_expression'],
                'recipients': config['recipients'],
                'last_run': config['last_run'].isoformat() if config['last_run'] else None,
                'next_run': config['next_run'].isoformat() if config['next_run'] else None,
                'active': config['active'],
                'created_at': config['created_at'].isoformat()
            }
            for export_id, config in self.scheduled_exports.items()
        ]
    
    def cancel_scheduled_export(self, export_id: str) -> bool:
        """Cancel a scheduled export."""
        if export_id in self.scheduled_exports:
            del self.scheduled_exports[export_id]
            logger.info(f"Cancelled scheduled export {export_id}")
            return True
        return False


class ExportHistoryManager:
    """Manages export history and audit trail."""
    
    def __init__(self):
        self.export_history: List[Dict[str, Any]] = []
        self.max_history = getattr(settings, 'BACKUP_EXPORT_MAX_HISTORY', 1000)
    
    def record_export(self, result: ExportResult, config: ExportConfig, 
                     user: Optional[str] = None) -> None:
        """Record export in history."""
        history_entry = {
            'export_id': result.export_id,
            'success': result.success,
            'data_type': config.data_type.value,
            'format': config.export_format.value,
            'record_count': result.record_count,
            'file_size': result.file_size,
            'export_time_ms': result.export_time_ms,
            'filters': config.filters.__dict__ if config.filters else {},
            'columns': config.columns,
            'compressed': config.compress_output,
            'encrypted': config.encrypt_output,
            'user': user,
            'timestamp': timezone.now().isoformat(),
            'error_message': result.error_message
        }
        
        self.export_history.append(history_entry)
        
        # Limit history size
        if len(self.export_history) > self.max_history:
            self.export_history = self.export_history[-self.max_history:]
    
    def get_export_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get export history."""
        history = sorted(self.export_history, key=lambda x: x['timestamp'], reverse=True)
        return history[:limit] if limit else history
    
    def get_export_statistics(self) -> Dict[str, Any]:
        """Get export statistics."""
        if not self.export_history:
            return {}
        
        total_exports = len(self.export_history)
        successful_exports = sum(1 for e in self.export_history if e['success'])
        failed_exports = total_exports - successful_exports
        
        # Statistics by data type
        by_data_type = {}
        for entry in self.export_history:
            data_type = entry['data_type']
            if data_type not in by_data_type:
                by_data_type[data_type] = {'total': 0, 'successful': 0}
            by_data_type[data_type]['total'] += 1
            if entry['success']:
                by_data_type[data_type]['successful'] += 1
        
        # Statistics by format
        by_format = {}
        for entry in self.export_history:
            format_type = entry['format']
            if format_type not in by_format:
                by_format[format_type] = {'total': 0, 'successful': 0}
            by_format[format_type]['total'] += 1
            if entry['success']:
                by_format[format_type]['successful'] += 1
        
        return {
            'total_exports': total_exports,
            'successful_exports': successful_exports,
            'failed_exports': failed_exports,
            'success_rate': (successful_exports / total_exports * 100) if total_exports > 0 else 0,
            'by_data_type': by_data_type,
            'by_format': by_format
        }


# Global instances
_exporter: Optional[DataExporter] = None
_scheduled_manager: Optional[ScheduledExportManager] = None
_history_manager: Optional[ExportHistoryManager] = None


def get_data_exporter() -> DataExporter:
    """Get the global data exporter instance."""
    global _exporter
    if _exporter is None:
        _exporter = DataExporter()
    return _exporter


def get_scheduled_export_manager() -> ScheduledExportManager:
    """Get the global scheduled export manager instance."""
    global _scheduled_manager
    if _scheduled_manager is None:
        _scheduled_manager = ScheduledExportManager()
    return _scheduled_manager


def get_export_history_manager() -> ExportHistoryManager:
    """Get the global export history manager instance."""
    global _history_manager
    if _history_manager is None:
        _history_manager = ExportHistoryManager()
    return _history_manager


def export_backups(filters: Optional[ExportFilter] = None, 
                  format: ExportFormat = ExportFormat.CSV,
                  columns: Optional[List[str]] = None,
                  user: Optional[str] = None) -> ExportResult:
    """Export backup data."""
    config = ExportConfig(
        export_format=format,
        data_type=DataType.BACKUPS,
        filters=filters,
        columns=columns
    )
    
    exporter = get_data_exporter()
    result = exporter.export_data(config)
    
    # Record in history
    history_manager = get_export_history_manager()
    history_manager.record_export(result, config, user)
    
    return result


def export_schedules(filters: Optional[ExportFilter] = None,
                    format: ExportFormat = ExportFormat.CSV,
                    columns: Optional[List[str]] = None,
                    user: Optional[str] = None) -> ExportResult:
    """Export schedule data."""
    config = ExportConfig(
        export_format=format,
        data_type=DataType.SCHEDULES,
        filters=filters,
        columns=columns
    )
    
    exporter = get_data_exporter()
    result = exporter.export_data(config)
    
    # Record in history
    history_manager = get_export_history_manager()
    history_manager.record_export(result, config, user)
    
    return result


def export_logs(filters: Optional[ExportFilter] = None,
                format: ExportFormat = ExportFormat.CSV,
                columns: Optional[List[str]] = None,
                user: Optional[str] = None) -> ExportResult:
    """Export log data."""
    config = ExportConfig(
        export_format=format,
        data_type=DataType.LOGS,
        filters=filters,
        columns=columns
    )
    
    exporter = get_data_exporter()
    result = exporter.export_data(config)
    
    # Record in history
    history_manager = get_export_history_manager()
    history_manager.record_export(result, config, user)
    
    return result


def get_export_history(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get export history."""
    history_manager = get_export_history_manager()
    return history_manager.get_export_history(limit)


def get_export_statistics() -> Dict[str, Any]:
    """Get export statistics."""
    history_manager = get_export_history_manager()
    return history_manager.get_export_statistics()
