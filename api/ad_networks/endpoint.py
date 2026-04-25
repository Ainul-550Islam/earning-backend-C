"""
api/ad_networks/endpoint.py
API endpoint utilities for ad networks module
SaaS-ready with tenant support
"""

import logging
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps

from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import (
    AdNetwork, Offer, UserOfferEngagement, OfferConversion,
    OfferReward, UserWallet, OfferClick, NetworkHealthCheck
)
from .choices import OfferStatus, EngagementStatus, ConversionStatus, RewardStatus
from .services import (
    OfferSyncService, ConversionService, RewardService,
    FraudDetectionService, NetworkHealthService, OfferRecommendService
)
from .validators import SecurityValidator, DataValidator
from .decorators import tenant_required, rate_limit, require_verification
from .constants import (
    API_RATE_LIMIT_PER_IP, API_RATE_LIMIT_PER_TENANT,
    CACHE_TIMEOUTS, FRAUD_SCORE_THRESHOLD
)

logger = logging.getLogger(__name__)
User = get_user_model()


class APIResponse:
    """Standard API response class"""
    
    @staticmethod
    def success(data: Any = None, message: str = None, 
                status_code: int = status.HTTP_200_OK) -> JsonResponse:
        """Return success response"""
        response_data = {
            'success': True,
            'message': message or 'Success',
            'data': data,
            'timestamp': timezone.now().isoformat()
        }
        return JsonResponse(response_data, status=status_code)
    
    @staticmethod
    def error(message: str, errors: List[str] = None,
              status_code: int = status.HTTP_400_BAD_REQUEST) -> JsonResponse:
        """Return error response"""
        response_data = {
            'success': False,
            'message': message,
            'errors': errors or [],
            'timestamp': timezone.now().isoformat()
        }
        return JsonResponse(response_data, status=status_code)
    
    @staticmethod
    def validation_errors(errors: Dict[str, List[str]]) -> JsonResponse:
        """Return validation error response"""
        response_data = {
            'success': False,
            'message': 'Validation failed',
            'errors': errors,
            'timestamp': timezone.now().isoformat()
        }
        return JsonResponse(response_data, status=status.HTTP_400_BAD_REQUEST)
    
    @staticmethod
    def paginated(data: List[Any], paginator: PageNumberPagination,
                  request) -> JsonResponse:
        """Return paginated response"""
        response_data = {
            'success': True,
            'data': data,
            'pagination': {
                'count': paginator.page.paginator.count,
                'next': paginator.get_next_link(),
                'previous': paginator.get_previous_link(),
                'page_size': paginator.page_size,
                'current_page': paginator.page.number,
                'total_pages': paginator.page.paginator.num_pages
            },
            'timestamp': timezone.now().isoformat()
        }
        return JsonResponse(response_data)


class APIEndpoint:
    """Base API endpoint class"""
    
    def __init__(self, tenant_id: str = None):
        self.tenant_id = tenant_id or 'default'
        self.security_validator = SecurityValidator()
        self.data_validator = DataValidator()
    
    def validate_request(self, request) -> Dict[str, Any]:
        """Validate API request"""
        validation_result = {
            'valid': True,
            'errors': []
        }
        
        # Check rate limiting
        if not self._check_rate_limit(request):
            validation_result['valid'] = False
            validation_result['errors'].append('Rate limit exceeded')
        
        # Check security
        security_check = self._check_security(request)
        if not security_check['valid']:
            validation_result['valid'] = False
            validation_result['errors'].extend(security_check['errors'])
        
        return validation_result
    
    def _check_rate_limit(self, request) -> bool:
        """Check rate limiting"""
        client_ip = self._get_client_ip(request)
        cache_key = f"api_rate_limit_{client_ip}"
        
        current_count = cache.get(cache_key, 0)
        if current_count >= API_RATE_LIMIT_PER_IP:
            return False
        
        cache.set(cache_key, current_count + 1, timeout=60)
        return True
    
    def _check_security(self, request) -> Dict[str, Any]:
        """Check security measures"""
        result = {'valid': True, 'errors': []}
        
        # Check for SQL injection
        for param, value in request.GET.items():
            if not self.security_validator.validate_sql_injection(value):
                result['valid'] = False
                result['errors'].append(f'Suspicious input in parameter: {param}')
        
        # Check for XSS
        for param, value in request.GET.items():
            if not self.security_validator.validate_xss(value):
                result['valid'] = False
                result['errors'].append(f'XSS detected in parameter: {param}')
        
        return result
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip
        
        return request.META.get('REMOTE_ADDR', '')
    
    def _get_tenant_id(self, request) -> str:
        """Get tenant ID from request"""
        # Try header
        tenant_id = request.META.get('HTTP_X_TENANT_ID')
        if tenant_id:
            return tenant_id
        
        # Try query parameter
        tenant_id = request.GET.get('tenant_id')
        if tenant_id:
            return tenant_id
        
        # Try session
        tenant_id = request.session.get('tenant_id')
        if tenant_id:
            return tenant_id
        
        return 'default'


