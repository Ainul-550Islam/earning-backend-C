# api/offer_inventory/optimization_scale/query_optimizer.py
"""
Optimization & Scale Package — all 10 modules.
Query optimization, CDN, image compression, worker pool,
request deduplication, bandwidth monitor, memory limiter,
load balancer config, real-time streaming, server-side rendering.
"""
import logging
import time
import hashlib
import threading
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════
# 1. QUERY OPTIMIZER
# ════════════════════════════════════════════════════════

class QueryOptimizer:
    """
    Database query optimization utilities.
    Slow query detection, N+1 prevention, query caching.
    """

    SLOW_QUERY_THRESHOLD_MS = 500

    @staticmethod
    def cached_query(key: str, fn, ttl: int = 300):
        """Cache the result of a DB query."""
        cached = cache.get(key)
        if cached is not None:
            return cached
        result = fn()
        cache.set(key, result, ttl)
        return result

    @staticmethod
    def bulk_prefetch_offers(offer_ids: list) -> dict:
        """
        Bulk fetch offers with all related data in minimal queries.
        Returns {offer_id: offer} dict.
        """
        from api.offer_inventory.models import Offer
        offers = Offer.objects.filter(
            id__in=offer_ids
        ).select_related(
            'network', 'category'
        ).prefetch_related(
            'caps', 'visibility_rules', 'tags', 'creatives'
        )
        return {str(o.id): o for o in offers}

    @staticmethod
    def paginate_large_queryset(qs, batch_size: int = 1000):
        """
        Memory-safe iteration over large querysets.
        Uses keyset pagination instead of OFFSET.
        """
        last_id = None
        while True:
            if last_id is None:
                batch = list(qs.order_by('id')[:batch_size])
            else:
                batch = list(qs.filter(id__gt=last_id).order_by('id')[:batch_size])
            if not batch:
                break
            yield from batch
            last_id = batch[-1].id
            if len(batch) < batch_size:
                break

    @staticmethod
    def get_slow_queries(threshold_ms: int = None) -> list:
        """Get recent slow queries from PerformanceMetric."""
        from api.offer_inventory.models import PerformanceMetric
        from django.db.models import Avg
        threshold = threshold_ms or QueryOptimizer.SLOW_QUERY_THRESHOLD_MS
        since     = timezone.now() - __import__('datetime').timedelta(hours=24)
        return list(
            PerformanceMetric.objects.filter(
                recorded_at__gte=since,
                avg_ms__gt=threshold
            ).values('endpoint', 'method', 'avg_ms', 'request_count')
            .order_by('-avg_ms')[:20]
        )

    @staticmethod
    def warm_offer_cache(tenant=None):
        """Pre-warm offer list cache after deployment."""
        from api.offer_inventory.repository import OfferRepository
        for page in range(1, 6):
            OfferRepository.get_active_offers(tenant=tenant, page=page)
        logger.info('Offer cache warmed: 5 pages')


# ════════════════════════════════════════════════════════
# 2. STATIC FILE CDN
# ════════════════════════════════════════════════════════

