# api/users/views.py (Complete Registration with Fraud Prevention)

import json
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

# Import our fraud prevention services
from api.users.services.vpn_detector import vpn_detector
from api.users.services.device_fingerprint import device_fingerprint_service
from api.users.services.risk_scoring import risk_scoring_engine
from api.users.services.multi_account_detector import multi_account_detector
from api.users.services.risk_scoring import RiskScoringEngine
# Import models
from api.users.models import (
    DeviceFingerprint,
    IPReputation,
    UserAccountLink,
    FraudDetectionLog,
    RateLimitTracker,
    UserBehavior
)


def get_client_ip(request):
    """Extract client IP from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@method_decorator(csrf_exempt, name='dispatch')
class UserRegistrationView(View):
    """
    Complete User Registration with Advanced Fraud Prevention
    
    POST /api/register/
    Body: {
        "username": "john_doe",
        "email": "john@example.com",
        "password": "secure_password",
        "device_fingerprint": {...}  # From JavaScript
    }
    """
    
    def post(self, request):
        try:
            # Parse request data
            data = json.loads(request.body)
            username = data.get('username')
            email = data.get('email')
            password = data.get('password')
            device_fp_data = data.get('device_fingerprint')
            
            # Validation
            if not all([username, email, password]):
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required fields'
                }, status=400)
            
            # Get client IP
            ip_address = get_client_ip(request)
            
            # ====================================
            # FRAUD PREVENTION PIPELINE
            # ====================================
            
            # Step 1: Rate Limiting Check
            rate_limit_result = self._check_rate_limit(ip_address)
            if rate_limit_result['blocked']:
                return JsonResponse({
                    'success': False,
                    'error': 'Rate limit exceeded. Please try again later.',
                    'blocked_until': rate_limit_result.get('blocked_until')
                }, status=429)
            
            # Step 2: Device Fingerprinting
            device = device_fingerprint_service.generate_fingerprint(
                request, 
                device_fp_data
            )
            
            # Check if device is blocked
            if device.is_blocked:
                self._log_fraud_event(
                    event_type='device_banned',
                    severity='high',
                    ip_address=ip_address,
                    device=device,
                    description='Blocked device attempted registration'
                )
                return JsonResponse({
                    'success': False,
                    'error': 'This device has been blocked due to suspicious activity'
                }, status=403)
            
            # Step 3: IP Reputation Check
            ip_reputation = self._get_or_create_ip_reputation(ip_address)
            
            # Check if IP is blacklisted
            if ip_reputation.is_blacklisted:
                self._log_fraud_event(
                    event_type='ip_banned',
                    severity='high',
                    ip_address=ip_address,
                    ip_reputation=ip_reputation,
                    description='Blacklisted IP attempted registration'
                )
                return JsonResponse({
                    'success': False,
                    'error': 'This IP address has been blocked'
                }, status=403)
            
            # Step 4: VPN/Proxy Detection
            vpn_result = vpn_detector.detect_vpn(ip_address)
            
            # Update IP reputation with VPN info
            ip_reputation.is_vpn = vpn_result.get('is_vpn', False)
            ip_reputation.is_proxy = vpn_result.get('is_proxy', False)
            ip_reputation.is_tor = vpn_result.get('is_tor', False)
            ip_reputation.is_datacenter = vpn_result.get('is_datacenter', False)
            ip_reputation.save()
            
            # Block Tor users immediately
            if vpn_result.get('is_tor'):
                ip_reputation.is_blacklisted = True
                ip_reputation.blacklist_reason = "Tor network detected"
                ip_reputation.save()
                
                self._log_fraud_event(
                    event_type='proxy_detected',
                    severity='critical',
                    ip_address=ip_address,
                    ip_reputation=ip_reputation,
                    description='Tor network detected',
                    metadata=vpn_result
                )
                
                return JsonResponse({
                    'success': False,
                    'error': 'Registration from Tor network is not allowed'
                }, status=403)
            
            # Step 5: Multi-Account Detection
            multi_account_result = multi_account_detector.check_multi_account(
                device, 
                ip_reputation
            )
            
            # Step 6: Calculate Risk Score
            risk_result = risk_scoring_engine.calculate_risk_score(
                user=None,  # No user yet
                device=device,
                ip_reputation=ip_reputation,
                vpn_detection_result=vpn_result
            )
            
            risk_score = risk_result['total_score']
            risk_level = risk_result['risk_level']
            
            # Step 7: Decision Making
            should_block = False
            should_require_verification = False
            block_reason = None
            
            # Critical risk = Auto-block
            if risk_score >= 86:
                should_block = True
                block_reason = "Critical risk score detected"
            
            # Multi-account with high severity = Block
            elif multi_account_result['should_block']:
                should_block = True
                block_reason = "Multiple account abuse detected"
            
            # High risk = Require verification
            elif risk_score >= 61:
                should_require_verification = True
            
            # VPN/Proxy = Require verification
            elif vpn_result.get('is_vpn') or vpn_result.get('is_proxy'):
                should_require_verification = True
            
            # BLOCK if necessary
            if should_block:
                self._log_fraud_event(
                    event_type='high_risk_score',
                    severity='critical',
                    ip_address=ip_address,
                    device=device,
                    ip_reputation=ip_reputation,
                    description=f'Registration blocked: {block_reason}',
                    metadata={
                        'risk_score': risk_score,
                        'risk_level': risk_level,
                        'vpn_result': vpn_result,
                        'multi_account': multi_account_result
                    }
                )
                
                return JsonResponse({
                    'success': False,
                    'error': 'Registration cannot be completed at this time',
                    'reason': 'Suspicious activity detected'
                }, status=403)
            
            # Step 8: Create User (with transaction)
            with transaction.atomic():
                # Check if user already exists
                if User.objects.filter(username=username).exists():
                    return JsonResponse({
                        'success': False,
                        'error': 'Username already exists'
                    }, status=400)
                
                if User.objects.filter(email=email).exists():
                    return JsonResponse({
                        'success': False,
                        'error': 'Email already exists'
                    }, status=400)
                
                # Create user
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )
                
                # If requires verification, set user as inactive
                if should_require_verification:
                    user.is_active = False
                    user.save()
                
                # Create UserAccountLink
                account_link = UserAccountLink.objects.create(
                    user=user,
                    device=device,
                    ip_reputation=ip_reputation,
                    registration_ip=ip_address,
                    risk_score=risk_score,
                    is_flagged=should_require_verification,
                    flag_reason=f"Risk level: {risk_level}" if should_require_verification else None
                )
                
                # Update device account count
                device.increment_account_count()
                
                # Update IP registration count
                ip_reputation.increment_registration()
                
                # Create UserBehavior profile
                UserBehavior.objects.create(user=user)
                
                # Log successful registration with risk info
                self._log_fraud_event(
                    event_type='anomaly_detected' if should_require_verification else 'suspicious_ip',
                    severity='medium' if should_require_verification else 'low',
                    user=user,
                    device=device,
                    ip_reputation=ip_reputation,
                    ip_address=ip_address,
                    description=f'New registration - Risk: {risk_level}',
                    metadata={
                        'risk_score': risk_score,
                        'requires_verification': should_require_verification
                    }
                )
                
                # Log multi-account if detected
                if multi_account_result['is_multi_account']:
                    multi_account_detector.log_multi_account_detection(
                        user, device, ip_reputation, multi_account_result
                    )
            
            # Prepare response
            response_data = {
                'success': True,
                'message': 'Registration successful',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'is_active': user.is_active
                },
                'fraud_check': {
                    'risk_score': risk_score,
                    'risk_level': risk_level,
                    'requires_verification': should_require_verification,
                    'vpn_detected': vpn_result.get('is_vpn', False),
                    'proxy_detected': vpn_result.get('is_proxy', False),
                }
            }
            
            # Add verification message if needed
            if should_require_verification:
                response_data['message'] = 'Registration successful. Email verification required.'
                response_data['verification_required'] = True
            
            return JsonResponse(response_data, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Server error: {str(e)}'
            }, status=500)
    
    def _check_rate_limit(self, ip_address):
        """Check and update rate limiting"""
        from django.utils import timezone
        from datetime import timedelta
        
        identifier = f"ip_{ip_address}"
        tracker, created = RateLimitTracker.objects.get_or_create(
            identifier=identifier,
            limit_type='registration'
        )
        
        # Check if currently blocked
        if tracker.is_blocked and tracker.block_until:
            if timezone.now() < tracker.block_until:
                return {
                    'blocked': True,
                    'blocked_until': tracker.block_until.isoformat()
                }
            else:
                # Unblock
                tracker.is_blocked = False
                tracker.block_until = None
                tracker.request_count = 0
                tracker.save()
        
        # Increment and check limit
        is_blocked = tracker.increment_request()
        
        return {
            'blocked': is_blocked,
            'blocked_until': tracker.block_until.isoformat() if tracker.block_until else None
        }
    
    def _get_or_create_ip_reputation(self, ip_address):
        """Get or create IP reputation record"""
        ip_rep, created = IPReputation.objects.get_or_create(
            ip_address=ip_address,
            defaults={'reputation': 'neutral'}
        )
        return ip_rep
    
    def _log_fraud_event(self, event_type, severity, ip_address, 
                        user=None, device=None, ip_reputation=None, 
                        description='', metadata=None):
        """Log fraud detection event"""
        try:
            FraudDetectionLog.objects.create(
                event_type=event_type,
                severity=severity,
                user=user,
                device=device,
                ip_reputation=ip_reputation,
                ip_address=ip_address,
                description=description,
                metadata=metadata or {}
            )
        except Exception as e:
            print(f"Error logging fraud event: {e}")


# For DRF compatibility, create an API view wrapper
@api_view(['POST'])
def register_user_api(request):
    """DRF-compatible registration endpoint"""
    view = UserRegistrationView()
    return view.post(request)