class OfferEndpoint(APIEndpoint):
    """Offer API endpoint"""
    
    def get_offers(self, request) -> JsonResponse:
        """Get offers list"""
        try:
            # Validate request
            validation = self.validate_request(request)
            if not validation['valid']:
                return APIResponse.error('Invalid request', validation['errors'])
            
            # Get parameters
            tenant_id = self._get_tenant_id(request)
            category_id = request.GET.get('category_id')
            network_id = request.GET.get('network_id')
            min_reward = request.GET.get('min_reward')
            max_reward = request.GET.get('max_reward')
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 20))
            
            # Build queryset
            queryset = Offer.objects.filter(
                tenant_id=tenant_id,
                status=OfferStatus.ACTIVE
            )
            
            if category_id:
                queryset = queryset.filter(category_id=category_id)
            
            if network_id:
                queryset = queryset.filter(ad_network_id=network_id)
            
            if min_reward:
                queryset = queryset.filter(reward_amount__gte=min_reward)
            
            if max_reward:
                queryset = queryset.filter(reward_amount__lte=max_reward)
            
            # Order and paginate
            queryset = queryset.order_by('-priority', '-created_at')
            
            # Apply pagination
            paginator = PageNumberPagination()
            paginator.page_size = page_size
            page_obj = paginator.paginate_queryset(queryset, request)
            
            # Serialize data
            offers_data = []
            for offer in page_obj:
                offers_data.append({
                    'id': offer.id,
                    'title': offer.title,
                    'description': offer.description,
                    'reward_amount': float(offer.reward_amount),
                    'currency': offer.reward_currency,
                    'category': offer.category.name if offer.category else None,
                    'network': offer.ad_network.name,
                    'difficulty': offer.difficulty,
                    'estimated_time': offer.estimated_time,
                    'is_featured': offer.is_featured,
                    'is_hot': offer.is_hot,
                    'is_new': offer.is_new,
                    'created_at': offer.created_at.isoformat()
                })
            
            return APIResponse.paginated(offers_data, paginator, request)
            
        except Exception as e:
            logger.error(f"Error getting offers: {str(e)}")
            return APIResponse.error('Internal server error')
    
    def get_offer_details(self, request, offer_id: int) -> JsonResponse:
        """Get offer details"""
        try:
            # Validate request
            validation = self.validate_request(request)
            if not validation['valid']:
                return APIResponse.error('Invalid request', validation['errors'])
            
            # Get offer
            tenant_id = self._get_tenant_id(request)
            try:
                offer = Offer.objects.get(
                    id=offer_id,
                    tenant_id=tenant_id
                )
            except Offer.DoesNotExist:
                return APIResponse.error('Offer not found', status_code=404)
            
            # Serialize offer data
            offer_data = {
                'id': offer.id,
                'title': offer.title,
                'description': offer.description,
                'short_description': offer.short_description,
                'reward_amount': float(offer.reward_amount),
                'currency': offer.reward_currency,
                'category': offer.category.name if offer.category else None,
                'network': offer.ad_network.name,
                'difficulty': offer.difficulty,
                'estimated_time': offer.estimated_time,
                'requirements': offer.requirements,
                'instructions': offer.instructions,
                'countries': offer.countries,
                'platforms': offer.platforms,
                'device_type': offer.device_type,
                'is_featured': offer.is_featured,
                'is_hot': offer.is_hot,
                'is_new': offer.is_new,
                'preview_url': offer.preview_url,
                'tracking_url': offer.tracking_url,
                'expires_at': offer.expires_at.isoformat() if offer.expires_at else None,
                'created_at': offer.created_at.isoformat(),
                'updated_at': offer.updated_at.isoformat()
            }
            
            return APIResponse.success(offer_data)
            
        except Exception as e:
            logger.error(f"Error getting offer details: {str(e)}")
            return APIResponse.error('Internal server error')
    
    def track_click(self, request, offer_id: int) -> JsonResponse:
        """Track offer click"""
        try:
            # Validate request
            validation = self.validate_request(request)
            if not validation['valid']:
                return APIResponse.error('Invalid request', validation['errors'])
            
            # Get offer
            tenant_id = self._get_tenant_id(request)
            try:
                offer = Offer.objects.get(
                    id=offer_id,
                    tenant_id=tenant_id,
                    status=OfferStatus.ACTIVE
                )
            except Offer.DoesNotExist:
                return APIResponse.error('Offer not found', status_code=404)
            
            # Create click record
            click_data = {
                'offer': offer,
                'ip_address': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'referrer_url': request.META.get('HTTP_REFERER', ''),
                'session_id': request.COOKIES.get('sessionid', ''),
                'tenant_id': tenant_id
            }
            
            # Add user if authenticated
            if request.user.is_authenticated:
                click_data['user'] = request.user
            
            # Check fraud indicators
            fraud_check = self._check_fraud_indicators(request, offer)
            click_data.update(fraud_check)
            
            # Create click
            click = OfferClick.objects.create(**click_data)
            
            # Update click cache
            cache_key = f"offer_clicks_{offer.id}_{tenant_id}"
            current_clicks = cache.get(cache_key, 0)
            cache.set(cache_key, current_clicks + 1, timeout=3600)
            
            return APIResponse.success({
                'click_id': click.id,
                'tracking_url': offer.tracking_url
            }, 'Click tracked successfully')
            
        except Exception as e:
            logger.error(f"Error tracking click: {str(e)}")
            return APIResponse.error('Internal server error')
    
    def _check_fraud_indicators(self, request, offer) -> Dict[str, Any]:
        """Check for fraud indicators"""
        fraud_score = 0
        indicators = []
        
        # Check IP address
        client_ip = self._get_client_ip(request)
        if self._is_suspicious_ip(client_ip):
            fraud_score += 40
            indicators.append('suspicious_ip')
        
        # Check user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if self._is_bot_user_agent(user_agent):
            fraud_score += 30
            indicators.append('bot_user_agent')
        
        # Check request frequency
        if self._is_high_frequency_request(request):
            fraud_score += 25
            indicators.append('high_frequency')
        
        return {
            'fraud_score': min(fraud_score, 100),
            'indicators': indicators,
            'is_suspicious': fraud_score >= FRAUD_SCORE_THRESHOLD
        }
    
    def _is_suspicious_ip(self, ip_address: str) -> bool:
        """Check if IP is suspicious"""
        try:
            from .models import KnownBadIP
            return KnownBadIP.objects.filter(
                ip_address=ip_address,
                is_active=True
            ).exists()
        except:
            return False
    
    def _is_bot_user_agent(self, user_agent: str) -> bool:
        """Check if user agent indicates a bot"""
        bot_indicators = [
            'bot', 'crawler', 'spider', 'scraper', 'curl', 'wget',
            'python-requests', 'httpie', 'postman', 'insomnia'
        ]
        
        user_agent_lower = user_agent.lower()
        return any(indicator in user_agent_lower for indicator in bot_indicators)
    
    def _is_high_frequency_request(self, request) -> bool:
        """Check if request frequency is too high"""
        client_ip = self._get_client_ip(request)
        cache_key = f"request_freq_{client_ip}"
        
        current_count = cache.get(cache_key, 0)
        if current_count > 100:  # More than 100 requests per minute
            return True
        
        cache.set(cache_key, current_count + 1, timeout=60)
        return False


