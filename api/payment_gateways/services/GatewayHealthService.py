# api/payment_gateways/services/GatewayHealthService.py
# Ping all gateways and record health status

import requests
import time
import logging
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

HEALTH_ENDPOINTS = {
    'bkash':      'https://tokenized.sandbox.bka.sh/v1.2.0-beta/tokenized/checkout/token/grant',
    'nagad':      'https://api.mynagad.com/api/dfs',
    'sslcommerz': 'https://sandbox.sslcommerz.com/gwprocess/v4/api.php',
    'amarpay':    'https://sandbox.aamarpay.com/request.php',
    'upay':       'https://uat.upay.com.bd/api/v1',
    'shurjopay':  'https://sandbox.shurjopayment.com/api/get_token',
    'stripe':     'https://api.stripe.com/v1',
    'paypal':     'https://api-m.sandbox.paypal.com/v2',
    'payoneer':   'https://api.sandbox.payoneer.com/v2',
    'crypto':     'https://api.commerce.coinbase.com/charges',
}


class GatewayHealthService:
    """
    Pings all gateways and records health status.
    Called every 5 minutes by Celery Beat.
    Updates PaymentGateway.health_status and GatewayHealthLog.
    """

    TIMEOUT          = 5    # seconds
    DEGRADED_MS      = 2000 # 2s = degraded
    DOWN_CODES       = {500, 502, 503, 504}

    def check_all(self) -> dict:
        """Check health of all configured gateways."""
        from api.payment_gateways.models import PaymentGateway
        results = {}
        gateways = PaymentGateway.objects.filter(status__in=['active', 'maintenance', 'degraded'])
        for gw in gateways:
            try:
                result = self.check_single(gw.name)
                results[gw.name] = result
            except Exception as e:
                logger.error(f'Health check error for {gw.name}: {e}')
                results[gw.name] = {'status': 'error', 'error': str(e)}
        return results

    def check_single(self, gateway_name: str) -> dict:
        """Check health of a single gateway."""
        from api.payment_gateways.models import PaymentGateway, GatewayHealthLog

        url    = HEALTH_ENDPOINTS.get(gateway_name, '')
        start  = time.time()
        status = 'unknown'
        http_code = None
        error  = ''

        if url:
            try:
                resp      = requests.head(url, timeout=self.TIMEOUT, allow_redirects=True)
                elapsed   = int((time.time() - start) * 1000)
                http_code = resp.status_code

                if http_code in self.DOWN_CODES:
                    status = 'down'
                    error  = f'HTTP {http_code}'
                elif elapsed > self.DEGRADED_MS:
                    status = 'degraded'
                else:
                    status = 'healthy'
            except requests.exceptions.Timeout:
                elapsed = self.TIMEOUT * 1000
                status  = 'timeout'
                error   = 'Request timed out'
            except requests.exceptions.ConnectionError:
                elapsed = int((time.time() - start) * 1000)
                status  = 'down'
                error   = 'Connection error'
            except Exception as e:
                elapsed = int((time.time() - start) * 1000)
                status  = 'error'
                error   = str(e)
        else:
            elapsed = 0
            status  = 'unknown'
            error   = 'No health endpoint configured'

        # Save log
        try:
            gw = PaymentGateway.objects.get(name=gateway_name)
            GatewayHealthLog.objects.create(
                gateway=gw, status=status,
                response_time_ms=elapsed,
                http_status_code=http_code,
                error=error,
            )
            # Update gateway health status
            gw.health_status        = status
            gw.last_health_check    = timezone.now()
            gw.avg_response_time_ms = elapsed
            gw.save(update_fields=['health_status','last_health_check','avg_response_time_ms'])

            # Cache for status page
            cache.set(f'gw_health:{gateway_name}', {
                'status': status, 'ms': elapsed, 'code': http_code
            }, 300)

        except Exception as e:
            logger.warning(f'Could not save health log for {gateway_name}: {e}')

        return {'status': status, 'ms': elapsed, 'http_code': http_code, 'error': error}

    def get_status_summary(self) -> dict:
        """Get cached health summary for all gateways."""
        from api.payment_gateways.models import PaymentGateway
        summary = {}
        for gw in PaymentGateway.objects.all():
            cached = cache.get(f'gw_health:{gw.name}')
            summary[gw.name] = cached or {'status': gw.health_status, 'ms': gw.avg_response_time_ms}
        return summary
