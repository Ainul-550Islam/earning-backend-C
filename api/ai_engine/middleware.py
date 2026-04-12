"""
api/ai_engine/middleware.py
============================
AI Engine — Request/Response Middleware।
Fraud scoring, rate limiting, logging।
"""

import time
import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class AIEngineLoggingMiddleware(MiddlewareMixin):
    """
    AI Engine endpoints এর request/response log করো।
    """

    def process_request(self, request):
        if '/ai-engine/' in request.path:
            request._ai_start_time = time.time()

    def process_response(self, request, response):
        if hasattr(request, '_ai_start_time') and '/ai-engine/' in request.path:
            duration_ms = (time.time() - request._ai_start_time) * 1000
            if duration_ms > 500:
                logger.warning(
                    f"Slow AI endpoint: {request.path} "
                    f"method={request.method} "
                    f"duration={duration_ms:.1f}ms "
                    f"status={response.status_code}"
                )
        return response


class FraudCheckMiddleware(MiddlewareMixin):
    """
    Sensitive endpoints এ auto fraud check।
    """

    PROTECTED_PATHS = [
        '/api/payment/',
        '/api/withdrawal/',
        '/api/payout/',
    ]

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None

        should_check = any(request.path.startswith(p) for p in self.PROTECTED_PATHS)
        if not should_check:
            return None

        # Quick fraud score check
        try:
            from .services import FraudDetectionService
            metadata = {
                'ip_address': self._get_client_ip(request),
                'is_vpn': getattr(request, 'is_vpn', False),
                'is_proxy': getattr(request, 'is_proxy', False),
            }
            result = FraudDetectionService.score_user_action(
                user=request.user,
                action_type='payment_attempt',
                metadata=metadata,
            )
            if result.get('is_fraud') and result.get('fraud_score', 0) >= 0.95:
                logger.warning(f"Blocked high-fraud request: user={request.user.id}")
                return JsonResponse(
                    {'success': False, 'message': 'Request blocked due to suspicious activity.'},
                    status=403
                )
        except Exception as e:
            logger.error(f"Fraud middleware error: {e}")

        return None

    def _get_client_ip(self, request) -> str:
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
