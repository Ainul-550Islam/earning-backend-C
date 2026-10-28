# api/cms/endpoint.py
"""API endpoint utilities and base classes for CMS."""
import logging
from typing import Any, Dict, List, Optional, Type, Union
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage
from django.db.models import QuerySet
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework import permissions, serializers

logger = logging.getLogger(__name__)

# ── Original Endpoint Registry (Enhanced) ─────────────────────────────────────

API_PREFIX = "/api/cms"

ENDPOINTS = {
    # ── Core CMS ─────────────────────────────────────────────────
    "health":                   f"{API_PREFIX}/health/",
    "integration_status":       f"{API_PREFIX}/integration/status/",

    # ── CPAlead / Offerwall ───────────────────────────────────────
    "cpalead_postback":         f"{API_PREFIX}/webhooks/cpalead/",
    "cpalead_postback_v2":      f"{API_PREFIX}/webhooks/cpalead/v2/",
    "offerwall_embed":          f"{API_PREFIX}/offerwall/embed/",
    "offerwall_offers":         f"{API_PREFIX}/offerwall/offers/",
    "offerwall_click":          f"{API_PREFIX}/offerwall/click/",
    "offerwall_balance":        f"{API_PREFIX}/offerwall/balance/",
    "offerwall_history":        f"{API_PREFIX}/offerwall/history/",

    # ── Content Locker ────────────────────────────────────────────
    "locker_check":             f"{API_PREFIX}/lockers/{{id}}/check/",
    "locker_unlock":            f"{API_PREFIX}/lockers/{{id}}/unlock/",

    # ── Referral ──────────────────────────────────────────────────
    "referral_stats":           f"{API_PREFIX}/referral/stats/",
    "referral_referred":        f"{API_PREFIX}/referral/referred/",
    "referral_apply":           f"{API_PREFIX}/referral/apply/",

    # ── Leaderboard ───────────────────────────────────────────────
    "leaderboard_top":          f"{API_PREFIX}/leaderboard/top/",
    "leaderboard_my_rank":      f"{API_PREFIX}/leaderboard/my_rank/",
    "leaderboard_streak":       f"{API_PREFIX}/leaderboard/streak/",
    "leaderboard_milestones":   f"{API_PREFIX}/leaderboard/milestones/",

    # ── Quiz ──────────────────────────────────────────────────────
    "quiz_list":                f"{API_PREFIX}/quiz/list_quizzes/",
    "quiz_start":               f"{API_PREFIX}/quiz/{{id}}/start/",
    "quiz_submit":              f"{API_PREFIX}/quiz/{{id}}/attempts/{{attempt_id}}/submit/",

    # ── SmartLink ─────────────────────────────────────────────────
    "smartlink_resolve":        f"{API_PREFIX}/smartlinks/{{slug}}/resolve/",
    "smartlink_analytics":      f"{API_PREFIX}/smartlinks/{{slug}}/analytics/",

    # ── Withdrawal ────────────────────────────────────────────────
    "withdrawal_history":       f"{API_PREFIX}/withdrawals/history/",
    "withdrawal_request":       f"{API_PREFIX}/withdrawals/request_payout/",
    "withdrawal_methods":       f"{API_PREFIX}/withdrawals/methods/",
    "withdrawal_add_method":    f"{API_PREFIX}/withdrawals/add_method/",
    "withdrawal_stats":         f"{API_PREFIX}/withdrawals/stats/",

    # ── Survey Management (New) ─────────────────────────────────────
    "survey_list":              f"{API_PREFIX}/surveys/",
    "survey_detail":            f"{API_PREFIX}/surveys/{{id}}/",
    "survey_start":             f"{API_PREFIX}/surveys/{{id}}/start/",
    "survey_submit":            f"{API_PREFIX}/surveys/{{id}}/submit/",
    "survey_recommendations":    f"{API_PREFIX}/surveys/recommendations/",

    # ── Reward Management (New) ───────────────────────────────────
    "reward_history":           f"{API_PREFIX}/rewards/history/",
    "reward_summary":           f"{API_PREFIX}/rewards/summary/",
    "reward_payout":            f"{API_PREFIX}/rewards/payout/",
    "reward_pools":             f"{API_PREFIX}/rewards/pools/",

    # ── User Profile (New) ─────────────────────────────────────────
    "profile_view":             f"{API_PREFIX}/profile/",
    "profile_update":           f"{API_PREFIX}/profile/update/",
    "profile_completeness":     f"{API_PREFIX}/profile/completeness/",
    "profile_segments":         f"{API_PREFIX}/profile/segments/",

    # ── Analytics (New) ───────────────────────────────────────────
    "analytics_dashboard":       f"{API_PREFIX}/analytics/dashboard/",
    "analytics_reports":        f"{API_PREFIX}/analytics/reports/",
    "analytics_export":         f"{API_PREFIX}/analytics/export/",

    # ── Task Management (New) ─────────────────────────────────────
    "task_list":                f"{API_PREFIX}/tasks/",
    "task_execute":             f"{API_PREFIX}/tasks/{{id}}/execute/",
    "task_history":            f"{API_PREFIX}/tasks/history/",
    "task_status":             f"{API_PREFIX}/tasks/{{id}}/status/",

    # ── Webhooks (New) ───────────────────────────────────────────────
    "webhook_list":             f"{API_PREFIX}/webhooks/",
    "webhook_create":           f"{API_PREFIX}/webhooks/create/",
    "webhook_detail":           f"{API_PREFIX}/webhooks/{{id}}/",
    "webhook_test":            f"{API_PREFIX}/webhooks/{{id}}/test/",
    "webhook_deliveries":      f"{API_PREFIX}/webhooks/{{id}}/deliveries/",
}