class StaticFileCDN:
    """CDN URL management for static assets and offer images."""

    CDN_BASE     = ''  # Set from settings
    USE_CDN      = False

    @classmethod
    def setup(cls):
        from django.conf import settings
        cls.CDN_BASE  = getattr(settings, 'CDN_BASE_URL', '')
        cls.USE_CDN   = bool(cls.CDN_BASE)

    @classmethod
    def url(cls, path: str) -> str:
        """Convert a path to CDN URL if CDN is configured."""
        cls.setup()
        if not path:
            return path
        if cls.USE_CDN and not path.startswith(('http://', 'https://')):
            return f'{cls.CDN_BASE.rstrip("/")}/{path.lstrip("/")}'
        return path

    @classmethod
    def offer_image_url(cls, offer) -> str:
        """Get CDN URL for an offer image."""
        url = offer.image_url or ''
        return cls.url(url) if url else ''

    @classmethod
    def rewrite_offer_urls(cls, offers: list) -> list:
        """Rewrite all image URLs in an offer list to CDN URLs."""
        cls.setup()
        if not cls.USE_CDN:
            return offers
        for offer in offers:
            if hasattr(offer, 'image_url') and offer.image_url:
                offer.image_url = cls.url(offer.image_url)
        return offers

    @staticmethod
    def purge_cache(path: str) -> bool:
        """Purge CDN cache for a specific path (Cloudflare example)."""
        from django.conf import settings
        cf_zone  = getattr(settings, 'CLOUDFLARE_ZONE_ID', '')
        cf_token = getattr(settings, 'CLOUDFLARE_API_TOKEN', '')
        if not all([cf_zone, cf_token]):
            return False
        try:
            import requests
            resp = requests.post(
                f'https://api.cloudflare.com/client/v4/zones/{cf_zone}/purge_cache',
                headers={'Authorization': f'Bearer {cf_token}'},
                json={'files': [path]},
                timeout=5,
            )
            return resp.ok
        except Exception as e:
            logger.error(f'CDN purge error: {e}')
            return False


# ════════════════════════════════════════════════════════
# 3. IMAGE COMPRESSOR
# ════════════════════════════════════════════════════════

