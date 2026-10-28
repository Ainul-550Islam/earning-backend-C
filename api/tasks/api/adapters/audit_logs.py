"""
api/adapters/audit_logs.py
Audit logs adapter for earning backend platform
"""
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields
from decimal import Decimal
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_audit_logs(request):
    """Get audit logs for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        limit = int(request.GET.get('limit', 100))
        offset = int(request.GET.get('offset', 0))
        log_type = request.GET.get('type')  # 'all', 'security', 'system', 'user', 'admin'
        severity = request.GET.get('severity')  # 'all', 'critical', 'high', 'medium', 'low'
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Get audit logs
        from audit_logs.models import AuditLog
        queryset = AuditLog.objects.filter(
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Apply filters
        if log_type and log_type != 'all':
            queryset = queryset.filter(log_type=log_type)
        if severity and severity != 'all':
            queryset = queryset.filter(severity=severity)
        
        # Apply date range
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Paginate
        logs = queryset[offset:offset+limit]
        
        # Serialize logs
        log_data = []
        for log in logs:
            log_data.append({
                'id': log.id,
                'log_type': log.log_type,
                'severity': log.severity,
                'message': log.message,
                'details': log.details,
                'user_id': log.user_id,
                'user_username': log.user.username if log.user else None,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent,
                'action': log.action,
                'resource': log.resource,
                'status': log.status,
                'created_at': log.created_at.isoformat(),
                'metadata': log.metadata,
                'tenant_id': log.tenant_id
            })
        
        return Response({
            'success': True,
            'data': {
                'logs': log_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(log_data) == limit
                },
                'filters': {
                    'type': log_type,
                    'severity': severity,
                    'start_date': start_date,
                    'end_date': end_date
                },
                'summary': _get_audit_summary(queryset)
            },
            'message': 'Audit logs retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AuditLogsAdapter] Error getting audit logs: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve audit logs',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_audit_log(request):
    """Create a new audit log entry."""
    try:
        user = request.user
        data = request.data
        
        # Validate required fields
        required_fields = ['log_type', 'message']
        for field in required_fields:
            if field not in data:
                return Response({
                    'success': False,
                    'error': 'Missing required field',
                    'details': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create audit log
        from audit_logs.models import AuditLog
        audit_log = AuditLog.objects.create(
            log_type=data['log_type'],
            severity=data.get('severity', 'medium'),
            message=data['message'],
            details=data.get('details', {}),
            user=user,
            action=data.get('action', 'system_action'),
            resource=data.get('resource', 'system'),
            status=data.get('status', 'success'),
            metadata=data.get('metadata', {}),
            tenant_id=getattr(request, 'tenant_id', None),
            created_at=timezone.now()
        )
        
        return Response({
            'success': True,
            'data': {
                'log_id': audit_log.id,
                'log_type': audit_log.log_type,
                'severity': audit_log.severity,
                'message': audit_log.message,
                'created_at': audit_log.created_at.isoformat()
            },
            'message': 'Audit log created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[AuditLogsAdapter] Error creating audit log: {e}")
        return Response({
            'success': False,
            'error': 'Failed to create audit log',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_audit_logs(request):
    """Get user's audit logs."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
        
        # Get user's audit logs
        from audit_logs.models import AuditLog
        queryset = AuditLog.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Apply filters
        log_type = request.GET.get('type')
        if log_type and log_type != 'all':
            queryset = queryset.filter(log_type=log_type)
        
        # Paginate
        logs = queryset[offset:offset+limit]
        
        # Serialize logs
        log_data = []
        for log in logs:
            log_data.append({
                'id': log.id,
                'log_type': log.log_type,
                'severity': log.severity,
                'message': log.message,
                'details': log.details,
                'action': log.action,
                'resource': log.resource,
                'status': log.status,
                'created_at': log.created_at.isoformat(),
                'metadata': log.metadata
            })
        
        return Response({
            'success': True,
            'data': {
                'logs': log_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(log_data) == limit
                },
                'filters': {
                    'type': log_type
                }
            },
            'message': 'User audit logs retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AuditLogsAdapter] Error getting user audit logs: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve user audit logs',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_audit_summary(request):
    """Get audit summary statistics."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get audit logs for summary
        from audit_logs.models import AuditLog
        queryset = AuditLog.objects.filter(
            created_at__gte=start_date,
            tenant_id=tenant_id
        )
        
        # Calculate summary statistics
        summary = _get_audit_summary(queryset)
        
        return Response({
            'success': True,
            'data': {
                'tenant_id': tenant_id,
                'period': {
                    'days': days,
                    'start_date': start_date.isoformat(),
                    'end_date': timezone.now().isoformat()
                },
                'summary': summary
            },
            'message': 'Audit summary retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AuditLogsAdapter] Error getting audit summary: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve audit summary',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_security_events(request):
    """Get security-related audit events."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get security events
        from audit_logs.models import AuditLog
        security_events = AuditLog.objects.filter(
            tenant_id=tenant_id,
            log_type__in=['security', 'fraud', 'login_attempt', 'permission_denied'],
            created_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-created_at')
        
        # Serialize events
        event_data = []
        for event in security_events:
            event_data.append({
                'id': event.id,
                'log_type': event.log_type,
                'severity': event.severity,
                'message': event.message,
                'details': event.details,
                'user_id': event.user_id,
                'user_username': event.user.username if event.user else None,
                'ip_address': event.ip_address,
                'user_agent': event.user_agent,
                'action': event.action,
                'resource': event.resource,
                'status': event.status,
                'created_at': event.created_at.isoformat(),
                'metadata': event.metadata
            })
        
        return Response({
            'success': True,
            'data': {
                'events': event_data,
                'summary': _get_security_summary(security_events)
            },
            'message': 'Security events retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AuditLogsAdapter] Error getting security events: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve security events',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _get_audit_summary(queryset) -> Dict:
    """Calculate audit summary statistics."""
    try:
        total_logs = queryset.count()
        
        # Count by log type
        log_types = queryset.values('log_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Count by severity
        severity_counts = queryset.values('severity').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Count by status
        status_counts = queryset.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Recent events
        recent_events = queryset.order_by('-created_at')[:10]
        
        return {
            'total_logs': total_logs,
            'log_types': [
                {
                    'type': item['log_type'],
                    'count': item['count'],
                    'percentage': round((item['count'] / max(total_logs, 1)) * 100, 2)
                }
                for item in log_types
            ],
            'severity_breakdown': [
                {
                    'severity': item['severity'],
                    'count': item['count'],
                    'percentage': round((item['count'] / max(total_logs, 1)) * 100, 2)
                }
                for item in severity_counts
            ],
            'status_breakdown': [
                {
                    'status': item['status'],
                    'count': item['count'],
                    'percentage': round((item['count'] / max(total_logs, 1)) * 100, 2)
                }
                for item in status_counts
            ],
            'recent_events': [
                {
                    'id': event.id,
                    'log_type': event.log_type,
                    'severity': event.severity,
                    'message': event.message,
                    'created_at': event.created_at.isoformat()
                }
                for event in recent_events
            ]
        }
        
    except Exception:
        return {}


def _get_security_summary(security_events) -> Dict:
    """Calculate security summary statistics."""
    try:
        total_events = len(security_events)
        
        # Count by severity
        severity_counts = {}
        for event in security_events:
            severity = event['severity']
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Count by event type
        event_types = {}
        for event in security_events:
            event_type = event['log_type']
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        # Recent critical events
        critical_events = [e for e in security_events if e['severity'] == 'critical'][:5]
        
        return {
            'total_security_events': total_events,
            'severity_breakdown': [
                {
                    'severity': severity,
                    'count': count,
                    'percentage': round((count / max(total_events, 1)) * 100, 2)
                }
                for severity, count in severity_counts.items()
            ],
            'event_type_breakdown': [
                {
                    'event_type': event_type,
                    'count': count,
                    'percentage': round((count / max(total_events, 1)) * 100, 2)
                }
                for event_type, count in event_types.items()
            ],
            'critical_events': critical_events,
            'high_risk_events': len([e for e in security_events if e['severity'] == 'high']),
            'recent_activity': _get_recent_security_activity(security_events)
        }
        
    except Exception:
        return {}


def _get_recent_security_activity(security_events) -> Dict:
    """Get recent security activity summary."""
    try:
        last_24_hours = timezone.now() - timedelta(hours=24)
        recent_activity = [e for e in security_events if e['created_at'] >= last_24_hours]
        
        return {
            'last_24_hours': {
                'total_events': len(recent_activity),
                'critical_events': len([e for e in recent_activity if e['severity'] == 'critical']),
                'high_risk_events': len([e for e in recent_activity if e['severity'] == 'high']),
                'unique_ips': len(set(e['ip_address'] for e in recent_activity)),
                'unique_users': len(set(e['user_id'] for e in recent_activity if e['user_id'])),
                'most_common_type': _get_most_common(recent_activity, 'log_type'),
                'most_common_severity': _get_most_common(recent_activity, 'severity')
            },
            'last_7_days': {
                'total_events': len([e for e in security_events if e['created_at'] >= timezone.now() - timedelta(days=7)])
            }
        }
        
    except Exception:
        return {}


def _get_most_common(items, field) -> str:
    """Get most common value from list of items."""
    try:
        if not items:
            return None
        
        counts = {}
        for item in items:
            value = item.get(field)
            if value:
                counts[value] = counts.get(value, 0) + 1
        
        if counts:
            return max(counts, key=counts.get)
        return None
        
    except Exception:
        return None