# ── Base Endpoint Classes ─────────────────────────────────────

class CMSEndpoint(APIView):
    """Base API endpoint for CMS with common functionality."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get_success_response(self, data: Any = None, message: str = "Success", 
                          status_code: int = status.HTTP_200_OK) -> Response:
        """Return standardized success response."""
        response_data = {
            'success': True,
            'message': message,
            'timestamp': timezone.now().isoformat()
        }
        
        if data is not None:
            response_data['data'] = data
        
        return Response(response_data, status=status_code)
    
    def get_error_response(self, message: str, error_code: str = None, 
                         status_code: int = status.HTTP_400_BAD_REQUEST, 
                         details: Dict[str, Any] = None) -> Response:
        """Return standardized error response."""
        response_data = {
            'success': False,
            'error': message,
            'timestamp': timezone.now().isoformat()
        }
        
        if error_code:
            response_data['error_code'] = error_code
        
        if details:
            response_data['details'] = details
        
        return Response(response_data, status=status_code)
    
    def get_paginated_response(self, queryset: QuerySet, page: int = 1, 
                           page_size: int = 20) -> Response:
        """Return paginated response."""
        paginator = Paginator(queryset, page_size)
        
        try:
            page_obj = paginator.page(page)
        except EmptyPage:
            return self.get_error_response(
                "Page not found",
                error_code="page_not_found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(page_obj.object_list, many=True)
        
        return self.get_success_response({
            'items': serializer.data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'items_per_page': page_size,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        })


# ── Endpoint Utilities ─────────────────────────────────────

def get_endpoint_url(endpoint_name: str, **kwargs) -> str:
    """Get full URL for an endpoint."""
    if endpoint_name not in ENDPOINTS:
        raise ValueError(f"Endpoint '{endpoint_name}' not found")
    
    url = ENDPOINTS[endpoint_name]
    
    # Replace URL parameters
    for key, value in kwargs.items():
        url = url.replace(f"{{{{{key}}}}}", str(value))
    
    return url


def list_all_endpoints() -> Dict[str, str]:
    """List all available endpoints."""
    return ENDPOINTS.copy()


def get_endpoints_by_category(category: str) -> Dict[str, str]:
    """Get endpoints by category."""
    categories = {
        'core': ['health', 'integration_status'],
        'surveys': ['survey_list', 'survey_detail', 'survey_start', 'survey_submit', 'survey_recommendations'],
        'rewards': ['reward_history', 'reward_summary', 'reward_payout', 'reward_pools'],
        'profile': ['profile_view', 'profile_update', 'profile_completeness', 'profile_segments'],
        'analytics': ['analytics_dashboard', 'analytics_reports', 'analytics_export'],
        'tasks': ['task_list', 'task_execute', 'task_history', 'task_status'],
        'webhooks': ['webhook_list', 'webhook_create', 'webhook_detail', 'webhook_test', 'webhook_deliveries'],
        'offerwall': ['cpalead_postback', 'cpalead_postback_v2', 'offerwall_embed', 'offerwall_offers', 
                     'offerwall_click', 'offerwall_balance', 'offerwall_history'],
        'locker': ['locker_check', 'locker_unlock'],
        'referral': ['referral_stats', 'referral_referred', 'referral_apply'],
        'leaderboard': ['leaderboard_top', 'leaderboard_my_rank', 'leaderboard_streak', 'leaderboard_milestones'],
        'quiz': ['quiz_list', 'quiz_start', 'quiz_submit'],
        'smartlink': ['smartlink_resolve', 'smartlink_analytics'],
        'withdrawal': ['withdrawal_history', 'withdrawal_request', 'withdrawal_methods', 'withdrawal_add_method', 'withdrawal_stats']
    }
    
    if category not in categories:
        return {}
    
    return {name: ENDPOINTS[name] for name in categories[category] if name in ENDPOINTS}


# ── Endpoint Documentation ─────────────────────────────────────

def generate_endpoint_docs() -> Dict[str, Any]:
    """Generate documentation for all endpoints."""
    docs = {
        'api_prefix': API_PREFIX,
        'categories': {},
        'endpoints': {}
    }
    
    # Group by category
    categories = {
        'core': 'Core CMS functionality',
        'surveys': 'Survey management',
        'rewards': 'Reward system',
        'profile': 'User profile management',
        'analytics': 'Analytics and reporting',
        'tasks': 'Task management',
        'webhooks': 'Webhook management',
        'offerwall': 'Offerwall integration',
        'locker': 'Content locker',
        'referral': 'Referral system',
        'leaderboard': 'Leaderboard',
        'quiz': 'Quiz system',
        'smartlink': 'Smart links',
        'withdrawal': 'Withdrawal system'
    }
    
    for category, description in categories.items():
        endpoints = get_endpoints_by_category(category)
        if endpoints:
            docs['categories'][category] = {
                'description': description,
                'endpoints': list(endpoints.keys())
            }
    
    # Add endpoint details
    for name, url in ENDPOINTS.items():
        docs['endpoints'][name] = {
            'url': url,
            'methods': ['GET', 'POST', 'PUT', 'DELETE'],  # Would be refined based on actual implementation
            'description': f"Endpoint for {name.replace('_', ' ')}"
        }
    
    return docs


# ── Endpoint Configuration ─────────────────────────────────────

class EndpointConfig:
    """Configuration for endpoint system."""
    
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    DEFAULT_CACHE_TIMEOUT = 300  # 5 minutes
    DEFAULT_RATE_LIMIT = '1000/hour'
    
    @classmethod
    def get_page_size(cls) -> int:
        from django.conf import settings
        return getattr(settings, 'CMS_ENDPOINT_PAGE_SIZE', cls.DEFAULT_PAGE_SIZE)
    
    @classmethod
    def get_max_page_size(cls) -> int:
        from django.conf import settings
        return getattr(settings, 'CMS_ENDPOINT_MAX_PAGE_SIZE', cls.MAX_PAGE_SIZE)
    
    @classmethod
    def get_cache_timeout(cls) -> int:
        from django.conf import settings
        return getattr(settings, 'CMS_ENDPOINT_CACHE_TIMEOUT', cls.DEFAULT_CACHE_TIMEOUT)
    
    @classmethod
    def get_rate_limit(cls) -> str:
        from django.conf import settings
        return getattr(settings, 'CMS_ENDPOINT_RATE_LIMIT', cls.DEFAULT_RATE_LIMIT)


# ── Endpoint Health Check ─────────────────────────────────────

def check_endpoint_health() -> Dict[str, Any]:
    """Check health of all endpoints."""
    from django.test import Client
    from django.urls import reverse
    
    client = Client()
    health_status = {
        'overall_status': 'healthy',
        'endpoints': {},
        'timestamp': timezone.now().isoformat()
    }
    
    # Check core endpoints
    core_endpoints = ['health', 'integration_status']
    
    for endpoint_name in core_endpoints:
        try:
            url = get_endpoint_url(endpoint_name)
            response = client.get(url)
            
            health_status['endpoints'][endpoint_name] = {
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'status_code': response.status_code,
                'response_time': 0  # Would measure actual response time
            }
            
            if response.status_code != 200:
                health_status['overall_status'] = 'degraded'
                
        except Exception as e:
            health_status['endpoints'][endpoint_name] = {
                'status': 'error',
                'error': str(e)
            }
            health_status['overall_status'] = 'unhealthy'
    
    return health_status