class ConversionEndpoint(APIEndpoint):
    """Conversion API endpoint"""
    
    def create_conversion(self, request) -> JsonResponse:
        """Create new conversion"""
        try:
            # Validate request
            validation = self.validate_request(request)
            if not validation['valid']:
                return APIResponse.error('Invalid request', validation['errors'])
            
            # Get data
            tenant_id = self._get_tenant_id(request)
            data = json.loads(request.body) if request.body else {}
            
            # Validate required fields
            required_fields = ['conversion_id', 'user_id', 'offer_id', 'payout']
            validation_result = self.data_validator.validate_required_fields(
                data, required_fields
            )
            
            if not validation_result['valid']:
                return APIResponse.error(
                    'Missing required fields',
                    validation_result['missing_fields']
                )
            
            # Find engagement
            try:
                engagement = UserOfferEngagement.objects.get(
                    user_id=data['user_id'],
                    offer_id=data['offer_id'],
                    tenant_id=tenant_id
                )
            except UserOfferEngagement.DoesNotExist:
                return APIResponse.error('Engagement not found')
            
            # Check if conversion already exists
            if OfferConversion.objects.filter(
                external_id=data['conversion_id'],
                tenant_id=tenant_id
            ).exists():
                return APIResponse.error('Conversion already exists')
            
            # Create conversion
            conversion = OfferConversion.objects.create(
                external_id=data['conversion_id'],
                engagement=engagement,
                payout=data['payout'],
                currency=data.get('currency', 'USD'),
                conversion_status=ConversionStatus.PENDING,
                conversion_data=data.get('conversion_data', {}),
                tenant_id=tenant_id
            )
            
            # Calculate fraud score
            fraud_score = self._calculate_fraud_score(conversion, request)
            conversion.fraud_score = fraud_score
            conversion.save(update_fields=['fraud_score'])
            
            return APIResponse.success({
                'conversion_id': conversion.id,
                'fraud_score': fraud_score,
                'is_suspicious': fraud_score >= FRAUD_SCORE_THRESHOLD
            }, 'Conversion created successfully')
            
        except json.JSONDecodeError:
            return APIResponse.error('Invalid JSON data')
        except Exception as e:
            logger.error(f"Error creating conversion: {str(e)}")
            return APIResponse.error('Internal server error')
    
    def get_conversion_details(self, request, conversion_id: int) -> JsonResponse:
        """Get conversion details"""
        try:
            # Validate request
            validation = self.validate_request(request)
            if not validation['valid']:
                return APIResponse.error('Invalid request', validation['errors'])
            
            # Get conversion
            tenant_id = self._get_tenant_id(request)
            try:
                conversion = OfferConversion.objects.get(
                    id=conversion_id,
                    tenant_id=tenant_id
                )
            except OfferConversion.DoesNotExist:
                return APIResponse.error('Conversion not found', status_code=404)
            
            # Serialize conversion data
            conversion_data = {
                'id': conversion.id,
                'external_id': conversion.external_id,
                'engagement_id': conversion.engagement.id,
                'user_id': conversion.engagement.user.id,
                'offer_id': conversion.engagement.offer.id,
                'payout': float(conversion.payout),
                'currency': conversion.currency,
                'conversion_status': conversion.conversion_status,
                'fraud_score': conversion.fraud_score,
                'is_fraudulent': conversion.fraud_score >= FRAUD_SCORE_THRESHOLD,
                'approved_at': conversion.approved_at.isoformat() if conversion.approved_at else None,
                'rejected_at': conversion.rejected_at.isoformat() if conversion.rejected_at else None,
                'chargeback_at': conversion.chargeback_at.isoformat() if conversion.chargeback_at else None,
                'verification_notes': conversion.verification_notes,
                'rejection_reason': conversion.rejection_reason,
                'conversion_data': conversion.conversion_data,
                'created_at': conversion.created_at.isoformat(),
                'updated_at': conversion.updated_at.isoformat()
            }
            
            return APIResponse.success(conversion_data)
            
        except Exception as e:
            logger.error(f"Error getting conversion details: {str(e)}")
            return APIResponse.error('Internal server error')
    
    def _calculate_fraud_score(self, conversion, request) -> float:
        """Calculate fraud score for conversion"""
        score = 0.0
        
        # Check completion time
        if conversion.engagement.started_at and conversion.engagement.completed_at:
            completion_time = conversion.engagement.completed_at - conversion.engagement.started_at
            if completion_time.total_seconds() < 60:  # Less than 1 minute
                score += 30
            elif completion_time.total_seconds() < 300:  # Less than 5 minutes
                score += 15
        
        # Check payout amount
        if conversion.payout > 100:
            score += 25
        elif conversion.payout > 50:
            score += 10
        
        # Check IP address
        client_ip = self._get_client_ip(request)
        if self._is_suspicious_ip(client_ip):
            score += 40
        
        return min(score, 100.0)


