# api/users/admin_views.py (Admin Dashboard APIs)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

# Import models
from api.users.models import (
    DeviceFingerprint,
    IPReputation,
    UserAccountLink,
    FraudDetectionLog,
    RiskScoreHistory,
    RateLimitTracker,
    UserBehavior
)

# Import services
from api.users.services.multi_account_detector import multi_account_detector
from api.users.services.risk_scoring import risk_scoring_engine


# ==========================================
# Dashboard Overview
# ==========================================
@api_view(['GET'])
@permission_classes([IsAdminUser])
def fraud_dashboard_overview(request):
    """
    Get fraud detection dashboard overview
    
    GET /api/admin/fraud/dashboard/
    """
    # Time ranges
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)
    
    # Total statistics
    total_users = User.objects.count()
    total_devices = DeviceFingerprint.objects.count()
    total_ips = IPReputation.objects.count()
    
    # Recent registrations
    registrations_24h = UserAccountLink.objects.filter(
        registration_date__gte=last_24h
    ).count()
    
    registrations_7d = UserAccountLink.objects.filter(
        registration_date__gte=last_7d
    ).count()
    
    # Fraud statistics
    fraud_events_24h = FraudDetectionLog.objects.filter(
        detected_at__gte=last_24h
    ).count()
    
    fraud_events_7d = FraudDetectionLog.objects.filter(
        detected_at__gte=last_7d
    ).count()
    
    # High-risk users
    high_risk_users = UserAccountLink.objects.filter(
        risk_score__gte=61
    ).count()
    
    flagged_users = UserAccountLink.objects.filter(
        is_flagged=True
    ).count()
    
    # Blocked entities
    blocked_devices = DeviceFingerprint.objects.filter(is_blocked=True).count()
    blocked_ips = IPReputation.objects.filter(is_blacklisted=True).count()
    suspicious_devices = DeviceFingerprint.objects.filter(is_suspicious=True).count()
    
    # VPN/Proxy statistics
    vpn_users = IPReputation.objects.filter(is_vpn=True).count()
    proxy_users = IPReputation.objects.filter(is_proxy=True).count()
    tor_users = IPReputation.objects.filter(is_tor=True).count()
    
    # Multi-account statistics
    multi_account_devices = DeviceFingerprint.objects.filter(
        total_accounts__gte=3
    ).count()
    
    # Critical events
    critical_events = FraudDetectionLog.objects.filter(
        severity='critical',
        is_resolved=False
    ).count()
    
    return Response({
        'overview': {
            'total_users': total_users,
            'total_devices': total_devices,
            'total_ips': total_ips,
            'registrations_24h': registrations_24h,
            'registrations_7d': registrations_7d,
        },
        'fraud_stats': {
            'events_24h': fraud_events_24h,
            'events_7d': fraud_events_7d,
            'high_risk_users': high_risk_users,
            'flagged_users': flagged_users,
            'critical_events': critical_events,
        },
        'blocked': {
            'devices': blocked_devices,
            'ips': blocked_ips,
            'suspicious_devices': suspicious_devices,
        },
        'vpn_proxy': {
            'vpn': vpn_users,
            'proxy': proxy_users,
            'tor': tor_users,
        },
        'multi_account': {
            'devices_with_multiple': multi_account_devices,
        }
    })


# ==========================================
# Recent Fraud Events
# ==========================================
@api_view(['GET'])
@permission_classes([IsAdminUser])
def recent_fraud_events(request):
    """
    Get recent fraud detection events
    
    GET /api/admin/fraud/events/?limit=50&severity=high
    """
    limit = int(request.GET.get('limit', 50))
    severity = request.GET.get('severity', None)
    event_type = request.GET.get('event_type', None)
    
    events = FraudDetectionLog.objects.all()
    
    if severity:
        events = events.filter(severity=severity)
    
    if event_type:
        events = events.filter(event_type=event_type)
    
    events = events.order_by('-detected_at')[:limit]
    
    events_data = []
    for event in events:
        events_data.append({
            'id': event.id,
            'event_type': event.event_type,
            'severity': event.severity,
            'description': event.description,
            'ip_address': event.ip_address,
            'user': {
                'id': event.user.id,
                'username': event.user.username,
            } if event.user else None,
            'action_taken': event.action_taken,
            'is_resolved': event.is_resolved,
            'detected_at': event.detected_at.isoformat(),
            'metadata': event.metadata,
        })
    
    return Response({
        'events': events_data,
        'total': len(events_data)
    })


