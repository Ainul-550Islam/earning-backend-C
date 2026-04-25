"""
Report Export Service

Service for exporting reports in various formats,
including CSV, PDF, and Excel exports.
"""

import logging
import csv
import io
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.conf import settings

from ...models.reporting import AdvertiserReport, CampaignReport
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class ReportExportService:
    """
    Service for exporting reports in various formats.
    
    Handles CSV, PDF, and Excel exports,
    with customizable formatting and data selection.
    """
    
    def __init__(self):
        self.logger = logger
    
    def export_report_to_csv(self, advertiser, report_id: int, export_config: Dict[str, Any] = None) -> HttpResponse:
        """
        Export report to CSV format.
        
        Args:
            advertiser: Advertiser instance
            report_id: Report ID to export
            export_config: Export configuration
            
        Returns:
            HttpResponse: CSV file response
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Get report
            try:
                report = AdvertiserReport.objects.get(id=report_id, advertiser=advertiser)
            except AdvertiserReport.DoesNotExist:
                raise ValidationError("Report not found")
            
            # Prepare CSV data
            csv_data = self._prepare_csv_data(report, export_config)
            
            # Create CSV response
            response = HttpResponse(content_type='text/csv')
            filename = f"report_{report.report_type}_{report.period}_{timezone.now().strftime('%Y%m%d')}.csv"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            # Write CSV data
            writer = csv.writer(response)
            
            # Write headers
            if csv_data.get('headers'):
                writer.writerow(csv_data['headers'])
            
            # Write data rows
            for row in csv_data.get('rows', []):
                writer.writerow(row)
            
            # Log export
            self._log_export(advertiser, report, 'csv', export_config)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error exporting report to CSV: {e}")
            raise ValidationError(f"Failed to export report to CSV: {str(e)}")
    
    def export_report_to_pdf(self, advertiser, report_id: int, export_config: Dict[str, Any] = None) -> HttpResponse:
        """
        Export report to PDF format.
        
        Args:
            advertiser: Advertiser instance
            report_id: Report ID to export
            export_config: Export configuration
            
        Returns:
            HttpResponse: PDF file response
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Get report
            try:
                report = AdvertiserReport.objects.get(id=report_id, advertiser=advertiser)
            except AdvertiserReport.DoesNotExist:
                raise ValidationError("Report not found")
            
            # Generate PDF content
            pdf_content = self._generate_pdf_content(report, export_config)
            
            # Create PDF response
            response = HttpResponse(content_type='application/pdf')
            filename = f"report_{report.report_type}_{report.period}_{timezone.now().strftime('%Y%m%d')}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response.write(pdf_content)
            
            # Log export
            self._log_export(advertiser, report, 'pdf', export_config)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error exporting report to PDF: {e}")
            raise ValidationError(f"Failed to export report to PDF: {str(e)}")
    
    def export_report_to_excel(self, advertiser, report_id: int, export_config: Dict[str, Any] = None) -> HttpResponse:
        """
        Export report to Excel format.
        
        Args:
            advertiser: Advertiser instance
            report_id: Report ID to export
            export_config: Export configuration
            
        Returns:
            HttpResponse: Excel file response
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Get report
            try:
                report = AdvertiserReport.objects.get(id=report_id, advertiser=advertiser)
            except AdvertiserReport.DoesNotExist:
                raise ValidationError("Report not found")
            
            # Generate Excel content
            excel_content = self._generate_excel_content(report, export_config)
            
            # Create Excel response
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            filename = f"report_{report.report_type}_{report.period}_{timezone.now().strftime('%Y%m%d')}.xlsx"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response.write(excel_content)
            
            # Log export
            self._log_export(advertiser, report, 'excel', export_config)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error exporting report to Excel: {e}")
            raise ValidationError(f"Failed to export report to Excel: {str(e)}")
    
    def export_multiple_reports(self, advertiser, report_ids: List[int], format: str, export_config: Dict[str, Any] = None) -> HttpResponse:
        """
        Export multiple reports in specified format.
        
        Args:
            advertiser: Advertiser instance
            report_ids: List of report IDs to export
            format: Export format ('csv', 'pdf', 'excel')
            export_config: Export configuration
            
        Returns:
            HttpResponse: Export file response
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate format
            valid_formats = ['csv', 'pdf', 'excel']
            if format not in valid_formats:
                raise ValidationError(f"Invalid format: {format}")
            
            # Get reports
            reports = AdvertiserReport.objects.filter(id__in=report_ids, advertiser=advertiser)
            
            if len(reports) != len(report_ids):
                raise ValidationError("Some reports not found")
            
            # Export based on format
            if format == 'csv':
                return self._export_multiple_csv(advertiser, reports, export_config)
            elif format == 'pdf':
                return self._export_multiple_pdf(advertiser, reports, export_config)
            else:  # excel
                return self._export_multiple_excel(advertiser, reports, export_config)
            
        except Exception as e:
            self.logger.error(f"Error exporting multiple reports: {e}")
            raise ValidationError(f"Failed to export multiple reports: {str(e)}")
    
    def get_export_history(self, advertiser, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get export history for advertiser.
        
        Args:
            advertiser: Advertiser instance
            limit: Maximum number of records
            
        Returns:
            List[Dict[str, Any]]: Export history
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # This would retrieve from an export history model
            # For now, return empty list
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting export history: {e}")
            raise ValidationError(f"Failed to get export history: {str(e)}")
    
    def schedule_export(self, advertiser, export_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Schedule recurring export.
        
        Args:
            advertiser: Advertiser instance
            export_config: Export configuration
            
        Returns:
            Dict[str, Any]: Scheduled export result
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Validate export configuration
                self._validate_export_config(export_config)
                
                # Store scheduled export in metadata
                metadata = advertiser.profile.metadata or {}
                
                if 'scheduled_exports' not in metadata:
                    metadata['scheduled_exports'] = []
                
                scheduled_export = {
                    'id': f"export_{timezone.now().timestamp()}",
                    'name': export_config.get('name', 'Unnamed Export'),
                    'report_type': export_config.get('report_type'),
                    'format': export_config.get('format', 'csv'),
                    'frequency': export_config.get('frequency', 'daily'),
                    'recipients': export_config.get('recipients', []),
                    'filters': export_config.get('filters', {}),
                    'created_at': timezone.now().isoformat(),
                    'is_active': True,
                    'next_run': self._calculate_next_export_run(export_config.get('frequency')),
                    'last_run': None,
                }
                
                metadata['scheduled_exports'].append(scheduled_export)
                advertiser.profile.metadata = metadata
                advertiser.profile.save()
                
                # Send notification
                self._send_export_scheduled_notification(advertiser, scheduled_export)
                
                self.logger.info(f"Scheduled export: {scheduled_export['name']} for {advertiser.company_name}")
                
                return scheduled_export
                
        except Exception as e:
            self.logger.error(f"Error scheduling export: {e}")
            raise ValidationError(f"Failed to schedule export: {str(e)}")
    
    def _prepare_csv_data(self, report: AdvertiserReport, export_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Prepare CSV data from report."""
        config = export_config or {}
        
        # Extract data from report
        report_data = report.data or {}
        
        # Prepare headers based on report type
        if report.report_type == 'performance':
            headers = ['Date', 'Campaign', 'Impressions', 'Clicks', 'Conversions', 'Spend', 'CTR', 'CPA']
            rows = self._prepare_performance_csv_rows(report_data, config)
        elif report.report_type == 'financial':
            headers = ['Date', 'Type', 'Amount', 'Description', 'Balance']
            rows = self._prepare_financial_csv_rows(report_data, config)
        else:
            headers = ['Metric', 'Value']
            rows = self._prepare_generic_csv_rows(report_data, config)
        
        return {
            'headers': headers,
            'rows': rows,
        }
    
    def _prepare_performance_csv_rows(self, data: Dict[str, Any], config: Dict[str, Any]) -> List[List]:
        """Prepare performance report CSV rows."""
        rows = []
        
        # Add summary row
        summary = data.get('summary', {})
        rows.append([
            'Summary',
            'All Campaigns',
            summary.get('total_impressions', 0),
            summary.get('total_clicks', 0),
            summary.get('total_conversions', 0),
            f"{summary.get('total_spend', 0):.2f}",
            f"{summary.get('ctr', 0):.2f}%",
            f"{summary.get('cpa', 0):.2f}"
        ])
        
        # Add daily breakdown
        daily_data = data.get('daily_breakdown', {})
        for date, day_data in daily_data.items():
            rows.append([
                date,
                'Daily Total',
                day_data.get('impressions', 0),
                day_data.get('clicks', 0),
                day_data.get('conversions', 0),
                f"{day_data.get('spend', 0):.2f}",
                "",  # CTR calculated
                "",  # CPA calculated
            ])
        
        return rows
    
    def _prepare_financial_csv_rows(self, data: Dict[str, Any], config: Dict[str, Any]) -> List[List]:
        """Prepare financial report CSV rows."""
        rows = []
        
        # Add summary
        summary = data.get('summary', {})
        rows.append([
            'Period Summary',
            'Summary',
            f"{summary.get('net_flow', 0):.2f}",
            'Net flow for period',
            f"{summary.get('current_balance', 0):.2f}"
        ])
        
        # Add daily breakdown
        daily_data = data.get('daily_breakdown', {})
        for date, day_data in daily_data.items():
            rows.append([
                date,
                'Daily',
                f"{day_data.get('net_flow', 0):.2f}",
                'Daily net flow',
                ""
            ])
        
        return rows
    
    def _prepare_generic_csv_rows(self, data: Dict[str, Any], config: Dict[str, Any]) -> List[List]:
        """Prepare generic CSV rows."""
        rows = []
        
        def flatten_dict(d, parent_key='', sep='_'):
            items = []
            for k, v in d.items():
                if isinstance(v, dict):
                    items.extend(flatten_dict(v, f"{parent_key}{k}{sep}").items())
                else:
                    items.append((f"{parent_key}{k}", v))
            return dict(items)
        
        flat_data = flatten_dict(data)
        
        for key, value in flat_data.items():
            rows.append([key, str(value)])
        
        return rows
    
    def _generate_pdf_content(self, report: AdvertiserReport, export_config: Dict[str, Any] = None) -> bytes:
        """Generate PDF content from report."""
        try:
            # This would implement PDF generation using a library like ReportLab
            # For now, return placeholder content
            
            template_context = {
                'report': report,
                'data': report.data or {},
                'generated_at': timezone.now(),
                'advertiser': report.advertiser,
                'config': export_config or {},
            }
            
            # Render HTML template
            html_content = render_to_string('advertiser_portal/reports/pdf_template.html', template_context)
            
            # Convert HTML to PDF (placeholder)
            pdf_content = f"PDF content for report {report.id}".encode('utf-8')
            
            return pdf_content
            
        except Exception as e:
            self.logger.error(f"Error generating PDF content: {e}")
            raise ValidationError(f"Failed to generate PDF content: {str(e)}")
    
    def _generate_excel_content(self, report: AdvertiserReport, export_config: Dict[str, Any] = None) -> bytes:
        """Generate Excel content from report."""
        try:
            # This would implement Excel generation using a library like openpyxl
            # For now, return placeholder content
            
            excel_content = f"Excel content for report {report.id}".encode('utf-8')
            
            return excel_content
            
        except Exception as e:
            self.logger.error(f"Error generating Excel content: {e}")
            raise ValidationError(f"Failed to generate Excel content: {str(e)}")
    
    def _export_multiple_csv(self, advertiser, reports, export_config: Dict[str, Any]) -> HttpResponse:
        """Export multiple reports to CSV."""
        response = HttpResponse(content_type='text/csv')
        filename = f"multiple_reports_{timezone.now().strftime('%Y%m%d')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        
        # Write header for combined export
        writer.writerow(['Report Type', 'Period', 'Date', 'Metric', 'Value'])
        
        for report in reports:
            csv_data = self._prepare_csv_data(report, export_config)
            
            # Add report header
            writer.writerow([report.report_type, report.period, '', '', ''])
            
            # Add data rows
            for row in csv_data.get('rows', []):
                # Convert row to match combined format
                if len(row) >= 2:
                    writer.writerow([report.report_type, report.period, '', row[0], row[1]])
            
            # Add separator
            writer.writerow(['', '', '', '', ''])
        
        return response
    
    def _export_multiple_pdf(self, advertiser, reports, export_config: Dict[str, Any]) -> HttpResponse:
        """Export multiple reports to PDF."""
        # This would combine multiple PDFs into one
        pdf_content = f"Combined PDF for {len(reports)} reports".encode('utf-8')
        
        response = HttpResponse(content_type='application/pdf')
        filename = f"multiple_reports_{timezone.now().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write(pdf_content)
        
        return response
    
    def _export_multiple_excel(self, advertiser, reports, export_config: Dict[str, Any]) -> HttpResponse:
        """Export multiple reports to Excel."""
        # This would create multiple sheets in Excel
        excel_content = f"Combined Excel for {len(reports)} reports".encode('utf-8')
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        filename = f"multiple_reports_{timezone.now().strftime('%Y%m%d')}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write(excel_content)
        
        return response
    
    def _validate_export_config(self, config: Dict[str, Any]):
        """Validate export configuration."""
        required_fields = ['name', 'report_type', 'format', 'frequency', 'recipients']
        
        for field in required_fields:
            if field not in config:
                raise ValidationError(f"Missing required field: {field}")
        
        valid_formats = ['csv', 'pdf', 'excel']
        if config['format'] not in valid_formats:
            raise ValidationError(f"Invalid format: {config['format']}")
        
        valid_frequencies = ['daily', 'weekly', 'monthly']
        if config['frequency'] not in valid_frequencies:
            raise ValidationError(f"Invalid frequency: {config['frequency']}")
    
    def _calculate_next_export_run(self, frequency: str) -> str:
        """Calculate next export run time."""
        now = timezone.now()
        
        if frequency == 'daily':
            next_run = now + timezone.timedelta(days=1)
            next_run = next_run.replace(hour=8, minute=0, second=0, microsecond=0)
        elif frequency == 'weekly':
            next_run = now + timezone.timedelta(weeks=1)
            next_run = next_run.replace(hour=8, minute=0, second=0, microsecond=0)
        elif frequency == 'monthly':
            next_run = now + timezone.timedelta(days=30)
            next_run = next_run.replace(hour=8, minute=0, second=0, microsecond=0)
        else:
            next_run = now + timezone.timedelta(days=1)
        
        return next_run.isoformat()
    
    def _log_export(self, advertiser, report, format: str, config: Dict[str, Any]):
        """Log export for analytics."""
        # This would implement export logging
        metadata = report.metadata or {}
        
        if 'exports' not in metadata:
            metadata['exports'] = []
        
        export_log = {
            'format': format,
            'exported_at': timezone.now().isoformat(),
            'config': config,
            'exported_by': advertiser.id,
        }
        
        metadata['exports'].append(export_log)
        report.metadata = metadata
        report.save()
    
    def _send_export_scheduled_notification(self, advertiser, scheduled_export: Dict[str, Any]):
        """Send export scheduled notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='report_created',
            title=_('Export Scheduled'),
            message=_(
                'Your export "{name}" has been scheduled to run {frequency} in {format} format.'
            ).format(
                name=scheduled_export['name'],
                frequency=scheduled_export['frequency'],
                format=scheduled_export['format']
            ),
            priority='low',
            action_url='/advertiser/reports/exports/',
            action_text=_('Manage Exports')
        )
