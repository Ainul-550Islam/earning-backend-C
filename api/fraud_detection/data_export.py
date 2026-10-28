# =============================================================================
# fraud_detection/data_export.py
# =============================================================================
"""
Data Export Functionality for Fraud Detection System.

Provides comprehensive data export capabilities with multiple formats,
filtering options, and performance optimization for large datasets.
"""

from __future__ import annotations

import logging
import csv
import io
import zipfile
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple, BinaryIO
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from django.db.models import QuerySet
from django.core.paginator import Paginator
from django.core.cache import cache
from django.contrib.auth import get_user_model

from api.fraud_detection.models import (
    FraudCase, FraudAlert, FraudRule, FraudRiskProfile,
    DeviceFingerprint, FraudSuspiciousIP
)
from api.fraud_detection.selectors import (
    fraud_case_selector, fraud_alert_selector, fraud_rule_selector
)
from api.fraud_detection.exceptions import ExportError
from api.fraud_detection.helpers import (
    format_currency_amount, parse_datetime_string, sanitize_string
)


logger = logging.getLogger(__name__)

User = get_user_model()


class ExportFormat(Enum):
    """Supported export formats."""
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    PDF = "pdf"
    XML = "xml"


class ExportStatus(Enum):
    """Export operation status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExportConfig:
    """Configuration for data export operations."""
    export_type: str
    format: ExportFormat
    filters: Optional[Dict[str, Any]] = None
    fields: Optional[List[str]] = None
    include_metadata: bool = True
    include_headers: bool = True
    max_records: Optional[int] = None
    chunk_size: int = 1000
    compress: bool = False
    created_by: Optional[Union[int, str]] = None
    
    def __post_init__(self):
        if self.filters is None:
            self.filters = {}
        if self.fields is None:
            self.fields = []


@dataclass
class ExportResult:
    """Result of data export operation."""
    success: bool
    export_id: str
    format: ExportFormat
    filename: str
    file_size: int
    record_count: int
    download_url: Optional[str] = None
    error_message: Optional[str] = None
    processing_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseExporter:
    """Base class for data exporters."""
    
    def __init__(self, config: ExportConfig):
        """Initialize exporter."""
        self.config = config
        self.export_id = self._generate_export_id()
        self.start_time = timezone.now()
        self.record_count = 0
    
    def export(self) -> ExportResult:
        """
        Perform data export.
        
        Returns:
            Export result
        """
        try:
            # Get data
            queryset = self._get_queryset()
            
            # Process data in chunks
            data_chunks = self._process_data_chunks(queryset)
            
            # Generate export file
            file_content = self._generate_export_file(data_chunks)
            
            # Create result
            processing_time = (timezone.now() - self.start_time).total_seconds()
            
            result = ExportResult(
                success=True,
                export_id=self.export_id,
                format=self.config.format,
                filename=self._generate_filename(),
                file_size=len(file_content),
                record_count=self.record_count,
                processing_time=processing_time,
                metadata={
                    'export_type': self.config.export_type,
                    'filters': self.config.filters,
                    'fields': self.config.fields,
                    'chunk_size': self.config.chunk_size
                }
            )
            
            # Store file for download
            self._store_export_file(file_content, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Export failed: {e}")
            processing_time = (timezone.now() - self.start_time).total_seconds()
            
            return ExportResult(
                success=False,
                export_id=self.export_id,
                format=self.config.format,
                filename="",
                file_size=0,
                record_count=0,
                error_message=str(e),
                processing_time=processing_time
            )
    
    def _get_queryset(self) -> QuerySet:
        """Get queryset for export."""
        raise NotImplementedError("Subclasses must implement _get_queryset")
    
    def _process_data_chunks(self, queryset: QuerySet) -> List[List[Dict[str, Any]]]:
        """Process data in chunks."""
        chunks = []
        
        # Apply filters
        queryset = self._apply_filters(queryset)
        
        # Apply max records limit
        if self.config.max_records:
            queryset = queryset[:self.config.max_records]
        
        # Process in chunks
        paginator = Paginator(queryset, self.config.chunk_size)
        
        for page_num in paginator.page_range:
            page = paginator.page(page_num)
            chunk = self._convert_queryset_to_dicts(page.object_list)
            chunks.append(chunk)
            self.record_count += len(chunk)
        
        return chunks
    
    def _apply_filters(self, queryset: QuerySet) -> QuerySet:
        """Apply filters to queryset."""
        filters = self.config.filters
        
        # Date range filters
        if 'date_from' in filters:
            date_from = parse_datetime_string(filters['date_from'])
            if date_from and hasattr(queryset.model, 'created_at'):
                queryset = queryset.filter(created_at__gte=date_from)
        
        if 'date_to' in filters:
            date_to = parse_datetime_string(filters['date_to'])
            if date_to and hasattr(queryset.model, 'created_at'):
                queryset = queryset.filter(created_at__lte=date_to)
        
        # Status filters
        if 'status' in filters and hasattr(queryset.model, 'status'):
            queryset = queryset.filter(status=filters['status'])
        
        # Severity filters
        if 'severity' in filters and hasattr(queryset.model, 'severity'):
            queryset = queryset.filter(severity=filters['severity'])
        
        # User filter
        if 'user_id' in filters and hasattr(queryset.model, 'user_id'):
            queryset = queryset.filter(user_id=filters['user_id'])
        
        # Risk score filters
        if 'min_risk_score' in filters and hasattr(queryset.model, 'risk_score'):
            queryset = queryset.filter(risk_score__gte=filters['min_risk_score'])
        
        if 'max_risk_score' in filters and hasattr(queryset.model, 'risk_score'):
            queryset = queryset.filter(risk_score__lte=filters['max_risk_score'])
        
        return queryset
    
    def _convert_queryset_to_dicts(self, objects: List[Any]) -> List[Dict[str, Any]]:
        """Convert queryset objects to dictionaries."""
        result = []
        
        for obj in objects:
            obj_dict = {}
            
            # Get fields to export
            fields = self.config.fields or self._get_default_fields()
            
            for field in fields:
                if hasattr(obj, field):
                    value = getattr(obj, field)
                    
                    # Format value based on type
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    elif isinstance(value, Decimal):
                        value = float(value)
                    elif isinstance(value, bool):
                        value = str(value).lower()
                    elif value is None:
                        value = ""
                    
                    obj_dict[field] = value
            
            # Add metadata if requested
            if self.config.include_metadata:
                obj_dict['_metadata'] = {
                    'model': obj.__class__.__name__,
                    'exported_at': timezone.now().isoformat()
                }
            
            result.append(obj_dict)
        
        return result
    
    def _get_default_fields(self) -> List[str]:
        """Get default fields for export."""
        return ['id', 'created_at', 'updated_at']
    
    def _generate_export_file(self, data_chunks: List[List[Dict[str, Any]]]) -> bytes:
        """Generate export file content."""
        raise NotImplementedError("Subclasses must implement _generate_export_file")
    
    def _generate_filename(self) -> str:
        """Generate filename for export."""
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        return f"fraud_{self.config.export_type}_{timestamp}.{self.config.format.value}"
    
    def _store_export_file(self, content: bytes, result: ExportResult):
        """Store export file for download."""
        try:
            # Store in cache temporarily (for small files)
            if len(content) < 50 * 1024 * 1024:  # 50MB limit
                cache_key = f"export_file_{result.export_id}"
                cache.set(cache_key, content, timeout=3600)  # 1 hour
                result.download_url = f"/api/fraud-detection/export/download/{result.export_id}/"
            else:
                # For larger files, store in file system
                file_path = self._save_to_filesystem(content, result.filename)
                result.download_url = f"/api/fraud-detection/export/download/file/{result.export_id}/"
        
        except Exception as e:
            logger.error(f"Error storing export file: {e}")
    
    def _save_to_filesystem(self, content: bytes, filename: str) -> str:
        """Save content to filesystem."""
        import os
        from django.conf import settings
        
        # Create export directory
        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
        os.makedirs(export_dir, exist_ok=True)
        
        # Save file
        file_path = os.path.join(export_dir, filename)
        with open(file_path, 'wb') as f:
            f.write(content)
        
        return file_path
    
    def _generate_export_id(self) -> str:
        """Generate unique export ID."""
        import uuid
        return str(uuid.uuid4())


class CSVExporter(BaseExporter):
    """CSV format exporter."""
    
    def _generate_export_file(self, data_chunks: List[List[Dict[str, Any]]]) -> bytes:
        """Generate CSV export file."""
        output = io.StringIO()
        
        # Get headers
        if data_chunks and data_chunks[0]:
            headers = list(data_chunks[0][0].keys())
        else:
            headers = []
        
        writer = csv.DictWriter(output, fieldnames=headers)
        
        # Write headers
        if self.config.include_headers:
            writer.writeheader()
        
        # Write data
        for chunk in data_chunks:
            for row in chunk:
                # Sanitize string values
                sanitized_row = {}
                for key, value in row.items():
                    if isinstance(value, str):
                        sanitized_row[key] = sanitize_string(value, 1000)
                    else:
                        sanitized_row[key] = value
                
                writer.writerow(sanitized_row)
        
        content = output.getvalue()
        output.close()
        
        return content.encode('utf-8')


class ExcelExporter(BaseExporter):
    """Excel format exporter."""
    
    def _generate_export_file(self, data_chunks: List[List[Dict[str, Any]]]) -> bytes:
        """Generate Excel export file."""
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill
        except ImportError:
            raise ExportError("openpyxl library is required for Excel export")
        
        # Create workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Fraud Data Export"
        
        # Get headers
        if data_chunks and data_chunks[0]:
            headers = list(data_chunks[0][0].keys())
        else:
            headers = []
        
        # Write headers
        if self.config.include_headers and headers:
            header_font = Font(bold=True)
            header_fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
            
            for col_num, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_num, value=header)
                cell.font = header_font
                cell.fill = header_fill
        
        # Write data
        row_num = 2
        for chunk in data_chunks:
            for row_data in chunk:
                for col_num, header in enumerate(headers, 1):
                    value = row_data.get(header, "")
                    
                    # Format values
                    if isinstance(value, (int, float)):
                        ws.cell(row=row_num, column=col_num, value=value)
                    elif isinstance(value, str):
                        ws.cell(row=row_num, column=col_num, value=sanitize_string(value, 32767))
                    else:
                        ws.cell(row=row_num, column=col_num, value=str(value))
                
                row_num += 1
        
        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except (TypeError, AttributeError):
                    pass
            
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # Save to bytes
        output = io.BytesIO()
        wb.save(output)
        
        return output.getvalue()


class JSONExporter(BaseExporter):
    """JSON format exporter."""
    
    def _generate_export_file(self, data_chunks: List[List[Dict[str, Any]]]) -> bytes:
        """Generate JSON export file."""
        # Flatten all chunks
        all_data = []
        for chunk in data_chunks:
            all_data.extend(chunk)
        
        # Create export structure
        export_data = {
            'export_info': {
                'export_id': self.export_id,
                'export_type': self.config.export_type,
                'format': 'json',
                'created_at': timezone.now().isoformat(),
                'record_count': self.record_count,
                'filters': self.config.filters,
                'fields': self.config.fields
            },
            'data': all_data
        }
        
        # Convert to JSON
        content = json.dumps(export_data, indent=2, default=str, ensure_ascii=False)
        
        return content.encode('utf-8')


class PDFExporter(BaseExporter):
    """PDF format exporter."""
    
    def _generate_export_file(self, data_chunks: List[List[Dict[str, Any]]]) -> bytes:
        """Generate PDF export file."""
        try:
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.pdfgen import canvas
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
            from reportlab.lib.styles import getSampleStyleSheet
        except ImportError:
            raise ExportError("reportlab library is required for PDF export")
        
        # Create PDF buffer
        output = io.BytesIO()
        
        # Create document
        doc = SimpleDocTemplate(output, pagesize=landscape(letter))
        
        # Get data
        if data_chunks and data_chunks[0]:
            headers = list(data_chunks[0][0].keys())
            all_data = []
            for chunk in data_chunks:
                all_data.extend(chunk)
        else:
            headers = []
            all_data = []
        
        # Create table data
        table_data = [headers] if self.config.include_headers else []
        
        for row_data in all_data:
            row = []
            for header in headers:
                value = row_data.get(header, "")
                if isinstance(value, (int, float)):
                    row.append(str(value))
                else:
                    row.append(sanitize_string(str(value), 50))
            table_data.append(row)
        
        # Create table
        if table_data:
            table = Table(table_data)
            
            # Style table
            style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ])
            
            table.setStyle(style)
            
            # Add alternating row colors
            for i in range(1, len(table_data)):
                if i % 2 == 0:
                    style.add(('BACKGROUND', (0, i), (-1, i), colors.lightgrey))
            
            elements = [table]
        else:
            elements = [Paragraph("No data to export", getSampleStyleSheet()['Normal'])]
        
        # Build PDF
        doc.build(elements)
        
        return output.getvalue()


class XMLExporter(BaseExporter):
    """XML format exporter."""
    
    def _generate_export_file(self, data_chunks: List[List[Dict[str, Any]]]) -> bytes:
        """Generate XML export file."""
        import xml.etree.ElementTree as ET
        
        # Create root element
        root = ET.Element("fraud_export")
        
        # Add metadata
        metadata = ET.SubElement(root, "metadata")
        ET.SubElement(metadata, "export_id").text = self.export_id
        ET.SubElement(metadata, "export_type").text = self.config.export_type
        ET.SubElement(metadata, "format").text = "xml"
        ET.SubElement(metadata, "created_at").text = timezone.now().isoformat()
        ET.SubElement(metadata, "record_count").text = str(self.record_count)
        
        # Add data
        data_element = ET.SubElement(root, "data")
        
        for chunk in data_chunks:
            for row_data in chunk:
                item_element = ET.SubElement(data_element, "item")
                
                for key, value in row_data.items():
                    # Sanitize key for XML
                    safe_key = key.replace(" ", "_").replace("-", "_")
                    
                    element = ET.SubElement(item_element, safe_key)
                    element.text = str(value) if value is not None else ""
        
        # Generate XML
        xml_str = ET.tostring(root, encoding='unicode', xml_declaration=True)
        
        return xml_str.encode('utf-8')


class FraudCaseExporter(CSVExporter):
    """Exporter for fraud cases."""
    
    def _get_queryset(self) -> QuerySet:
        """Get fraud cases queryset."""
        return FraudCase.objects.all()
    
    def _get_default_fields(self) -> List[str]:
        """Get default fields for fraud cases."""
        return [
            'id', 'user_id', 'case_type', 'severity', 'status', 'risk_score',
            'title', 'description', 'detection_method', 'created_at', 'updated_at',
            'financial_impact', 'regulatory_impact', 'assigned_to', 'resolved_at'
        ]


class FraudAlertExporter(CSVExporter):
    """Exporter for fraud alerts."""
    
    def _get_queryset(self) -> QuerySet:
        """Get fraud alerts queryset."""
        return FraudAlert.objects.all()
    
    def _get_default_fields(self) -> List[str]:
        """Get default fields for fraud alerts."""
        return [
            'id', 'user_id', 'alert_type', 'severity_score', 'title', 'description',
            'acknowledged', 'acknowledged_by', 'acknowledged_at', 'resolved', 'resolved_by',
            'resolved_at', 'created_at', 'case_id'
        ]


class FraudRuleExporter(CSVExporter):
    """Exporter for fraud rules."""
    
    def _get_queryset(self) -> QuerySet:
        """Get fraud rules queryset."""
        return FraudRule.objects.all()
    
    def _get_default_fields(self) -> List[str]:
        """Get default fields for fraud rules."""
        return [
            'id', 'name', 'description', 'rule_type', 'enabled', 'priority',
            'risk_score_impact', 'confidence_score', 'conditions', 'actions',
            'created_at', 'updated_at'
        ]


class ExportManager:
    """Manager for coordinating export operations."""
    
    exporters = {
        'cases': FraudCaseExporter,
        'alerts': FraudAlertExporter,
        'rules': FraudRuleExporter
    }
    
    format_exporters = {
        ExportFormat.CSV: CSVExporter,
        ExportFormat.EXCEL: ExcelExporter,
        ExportFormat.JSON: JSONExporter,
        ExportFormat.PDF: PDFExporter,
        ExportFormat.XML: XMLExporter
    }
    
    def __init__(self):
        """Initialize export manager."""
        self.active_exports = {}
    
    def create_export(self, export_type: str, format_type: str, 
                     filters: Optional[Dict[str, Any]] = None,
                     fields: Optional[List[str]] = None,
                     **kwargs) -> ExportResult:
        """
        Create and execute export.
        
        Args:
            export_type: Type of data to export
            format_type: Export format
            filters: Export filters
            fields: Fields to include
            **kwargs: Additional export options
            
        Returns:
            Export result
        """
        try:
            # Create export config
            config = ExportConfig(
                export_type=export_type,
                format=ExportFormat(format_type),
                filters=filters,
                fields=fields,
                **kwargs
            )
            
            # Get appropriate exporter
            exporter_class = self.exporters.get(export_type)
            if not exporter_class:
                raise ExportError(f"Unknown export type: {export_type}")
            
            # Create exporter instance
            exporter = exporter_class(config)
            
            # Execute export
            result = exporter.export()
            
            # Store active export
            if result.success:
                self.active_exports[result.export_id] = {
                    'result': result,
                    'created_at': timezone.now(),
                    'expires_at': timezone.now() + timedelta(hours=24)
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Export creation failed: {e}")
            raise ExportError(f"Export creation failed: {e}")
    
    def get_export_status(self, export_id: str) -> Optional[ExportResult]:
        """
        Get export status.
        
        Args:
            export_id: Export ID
            
        Returns:
            Export result or None
        """
        export_info = self.active_exports.get(export_id)
        if export_info:
            return export_info['result']
        return None
    
    def download_export(self, export_id: str) -> Optional[bytes]:
        """
        Download exported file.
        
        Args:
            export_id: Export ID
            
        Returns:
            File content or None
        """
        try:
            # Try to get from cache first
            cache_key = f"export_file_{export_id}"
            content = cache.get(cache_key)
            
            if content:
                return content
            
            # Try to get from filesystem
            export_info = self.active_exports.get(export_id)
            if export_info:
                result = export_info['result']
                if result.download_url and 'file/' in result.download_url:
                    # Read from filesystem
                    import os
                    from django.conf import settings
                    
                    file_path = os.path.join(settings.MEDIA_ROOT, 'exports', result.filename)
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            content = f.read()
                        return content
            
            return None
            
        except Exception as e:
            logger.error(f"Error downloading export {export_id}: {e}")
            return None
    
    def cleanup_expired_exports(self):
        """Clean up expired exports."""
        now = timezone.now()
        expired_exports = []
        
        for export_id, export_info in self.active_exports.items():
            if export_info['expires_at'] < now:
                expired_exports.append(export_id)
        
        for export_id in expired_exports:
            del self.active_exports[export_id]
            
            # Remove from cache
            cache_key = f"export_file_{export_id}"
            cache.delete(cache_key)
            
            # Remove from filesystem
            export_info = self.active_exports.get(export_id, {})
            if export_info:
                result = export_info['result']
                if result.download_url and 'file/' in result.download_url:
                    import os
                    from django.conf import settings
                    
                    file_path = os.path.join(settings.MEDIA_ROOT, 'exports', result.filename)
                    if os.path.exists(file_path):
                        os.remove(file_path)
        
        logger.info(f"Cleaned up {len(expired_exports)} expired exports")
    
    def get_export_history(self, user_id: Optional[Union[int, str]] = None) -> List[Dict[str, Any]]:
        """
        Get export history.
        
        Args:
            user_id: User ID filter (optional)
            
        Returns:
            List of export information
        """
        history = []
        
        for export_id, export_info in self.active_exports.items():
            result = export_info['result']
            
            # Filter by user if specified
            if user_id and result.metadata.get('created_by') != user_id:
                continue
            
            history.append({
                'export_id': export_id,
                'export_type': result.metadata.get('export_type'),
                'format': result.format.value,
                'filename': result.filename,
                'record_count': result.record_count,
                'file_size': result.file_size,
                'created_at': export_info['created_at'].isoformat(),
                'expires_at': export_info['expires_at'].isoformat(),
                'download_url': result.download_url,
                'success': result.success
            })
        
        # Sort by creation date (newest first)
        history.sort(key=lambda x: x['created_at'], reverse=True)
        
        return history


# Global export manager instance
export_manager = ExportManager()


# Convenience functions
def export_fraud_cases(format_type: str = 'csv', filters: Optional[Dict[str, Any]] = None,
                       fields: Optional[List[str]] = None, **kwargs) -> ExportResult:
    """Export fraud cases."""
    return export_manager.create_export('cases', format_type, filters, fields, **kwargs)


def export_fraud_alerts(format_type: str = 'csv', filters: Optional[Dict[str, Any]] = None,
                        fields: Optional[List[str]] = None, **kwargs) -> ExportResult:
    """Export fraud alerts."""
    return export_manager.create_export('alerts', format_type, filters, fields, **kwargs)


def export_fraud_rules(format_type: str = 'csv', filters: Optional[Dict[str, Any]] = None,
                       fields: Optional[List[str]] = None, **kwargs) -> ExportResult:
    """Export fraud rules."""
    return export_manager.create_export('rules', format_type, filters, fields, **kwargs)


# Export all classes and functions
__all__ = [
    # Enums and data classes
    'ExportFormat',
    'ExportStatus',
    'ExportConfig',
    'ExportResult',
    
    # Base exporter
    'BaseExporter',
    
    # Format exporters
    'CSVExporter',
    'ExcelExporter',
    'JSONExporter',
    'PDFExporter',
    'XMLExporter',
    
    # Model exporters
    'FraudCaseExporter',
    'FraudAlertExporter',
    'FraudRuleExporter',
    
    # Manager
    'ExportManager',
    'export_manager',
    
    # Convenience functions
    'export_fraud_cases',
    'export_fraud_alerts',
    'export_fraud_rules',
]