# ==========================================
# High-Risk Users
# ==========================================
@api_view(['GET'])
@permission_classes([IsAdminUser])
def high_risk_users(request):
    """
    Get list of high-risk users
    
    GET /api/admin/fraud/high-risk-users/?min_score=61
    """
    min_score = int(request.GET.get('min_score', 61))
    
    high_risk = UserAccountLink.objects.filter(
        risk_score__gte=min_score
    ).select_related('user', 'device', 'ip_reputation').order_by('-risk_score')
    
    users_data = []
    for link in high_risk:
        # Get latest risk history
        latest_history = RiskScoreHistory.objects.filter(
            user=link.user
        ).first()
        
        users_data.append({
            'user': {
                'id': link.user.id,
                'username': link.user.username,
                'email': link.user.email,
                'is_active': link.user.is_active,
                'date_joined': link.user.date_joined.isoformat(),
            },
            'risk_score': link.risk_score,
            'is_flagged': link.is_flagged,
            'flag_reason': link.flag_reason,
            'registration_ip': link.registration_ip,
            'registration_date': link.registration_date.isoformat(),
            'device_accounts': link.device.total_accounts,
            'ip_reputation': link.ip_reputation.reputation,
            'risk_factors': latest_history.factors if latest_history else {},
        })
    
    return Response({
        'high_risk_users': users_data,
        'total': len(users_data)
    })


# ==========================================
# Multi-Account Analysis
# ==========================================
@api_view(['GET'])
@permission_classes([IsAdminUser])
def multi_account_analysis(request):
    """
    Get multi-account analysis
    
    GET /api/admin/fraud/multi-account/
    """
    # Devices with multiple accounts
    multi_devices = DeviceFingerprint.objects.filter(
        total_accounts__gte=3
    ).order_by('-total_accounts')[:50]
    
    devices_data = []
    for device in multi_devices:
        # Get accounts on this device
        accounts = UserAccountLink.objects.filter(
            device=device
        ).select_related('user')
        
        devices_data.append({
            'device_hash': device.fingerprint_hash[:16],
            'total_accounts': device.total_accounts,
            'is_suspicious': device.is_suspicious,
            'is_blocked': device.is_blocked,
            'first_seen': device.first_seen.isoformat(),
            'last_seen': device.last_seen.isoformat(),
            'accounts': [
                {
                    'user_id': acc.user.id,
                    'username': acc.user.username,
                    'email': acc.user.email,
                    'registration_date': acc.registration_date.isoformat(),
                    'risk_score': acc.risk_score,
                }
                for acc in accounts[:10]  # Limit to 10
            ]
        })
    
    # IPs with multiple accounts
    multi_ips = IPReputation.objects.annotate(
        account_count=Count('users')
    ).filter(account_count__gte=5).order_by('-account_count')[:50]
    
    ips_data = []
    for ip in multi_ips:
        accounts = UserAccountLink.objects.filter(
            ip_reputation=ip
        ).select_related('user')
        
        ips_data.append({
            'ip_address': ip.ip_address,
            'account_count': ip.total_registrations,
            'reputation': ip.reputation,
            'is_vpn': ip.is_vpn,
            'is_proxy': ip.is_proxy,
            'is_blacklisted': ip.is_blacklisted,
            'country': ip.country_code,
            'accounts': [
                {
                    'user_id': acc.user.id,
                    'username': acc.user.username,
                    'registration_date': acc.registration_date.isoformat(),
                }
                for acc in accounts[:10]
            ]
        })
    
    return Response({
        'multi_account_devices': devices_data,
        'multi_account_ips': ips_data,
    })


