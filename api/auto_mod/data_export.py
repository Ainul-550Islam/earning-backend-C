# =============================================================================
# auto_mod/data_export.py
# =============================================================================

"""
Data export system for auto moderation.
Provides comprehensive data export capabilities in multiple formats.
"""

import logging
import csv
import io
import json
import zipfile
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill

from .models import (
    SuspiciousSubmission, ModerationDecision, ModerationAppeal,
    ModerationQueue, TaskBot, AutoApprovalRule, MLModelVersion
)
from .analytics import analytics_engine
from .exceptions import ModerationError

logger = logging.getLogger(__name__)


class ExportFormat:
    """Export format types."""
    JSON = "json"
    CSV = "csv"
    EXCEL = "xlsx"
    PDF = "pdf"


class ExportScope:
    """Export scope types."""
    SUBMISSIONS = "submissions"
    DECISIONS = "decisions"
    APPEALS = "appeals"
    QUEUE = "queue"
    BOTS = "bots"
    RULES = "rules"
    ANALYTICS = "analytics"
    FULL_SYSTEM = "full_system"


class DataExporter:
    """
    Data exporter for auto moderation system.
    """
    
    def __init__(self):
        self.max_records_per_export = 10000
        self.supported_formats = [ExportFormat.JSON, ExportFormat.CSV, ExportFormat.EXCEL]
    
    def export_data(self, scope: str, format_type: str, filters: Dict[str, Any] = None,
                   start_date: datetime = None, end_date: datetime = None,
                   limit: int = None) -> Union[HttpResponse, bytes]:
        """
        Export data in specified format.
        
        Args:
            scope: Export scope
            format_type: Export format
            filters: Additional filters
            start_date: Start date filter
            end_date: End date filter
            limit: Record limit
            
        Returns:
            Exported data
        """
        try:
            if format_type not in self.supported_formats:
                raise ValueError(f"Unsupported format: {format_type}")
            
            # Get data based on scope
            data = self._get_data_by_scope(scope, filters, start_date, end_date, limit)
            
            # Export in specified format
            if format_type == ExportFormat.JSON:
                return self._export_json(data, scope)
            elif format_type == ExportFormat.CSV:
                return self._export_csv(data, scope)
            elif format_type == ExportFormat.EXCEL:
                return self._export_excel(data, scope)
            else:
                raise ValueError(f"Unsupported format: {format_type}")
                
        except Exception as exc:
            logger.error(f"Export data failed: {exc}")
            raise ModerationError(f"Failed to export data: {exc}")
    
    def _get_data_by_scope(self, scope: str, filters: Dict[str, Any] = None,
                          start_date: datetime = None, end_date: datetime = None,
                          limit: int = None) -> List[Dict[str, Any]]:
        """Get data based on export scope."""
        filters = filters or {}
        
        if limit is None:
            limit = self.max_records_per_export
        
        if scope == ExportScope.SUBMISSIONS:
            return self._get_submissions_data(filters, start_date, end_date, limit)
        elif scope == ExportScope.DECISIONS:
            return self._get_decisions_data(filters, start_date, end_date, limit)
        elif scope == ExportScope.APPEALS:
            return self._get_appeals_data(filters, start_date, end_date, limit)
        elif scope == ExportScope.QUEUE:
            return self._get_queue_data(filters, limit)
        elif scope == ExportScope.BOTS:
            return self._get_bots_data(filters, limit)
        elif scope == ExportScope.RULES:
            return self._get_rules_data(filters, limit)
        elif scope == ExportScope.ANALYTICS:
            return self._get_analytics_data(filters, start_date, end_date)
        elif scope == ExportScope.FULL_SYSTEM:
            return self._get_full_system_data(filters, start_date, end_date, limit)
        else:
            raise ValueError(f"Unsupported scope: {scope}")
    
    def _get_submissions_data(self, filters: Dict[str, Any], start_date: datetime,
                            end_date: datetime, limit: int) -> List[Dict[str, Any]]:
        """Get submissions data."""
        queryset = SuspiciousSubmission.objects.all()
        
        # Apply date filters
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Apply additional filters
        if 'status' in filters:
            queryset = queryset.filter(status=filters['status'])
        if 'submission_type' in filters:
            queryset = queryset.filter(submission_type=filters['submission_type'])
        if 'user_id' in filters:
            queryset = queryset.filter(user_id=filters['user_id'])
        
        # Limit results
        queryset = queryset[:limit]
        
        # Convert to dictionaries
        data = []
        for submission in queryset:
            data.append({
                'id': str(submission.id),
                'user_id': str(submission.user_id),
                'status': submission.status,
                'submission_type': submission.submission_type,
                'risk_score': submission.risk_score,
                'ai_confidence': submission.ai_confidence,
                'flag_reason': submission.flag_reason,
                'created_at': submission.created_at.isoformat(),
                'updated_at': submission.updated_at.isoformat(),
                'metadata': submission.metadata or {},
            })
        
        return data
    
    def _get_decisions_data(self, filters: Dict[str, Any], start_date: datetime,
                           end_date: datetime, limit: int) -> List[Dict[str, Any]]:
        """Get decisions data."""
        queryset = ModerationDecision.objects.all()
        
        # Apply date filters
        if start_date:
            queryset = queryset.filter(decided_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(decided_at__lte=end_date)
        
        # Apply additional filters
        if 'decision_type' in filters:
            queryset = queryset.filter(decision_type=filters['decision_type'])
        if 'is_automated' in filters:
            queryset = queryset.filter(is_automated=filters['is_automated'])
        if 'decider_id' in filters:
            queryset = queryset.filter(decider_id=filters['decider_id'])
        
        # Limit results
        queryset = queryset[:limit]
        
        # Convert to dictionaries
        data = []
        for decision in queryset:
            data.append({
                'id': str(decision.id),
                'submission_id': str(decision.submission_id),
                'decider_id': str(decision.decider_id) if decision.decider_id else None,
                'decision_type': decision.decision_type,
                'confidence': decision.confidence,
                'is_automated': decision.is_automated,
                'reason': decision.reason,
                'processing_time': decision.processing_time,
                'decided_at': decision.decided_at.isoformat(),
                'metadata': decision.metadata or {},
            })
        
        return data
    
    def _get_appeals_data(self, filters: Dict[str, Any], start_date: datetime,
                         end_date: datetime, limit: int) -> List[Dict[str, Any]]:
        """Get appeals data."""
        queryset = ModerationAppeal.objects.all()
        
        # Apply date filters
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Apply additional filters
        if 'status' in filters:
            queryset = queryset.filter(status=filters['status'])
        if 'appeal_type' in filters:
            queryset = queryset.filter(appeal_type=filters['appeal_type'])
        if 'user_id' in filters:
            queryset = queryset.filter(user_id=filters['user_id'])
        
        # Limit results
        queryset = queryset[:limit]
        
        # Convert to dictionaries
        data = []
        for appeal in queryset:
            data.append({
                'id': str(appeal.id),
                'original_decision_id': str(appeal.original_decision_id),
                'user_id': str(appeal.user_id),
                'reviewer_id': str(appeal.reviewer_id) if appeal.reviewer_id else None,
                'appeal_type': appeal.appeal_type,
                'status': appeal.status,
                'reason': appeal.reason,
                'evidence': appeal.evidence or {},
                'created_at': appeal.created_at.isoformat(),
                'reviewed_at': appeal.reviewed_at.isoformat() if appeal.reviewed_at else None,
                'review_reason': appeal.review_reason,
            })
        
        return data
    
    def _get_queue_data(self, filters: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """Get queue data."""
        queryset = ModerationQueue.objects.all()
        
        # Apply additional filters
        if 'status' in filters:
            queryset = queryset.filter(status=filters['status'])
        if 'priority' in filters:
            queryset = queryset.filter(priority=filters['priority'])
        if 'assigned_to' in filters:
            queryset = queryset.filter(assigned_to_id=filters['assigned_to'])
        
        # Limit results
        queryset = queryset[:limit]
        
        # Convert to dictionaries
        data = []
        for queue_item in queryset:
            data.append({
                'id': str(queue_item.id),
                'submission_id': str(queue_item.submission_id),
                'decision_id': str(queue_item.decision_id) if queue_item.decision_id else None,
                'assigned_to_id': str(queue_item.assigned_to_id) if queue_item.assigned_to_id else None,
                'assigned_by_id': str(queue_item.assigned_by_id) if queue_item.assigned_by_id else None,
                'status': queue_item.status,
                'priority': queue_item.priority,
                'escalation_level': queue_item.escalation_level,
                'due_date': queue_item.due_date.isoformat() if queue_item.due_date else None,
                'created_at': queue_item.created_at.isoformat(),
                'updated_at': queue_item.updated_at.isoformat(),
            })
        
        return data
    
    def _get_bots_data(self, filters: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """Get bots data."""
        queryset = TaskBot.objects.all()
        
        # Apply additional filters
        if 'status' in filters:
            queryset = queryset.filter(status=filters['status'])
        if 'bot_type' in filters:
            queryset = queryset.filter(bot_type=filters['bot_type'])
        if 'is_active' in filters:
            queryset = queryset.filter(is_active=filters['is_active'])
        
        # Limit results
        queryset = queryset[:limit]
        
        # Convert to dictionaries
        data = []
        for bot in queryset:
            data.append({
                'id': str(bot.id),
                'name': bot.name,
                'bot_type': bot.bot_type,
                'status': bot.status,
                'is_active': bot.is_active,
                'performance_score': bot.performance_score,
                'configuration': bot.configuration or {},
                'created_at': bot.created_at.isoformat(),
                'updated_at': bot.updated_at.isoformat(),
            })
        
        return data
    
    def _get_rules_data(self, filters: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """Get rules data."""
        queryset = AutoApprovalRule.objects.all()
        
        # Apply additional filters
        if 'rule_type' in filters:
            queryset = queryset.filter(rule_type=filters['rule_type'])
        if 'is_active' in filters:
            queryset = queryset.filter(is_active=filters['is_active'])
        if 'submission_type' in filters:
            queryset = queryset.filter(submission_type=filters['submission_type'])
        
        # Limit results
        queryset = queryset[:limit]
        
        # Convert to dictionaries
        data = []
        for rule in queryset:
            data.append({
                'id': str(rule.id),
                'name': rule.name,
                'rule_type': rule.rule_type,
                'conditions': rule.conditions or {},
                'confidence_threshold': rule.confidence_threshold,
                'submission_type': rule.submission_type,
                'is_active': rule.is_active,
                'priority': rule.priority,
                'created_at': rule.created_at.isoformat(),
                'updated_at': rule.updated_at.isoformat(),
            })
        
        return data
    
    def _get_analytics_data(self, filters: Dict[str, Any], start_date: datetime,
                           end_date: datetime) -> List[Dict[str, Any]]:
        """Get analytics data."""
        try:
            # Calculate days for analytics
            if start_date and end_date:
                days = (end_date - start_date).days
            else:
                days = 30  # Default to 30 days
            
            # Get analytics from analytics engine
            analytics_data = analytics_engine.get_dashboard_analytics(days=days)
            
            # Convert to list format
            return [analytics_data]
            
        except Exception as exc:
            logger.error(f"Get analytics data failed: {exc}")
            return []
    
    def _get_full_system_data(self, filters: Dict[str, Any], start_date: datetime,
                             end_date: datetime, limit: int) -> List[Dict[str, Any]]:
        """Get full system data."""
        # Combine data from all scopes
        all_data = {}
        
        # Get data from each scope
        scopes = [
            ExportScope.SUBMISSIONS,
            ExportScope.DECISIONS,
            ExportScope.APPEALS,
            ExportScope.QUEUE,
            ExportScope.BOTS,
            ExportScope.RULES,
        ]
        
        for scope in scopes:
            try:
                scope_data = self._get_data_by_scope(scope, filters, start_date, end_date, limit)
                all_data[scope] = scope_data
            except Exception as exc:
                logger.error(f"Get {scope} data failed: {exc}")
                all_data[scope] = []
        
        # Add analytics
        try:
            analytics_data = self._get_analytics_data(filters, start_date, end_date)
            all_data[ExportScope.ANALYTICS] = analytics_data
        except Exception as exc:
            logger.error(f"Get analytics data failed: {exc}")
            all_data[ExportScope.ANALYTICS] = []
        
        return [all_data]
    
    def _export_json(self, data: List[Dict[str, Any]], scope: str) -> HttpResponse:
        """Export data as JSON."""
        try:
            json_data = json.dumps(data, indent=2, default=str)
            
            response = HttpResponse(json_data, content_type='application/json')
            response['Content-Disposition'] = f'attachment; filename="{scope}_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'
            
            return response
            
        except Exception as exc:
            logger.error(f"JSON export failed: {exc}")
            raise ModerationError(f"Failed to export JSON: {exc}")
    
    def _export_csv(self, data: List[Dict[str, Any]], scope: str) -> HttpResponse:
        """Export data as CSV."""
        try:
            if not data:
                raise ValueError("No data to export")
            
            # Handle nested data for full system export
            if scope == ExportScope.FULL_SYSTEM and data and isinstance(data[0], dict):
                # Create separate CSV files for each scope
                return self._export_csv_multiple_files(data[0], scope)
            
            # Get headers from first item
            if not data:
                headers = []
            else:
                headers = list(data[0].keys())
            
            # Create CSV content
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write headers
            writer.writerow(headers)
            
            # Write data rows
            for item in data:
                row = []
                for header in headers:
                    value = item.get(header, '')
                    # Convert complex types to strings
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value)
                    elif value is None:
                        value = ''
                    else:
                        value = str(value)
                    row.append(value)
                writer.writerow(row)
            
            # Create response
            response = HttpResponse(output.getvalue(), content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{scope}_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            
            return response
            
        except Exception as exc:
            logger.error(f"CSV export failed: {exc}")
            raise ModerationError(f"Failed to export CSV: {exc}")
    
    def _export_csv_multiple_files(self, data: Dict[str, Any], scope: str) -> HttpResponse:
        """Export multiple CSV files in a ZIP archive."""
        try:
            # Create ZIP file in memory
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for sub_scope, sub_data in data.items():
                    if not sub_data:
                        continue
                    
                    # Get headers
                    headers = list(sub_data[0].keys()) if sub_data else []
                    
                    # Create CSV content
                    csv_buffer = io.StringIO()
                    writer = csv.writer(csv_buffer)
                    
                    # Write headers
                    writer.writerow(headers)
                    
                    # Write data rows
                    for item in sub_data:
                        row = []
                        for header in headers:
                            value = item.get(header, '')
                            if isinstance(value, (dict, list)):
                                value = json.dumps(value)
                            elif value is None:
                                value = ''
                            else:
                                value = str(value)
                            row.append(value)
                        writer.writerow(row)
                    
                    # Add to ZIP
                    csv_content = csv_buffer.getvalue()
                    zip_file.writestr(f"{sub_scope}.csv", csv_content.encode('utf-8'))
            
            # Create response
            response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{scope}_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.zip"'
            
            return response
            
        except Exception as exc:
            logger.error(f"Multiple CSV export failed: {exc}")
            raise ModerationError(f"Failed to export multiple CSV files: {exc}")
    
    def _export_excel(self, data: List[Dict[str, Any]], scope: str) -> HttpResponse:
        """Export data as Excel file."""
        try:
            if not data:
                raise ValueError("No data to export")
            
            # Handle nested data for full system export
            if scope == ExportScope.FULL_SYSTEM and data and isinstance(data[0], dict):
                # Create separate sheets for each scope
                return self._export_excel_multiple_sheets(data[0], scope)
            
            # Create workbook
            wb = Workbook()
            ws = wb.active
            ws.title = scope.replace('_', ' ').title()
            
            # Get headers from first item
            headers = list(data[0].keys())
            
            # Style headers
            header_font = Font(bold=True)
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_alignment = Alignment(horizontal="center")
            
            # Write headers
            for col_num, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_num, value=header.replace('_', ' ').title())
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
            
            # Write data rows
            for row_num, item in enumerate(data, 2):
                for col_num, header in enumerate(headers, 1):
                    value = item.get(header, '')
                    # Convert complex types to strings
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value)
                    elif value is None:
                        value = ''
                    else:
                        value = str(value)
                    
                    cell = ws.cell(row=row_num, column=col_num, value=value)
            
            # Auto-adjust column widths
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except Exception as _e:
                        pass  # logged: auto_mod silently handles this
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            # Save to bytes
            excel_buffer = io.BytesIO()
            wb.save(excel_buffer)
            
            # Create response
            response = HttpResponse(excel_buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="{scope}_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
            
            return response
            
        except Exception as exc:
            logger.error(f"Excel export failed: {exc}")
            raise ModerationError(f"Failed to export Excel: {exc}")
    
    def _export_excel_multiple_sheets(self, data: Dict[str, Any], scope: str) -> HttpResponse:
        """Export multiple Excel sheets in one workbook."""
        try:
            # Create workbook
            wb = Workbook()
            
            # Remove default sheet
            wb.remove(wb.active)
            
            # Create sheet for each scope
            for sub_scope, sub_data in data.items():
                if not sub_data:
                    continue
                
                # Create worksheet
                ws = wb.create_sheet(title=sub_scope.replace('_', ' ').title())
                
                # Get headers
                headers = list(sub_data[0].keys()) if sub_data else []
                
                # Style headers
                header_font = Font(bold=True)
                header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                header_alignment = Alignment(horizontal="center")
                
                # Write headers
                for col_num, header in enumerate(headers, 1):
                    cell = ws.cell(row=1, column=col_num, value=header.replace('_', ' ').title())
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = header_alignment
                
                # Write data rows
                for row_num, item in enumerate(sub_data, 2):
                    for col_num, header in enumerate(headers, 1):
                        value = item.get(header, '')
                        if isinstance(value, (dict, list)):
                            value = json.dumps(value)
                        elif value is None:
                            value = ''
                        else:
                            value = str(value)
                        
                        cell = ws.cell(row=row_num, column=col_num, value=value)
                
                # Auto-adjust column widths
                for column in ws.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except Exception as _e:
                            pass  # logged: auto_mod silently handles this
                    adjusted_width = min(max_length + 2, 50)
                    ws.column_dimensions[column_letter].width = adjusted_width
            
            # Save to bytes
            excel_buffer = io.BytesIO()
            wb.save(excel_buffer)
            
            # Create response
            response = HttpResponse(excel_buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="{scope}_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
            
            return response
            
        except Exception as exc:
            logger.error(f"Multiple Excel export failed: {exc}")
            raise ModerationError(f"Failed to export multiple Excel sheets: {exc}")
    
    def get_export_statistics(self) -> Dict[str, Any]:
        """Get export statistics."""
        try:
            stats = {
                'supported_formats': self.supported_formats,
                'supported_scopes': [
                    ExportScope.SUBMISSIONS,
                    ExportScope.DECISIONS,
                    ExportScope.APPEALS,
                    ExportScope.QUEUE,
                    ExportScope.BOTS,
                    ExportScope.RULES,
                    ExportScope.ANALYTICS,
                    ExportScope.FULL_SYSTEM,
                ],
                'max_records_per_export': self.max_records_per_export,
                'available_filters': {
                    ExportScope.SUBMISSIONS: ['status', 'submission_type', 'user_id'],
                    ExportScope.DECISIONS: ['decision_type', 'is_automated', 'decider_id'],
                    ExportScope.APPEALS: ['status', 'appeal_type', 'user_id'],
                    ExportScope.QUEUE: ['status', 'priority', 'assigned_to'],
                    ExportScope.BOTS: ['status', 'bot_type', 'is_active'],
                    ExportScope.RULES: ['rule_type', 'is_active', 'submission_type'],
                },
                'generated_at': timezone.now().isoformat(),
            }
            
            return stats
            
        except Exception as exc:
            logger.error(f"Get export statistics failed: {exc}")
            return {'error': str(exc)}


# Global exporter instance
data_exporter = DataExporter()


# Utility functions
def export_moderation_data(scope: str, format_type: str, filters: Dict[str, Any] = None,
                          start_date: datetime = None, end_date: datetime = None,
                          limit: int = None) -> Union[HttpResponse, bytes]:
    """Export moderation data."""
    return data_exporter.export_data(scope, format_type, filters, start_date, end_date, limit)


def export_submissions(format_type: str = ExportFormat.CSV, filters: Dict[str, Any] = None,
                      start_date: datetime = None, end_date: datetime = None,
                      limit: int = None) -> Union[HttpResponse, bytes]:
    """Export submissions data."""
    return export_moderation_data(ExportScope.SUBMISSIONS, format_type, filters, start_date, end_date, limit)


def export_decisions(format_type: str = ExportFormat.CSV, filters: Dict[str, Any] = None,
                     start_date: datetime = None, end_date: datetime = None,
                     limit: int = None) -> Union[HttpResponse, bytes]:
    """Export decisions data."""
    return export_moderation_data(ExportScope.DECISIONS, format_type, filters, start_date, end_date, limit)


def export_analytics_report(days: int = 30, format_type: str = ExportFormat.EXCEL) -> Union[HttpResponse, bytes]:
    """Export analytics report."""
    start_date = timezone.now() - timedelta(days=days)
    return export_moderation_data(ExportScope.ANALYTICS, format_type, {}, start_date, timezone.now())


def get_export_capabilities() -> Dict[str, Any]:
    """Get export capabilities."""
    return data_exporter.get_export_statistics()


# Initialize logging
logger.info("Data export module initialized with multi-format export capabilities")
