# api/promotions/monitoring/traffic_monitor.py
# Traffic Monitor — Request rate, geographic traffic, anomaly detection
import logging, time
from django.core.cache import cache
logger = logging.getLogger('monitoring.traffic')

class TrafficMonitor:
    """Real-time traffic monitoring।"""
    WINDOW    = 300    # 5 min sliding window
    MAX_RPS   = 1000   # Requests per second threshold
    STREAM    = 'monitor:traffic:stream'

    def record_request(self, path: str, ip: str, country: str, status: int, ms: float):
        ts     = time.time()
        stream = cache.get(self.STREAM) or []
        stream.append({'path': path, 'ip': ip, 'country': country, 'status': status, 'ms': ms, 'ts': ts})
        # Keep last 5 minutes
        cutoff = ts - self.WINDOW
        stream = [r for r in stream if r['ts'] > cutoff][-10000:]
        cache.set(self.STREAM, stream, timeout=self.WINDOW + 60)

        # High RPS check
        if len(stream) / self.WINDOW > self.MAX_RPS:
            logger.warning(f'High RPS: {len(stream)/self.WINDOW:.0f} req/s')

    def get_stats(self) -> dict:
        stream = cache.get(self.STREAM) or []
        if not stream:
            return {'rps': 0, 'total': 0}
        now  = time.time()
        cutoff = now - self.WINDOW
        recent = [r for r in stream if r['ts'] > cutoff]
        from collections import Counter
        countries = Counter(r['country'] for r in recent)
        errors    = sum(1 for r in recent if r['status'] >= 500)
        avg_ms    = sum(r['ms'] for r in recent) / max(len(recent), 1)
        return {
            'rps':        round(len(recent)/self.WINDOW, 2),
            'total':      len(recent),
            'error_rate': round(errors/max(len(recent),1), 4),
            'avg_ms':     round(avg_ms, 2),
            'top_countries': dict(countries.most_common(5)),
        }

    def detect_ddos(self, ip: str) -> bool:
        """Single IP থেকে too many requests detect করে।"""
        stream  = cache.get(self.STREAM) or []
        recent  = [r for r in stream if r['ip'] == ip and r['ts'] > time.time() - 60]
        if len(recent) > 300:  # 300 req/min from single IP
            logger.critical(f'Potential DDoS from IP: {ip} ({len(recent)} req/min)')
            return True
        return False
