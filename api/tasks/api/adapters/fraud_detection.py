"""
api/adapters/fraud_detection.py
Fraud detection adapter for earning backend platform
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
@permission_classes([IsAuthenticated])
def fraud_profile(request):
    """Get user's fraud profile and risk assessment."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get fraud assessment data
        fraud_score = cache.get(f'fraud_score_{user.id}', 0)
        risk_factors = _calculate_risk_factors(user)
        
        fraud_data = {
            'user_id': user.id,
            'tenant_id': tenant_id,
            'fraud_score': fraud_score,
            'risk_level': _get_risk_level(fraud_score),
            'risk_factors': risk_factors,
            'assessment': {
                'is_high_risk': fraud_score >= 60,
                'is_medium_risk': 40 <= fraud_score < 60,
                'is_low_risk': fraud_score < 40,
                'requires_review': fraud_score >= 50,
                'auto_suspend_threshold': 80,
            },
            'flags': {
                'is_fraud_flagged': cache.get(f'fraud_flagged_{user.id}', False),
                'is_suspended': getattr(user, 'is_suspended', False),
                'suspension_reason': cache.get(f'suspension_reason_{user.id}', None),
                'last_review': cache.get(f'last_fraud_review_{user.id}', None),
            },
            'behavioral_analysis': _get_behavioral_analysis(user),
            'device_analysis': _get_device_analysis(user),
            'location_analysis': _get_location_analysis(user),
            'velocity_analysis': _get_velocity_analysis(user),
        }
        
        return Response({
            'success': True,
            'data': fraud_data,
            'message': 'Fraud profile retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[FraudDetectionAdapter] Error getting fraud profile: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve fraud profile',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def fraud_dashboard(request):
    """Get fraud detection dashboard for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get fraud statistics
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # High-risk users
        high_risk_users = User.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).annotate(
            fraud_score=F('fraud_score')
        ).filter(fraud_score__gte=60).order_by('-fraud_score')[:20]
        
        # Fraud statistics
        total_users = User.objects.filter(tenant_id=tenant_id, is_active=True).count()
        high_risk_count = User.objects.filter(
            tenant_id=tenant_id,
            is_active=True,
            fraud_score__gte=60
        ).count()
        
        medium_risk_count = User.objects.filter(
            tenant_id=tenant_id,
            is_active=True,
            fraud_score__gte=40,
            fraud_score__lt=60
        ).count()
        
        # Recent fraud events
        recent_fraud_events = []
        for i in range(50):  # Get last 50 events from cache
            event_key = f'fraud_event_{tenant_id}_{i}'
            event = cache.get(event_key)
            if event:
                recent_fraud_events.append(event)
        
        dashboard_data = {
            'tenant_id': tenant_id,
            'user_risk_distribution': {
                'total_users': total_users,
                'high_risk': high_risk_count,
                'medium_risk': medium_risk_count,
                'low_risk': total_users - high_risk_count - medium_risk_count,
                'high_risk_percentage': round((high_risk_count / max(total_users, 1)) * 100, 2),
                'medium_risk_percentage': round((medium_risk_count / max(total_users, 1)) * 100, 2),
                'low_risk_percentage': round(((total_users - high_risk_count - medium_risk_count) / max(total_users, 1)) * 100, 2),
            },
            'high_risk_users': [
                {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'fraud_score': user.fraud_score,
                    'risk_level': _get_risk_level(user.fraud_score),
                    'last_login': getattr(user, 'last_login', None),
                    'registration_date': user.date_joined.isoformat(),
                }
                for user in high_risk_users
            ],
            'recent_fraud_events': recent_fraud_events,
            'system_status': {
                'fraud_detection_enabled': True,
                'auto_suspension_enabled': True,
                'manual_review_required': True,
                'last_scan': cache.get(f'last_fraud_scan_{tenant_id}', timezone.now().isoformat()),
            }
        }
        
        return Response({
            'success': True,
            'data': dashboard_data,
            'message': 'Fraud dashboard retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[FraudDetectionAdapter] Error getting fraud dashboard: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve fraud dashboard',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def manual_fraud_review(request):
    """Perform manual fraud review on user."""
    try:
        user = request.user
        data = request.data
        
        target_user_id = data.get('user_id')
        review_action = data.get('action')  # 'flag', 'unflag', 'suspend', 'unsuspend'
        review_notes = data.get('notes', '')
        
        if not target_user_id or not review_action:
            return Response({
                'success': False,
                'error': 'Missing required fields',
                'details': 'user_id and action are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get target user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        target_user = User.objects.get(id=target_user_id)
        
        # Perform review action
        if review_action == 'flag':
            cache.set(f'fraud_flagged_{target_user_id}', True, timeout=86400)
            _create_fraud_event(target_user.id, 'manual_flag', review_notes, user.id)
        
        elif review_action == 'unflag':
            cache.delete(f'fraud_flagged_{target_user_id}')
            _create_fraud_event(target_user.id, 'manual_unflag', review_notes, user.id)
        
        elif review_action == 'suspend':
            target_user.is_suspended = True
            target_user.save()
            cache.set(f'suspension_reason_{target_user_id}', review_notes, timeout=86400)
            _create_fraud_event(target_user.id, 'manual_suspend', review_notes, user.id)
        
        elif review_action == 'unsuspend':
            target_user.is_suspended = False
            target_user.save()
            cache.delete(f'suspension_reason_{target_user_id}')
            _create_fraud_event(target_user.id, 'manual_unsuspend', review_notes, user.id)
        
        return Response({
            'success': True,
            'data': {
                'user_id': target_user_id,
                'action': review_action,
                'reviewed_by': user.id,
                'reviewed_at': timezone.now().isoformat(),
                'notes': review_notes
            },
            'message': f'Fraud review {review_action} completed successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[FraudDetectionAdapter] Error performing fraud review: {e}")
        return Response({
            'success': False,
            'error': 'Failed to perform fraud review',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fraud_alerts(request):
    """Get fraud alerts for user."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get user's fraud alerts
        alerts = []
        
        # Check for high fraud score
        fraud_score = cache.get(f'fraud_score_{user.id}', 0)
        if fraud_score >= 60:
            alerts.append({
                'type': 'high_fraud_score',
                'level': 'critical',
                'message': f'High fraud score detected: {fraud_score}',
                'timestamp': timezone.now().isoformat(),
                'requires_action': True
            })
        
        # Check for unusual login patterns
        unusual_logins = cache.get(f'unusual_logins_{user.id}', [])
        for login in unusual_logins:
            alerts.append({
                'type': 'unusual_login',
                'level': 'warning',
                'message': f'Unusual login detected from {login.get("ip", "unknown")}',
                'timestamp': login.get('timestamp', timezone.now().isoformat()),
                'requires_action': True
            })
        
        # Check for velocity violations
        velocity_violations = cache.get(f'velocity_violations_{user.id}', [])
        for violation in velocity_violations:
            alerts.append({
                'type': 'velocity_violation',
                'level': 'warning',
                'message': f'Activity velocity violation: {violation.get("type", "unknown")}',
                'timestamp': violation.get('timestamp', timezone.now().isoformat()),
                'requires_action': True
            })
        
        return Response({
            'success': True,
            'data': {
                'user_id': user.id,
                'tenant_id': tenant_id,
                'fraud_score': fraud_score,
                'alerts': alerts,
                'alert_count': len(alerts),
                'last_updated': timezone.now().isoformat()
            },
            'message': 'Fraud alerts retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[FraudDetectionAdapter] Error getting fraud alerts: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve fraud alerts',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _calculate_risk_factors(user) -> Dict:
    """Calculate risk factors for user."""
    try:
        risk_factors = {}
        
        # Account age risk
        account_age_days = (timezone.now() - user.date_joined).days
        if account_age_days < 7:
            risk_factors['account_age'] = {'risk': 'high', 'score': 20, 'details': 'Account less than 7 days old'}
        elif account_age_days < 30:
            risk_factors['account_age'] = {'risk': 'medium', 'score': 10, 'details': 'Account less than 30 days old'}
        else:
            risk_factors['account_age'] = {'risk': 'low', 'score': 0, 'details': 'Account age normal'}
        
        # Login pattern risk
        failed_logins = cache.get(f'failed_logins_{user.id}', 0)
        if failed_logins > 5:
            risk_factors['login_pattern'] = {'risk': 'high', 'score': 15, 'details': f'{failed_logins} failed login attempts'}
        elif failed_logins > 2:
            risk_factors['login_pattern'] = {'risk': 'medium', 'score': 8, 'details': f'{failed_logins} failed login attempts'}
        else:
            risk_factors['login_pattern'] = {'risk': 'low', 'score': 0, 'details': 'Normal login pattern'}
        
        # Device risk
        device_count = cache.get(f'device_count_{user.id}', 1)
        if device_count > 5:
            risk_factors['device_usage'] = {'risk': 'high', 'score': 12, 'details': f'{device_count} different devices'}
        elif device_count > 3:
            risk_factors['device_usage'] = {'risk': 'medium', 'score': 6, 'details': f'{device_count} different devices'}
        else:
            risk_factors['device_usage'] = {'risk': 'low', 'score': 0, 'details': 'Normal device usage'}
        
        # Location risk
        location_count = cache.get(f'location_count_{user.id}', 1)
        if location_count > 3:
            risk_factors['location_usage'] = {'risk': 'high', 'score': 10, 'details': f'{location_count} different locations'}
        elif location_count > 2:
            risk_factors['location_usage'] = {'risk': 'medium', 'score': 5, 'details': f'{location_count} different locations'}
        else:
            risk_factors['location_usage'] = {'risk': 'low', 'score': 0, 'details': 'Normal location usage'}
        
        # Activity velocity risk
        task_velocity = cache.get(f'task_velocity_{user.id}', 0)
        if task_velocity > 50:
            risk_factors['activity_velocity'] = {'risk': 'high', 'score': 18, 'details': f'High task completion velocity: {task_velocity}/hour'}
        elif task_velocity > 20:
            risk_factors['activity_velocity'] = {'risk': 'medium', 'score': 9, 'details': f'Elevated task completion velocity: {task_velocity}/hour'}
        else:
            risk_factors['activity_velocity'] = {'risk': 'low', 'score': 0, 'details': 'Normal activity velocity'}
        
        return risk_factors
        
    except Exception:
        return {}


def _get_risk_level(score: int) -> str:
    """Get risk level based on score."""
    if score >= 80:
        return 'critical'
    elif score >= 60:
        return 'high'
    elif score >= 40:
        return 'medium'
    elif score >= 20:
        return 'low'
    else:
        return 'minimal'


def _get_behavioral_analysis(user) -> Dict:
    """Get behavioral analysis for user."""
    try:
        analysis = {}
        
        # Login frequency
        login_frequency = cache.get(f'login_frequency_{user.id}', {})
        analysis['login_frequency'] = {
            'avg_daily_logins': login_frequency.get('avg_daily', 0),
            'peak_hours': login_frequency.get('peak_hours', []),
            'unusual_times': login_frequency.get('unusual_times', []),
            'risk_score': login_frequency.get('risk_score', 0)
        }
        
        # Task completion patterns
        task_patterns = cache.get(f'task_patterns_{user.id}', {})
        analysis['task_patterns'] = {
            'avg_completion_time': task_patterns.get('avg_completion_time', 0),
            'completion_rate': task_patterns.get('completion_rate', 0),
            'preferred_categories': task_patterns.get('preferred_categories', []),
            'peak_activity_hours': task_patterns.get('peak_hours', []),
            'risk_score': task_patterns.get('risk_score', 0)
        }
        
        # Session patterns
        session_patterns = cache.get(f'session_patterns_{user.id}', {})
        analysis['session_patterns'] = {
            'avg_session_duration': session_patterns.get('avg_duration', 0),
            'sessions_per_day': session_patterns.get('per_day', 0),
            'peak_usage_times': session_patterns.get('peak_times', []),
            'risk_score': session_patterns.get('risk_score', 0)
        }
        
        return analysis
        
    except Exception:
        return {}


def _get_device_analysis(user) -> Dict:
    """Get device analysis for user."""
    try:
        devices = cache.get(f'devices_{user.id}', [])
        
        if not devices:
            return {'devices': [], 'risk_score': 0, 'analysis': 'No device data available'}
        
        analysis = {
            'devices': devices,
            'unique_devices': len(devices),
            'risk_score': 0,
            'analysis': []
        }
        
        # Analyze device patterns
        if len(devices) > 5:
            analysis['risk_score'] += 15
            analysis['analysis'].append('High number of unique devices detected')
        
        # Check for suspicious devices
        suspicious_devices = [d for d in devices if d.get('is_suspicious', False)]
        if suspicious_devices:
            analysis['risk_score'] += 20
            analysis['analysis'].append(f'{len(suspicious_devices)} suspicious devices detected')
        
        return analysis
        
    except Exception:
        return {'devices': [], 'risk_score': 0, 'analysis': 'Error analyzing devices'}


def _get_location_analysis(user) -> Dict:
    """Get location analysis for user."""
    try:
        locations = cache.get(f'locations_{user.id}', [])
        
        if not locations:
            return {'locations': [], 'risk_score': 0, 'analysis': 'No location data available'}
        
        analysis = {
            'locations': locations,
            'unique_locations': len(locations),
            'risk_score': 0,
            'analysis': []
        }
        
        # Analyze location patterns
        if len(locations) > 3:
            analysis['risk_score'] += 10
            analysis['analysis'].append('High number of unique locations detected')
        
        # Check for impossible travel
        if len(locations) > 1:
            for i in range(1, len(locations)):
                prev_loc = locations[i-1]
                curr_loc = locations[i]
                time_diff = (curr_loc['timestamp'] - prev_loc['timestamp']).total_seconds()
                
                # Check if travel is impossible (faster than 500 km/h)
                if time_diff < 3600:  # Less than 1 hour
                    distance = _calculate_distance(prev_loc, curr_loc)
                    if distance > 500000:  # 500km
                        analysis['risk_score'] += 25
                        analysis['analysis'].append('Impossible travel speed detected')
                        break
        
        return analysis
        
    except Exception:
        return {'locations': [], 'risk_score': 0, 'analysis': 'Error analyzing locations'}


def _get_velocity_analysis(user) -> Dict:
    """Get velocity analysis for user."""
    try:
        velocity_data = cache.get(f'velocity_data_{user.id}', {})
        
        if not velocity_data:
            return {'risk_score': 0, 'analysis': 'No velocity data available'}
        
        analysis = {
            'risk_score': 0,
            'analysis': []
        }
        
        # Check task completion velocity
        task_velocity = velocity_data.get('task_completion_velocity', 0)
        if task_velocity > 50:
            analysis['risk_score'] += 20
            analysis['analysis'].append('Extremely high task completion velocity')
        elif task_velocity > 25:
            analysis['risk_score'] += 10
            analysis['analysis'].append('High task completion velocity')
        
        # Check login velocity
        login_velocity = velocity_data.get('login_velocity', 0)
        if login_velocity > 10:
            analysis['risk_score'] += 15
            analysis['analysis'].append('High login frequency')
        
        # Check withdrawal velocity
        withdrawal_velocity = velocity_data.get('withdrawal_velocity', 0)
        if withdrawal_velocity > 5:
            analysis['risk_score'] += 25
            analysis['analysis'].append('High withdrawal request frequency')
        
        return analysis
        
    except Exception:
        return {'risk_score': 0, 'analysis': 'Error analyzing velocity'}


def _create_fraud_event(user_id: int, event_type: str, notes: str, reviewer_id: int):
    """Create fraud event for audit trail."""
    try:
        event = {
            'user_id': user_id,
            'event_type': event_type,
            'notes': notes,
            'reviewer_id': reviewer_id,
            'timestamp': timezone.now().isoformat(),
            'tenant_id': getattr(request, 'tenant_id', None) if 'request' in locals() else None
        }
        
        # Store in cache for audit
        import uuid
        event_id = str(uuid.uuid4())
        cache.set(f'fraud_event_{event_id}', event, timeout=86400 * 30)  # 30 days
        
        return event_id
        
    except Exception:
        return None


def _calculate_distance(loc1: Dict, loc2: Dict) -> float:
    """Calculate distance between two locations (simplified)."""
    try:
        # This is a simplified distance calculation
        # In production, use proper geolocation libraries
        lat1, lon1 = loc1.get('latitude', 0), loc1.get('longitude', 0)
        lat2, lon2 = loc2.get('latitude', 0), loc2.get('longitude', 0)
        
        # Simple Euclidean distance (not accurate for Earth)
        return ((lat2 - lat1) ** 2 + (lon2 - lon1) ** 2) ** 0.5
        
    except Exception:
        return 0