# ==========================================
# User Risk Profile
# ==========================================
@api_view(['GET'])
@permission_classes([IsAdminUser])
def user_risk_profile(request, user_id):
    """
    Get detailed risk profile for a user
    
    GET /api/admin/fraud/user/<user_id>/profile/
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({
            'error': 'User not found'
        }, status=404)
    
    # Get account link
    account_link = UserAccountLink.objects.filter(user=user).first()
    
    if not account_link:
        return Response({
            'error': 'No account link found'
        }, status=404)
    
    # Get risk trend
    risk_trend = risk_scoring_engine.get_user_risk_trend(user, days=30)
    
    # Get related accounts
    related = multi_account_detector.get_related_accounts(
        device=account_link.device,
        ip_reputation=account_link.ip_reputation
    )
    
    # Get account network
    network = multi_account_detector.get_account_network(user)
    
    # Get fraud events for this user
    fraud_events = FraudDetectionLog.objects.filter(
        user=user
    ).order_by('-detected_at')[:20]
    
    events_data = [
        {
            'event_type': event.event_type,
            'severity': event.severity,
            'description': event.description,
            'detected_at': event.detected_at.isoformat(),
        }
        for event in fraud_events
    ]
    
    return Response({
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_active': user.is_active,
            'date_joined': user.date_joined.isoformat(),
        },
        'risk_profile': {
            'current_score': account_link.risk_score,
            'is_flagged': account_link.is_flagged,
            'flag_reason': account_link.flag_reason,
            'trend': risk_trend,
        },
        'registration': {
            'ip': account_link.registration_ip,
            'date': account_link.registration_date.isoformat(),
            'device_hash': account_link.device.fingerprint_hash[:16],
        },
        'ip_reputation': {
            'reputation': account_link.ip_reputation.reputation,
            'is_vpn': account_link.ip_reputation.is_vpn,
            'is_proxy': account_link.ip_reputation.is_proxy,
            'is_tor': account_link.ip_reputation.is_tor,
            'is_blacklisted': account_link.ip_reputation.is_blacklisted,
        },
        'device_info': {
            'total_accounts': account_link.device.total_accounts,
            'is_suspicious': account_link.device.is_suspicious,
            'is_blocked': account_link.device.is_blocked,
        },
        'related_accounts': related,
        'network': network,
        'fraud_events': events_data,
    })


# ==========================================
# Block/Unblock Actions
# ==========================================
@api_view(['POST'])
@permission_classes([IsAdminUser])
def block_device(request):
    """
    Block a device
    
    POST /api/admin/fraud/device/block/
    Body: {"device_hash": "abc123..."}
    """
    device_hash = request.data.get('device_hash')
    
    try:
        device = DeviceFingerprint.objects.get(fingerprint_hash=device_hash)
        device.is_blocked = True
        device.save()
        
        return Response({
            'success': True,
            'message': f'Device {device_hash[:16]} blocked'
        })
    except DeviceFingerprint.DoesNotExist:
        return Response({
            'error': 'Device not found'
        }, status=404)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def block_ip(request):
    """
    Block an IP address
    
    POST /api/admin/fraud/ip/block/
    Body: {"ip_address": "1.2.3.4", "reason": "Suspicious activity"}
    """
    ip_address = request.data.get('ip_address')
    reason = request.data.get('reason', 'Manually blocked by admin')
    
    try:
        ip_rep = IPReputation.objects.get(ip_address=ip_address)
        ip_rep.is_blacklisted = True
        ip_rep.blacklist_reason = reason
        ip_rep.reputation = 'blocked'
        ip_rep.save()
        
        return Response({
            'success': True,
            'message': f'IP {ip_address} blocked'
        })
    except IPReputation.DoesNotExist:
        # Create new entry
        IPReputation.objects.create(
            ip_address=ip_address,
            is_blacklisted=True,
            blacklist_reason=reason,
            reputation='blocked'
        )
        
        return Response({
            'success': True,
            'message': f'IP {ip_address} blocked'
        })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def unblock_ip(request):
    """
    Unblock an IP address
    
    POST /api/admin/fraud/ip/unblock/
    Body: {"ip_address": "1.2.3.4"}
    """
    ip_address = request.data.get('ip_address')
    
    try:
        ip_rep = IPReputation.objects.get(ip_address=ip_address)
        ip_rep.is_blacklisted = False
        ip_rep.blacklist_reason = None
        ip_rep.reputation = 'neutral'
        ip_rep.save()
        
        return Response({
            'success': True,
            'message': f'IP {ip_address} unblocked'
        })
    except IPReputation.DoesNotExist:
        return Response({
            'error': 'IP not found'
        }, status=404)


# ==========================================
# Statistics & Charts
# ==========================================
@api_view(['GET'])
@permission_classes([IsAdminUser])
def fraud_statistics(request):
    """
    Get fraud statistics for charts
    
    GET /api/admin/fraud/statistics/?days=30
    """
    days = int(request.GET.get('days', 30))
    cutoff = timezone.now() - timedelta(days=days)
    
    # Daily fraud events
    daily_events = FraudDetectionLog.objects.filter(
        detected_at__gte=cutoff
    ).extra({'date': 'date(detected_at)'}).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Events by severity
    by_severity = FraudDetectionLog.objects.filter(
        detected_at__gte=cutoff
    ).values('severity').annotate(count=Count('id'))
    
    # Events by type
    by_type = FraudDetectionLog.objects.filter(
        detected_at__gte=cutoff
    ).values('event_type').annotate(count=Count('id'))
    
    return Response({
        'daily_events': list(daily_events),
        'by_severity': list(by_severity),
        'by_type': list(by_type),
    })