"""
Advertiser Audit Management

This module handles audit trails, compliance monitoring, and audit reporting
for advertisers including activity logging, compliance checks, and audit trails.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from ..database_models.advertiser_model import Advertiser
from ..database_models.audit_model import AuditLog
from ..database_models.compliance_model import ComplianceCheck
from ..database_models.reporting_model import Report as AuditReport
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AdvertiserAuditService:
    """Service for managing advertiser audit operations."""
    
    @staticmethod
    def log_activity(advertiser_id: UUID, activity_data: Dict[str, Any],
                     logged_by: Optional[User] = None) -> AuditLog:
        """Log activity for advertiser."""
        try:
            advertiser = AdvertiserAuditService.get_advertiser(advertiser_id)
            
            # Validate activity data
            action = activity_data.get('action')
            if not action:
                raise AdvertiserValidationError("action is required")
            
            object_type = activity_data.get('object_type', 'advertiser')
            object_id = activity_data.get('object_id', str(advertiser_id))
            
            with transaction.atomic():
                # Create audit log entry
                audit_log = AuditLog.objects.create(
                    advertiser=advertiser,
                    user=logged_by,
                    action=action,
                    object_type=object_type,
                    object_id=object_id,
                    description=activity_data.get('description', ''),
                    old_values=activity_data.get('old_values', {}),
                    new_values=activity_data.get('new_values', {}),
                    ip_address=activity_data.get('ip_address', ''),
                    user_agent=activity_data.get('user_agent', ''),
                    metadata=activity_data.get('metadata', {}),
                    created_at=timezone.now()
                )
                
                return audit_log
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error logging activity {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to log activity: {str(e)}")
    
    @staticmethod
    def perform_compliance_check(advertiser_id: UUID, check_data: Dict[str, Any],
                                 performed_by: Optional[User] = None) -> ComplianceCheck:
        """Perform compliance check for advertiser."""
        try:
            advertiser = AdvertiserAuditService.get_advertiser(advertiser_id)
            
            # Validate check data
            check_type = check_data.get('check_type', 'manual')
            if check_type not in ['manual', 'automatic', 'scheduled', 'random']:
                raise AdvertiserValidationError("Invalid check_type")
            
            with transaction.atomic():
                # Perform compliance checks
                check_results = AdvertiserAuditService._perform_compliance_checks(advertiser, check_data)
                
                # Calculate compliance score
                compliance_score = AdvertiserAuditService._calculate_compliance_score(check_results)
                
                # Determine compliance status
                if compliance_score >= 90:
                    compliance_status = 'compliant'
                elif compliance_score >= 70:
                    compliance_status = 'partially_compliant'
                else:
                    compliance_status = 'non_compliant'
                
                # Create compliance check record
                compliance_check = ComplianceCheck.objects.create(
                    advertiser=advertiser,
                    check_type=check_type,
                    check_results=check_results,
                    compliance_score=compliance_score,
                    compliance_status=compliance_status,
                    issues_identified=check_results.get('issues', []),
                    recommendations=check_results.get('recommendations', []),
                    next_check_date=check_data.get('next_check_date'),
                    performed_by=performed_by,
                    performed_at=timezone.now()
                )
                
                # Send notification for non-compliant status
                if compliance_status == 'non_compliant':
                    Notification.objects.create(
                        advertiser=advertiser,
                        user=performed_by,
                        title='Compliance Issues Identified',
                        message=f'Compliance check identified {len(check_results.get("issues", []))} issues.',
                        notification_type='compliance',
                        priority='high',
                        channels=['in_app', 'email']
                    )
                
                # Log compliance check
                AuditLog.log_action(
                    action='perform_compliance_check',
                    object_type='ComplianceCheck',
                    object_id=str(compliance_check.id),
                    user=performed_by,
                    advertiser=advertiser,
                    description=f"Performed {check_type} compliance check: {compliance_status}"
                )
                
                return compliance_check
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error performing compliance check {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to perform compliance check: {str(e)}")
    
    @staticmethod
    def generate_audit_report(advertiser_id: UUID, report_data: Dict[str, Any],
                              generated_by: Optional[User] = None) -> AuditReport:
        """Generate audit report for advertiser."""
        try:
            advertiser = AdvertiserAuditService.get_advertiser(advertiser_id)
            
            # Validate report data
            report_type = report_data.get('report_type', 'comprehensive')
            if report_type not in ['comprehensive', 'compliance', 'activity', 'financial', 'security']:
                raise AdvertiserValidationError("Invalid report_type")
            
            date_range = report_data.get('date_range')
            if not date_range:
                # Default to last 90 days
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=90)
                date_range = {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            
            with transaction.atomic():
                # Generate report data based on type
                if report_type == 'comprehensive':
                    report_content = AdvertiserAuditService._generate_comprehensive_report(
                        advertiser, date_range, report_data
                    )
                elif report_type == 'compliance':
                    report_content = AdvertiserAuditService._generate_compliance_report(
                        advertiser, date_range, report_data
                    )
                elif report_type == 'activity':
                    report_content = AdvertiserAuditService._generate_activity_report(
                        advertiser, date_range, report_data
                    )
                elif report_type == 'financial':
                    report_content = AdvertiserAuditService._generate_financial_report(
                        advertiser, date_range, report_data
                    )
                elif report_type == 'security':
                    report_content = AdvertiserAuditService._generate_security_report(
                        advertiser, date_range, report_data
                    )
                
                # Create audit report
                audit_report = AuditReport.objects.create(
                    advertiser=advertiser,
                    report_type=report_type,
                    title=report_data.get('title', f'{report_type.title()} Audit Report'),
                    content=report_content,
                    date_range=date_range,
                    report_period=report_data.get('report_period', '90_days'),
                    summary=report_content.get('summary', ''),
                    findings=report_content.get('findings', []),
                    recommendations=report_content.get('recommendations', []),
                    risk_level=report_content.get('risk_level', 'medium'),
                    generated_by=generated_by,
                    generated_at=timezone.now()
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=generated_by,
                    title='Audit Report Generated',
                    message=f'Your {report_type} audit report has been generated.',
                    notification_type='audit',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log report generation
                AuditLog.log_action(
                    action='generate_audit_report',
                    object_type='AuditReport',
                    object_id=str(audit_report.id),
                    user=generated_by,
                    advertiser=advertiser,
                    description=f"Generated {report_type} audit report"
                )
                
                return audit_report
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error generating audit report {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to generate audit report: {str(e)}")
    
    @staticmethod
    def get_audit_trail(advertiser_id: UUID, filters: Optional[Dict[str, Any]] = None,
                        page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """Get audit trail for advertiser."""
        try:
            advertiser = AdvertiserAuditService.get_advertiser(advertiser_id)
            
            queryset = AuditLog.objects.filter(advertiser=advertiser)
            
            # Apply filters
            if filters:
                if 'action' in filters:
                    queryset = queryset.filter(action=filters['action'])
                if 'object_type' in filters:
                    queryset = queryset.filter(object_type=filters['object_type'])
                if 'user' in filters:
                    queryset = queryset.filter(user__username__icontains=filters['user'])
                if 'date_from' in filters:
                    queryset = queryset.filter(created_at__date__gte=filters['date_from'])
                if 'date_to' in filters:
                    queryset = queryset.filter(created_at__date__lte=filters['date_to'])
                if 'search' in filters:
                    search = filters['search']
                    queryset = queryset.filter(
                        Q(description__icontains=search) |
                        Q(action__icontains=search)
                    )
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            audit_logs = queryset[offset:offset + page_size].order_by('-created_at')
            
            return {
                'advertiser_id': str(advertiser_id),
                'audit_trail': [
                    {
                        'id': str(log.id),
                        'user': log.user.username if log.user else 'System',
                        'action': log.action,
                        'object_type': log.object_type,
                        'object_id': log.object_id,
                        'description': log.description,
                        'old_values': log.old_values,
                        'new_values': log.new_values,
                        'ip_address': log.ip_address,
                        'user_agent': log.user_agent,
                        'metadata': log.metadata,
                        'created_at': log.created_at.isoformat()
                    }
                    for log in audit_logs
                ],
                'pagination': {
                    'total_count': total_count,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total_count + page_size - 1) // page_size,
                    'has_next': offset + page_size < total_count,
                    'has_previous': page > 1
                }
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting audit trail {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get audit trail: {str(e)}")
    
    @staticmethod
    def get_compliance_history(advertiser_id: UUID, filters: Optional[Dict[str, Any]] = None,
                               page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get compliance check history for advertiser."""
        try:
            advertiser = AdvertiserAuditService.get_advertiser(advertiser_id)
            
            queryset = ComplianceCheck.objects.filter(advertiser=advertiser)
            
            # Apply filters
            if filters:
                if 'check_type' in filters:
                    queryset = queryset.filter(check_type=filters['check_type'])
                if 'compliance_status' in filters:
                    queryset = queryset.filter(compliance_status=filters['compliance_status'])
                if 'date_from' in filters:
                    queryset = queryset.filter(performed_at__date__gte=filters['date_from'])
                if 'date_to' in filters:
                    queryset = queryset.filter(performed_at__date__lte=filters['date_to'])
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            compliance_checks = queryset[offset:offset + page_size].order_by('-performed_at')
            
            return {
                'advertiser_id': str(advertiser_id),
                'compliance_history': [
                    {
                        'id': str(check.id),
                        'check_type': check.check_type,
                        'compliance_score': check.compliance_score,
                        'compliance_status': check.compliance_status,
                        'issues_identified': check.issues_identified,
                        'recommendations': check.recommendations,
                        'check_results': check.check_results,
                        'performed_by': check.performed_by.username if check.performed_by else 'System',
                        'performed_at': check.performed_at.isoformat(),
                        'next_check_date': check.next_check_date.isoformat() if check.next_check_date else None
                    }
                    for check in compliance_checks
                ],
                'pagination': {
                    'total_count': total_count,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total_count + page_size - 1) // page_size,
                    'has_next': offset + page_size < total_count,
                    'has_previous': page > 1
                }
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting compliance history {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get compliance history: {str(e)}")
    
    @staticmethod
    def get_audit_reports(advertiser_id: UUID, filters: Optional[Dict[str, Any]] = None,
                          page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get audit reports for advertiser."""
        try:
            advertiser = AdvertiserAuditService.get_advertiser(advertiser_id)
            
            queryset = AuditReport.objects.filter(advertiser=advertiser)
            
            # Apply filters
            if filters:
                if 'report_type' in filters:
                    queryset = queryset.filter(report_type=filters['report_type'])
                if 'risk_level' in filters:
                    queryset = queryset.filter(risk_level=filters['risk_level'])
                if 'date_from' in filters:
                    queryset = queryset.filter(generated_at__date__gte=filters['date_from'])
                if 'date_to' in filters:
                    queryset = queryset.filter(generated_at__date__lte=filters['date_to'])
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            audit_reports = queryset[offset:offset + page_size].order_by('-generated_at')
            
            return {
                'advertiser_id': str(advertiser_id),
                'audit_reports': [
                    {
                        'id': str(report.id),
                        'report_type': report.report_type,
                        'title': report.title,
                        'summary': report.summary,
                        'risk_level': report.risk_level,
                        'findings_count': len(report.findings),
                        'recommendations_count': len(report.recommendations),
                        'date_range': report.date_range,
                        'generated_by': report.generated_by.username if report.generated_by else 'System',
                        'generated_at': report.generated_at.isoformat()
                    }
                    for report in audit_reports
                ],
                'pagination': {
                    'total_count': total_count,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total_count + page_size - 1) // page_size,
                    'has_next': offset + page_size < total_count,
                    'has_previous': page > 1
                }
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting audit reports {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get audit reports: {str(e)}")
    
    @staticmethod
    def get_audit_summary(advertiser_id: UUID, date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get audit summary for advertiser."""
        try:
            advertiser = AdvertiserAuditService.get_advertiser(advertiser_id)
            
            # Default date range (last 30 days)
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Get audit statistics
            audit_logs = AuditLog.objects.filter(
                advertiser=advertiser,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
            
            # Get compliance statistics
            compliance_checks = ComplianceCheck.objects.filter(
                advertiser=advertiser,
                performed_at__date__gte=start_date,
                performed_at__date__lte=end_date
            )
            
            # Get report statistics
            audit_reports = AuditReport.objects.filter(
                advertiser=advertiser,
                generated_at__date__gte=start_date,
                generated_at__date__lte=end_date
            )
            
            # Calculate metrics
            total_activities = audit_logs.count()
            total_compliance_checks = compliance_checks.count()
            total_reports = audit_reports.count()
            
            # Get activity breakdown
            activity_by_type = audit_logs.values('action').annotate(
                count=Count('id')
            )
            
            # Get compliance status breakdown
            compliance_by_status = compliance_checks.values('compliance_status').annotate(
                count=Count('id'),
                avg_score=Avg('compliance_score')
            )
            
            # Get risk level breakdown
            risk_by_level = audit_reports.values('risk_level').annotate(
                count=Count('id')
            )
            
            # Get recent activities
            recent_activities = audit_logs.order_by('-created_at')[:10]
            
            return {
                'advertiser_id': str(advertiser_id),
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'summary_metrics': {
                    'total_activities': total_activities,
                    'total_compliance_checks': total_compliance_checks,
                    'total_reports': total_reports,
                    'avg_compliance_score': compliance_checks.aggregate(
                        avg=Avg('compliance_score')
                    )['avg'] or 0
                },
                'activity_breakdown': [
                    {
                        'action': item['action'],
                        'count': item['count']
                    }
                    for item in activity_by_type
                ],
                'compliance_breakdown': [
                    {
                        'status': item['compliance_status'],
                        'count': item['count'],
                        'avg_score': float(item['avg_score'] or 0)
                    }
                    for item in compliance_by_status
                ],
                'risk_breakdown': [
                    {
                        'risk_level': item['risk_level'],
                        'count': item['count']
                    }
                    for item in risk_by_level
                ],
                'recent_activities': [
                    {
                        'id': str(activity.id),
                        'action': activity.action,
                        'description': activity.description,
                        'user': activity.user.username if activity.user else 'System',
                        'created_at': activity.created_at.isoformat()
                    }
                    for activity in recent_activities
                ]
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting audit summary {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get audit summary: {str(e)}")
    
    @staticmethod
    def _perform_compliance_checks(advertiser: Advertiser, check_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive compliance checks."""
        try:
            results = {
                'checks_performed': [],
                'issues': [],
                'recommendations': [],
                'score_breakdown': {}
            }
            
            # Check profile completeness
            profile_score = AdvertiserAuditService._check_profile_completeness(advertiser)
            results['checks_performed'].append('profile_completeness')
            results['score_breakdown']['profile_completeness'] = profile_score
            
            if profile_score < 80:
                results['issues'].append({
                    'type': 'profile_incomplete',
                    'severity': 'medium',
                    'description': 'Advertiser profile is incomplete',
                    'score': profile_score
                })
                results['recommendations'].append('Complete advertiser profile information')
            
            # Check verification status
            verification_score = AdvertiserAuditService._check_verification_status(advertiser)
            results['checks_performed'].append('verification_status')
            results['score_breakdown']['verification_status'] = verification_score
            
            if verification_score < 70:
                results['issues'].append({
                    'type': 'verification_pending',
                    'severity': 'high',
                    'description': 'Advertiser verification is incomplete',
                    'score': verification_score
                })
                results['recommendations'].append('Complete verification process')
            
            # Check billing compliance
            billing_score = AdvertiserAuditService._check_billing_compliance(advertiser)
            results['checks_performed'].append('billing_compliance')
            results['score_breakdown']['billing_compliance'] = billing_score
            
            if billing_score < 80:
                results['issues'].append({
                    'type': 'billing_non_compliant',
                    'severity': 'medium',
                    'description': 'Billing information needs attention',
                    'score': billing_score
                })
                results['recommendations'].append('Update billing information')
            
            # Check activity compliance
            activity_score = AdvertiserAuditService._check_activity_compliance(advertiser)
            results['checks_performed'].append('activity_compliance')
            results['score_breakdown']['activity_compliance'] = activity_score
            
            if activity_score < 70:
                results['issues'].append({
                    'type': 'suspicious_activity',
                    'severity': 'high',
                    'description': 'Unusual activity detected',
                    'score': activity_score
                })
                results['recommendations'].append('Review recent account activity')
            
            return results
            
        except Exception as e:
            logger.error(f"Error performing compliance checks: {str(e)}")
            return {
                'checks_performed': [],
                'issues': [{'type': 'check_error', 'severity': 'high', 'description': str(e)}],
                'recommendations': ['Contact support for assistance'],
                'score_breakdown': {}
            }
    
    @staticmethod
    def _check_profile_completeness(advertiser: Advertiser) -> float:
        """Check profile completeness score."""
        try:
            required_fields = [
                'company_name',
                'contact_name',
                'contact_email',
                'contact_phone',
                'website',
                'description'
            ]
            
            completed_fields = 0
            for field in required_fields:
                if getattr(advertiser, field, None):
                    completed_fields += 1
            
            return (completed_fields / len(required_fields)) * 100
            
        except Exception as e:
            logger.error(f"Error checking profile completeness: {str(e)}")
            return 0
    
    @staticmethod
    def _check_verification_status(advertiser: Advertiser) -> float:
        """Check verification status score."""
        try:
            score = 0
            
            if advertiser.is_verified:
                score += 50
            
            if advertiser.verification_date:
                score += 25
            
            if advertiser.verified_by:
                score += 25
            
            return score
            
        except Exception as e:
            logger.error(f"Error checking verification status: {str(e)}")
            return 0
    
    @staticmethod
    def _check_billing_compliance(advertiser: Advertiser) -> float:
        """Check billing compliance score."""
        try:
            from ..database_models.billing_model import BillingProfile
            
            billing_profile = BillingProfile.objects.filter(advertiser=advertiser).first()
            
            if not billing_profile:
                return 0
            
            score = 0
            
            if billing_profile.is_verified:
                score += 40
            
            if billing_profile.billing_email:
                score += 20
            
            if billing_profile.payment_method_set.exists():
                score += 20
            
            if billing_profile.auto_charge:
                score += 20
            
            return score
            
        except Exception as e:
            logger.error(f"Error checking billing compliance: {str(e)}")
            return 0
    
    @staticmethod
    def _check_activity_compliance(advertiser: Advertiser) -> float:
        """Check activity compliance score."""
        try:
            # Get recent activity
            recent_logs = AuditLog.objects.filter(
                advertiser=advertiser,
                created_at__gte=timezone.now() - timedelta(days=7)
            )
            
            # Check for suspicious patterns
            suspicious_actions = ['delete', 'bulk_update', 'mass_change']
            suspicious_count = recent_logs.filter(action__in=suspicious_actions).count()
            
            # Calculate score based on suspicious activity
            if suspicious_count == 0:
                return 100
            elif suspicious_count <= 2:
                return 70
            elif suspicious_count <= 5:
                return 40
            else:
                return 10
                
        except Exception as e:
            logger.error(f"Error checking activity compliance: {str(e)}")
            return 50
    
    @staticmethod
    def _calculate_compliance_score(check_results: Dict[str, Any]) -> float:
        """Calculate overall compliance score."""
        try:
            score_breakdown = check_results.get('score_breakdown', {})
            
            if not score_breakdown:
                return 0
            
            total_score = sum(score_breakdown.values())
            avg_score = total_score / len(score_breakdown)
            
            return round(avg_score, 2)
            
        except Exception as e:
            logger.error(f"Error calculating compliance score: {str(e)}")
            return 0
    
    @staticmethod
    def _generate_comprehensive_report(advertiser: Advertiser, date_range: Dict[str, str],
                                        report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive audit report."""
        try:
            # Get all data for comprehensive report
            audit_trail = AdvertiserAuditService.get_audit_trail(
                str(advertiser.id),
                {'date_from': date_range['start_date'], 'date_to': date_range['end_date']},
                page=1,
                page_size=1000
            )
            
            compliance_history = AdvertiserAuditService.get_compliance_history(
                str(advertiser.id),
                {'date_from': date_range['start_date'], 'date_to': date_range['end_date']},
                page=1,
                page_size=100
            )
            
            # Generate summary
            summary = f"Comprehensive audit report for {advertiser.company_name} covering period {date_range['start_date']} to {date_range['end_date']}"
            
            # Identify findings
            findings = []
            
            # Analyze activity patterns
            recent_activities = audit_trail['audit_trail'][:50]
            suspicious_activities = [a for a in recent_activities if a['action'] in ['delete', 'bulk_update', 'mass_change']]
            
            if suspicious_activities:
                findings.append({
                    'type': 'suspicious_activity',
                    'severity': 'high',
                    'description': f'{len(suspicious_activities)} suspicious activities detected',
                    'count': len(suspicious_activities)
                })
            
            # Analyze compliance issues
            non_compliant_checks = [c for c in compliance_history['compliance_history'] if c['compliance_status'] == 'non_compliant']
            
            if non_compliant_checks:
                findings.append({
                    'type': 'compliance_issues',
                    'severity': 'medium',
                    'description': f'{len(non_compliant_checks)} non-compliant checks',
                    'count': len(non_compliant_checks)
                })
            
            # Generate recommendations
            recommendations = []
            
            if suspicious_activities:
                recommendations.append('Review and investigate suspicious activities')
            
            if non_compliant_checks:
                recommendations.append('Address compliance issues identified in checks')
            
            recommendations.append('Regular monitoring and audit reviews')
            
            # Determine risk level
            risk_level = 'low'
            if suspicious_activities:
                risk_level = 'high'
            elif non_compliant_checks:
                risk_level = 'medium'
            
            return {
                'summary': summary,
                'findings': findings,
                'recommendations': recommendations,
                'risk_level': risk_level,
                'audit_trail_summary': {
                    'total_activities': audit_trail['pagination']['total_count'],
                    'top_actions': [a['action'] for a in recent_activities[:10]]
                },
                'compliance_summary': {
                    'total_checks': compliance_history['pagination']['total_count'],
                    'compliance_rate': len([c for c in compliance_history['compliance_history'] if c['compliance_status'] == 'compliant']) / max(compliance_history['pagination']['total_count'], 1) * 100
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating comprehensive report: {str(e)}")
            return {
                'summary': 'Error generating report',
                'findings': [{'type': 'error', 'severity': 'high', 'description': str(e)}],
                'recommendations': ['Contact support'],
                'risk_level': 'high'
            }
    
    @staticmethod
    def _generate_compliance_report(advertiser: Advertiser, date_range: Dict[str, str],
                                   report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate compliance-focused audit report."""
        try:
            compliance_history = AdvertiserAuditService.get_compliance_history(
                str(advertiser.id),
                {'date_from': date_range['start_date'], 'date_to': date_range['end_date']},
                page=1,
                page_size=1000
            )
            
            summary = f"Compliance audit report for {advertiser.company_name}"
            
            findings = []
            recommendations = []
            
            # Analyze compliance trends
            checks = compliance_history['compliance_history']
            if checks:
                avg_score = sum(c['compliance_score'] for c in checks) / len(checks)
                
                if avg_score < 70:
                    findings.append({
                        'type': 'low_compliance_score',
                        'severity': 'high',
                        'description': f'Average compliance score: {avg_score:.1f}',
                        'score': avg_score
                    })
                    recommendations.append('Improve overall compliance measures')
                
                non_compliant_count = len([c for c in checks if c['compliance_status'] == 'non_compliant'])
                if non_compliant_count > 0:
                    findings.append({
                        'type': 'non_compliant_checks',
                        'severity': 'medium',
                        'description': f'{non_compliant_count} non-compliant checks',
                        'count': non_compliant_count
                    })
                    recommendations.append('Address specific compliance issues')
            
            risk_level = 'low' if not findings else 'medium' if len(findings) <= 2 else 'high'
            
            return {
                'summary': summary,
                'findings': findings,
                'recommendations': recommendations,
                'risk_level': risk_level,
                'compliance_metrics': {
                    'total_checks': len(checks),
                    'average_score': sum(c['compliance_score'] for c in checks) / len(checks) if checks else 0,
                    'compliance_rate': len([c for c in checks if c['compliance_status'] == 'compliant']) / max(len(checks), 1) * 100
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating compliance report: {str(e)}")
            return {
                'summary': 'Error generating compliance report',
                'findings': [{'type': 'error', 'severity': 'high', 'description': str(e)}],
                'recommendations': ['Contact support'],
                'risk_level': 'high'
            }
    
    @staticmethod
    def _generate_activity_report(advertiser: Advertiser, date_range: Dict[str, str],
                                  report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate activity-focused audit report."""
        try:
            audit_trail = AdvertiserAuditService.get_audit_trail(
                str(advertiser.id),
                {'date_from': date_range['start_date'], 'date_to': date_range['end_date']},
                page=1,
                page_size=1000
            )
            
            summary = f"Activity audit report for {advertiser.company_name}"
            
            findings = []
            recommendations = []
            
            # Analyze activity patterns
            activities = audit_trail['audit_trail']
            
            # Check for unusual activity patterns
            action_counts = {}
            for activity in activities:
                action = activity['action']
                action_counts[action] = action_counts.get(action, 0) + 1
            
            # Identify high-frequency actions
            high_frequency_actions = [(action, count) for action, count in action_counts.items() if count > 10]
            
            if high_frequency_actions:
                findings.append({
                    'type': 'high_frequency_actions',
                    'severity': 'medium',
                    'description': f'{len(high_frequency_actions)} actions with high frequency',
                    'actions': high_frequency_actions
                })
                recommendations.append('Review high-frequency action patterns')
            
            # Check for suspicious actions
            suspicious_actions = [a for a in activities if a['action'] in ['delete', 'bulk_update', 'mass_change']]
            
            if suspicious_actions:
                findings.append({
                    'type': 'suspicious_actions',
                    'severity': 'high',
                    'description': f'{len(suspicious_actions)} suspicious actions detected',
                    'count': len(suspicious_actions)
                })
                recommendations.append('Investigate suspicious activities')
            
            risk_level = 'low' if not findings else 'medium' if len(findings) <= 2 else 'high'
            
            return {
                'summary': summary,
                'findings': findings,
                'recommendations': recommendations,
                'risk_level': risk_level,
                'activity_metrics': {
                    'total_activities': len(activities),
                    'unique_actions': len(action_counts),
                    'top_actions': sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:10]
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating activity report: {str(e)}")
            return {
                'summary': 'Error generating activity report',
                'findings': [{'type': 'error', 'severity': 'high', 'description': str(e)}],
                'recommendations': ['Contact support'],
                'risk_level': 'high'
            }
    
    @staticmethod
    def _generate_financial_report(advertiser: Advertiser, date_range: Dict[str, str],
                                   report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate financial-focused audit report."""
        try:
            summary = f"Financial audit report for {advertiser.company_name}"
            
            # Mock financial audit data
            findings = []
            recommendations = []
            
            # Check for unusual spending patterns
            # This would integrate with actual financial data
            
            findings.append({
                'type': 'financial_review_needed',
                'severity': 'medium',
                'description': 'Financial audit requires manual review'
            })
            
            recommendations.append('Conduct detailed financial analysis')
            
            return {
                'summary': summary,
                'findings': findings,
                'recommendations': recommendations,
                'risk_level': 'medium'
            }
            
        except Exception as e:
            logger.error(f"Error generating financial report: {str(e)}")
            return {
                'summary': 'Error generating financial report',
                'findings': [{'type': 'error', 'severity': 'high', 'description': str(e)}],
                'recommendations': ['Contact support'],
                'risk_level': 'high'
            }
    
    @staticmethod
    def _generate_security_report(advertiser: Advertiser, date_range: Dict[str, str],
                                  report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate security-focused audit report."""
        try:
            audit_trail = AdvertiserAuditService.get_audit_trail(
                str(advertiser.id),
                {'date_from': date_range['start_date'], 'date_to': date_range['end_date']},
                page=1,
                page_size=1000
            )
            
            summary = f"Security audit report for {advertiser.company_name}"
            
            findings = []
            recommendations = []
            
            # Check for security-related activities
            activities = audit_trail['audit_trail']
            
            # Check for login activities from different IPs
            ip_addresses = set()
            for activity in activities:
                if activity['ip_address']:
                    ip_addresses.add(activity['ip_address'])
            
            if len(ip_addresses) > 5:
                findings.append({
                    'type': 'multiple_ip_addresses',
                    'severity': 'medium',
                    'description': f'Activity from {len(ip_addresses)} different IP addresses',
                    'count': len(ip_addresses)
                })
                recommendations.append('Review account access patterns')
            
            # Check for failed login attempts (mock data)
            findings.append({
                'type': 'security_review',
                'severity': 'low',
                'description': 'Regular security review recommended'
            })
            
            recommendations.append('Enable two-factor authentication')
            
            risk_level = 'low' if len(findings) <= 1 else 'medium'
            
            return {
                'summary': summary,
                'findings': findings,
                'recommendations': recommendations,
                'risk_level': risk_level,
                'security_metrics': {
                    'unique_ip_addresses': len(ip_addresses),
                    'total_activities': len(activities)
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating security report: {str(e)}")
            return {
                'summary': 'Error generating security report',
                'findings': [{'type': 'error', 'severity': 'high', 'description': str(e)}],
                'recommendations': ['Contact support'],
                'risk_level': 'high'
            }
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_audit_statistics() -> Dict[str, Any]:
        """Get audit statistics across all advertisers."""
        try:
            # Get audit log statistics
            total_audit_logs = AuditLog.objects.count()
            logs_by_action = AuditLog.objects.values('action').annotate(
                count=Count('id')
            )
            
            # Get compliance check statistics
            total_compliance_checks = ComplianceCheck.objects.count()
            checks_by_status = ComplianceCheck.objects.values('compliance_status').annotate(
                count=Count('id'),
                avg_score=Avg('compliance_score')
            )
            
            # Get audit report statistics
            total_audit_reports = AuditReport.objects.count()
            reports_by_type = AuditReport.objects.values('report_type').annotate(
                count=Count('id')
            )
            
            return {
                'audit_logs': {
                    'total': total_audit_logs,
                    'by_action': list(logs_by_action)
                },
                'compliance_checks': {
                    'total': total_compliance_checks,
                    'by_status': list(checks_by_status)
                },
                'audit_reports': {
                    'total': total_audit_reports,
                    'by_type': list(reports_by_type)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting audit statistics: {str(e)}")
            return {
                'audit_logs': {'total': 0, 'by_action': []},
                'compliance_checks': {'total': 0, 'by_status': []},
                'audit_reports': {'total': 0, 'by_type': []}
            }