class RewardEndpoint(APIEndpoint):
    """Reward API endpoint"""
    
    def get_user_rewards(self, request, user_id: int) -> JsonResponse:
        """Get user rewards"""
        try:
            # Validate request
            validation = self.validate_request(request)
            if not validation['valid']:
                return APIResponse.error('Invalid request', validation['errors'])
            
            # Get rewards
            tenant_id = self._get_tenant_id(request)
            rewards = OfferReward.objects.filter(
                user_id=user_id,
                tenant_id=tenant_id
            ).order_by('-created_at')
            
            # Serialize rewards data
            rewards_data = []
            for reward in rewards:
                rewards_data.append({
                    'id': reward.id,
                    'offer_id': reward.offer.id,
                    'offer_title': reward.offer.title,
                    'amount': float(reward.amount),
                    'currency': reward.currency,
                    'status': reward.status,
                    'approved_at': reward.approved_at.isoformat() if reward.approved_at else None,
                    'paid_at': reward.paid_at.isoformat() if reward.paid_at else None,
                    'payment_reference': reward.payment_reference,
                    'reason': reward.reason,
                    'cancellation_reason': reward.cancellation_reason,
                    'created_at': reward.created_at.isoformat()
                })
            
            return APIResponse.success(rewards_data)
            
        except Exception as e:
            logger.error(f"Error getting user rewards: {str(e)}")
            return APIResponse.error('Internal server error')
    
    def get_wallet_balance(self, request, user_id: int) -> JsonResponse:
        """Get user wallet balance"""
        try:
            # Validate request
            validation = self.validate_request(request)
            if not validation['valid']:
                return APIResponse.error('Invalid request', validation['errors'])
            
            # Get or create wallet
            tenant_id = self._get_tenant_id(request)
            wallet, created = UserWallet.objects.get_or_create(
                user_id=user_id,
                defaults={
                    'balance': Decimal('0.00'),
                    'total_earned': Decimal('0.00'),
                    'currency': 'USD',
                    'tenant_id': tenant_id
                }
            )
            
            # Calculate pending rewards
            pending_amount = OfferReward.objects.filter(
                user_id=user_id,
                status=RewardStatus.PENDING,
                tenant_id=tenant_id
            ).aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0.00')
            
            wallet_data = {
                'balance': float(wallet.balance),
                'total_earned': float(wallet.total_earned),
                'pending_rewards': float(pending_amount),
                'currency': wallet.currency,
                'available_balance': float(wallet.balance)
            }
            
            return APIResponse.success(wallet_data)
            
        except Exception as e:
            logger.error(f"Error getting wallet balance: {str(e)}")
            return APIResponse.error('Internal server error')


# Decorator for API endpoints
def api_endpoint(endpoint_class):
    """Decorator to create API endpoint from class"""
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Get tenant ID
            tenant_id = getattr(request, 'tenant_id', 'default')
            
            # Create endpoint instance
            endpoint = endpoint_class(tenant_id)
            
            # Call the function
            return func(endpoint, request, *args, **kwargs)
        
        return wrapper
    return decorator


# Export all classes and functions
__all__ = [
    # Classes
    'APIResponse',
    'APIEndpoint',
    'OfferEndpoint',
    'ConversionEndpoint',
    'RewardEndpoint',
    
    # Decorator
    'api_endpoint'
]
