# =============================================================================
# fraud_detection/management/commands/export_fraud_report.py
# =============================================================================
"""
Export Fraud Report Management Command.

Generate comprehensive fraud reports in various formats
including CSV, Excel, JSON, and PDF with customizable filters.
"""
from django.db import models

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Count, Avg, Sum, Q

from api.fraud_detection.models import (
    FraudAttempt, FraudAlert, FraudCase, UserRiskProfile,
    IPReputation, DeviceFingerprint, FraudWhitelist
)
from api.fraud_detection.services.FraudInsightService import FraudInsightService

import json
import csv
import logging
from datetime import timedelta
from typing import Dict, List, Any, Optional
import io
import zipfile

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Export comprehensive fraud reports in various formats'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            choices=['csv', 'excel', 'json', 'pdf', 'all'],
            default='csv',
            help='Export format (csv, excel, json, pdf, or all)'
        )
        parser.add_argument(
            '--report-type',
            type=str,
            choices=['overview', 'detailed', 'summary', 'trends', 'cases', 'alerts', 'users'],
            default='overview',
            help='Type of report to generate'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to include in report'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date (YYYY-MM-DD format)'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date (YYYY-MM-DD format)'
        )
        parser.add_argument(
            '--output-file',
            type=str,
            help='Output file path (without extension)'
        )
        parser.add_argument(
            '--filters',
            type=str,
            help='JSON string of filters to apply'
        )
        parser.add_argument(
            '--include-charts',
            action='store_true',
            help='Include charts in report (Excel/PDF only)'
        )
        parser.add_argument(
            '--split-by-user',
            action='store_true',
            help='Split report by user (for detailed reports)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output during export'
        )
    
    def handle(self, *args, **options):
        """Execute the fraud report export command."""
        self.format = options['format']
        self.report_type = options['report_type']
        self.days = options['days']
        self.start_date_str = options['start_date']
        self.end_date_str = options['end_date']
        self.output_file = options['output_file']
        self.filters_str = options['filters']
        self.include_charts = options['include_charts']
        self.split_by_user = options['split_by_user']
        self.verbose = options['verbose']
        
        # Parse dates
        self.start_date = self._parse_date(self.start_date) if self.start_date_str else timezone.now() - timedelta(days=self.days)
        self.end_date = self._parse_date(self.end_date_str) if self.end_date_str else timezone.now()
        
        # Parse filters
        self.filters = self._parse_filters(self.filters_str) if self.filters_str else {}
        
        # Initialize insight service
        self.insight_service = FraudInsightService()
        
        # Export results
        self.export_results = {
            'files_created': [],
            'records_exported': 0,
            'errors': []
        }
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Exporting fraud report: {self.report_type} '
                f'({self.format}, {self.start_date.date()} to {self.end_date.date()})'
            )
        )
        
        try:
            self._execute_export()
            
            self._print_summary()
            
        except Exception as e:
            logger.error(f"Fraud report export failed: {e}")
            raise CommandError(f"Fraud report export failed: {e}")
    
    def _parse_date(self, date_str):
        """Parse date string to datetime object."""
        try:
            from datetime import datetime
            return datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.get_current_timezone())
        except ValueError:
            raise CommandError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")
    
    def _parse_filters(self, filters_str):
        """Parse filters JSON string."""
        try:
            return json.loads(filters_str)
        except json.JSONDecodeError:
            raise CommandError(f"Invalid filters JSON: {filters_str}")
    
    def _execute_export(self):
        """Execute the export process."""
        # Generate output filename if not provided
        if not self.output_file:
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            self.output_file = f'fraud_report_{self.report_type}_{timestamp}'
        
        # Get report data
        report_data = self._get_report_data()
        
        # Export based on format
        if self.format == 'all':
            self._export_all_formats(report_data)
        else:
            self._export_format(report_data, self.format)
    
    def _get_report_data(self):
        """Get report data based on report type."""
        if self.report_type == 'overview':
            return self._get_overview_data()
        elif self.report_type == 'detailed':
            return self._get_detailed_data()
        elif self.report_type == 'summary':
            return self._get_summary_data()
        elif self.report_type == 'trends':
            return self._get_trends_data()
        elif self.report_type == 'cases':
            return self._get_cases_data()
        elif self.report_type == 'alerts':
            return self._get_alerts_data()
        elif self.report_type == 'users':
            return self._get_users_data()
        else:
            raise CommandError(f"Unknown report type: {self.report_type}")
    
    def _get_overview_data(self):
        """Get overview report data."""
        # Get overview statistics
        overview = self.insight_service.get_fraud_overview(self.days)
        
        # Add additional metrics
        additional_data = {
            'period': {
                'start_date': self.start_date.isoformat(),
                'end_date': self.end_date.isoformat(),
                'days': (self.end_date - self.start_date).days
            },
            'top_risk_factors': self.insight_service.get_top_risk_factors(self.days),
            'performance_metrics': self.insight_service.get_performance_metrics(self.days),
            'geographic_analysis': self.insight_service.get_geographic_analysis(self.days),
            'predictive_insights': self.insight_service.get_predictive_insights(self.days)
        }
        
        return {**overview, **additional_data}
    
    def _get_detailed_data(self):
        """Get detailed report data."""
        detailed_data = {
            'fraud_attempts': self._get_fraud_attempts_data(),
            'fraud_cases': self._get_fraud_cases_data(),
            'fraud_alerts': self._get_fraud_alerts_data(),
            'user_risk_profiles': self._get_user_risk_data(),
            'ip_reputations': self._get_ip_reputation_data(),
            'device_fingerprints': self._get_device_fingerprint_data(),
            'whitelist_entries': self._get_whitelist_data()
        }
        
        return detailed_data
    
    def _get_summary_data(self):
        """Get summary report data."""
        summary_data = {
            'executive_summary': self._get_executive_summary(),
            'key_metrics': self._get_key_metrics(),
            'risk_distribution': self._get_risk_distribution(),
            'trend_highlights': self._get_trend_highlights(),
            'recommendations': self._get_recommendations()
        }
        
        return summary_data
    
    def _get_trends_data(self):
        """Get trends report data."""
        trends_data = {
            'fraud_trends': self.insight_service.get_fraud_trends(self.days, 'daily'),
            'risk_score_trends': self._get_risk_score_trends(),
            'volume_trends': self._get_volume_trends(),
            'geographic_trends': self._get_geographic_trends(),
            'pattern_trends': self._get_pattern_trends()
        }
        
        return trends_data
    
    def _get_fraud_attempts_data(self):
        """Get fraud attempts data."""
        attempts = FraudAttempt.objects.filter(
            created_at__range=[self.start_date, self.end_date]
        ).select_related('user')
        
        if self.filters:
            attempts = self._apply_filters(attempts, self.filters)
        
        data = []
        for attempt in attempts:
            data.append({
                'attempt_id': attempt.attempt_id,
                'user_id': attempt.user.id,
                'username': attempt.user.username,
                'attempt_type': attempt.attempt_type,
                'description': attempt.description,
                'fraud_score': attempt.fraud_score,
                'confidence_score': attempt.confidence_score,
                'status': attempt.status,
                'amount_involved': attempt.amount_involved,
                'detected_by': attempt.detected_by,
                'created_at': attempt.created_at.isoformat(),
                'evidence_data': attempt.evidence_data
            })
        
        self.export_results['records_exported'] += len(data)
        return data
    
    def _get_fraud_cases_data(self):
        """Get fraud cases data."""
        cases = FraudCase.objects.filter(
            opened_at__range=[self.start_date, self.end_date]
        ).select_related('user', 'assigned_to', 'resolved_by')
        
        if self.filters:
            cases = self._apply_filters(cases, self.filters)
        
        data = []
        for case in cases:
            data.append({
                'case_id': case.id,
                'case_number': case.case_number,
                'user_id': case.user.id,
                'username': case.user.username,
                'title': case.title,
                'description': case.description,
                'risk_score': case.risk_score,
                'priority': case.priority,
                'status': case.status,
                'opened_at': case.opened_at.isoformat(),
                'assigned_to_id': case.assigned_to.id if case.assigned_to else None,
                'assigned_to_name': case.assigned_to.username if case.assigned_to else None,
                'resolved_at': case.resolved_at.isoformat() if case.resolved_at else None,
                'resolved_by_id': case.resolved_by.id if case.resolved_by else None,
                'resolution_notes': case.resolution_notes,
                'evidence_count': case.evidence.count(),
                'actions_count': case.actions.count()
            })
        
        self.export_results['records_exported'] += len(data)
        return data
    
    def _get_fraud_alerts_data(self):
        """Get fraud alerts data."""
        alerts = FraudAlert.objects.filter(
            created_at__range=[self.start_date, self.end_date]
        ).select_related('user')
        
        if self.filters:
            alerts = self._apply_filters(alerts, self.filters)
        
        data = []
        for alert in alerts:
            data.append({
                'alert_id': alert.id,
                'user_id': alert.user.id,
                'username': alert.user.username,
                'alert_type': alert.alert_type,
                'priority': alert.priority,
                'title': alert.title,
                'description': alert.description,
                'is_resolved': alert.is_resolved,
                'created_at': alert.created_at.isoformat(),
                'data': alert.data
            })
        
        self.export_results['records_exported'] += len(data)
        return data
    
    def _get_user_risk_data(self):
        """Get user risk profile data."""
        profiles = UserRiskProfile.objects.filter(
            last_risk_assessment__range=[self.start_date, self.end_date]
        ).select_related('user')
        
        if self.filters:
            profiles = self._apply_filters(profiles, self.filters)
        
        data = []
        for profile in profiles:
            data.append({
                'user_id': profile.user.id,
                'username': profile.user.username,
                'email': profile.user.email,
                'overall_risk_score': profile.overall_risk_score,
                'monitoring_level': profile.monitoring_level,
                'is_flagged': profile.is_flagged,
                'is_restricted': profile.is_restricted,
                'total_fraud_attempts': profile.total_fraud_attempts,
                'confirmed_fraud_attempts': profile.confirmed_fraud_attempts,
                'false_positives': profile.false_positives,
                'last_risk_assessment': profile.last_risk_assessment.isoformat(),
                'created_at': profile.created_at.isoformat(),
                'updated_at': profile.updated_at.isoformat()
            })
        
        self.export_results['records_exported'] += len(data)
        return data
    
    def _get_ip_reputation_data(self):
        """Get IP reputation data."""
        ips = IPReputation.objects.filter(
            last_seen__range=[self.start_date, self.end_date]
        )
        
        if self.filters:
            ips = self._apply_filters(ips, self.filters)
        
        data = []
        for ip_rep in ips:
            data.append({
                'ip_address': ip_rep.ip_address,
                'fraud_score': ip_rep.fraud_score,
                'spam_score': ip_rep.spam_score,
                'malware_score': ip_rep.malware_score,
                'total_requests': ip_rep.total_requests,
                'fraud_attempts': ip_rep.fraud_attempts,
                'unique_users': ip_rep.unique_users,
                'is_blacklisted': ip_rep.is_blacklisted,
                'blacklist_reason': ip_rep.blacklist_reason,
                'country': ip_rep.country,
                'region': ip_rep.region,
                'city': ip_rep.city,
                'last_seen': ip_rep.last_seen.isoformat(),
                'created_at': ip_rep.created_at.isoformat(),
                'updated_at': ip_rep.updated_at.isoformat()
            })
        
        self.export_results['records_exported'] += len(data)
        return data
    
    def _get_device_fingerprint_data(self):
        """Get device fingerprint data."""
        devices = DeviceFingerprint.objects.filter(
            last_seen__range=[self.start_date, self.end_date]
        ).select_related('user')
        
        if self.filters:
            devices = self._apply_filters(devices, self.filters)
        
        data = []
        for device in devices:
            data.append({
                'device_id': device.id,
                'device_hash': device.device_hash,
                'user_id': device.user.id if device.user else None,
                'username': device.user.username if device.user else None,
                'device_type': device.device_type,
                'trust_score': device.trust_score,
                'user_agent': device.user_agent,
                'screen_resolution': device.screen_resolution,
                'timezone': device.timezone,
                'language': device.language,
                'platform': device.platform,
                'browser': device.browser,
                'is_vpn': device.is_vpn,
                'is_proxy': device.is_proxy,
                'is_tor': device.is_tor,
                'last_seen': device.last_seen.isoformat(),
                'created_at': device.created_at.isoformat(),
                'updated_at': device.updated_at.isoformat()
            })
        
        self.export_results['records_exported'] += len(data)
        return data
    
    def _get_whitelist_data(self):
        """Get whitelist data."""
        whitelist = FraudWhitelist.objects.filter(
            created_at__range=[self.start_date, self.end_date]
        )
        
        if self.filters:
            whitelist = self._apply_filters(whitelist, self.filters)
        
        data = []
        for entry in whitelist:
            data.append({
                'entry_id': entry.id,
                'entity_type': entry.entity_type,
                'entity_value': entry.entity_value,
                'reason': entry.reason,
                'is_blacklisted': entry.is_blacklisted,
                'is_active': entry.is_active,
                'whitelisted_by_id': entry.whitelisted_by.id if entry.whitelisted_by else None,
                'whitelisted_by_name': entry.whitelisted_by.username if entry.whitelisted_by else None,
                'created_at': entry.created_at.isoformat(),
                'blacklisted_at': entry.blacklisted_at.isoformat() if entry.blacklisted_at else None,
                'expires_at': entry.expires_at.isoformat() if entry.expires_at else None,
                'deactivated_at': entry.deactivated_at.isoformat() if entry.deactivated_at else None,
                'metadata': entry.metadata
            })
        
        self.export_results['records_exported'] += len(data)
        return data
    
    def _apply_filters(self, queryset, filters):
        """Apply filters to queryset."""
        for key, value in filters.items():
            if key == 'status' and value:
                queryset = queryset.filter(status=value)
            elif key == 'priority' and value:
                queryset = queryset.filter(priority=value)
            elif key == 'risk_score_min' and value:
                queryset = queryset.filter(fraud_score__gte=value)
            elif key == 'risk_score_max' and value:
                queryset = queryset.filter(fraud_score__lte=value)
            elif key == 'user_id' and value:
                queryset = queryset.filter(user_id=value)
            elif key == 'is_flagged' and value is not None:
                queryset = queryset.filter(is_flagged=value)
            elif key == 'is_blacklisted' and value is not None:
                queryset = queryset.filter(is_blacklisted=value)
        
        return queryset
    
    def _export_all_formats(self, data):
        """Export data in all formats."""
        formats = ['csv', 'json', 'excel']
        
        if self.include_charts:
            formats.append('pdf')
        
        for format_type in formats:
            try:
                self._export_format(data, format_type)
            except Exception as e:
                error_msg = f"Error exporting {format_type}: {e}"
                logger.error(error_msg)
                self.export_results['errors'].append(error_msg)
    
    def _export_format(self, data, format_type):
        """Export data in specific format."""
        if format_type == 'csv':
            self._export_csv(data)
        elif format_type == 'json':
            self._export_json(data)
        elif format_type == 'excel':
            self._export_excel(data)
        elif format_type == 'pdf':
            self._export_pdf(data)
        else:
            raise CommandError(f"Unsupported export format: {format_type}")
    
    def _export_csv(self, data):
        """Export data to CSV."""
        output_file = f"{self.output_file}.csv"
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            if self.report_type == 'overview':
                self._write_csv_overview(csvfile, data)
            elif self.report_type == 'detailed':
                self._write_csv_detailed(csvfile, data)
            else:
                self._write_csv_generic(csvfile, data)
        
        self.export_results['files_created'].append(output_file)
        
        if self.verbose:
            self.stdout.write(f'✅ Exported CSV: {output_file}')
    
    def _write_csv_overview(self, csvfile, data):
        """Write overview data to CSV."""
        writer = csv.writer(csvfile)
        
        # Write overview metrics
        writer.writerow(['Metric', 'Value'])
        for key, value in data.items():
            if isinstance(value, (int, float, str)):
                writer.writerow([key, value])
    
    def _write_csv_detailed(self, csvfile, data):
        """Write detailed data to CSV."""
        writer = csv.writer(csvfile)
        
        # Write each data type
        for data_type, records in data.items():
            if records and isinstance(records, list):
                writer.writerow([f'=== {data_type.upper()} ==='])
                
                # Write headers
                if records:
                    headers = list(records[0].keys())
                    writer.writerow(headers)
                    
                    # Write data
                    for record in records:
                        writer.writerow([record.get(h, '') for h in headers])
                    
                    writer.writerow([])  # Empty line between sections
    
    def _write_csv_generic(self, csvfile, data):
        """Write generic data to CSV."""
        writer = csv.writer(csvfile)
        
        if isinstance(data, list) and data:
            # Write headers
            headers = list(data[0].keys())
            writer.writerow(headers)
            
            # Write data
            for record in data:
                writer.writerow([record.get(h, '') for h in headers])
        else:
            # Write key-value pairs
            writer.writerow(['Key', 'Value'])
            for key, value in data.items():
                writer.writerow([key, value])
    
    def _export_json(self, data):
        """Export data to JSON."""
        output_file = f"{self.output_file}.json"
        
        with open(output_file, 'w', encoding='utf-8') as jsonfile:
            json.dump(data, jsonfile, indent=2, default=str)
        
        self.export_results['files_created'].append(output_file)
        
        if self.verbose:
            self.stdout.write(f'✅ Exported JSON: {output_file}')
    
    def _export_excel(self, data):
        """Export data to Excel format."""
        try:
            import pandas as pd
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill
            from openpyxl.chart import BarChart, Reference
        except ImportError:
            raise CommandError("Excel export requires pandas and openpyxl: pip install pandas openpyxl")
        
        output_file = f"{self.output_file}.xlsx"
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            if self.report_type == 'overview':
                self._write_excel_overview(writer, data)
            elif self.report_type == 'detailed':
                self._write_excel_detailed(writer, data)
            else:
                self._write_excel_generic(writer, data)
        
        self.export_results['files_created'].append(output_file)
        
        if self.verbose:
            self.stdout.write(f'✅ Exported Excel: {output_file}')
    
    def _write_excel_overview(self, writer, data):
        """Write overview data to Excel."""
        # Create summary sheet
        summary_data = []
        for key, value in data.items():
            if isinstance(value, (int, float, str)):
                summary_data.append([key, value])
        
        df = pd.DataFrame(summary_data, columns=['Metric', 'Value'])
        df.to_excel(writer, sheet_name='Overview', index=False)
    
    def _write_excel_detailed(self, writer, data):
        """Write detailed data to Excel."""
        # Create sheet for each data type
        for data_type, records in data.items():
            if records and isinstance(records, list):
                df = pd.DataFrame(records)
                df.to_excel(writer, sheet_name=data_type[:31], index=False)  # Sheet name max 31 chars
    
    def _write_excel_generic(self, writer, data):
        """Write generic data to Excel."""
        if isinstance(data, list) and data:
            df = pd.DataFrame(data)
            df.to_excel(writer, sheet_name='Data', index=False)
        else:
            # Convert to list of dicts
            records = [{'key': k, 'value': v} for k, v in data.items()]
            df = pd.DataFrame(records)
            df.to_excel(writer, sheet_name='Data', index=False)
    
    def _export_pdf(self, data):
        """Export data to PDF format."""
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
        except ImportError:
            raise CommandError("PDF export requires reportlab: pip install reportlab")
        
        output_file = f"{self.output_file}.pdf"
        
        doc = SimpleDocTemplate(output_file, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Add title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30
        )
        story.append(Paragraph(f"Fraud Detection Report - {self.report_type.title()}", title_style))
        story.append(Spacer(1, 12))
        
        # Add period info
        story.append(Paragraph(f"Period: {self.start_date.date()} to {self.end_date.date()}", styles['Normal']))
        story.append(Spacer(1, 12))
        
        # Add data
        if self.report_type == 'overview':
            self._write_pdf_overview(story, data, styles)
        else:
            self._write_pdf_generic(story, data, styles)
        
        doc.build(story)
        
        self.export_results['files_created'].append(output_file)
        
        if self.verbose:
            self.stdout.write(f'✅ Exported PDF: {output_file}')
    
    def _write_pdf_overview(self, story, data, styles):
        """Write overview data to PDF."""
        for key, value in data.items():
            if isinstance(value, (int, float, str)):
                story.append(Paragraph(f"{key}: {value}", styles['Normal']))
                story.append(Spacer(1, 6))
    
    def _write_pdf_generic(self, story, data, styles):
        """Write generic data to PDF."""
        if isinstance(data, list) and data:
            # Create table
            headers = list(data[0].keys())
            table_data = [headers]
            
            for record in data[:20]:  # Limit to 20 records for PDF
                table_data.append([str(record.get(h, '')) for h in headers])
            
            table = Table(table_data)
            story.append(table)
            story.append(Spacer(1, 12))
        else:
            # Write key-value pairs
            for key, value in data.items():
                story.append(Paragraph(f"{key}: {value}", styles['Normal']))
                story.append(Spacer(1, 6))
    
    def _get_executive_summary(self):
        """Get executive summary data."""
        overview = self.insight_service.get_fraud_overview(self.days)
        
        return {
            'total_fraud_attempts': overview.get('total_attempts', 0),
            'confirmed_fraud_rate': overview.get('detection_rate', 0),
            'high_risk_users': overview.get('high_risk_users', 0),
            'active_cases': overview.get('open_cases', 0),
            'key_findings': [
                f"Detection rate: {overview.get('detection_rate', 0):.1f}%",
                f"Average resolution time: {overview.get('avg_resolution_time_hours', 0):.1f} hours",
                f"False positive rate: {overview.get('false_positive_rate', 0):.1f}%"
            ]
        }
    
    def _get_key_metrics(self):
        """Get key metrics for summary."""
        return {
            'fraud_detection_rate': self._calculate_detection_rate(),
            'case_resolution_rate': self._calculate_resolution_rate(),
            'alert_response_time': self._calculate_alert_response_time(),
            'user_risk_distribution': self._get_risk_distribution()
        }
    
    def _get_risk_distribution(self):
        """Get risk distribution data."""
        profiles = UserRiskProfile.objects.filter(
            last_risk_assessment__gte=self.start_date
        )
        
        distribution = {
            'low': profiles.filter(overall_risk_score__lt=40).count(),
            'medium': profiles.filter(overall_risk_score__gte=40, overall_risk_score__lt=60).count(),
            'high': profiles.filter(overall_risk_score__gte=60, overall_risk_score__lt=80).count(),
            'critical': profiles.filter(overall_risk_score__gte=80).count()
        }
        
        return distribution
    
    def _get_trend_highlights(self):
        """Get trend highlights."""
        trends = self.insight_service.get_fraud_trends(self.days, 'daily')
        
        if trends and trends.get('data'):
            data = trends['data']
            if len(data) >= 2:
                first_week = data[:7]
                last_week = data[-7:]
                
                first_week_avg = sum(d.get('attempts', 0) for d in first_week) / len(first_week)
                last_week_avg = sum(d.get('attempts', 0) for d in last_week) / len(last_week)
                
                return {
                    'trend_direction': 'increasing' if last_week_avg > first_week_avg else 'decreasing',
                    'change_percentage': ((last_week_avg - first_week_avg) / first_week_avg * 100) if first_week_avg > 0 else 0,
                    'peak_day': max(data, key=lambda x: x.get('attempts', 0)).get('period', 'Unknown')
                }
        
        return {}
    
    def _get_recommendations(self):
        """Get recommendations based on data."""
        recommendations = []
        
        overview = self.insight_service.get_fraud_overview(self.days)
        
        if overview.get('false_positive_rate', 0) > 20:
            recommendations.append("Review and adjust detection thresholds to reduce false positives")
        
        if overview.get('avg_resolution_time_hours', 0) > 48:
            recommendations.append("Implement automated case assignment to reduce resolution time")
        
        if overview.get('open_cases', 0) > 50:
            recommendations.append("Increase staff resources for case management")
        
        return recommendations
    
    def _calculate_detection_rate(self):
        """Calculate fraud detection rate."""
        total_attempts = FraudAttempt.objects.filter(
            created_at__range=[self.start_date, self.end_date]
        ).count()
        
        confirmed = FraudAttempt.objects.filter(
            created_at__range=[self.start_date, self.end_date],
            status='confirmed'
        ).count()
        
        return (confirmed / total_attempts * 100) if total_attempts > 0 else 0
    
    def _calculate_resolution_rate(self):
        """Calculate case resolution rate."""
        total_cases = FraudCase.objects.filter(
            opened_at__range=[self.start_date, self.end_date]
        ).count()
        
        resolved = FraudCase.objects.filter(
            opened_at__range=[self.start_date, self.end_date],
            status__in=['resolved', 'closed']
        ).count()
        
        return (resolved / total_cases * 100) if total_cases > 0 else 0
    
    def _calculate_alert_response_time(self):
        """Calculate average alert response time."""
        alerts = FraudAlert.objects.filter(
            created_at__range=[self.start_date, self.end_date],
            is_resolved=True
        )
        
        if alerts.exists():
            response_times = []
            for alert in alerts:
                # This would need a resolved_at field in the model
                # For now, return placeholder
                pass
        
        return 0  # Placeholder
    
    def _get_risk_score_trends(self):
        """Get risk score trends over time."""
        profiles = UserRiskProfile.objects.filter(
            last_risk_assessment__range=[self.start_date, self.end_date]
        )
        
        trends = []
        current_date = self.start_date
        
        while current_date <= self.end_date:
            day_profiles = profiles.filter(
                last_risk_assessment__date=current_date.date()
            )
            
            if day_profiles.exists():
                avg_score = day_profiles.aggregate(avg_score=models.Avg('overall_risk_score'))['avg_score'] or 0
                trends.append({
                    'date': current_date.date().isoformat(),
                    'avg_risk_score': avg_score,
                    'user_count': day_profiles.count()
                })
            
            current_date += timedelta(days=1)
        
        return trends
    
    def _get_volume_trends(self):
        """Get volume trends for fraud attempts."""
        attempts = FraudAttempt.objects.filter(
            created_at__range=[self.start_date, self.end_date]
        )
        
        trends = []
        current_date = self.start_date
        
        while current_date <= self.end_date:
            day_attempts = attempts.filter(created_at__date=current_date.date())
            
            trends.append({
                'date': current_date.date().isoformat(),
                'attempt_count': day_attempts.count(),
                'confirmed_count': day_attempts.filter(status='confirmed').count(),
                'amount_total': day_attempts.aggregate(total=Sum('amount_involved'))['total'] or 0
            })
            
            current_date += timedelta(days=1)
        
        return trends
    
    def _get_geographic_trends(self):
        """Get geographic trends."""
        attempts = FraudAttempt.objects.filter(
            created_at__range=[self.start_date, self.end_date]
        )
        
        # This would need proper IP geolocation data
        # For now, return placeholder
        return {
            'top_countries': [],
            'emerging_regions': [],
            'anomaly_locations': []
        }
    
    def _get_pattern_trends(self):
        """Get pattern detection trends."""
        # This would need pattern analyzer integration
        # For now, return placeholder
        return {
            'emerging_patterns': [],
            'declining_patterns': [],
            'pattern_effectiveness': {}
        }
    
    def _print_summary(self):
        """Print export summary."""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('FRAUD REPORT EXPORT SUMMARY'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'Report Type: {self.report_type}')
        self.stdout.write(f'Format: {self.format}')
        self.stdout.write(f'Period: {self.start_date.date()} to {self.end_date.date()}')
        self.stdout.write(f'Records Exported: {self.export_results["records_exported"]}')
        self.stdout.write(f'Files Created: {len(self.export_results["files_created"])}')
        
        if self.export_results['files_created']:
            self.stdout.write('\nFiles Created:')
            for file_path in self.export_results['files_created']:
                self.stdout.write(f'  📄 {file_path}')
        
        if self.export_results['errors']:
            self.stdout.write(f'\nErrors: {len(self.export_results["errors"])}')
            for error in self.export_results['errors']:
                self.stdout.write(f'  ❌ {error}')
        
        self.stdout.write('=' * 60)