class ImageCompressor:
    """Compress and optimize offer creative images."""

    MAX_WIDTH   = 800
    MAX_HEIGHT  = 600
    JPEG_QUALITY = 85

    @staticmethod
    def compress_from_url(image_url: str, output_path: str = None) -> dict:
        """Download and compress an image from URL."""
        try:
            import requests
            from PIL import Image
            import io

            resp = requests.get(image_url, timeout=10)
            resp.raise_for_status()

            img    = Image.open(io.BytesIO(resp.content))
            original_size = len(resp.content)

            # Resize if too large
            if img.width > ImageCompressor.MAX_WIDTH or img.height > ImageCompressor.MAX_HEIGHT:
                img.thumbnail(
                    (ImageCompressor.MAX_WIDTH, ImageCompressor.MAX_HEIGHT),
                    Image.LANCZOS
                )

            # Convert to RGB if needed (removes alpha for JPEG)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            output = io.BytesIO()
            img.save(output, format='JPEG', quality=ImageCompressor.JPEG_QUALITY, optimize=True)
            compressed = output.getvalue()
            compressed_size = len(compressed)

            saving_pct = round((1 - compressed_size / max(original_size, 1)) * 100, 1)
            return {
                'success'       : True,
                'original_size' : original_size,
                'compressed_size': compressed_size,
                'saving_pct'    : saving_pct,
                'width'         : img.width,
                'height'        : img.height,
                'data'          : compressed,
            }
        except ImportError:
            return {'success': False, 'error': 'Pillow not installed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_webp_url(original_url: str) -> str:
        """Return WebP version URL if available (CDN auto-convert)."""
        if not original_url:
            return original_url
        if '.jpg' in original_url or '.jpeg' in original_url or '.png' in original_url:
            return original_url.rsplit('.', 1)[0] + '.webp'
        return original_url


# ════════════════════════════════════════════════════════
# 4. WORKER POOL
# ════════════════════════════════════════════════════════

class WorkerPoolManager:
    """
    Manage Celery worker pools dynamically.
    Monitor queue depths and trigger scaling.
    """

    QUEUE_DEPTH_ALERT = 500     # Alert when queue exceeds this
    QUEUE_DEPTH_SCALE = 1000    # Consider scaling at this depth

    @staticmethod
    def get_queue_depths() -> dict:
        """Get current depth of all Celery queues."""
        try:
            import redis
            from django.conf import settings
            broker_url = getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/1')
            r = redis.from_url(broker_url)
            queues = ['default', 'postback', 'fraud', 'analytics', 'notification', 'payout']
            return {q: r.llen(q) for q in queues}
        except Exception as e:
            logger.error(f'Queue depth check error: {e}')
            return {}

    @staticmethod
    def get_worker_stats() -> dict:
        """Get active Celery worker statistics."""
        try:
            from celery import current_app
            inspector = current_app.control.inspect(timeout=3)
            active    = inspector.active()
            stats     = inspector.stats()
            return {
                'worker_count': len(active) if active else 0,
                'active_tasks': sum(len(v) for v in (active or {}).values()),
                'workers'     : list((active or {}).keys()),
            }
        except Exception as e:
            return {'worker_count': 0, 'error': str(e)}

    @staticmethod
    def should_scale_up() -> bool:
        """Check if worker scaling is needed."""
        depths = WorkerPoolManager.get_queue_depths()
        return any(d > WorkerPoolManager.QUEUE_DEPTH_SCALE for d in depths.values())

    @staticmethod
    def get_recommendations() -> dict:
        """Get scaling recommendations based on current load."""
        depths = WorkerPoolManager.get_queue_depths()
        stats  = WorkerPoolManager.get_worker_stats()
        alerts = []

        for queue, depth in depths.items():
            if depth > WorkerPoolManager.QUEUE_DEPTH_ALERT:
                alerts.append(f'Queue "{queue}" has {depth} pending tasks')

        return {
            'queue_depths'  : depths,
            'worker_count'  : stats.get('worker_count', 0),
            'active_tasks'  : stats.get('active_tasks', 0),
            'alerts'        : alerts,
            'scale_needed'  : WorkerPoolManager.should_scale_up(),
        }


# ════════════════════════════════════════════════════════
# 5. REQUEST DEDUPLICATION
# ════════════════════════════════════════════════════════

class RequestDeduplicator:
    """
    Idempotent request handling.
    Prevents duplicate processing of identical requests.
    """

    DEFAULT_TTL = 300   # 5 minutes

    @staticmethod
    def make_key(method: str, path: str, body_hash: str, user_id=None) -> str:
        raw = f'{method}:{path}:{body_hash}:{user_id}'
        return f'dedup:{hashlib.md5(raw.encode()).hexdigest()}'

    @staticmethod
    def is_duplicate(request_key: str) -> bool:
        """Check if this request was already processed."""
        return bool(cache.get(request_key))

    @staticmethod
    def mark_processed(request_key: str, result=None, ttl: int = None):
        """Mark a request as processed."""
        cache.set(request_key, result or '1', ttl or RequestDeduplicator.DEFAULT_TTL)

    @staticmethod
    def get_body_hash(body: bytes) -> str:
        return hashlib.md5(body or b'').hexdigest()

    @classmethod
    def check_and_mark(cls, method: str, path: str,
                        body: bytes = b'', user_id=None) -> dict:
        """
        Check if duplicate, and mark as processed if not.
        Returns {'is_duplicate': bool, 'key': str}
        """
        body_hash   = cls.get_body_hash(body)
        request_key = cls.make_key(method, path, body_hash, user_id)

        if cls.is_duplicate(request_key):
            return {'is_duplicate': True, 'key': request_key}

        cls.mark_processed(request_key)
        return {'is_duplicate': False, 'key': request_key}


# ════════════════════════════════════════════════════════
# 6. BANDWIDTH MONITOR
# ════════════════════════════════════════════════════════

class BandwidthMonitor:
    """Monitor API response sizes and bandwidth usage."""

    WINDOW_SECONDS = 3600   # 1 hour rolling window

    @staticmethod
    def record_response(endpoint: str, size_bytes: int, user_id=None):
        """Record a response size."""
        key   = f'bw:{endpoint}'
        stats = cache.get(key, {'total_bytes': 0, 'request_count': 0, 'max_bytes': 0})
        stats['total_bytes']   += size_bytes
        stats['request_count'] += 1
        stats['max_bytes']      = max(stats['max_bytes'], size_bytes)
        stats['avg_bytes']      = stats['total_bytes'] // stats['request_count']
        cache.set(key, stats, BandwidthMonitor.WINDOW_SECONDS)

    @staticmethod
    def get_bandwidth_stats(endpoint: str = None) -> dict:
        """Get bandwidth stats for an endpoint or all endpoints."""
        if endpoint:
            return cache.get(f'bw:{endpoint}', {})

        # Platform total
        total = cache.get('bw_total', {'total_bytes': 0})
        return {
            'total_bytes_hour': total.get('total_bytes', 0),
            'total_mb'        : round(total.get('total_bytes', 0) / 1024 / 1024, 2),
        }

    @staticmethod
    def check_large_response(size_bytes: int, threshold_mb: float = 1.0) -> bool:
        """Flag unusually large responses."""
        return size_bytes > threshold_mb * 1024 * 1024


# ════════════════════════════════════════════════════════
# 7. MEMORY USAGE LIMITER
# ════════════════════════════════════════════════════════

class MemoryUsageLimiter:
    """Prevent memory exhaustion from large operations."""

    MAX_QUERY_RESULTS  = 10000
    MAX_EXPORT_ROWS    = 100000
    MAX_BULK_IDS       = 5000
    MAX_NOTIFICATION_BATCH = 10000

    @staticmethod
    def limit_queryset(qs, max_results: int = None):
        """Apply result limit to a queryset."""
        limit = max_results or MemoryUsageLimiter.MAX_QUERY_RESULTS
        return qs[:limit]

    @staticmethod
    def get_memory_usage() -> dict:
        """Get current process memory usage."""
        try:
            import psutil, os
            process = psutil.Process(os.getpid())
            mem_mb  = process.memory_info().rss / 1024 / 1024
            return {
                'rss_mb'   : round(mem_mb, 1),
                'percent'  : round(process.memory_percent(), 1),
                'is_high'  : mem_mb > 512,
            }
        except ImportError:
            return {'rss_mb': 0, 'percent': 0, 'is_high': False}

    @staticmethod
    def check_before_bulk(item_count: int, operation: str) -> dict:
        """Safety check before large bulk operations."""
        limits = {
            'ids'           : MemoryUsageLimiter.MAX_BULK_IDS,
            'export'        : MemoryUsageLimiter.MAX_EXPORT_ROWS,
            'notification'  : MemoryUsageLimiter.MAX_NOTIFICATION_BATCH,
        }
        limit = limits.get(operation, 10000)
        if item_count > limit:
            return {
                'allowed': False,
                'reason' : f'{operation} limit is {limit}, requested {item_count}',
                'limit'  : limit,
            }
        return {'allowed': True, 'limit': limit}


# ════════════════════════════════════════════════════════
# 8. LOAD BALANCER CONFIG
# ════════════════════════════════════════════════════════

class LoadBalancerConfig:
    """Load balancer health check and session affinity configuration."""

    @staticmethod
    def health_check_response() -> dict:
        """Standard health check response for load balancer."""
        from api.offer_inventory.system_devops import SystemHealthChecker
        health = SystemHealthChecker.run_all_checks()
        return {
            'status'   : health['status'],
            'version'  : '2.0',
            'timestamp': timezone.now().isoformat(),
        }

    @staticmethod
    def get_server_info() -> dict:
        """Server metadata for routing decisions."""
        import socket, os
        return {
            'hostname' : socket.gethostname(),
            'pid'      : os.getpid(),
            'region'   : os.getenv('RAILWAY_REGION', os.getenv('AWS_REGION', 'unknown')),
        }

    @staticmethod
    def warmup_endpoint() -> dict:
        """Pre-warm caches after a new instance starts."""
        QueryOptimizer.warm_offer_cache()
        return {'warmed': True, 'timestamp': timezone.now().isoformat()}


# ════════════════════════════════════════════════════════
# 9. REAL-TIME STREAMING
# ════════════════════════════════════════════════════════

class RealTimeStreamingService:
    """
    Server-Sent Events (SSE) for real-time dashboard updates.
    Streams: live clicks, conversions, fraud alerts.
    """

    @staticmethod
    def live_stats_stream(tenant=None):
        """
        Generator for SSE live stats stream.
        Usage in view:
            StreamingHttpResponse(RealTimeStreamingService.live_stats_stream(), content_type='text/event-stream')
        """
        import json, time as _time
        while True:
            try:
                from api.offer_inventory.reporting_audit import AdminDashboardStats
                stats = AdminDashboardStats.get_live_stats(tenant=tenant)
                yield f'data: {json.dumps(stats)}\n\n'
            except Exception as e:
                yield f'data: {{"error": "{str(e)}"}}\n\n'
            _time.sleep(30)  # Update every 30 seconds

    @staticmethod
    def publish_event(channel: str, event_type: str, data: dict):
        """Publish a real-time event to Redis pub/sub."""
        try:
            import redis, json
            from django.conf import settings
            r       = redis.from_url(getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0'))
            payload = json.dumps({'type': event_type, 'data': data, 'ts': time.time()})
            r.publish(f'offer_inventory:{channel}', payload)
        except Exception as e:
            logger.debug(f'Real-time publish error: {e}')

    @staticmethod
    def subscribe_to_events(channel: str):
        """Subscribe to real-time events (for WebSocket handlers)."""
        try:
            import redis
            from django.conf import settings
            r      = redis.from_url(getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0'))
            pubsub = r.pubsub()
            pubsub.subscribe(f'offer_inventory:{channel}')
            return pubsub
        except Exception as e:
            logger.error(f'Subscribe error: {e}')
            return None


# ════════════════════════════════════════════════════════
# 10. SERVER-SIDE RENDERING HELPERS
# ════════════════════════════════════════════════════════

class SSRHelper:
    """
    Server-side rendering helpers for the offerwall.
    Pre-renders offer lists for SEO and initial page load performance.
    """

    @staticmethod
    def get_initial_page_data(tenant=None, country: str = '',
                               device: str = 'desktop') -> dict:
        """
        Get all data needed for initial page render in one call.
        Reduces round trips for mobile clients.
        """
        from api.offer_inventory.repository import (
            OfferRepository, NotificationRepository, FeatureFlagRepository
        )
        offers       = OfferRepository.get_active_offers(tenant=tenant, country=country, page=1)
        features     = {
            'offerwall' : FeatureFlagRepository.is_enabled('offer_wall', tenant),
            'referral'  : FeatureFlagRepository.is_enabled('referral', tenant),
            'kyc'       : FeatureFlagRepository.is_enabled('kyc', tenant),
        }
        from api.offer_inventory.models import OfferCategory, LoyaltyLevel
        categories  = list(OfferCategory.objects.filter(is_active=True).values('id', 'name', 'slug', 'icon_url'))
        tiers       = list(LoyaltyLevel.objects.all().order_by('level_order').values('name', 'min_points', 'payout_bonus_pct'))

        return {
            'offers'      : [{'id': str(o.id), 'title': o.title, 'reward': str(o.reward_amount)} for o in offers[:10]],
            'categories'  : categories,
            'loyalty_tiers': tiers,
            'features'    : features,
            'rendered_at' : timezone.now().isoformat(),
        }

    @staticmethod
    def cache_ssr_page(page_key: str, html: str, ttl: int = 60):
        """Cache pre-rendered HTML."""
        cache.set(f'ssr:{page_key}', html, ttl)

    @staticmethod
    def get_cached_ssr(page_key: str) -> str:
        """Get cached pre-rendered HTML."""
        return cache.get(f'ssr:{page_key}', '')
