# api/promotions/monitoring/uptime_checker.py
# Uptime Checker — External services health monitoring
import logging, time, requests
from dataclasses import dataclass
from django.core.cache import cache
logger = logging.getLogger('monitoring.uptime')

@dataclass
class ServiceStatus:
    name:        str
    url:         str
    is_up:       bool
    response_ms: float
    status_code: int
    error:       str = ''

class UptimeChecker:
    """External services (payment gateways, APIs) uptime monitor।"""

    SERVICES = [
        {'name': 'bKash',         'url': 'https://checkout.sandbox.bka.sh/'},
        {'name': 'ExchangeRate',  'url': 'https://open.er-api.com/v6/latest/USD'},
        {'name': 'Google Vision', 'url': 'https://vision.googleapis.com/'},
    ]

    def check_all(self) -> list[ServiceStatus]:
        return [self.check(s['name'], s['url']) for s in self.SERVICES]

    def check(self, name: str, url: str, timeout: int = 5) -> ServiceStatus:
        start = time.monotonic()
        try:
            r    = requests.get(url, timeout=timeout)
            ms   = round((time.monotonic() - start) * 1000, 2)
            status = ServiceStatus(name=name, url=url, is_up=r.status_code < 500, response_ms=ms, status_code=r.status_code)
        except Exception as e:
            ms     = round((time.monotonic() - start) * 1000, 2)
            status = ServiceStatus(name=name, url=url, is_up=False, response_ms=ms, status_code=0, error=str(e)[:100])
            logger.warning(f'Service down: {name} — {e}')

        # Cache status
        cache.set(f'monitor:uptime:{name}', status.__dict__, timeout=300)
        return status

    def get_cached_status(self, name: str) -> dict | None:
        return cache.get(f'monitor:uptime:{name}')

    def get_all_cached(self) -> list:
        return [self.get_cached_status(s['name']) for s in self.SERVICES]
