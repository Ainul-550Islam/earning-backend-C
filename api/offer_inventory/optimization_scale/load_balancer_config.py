# api/offer_inventory/optimization_scale/load_balancer_config.py
"""Load Balancer Config — Health check and warmup for load balancer."""
import logging
import socket
import os
from django.utils import timezone

logger = logging.getLogger(__name__)


class LoadBalancerConfig:
    """Load balancer integration helpers."""

    @staticmethod
    def health_check_response() -> dict:
        """Standard health check response for ALB/Nginx/Railway."""
        from api.offer_inventory.system_devops.health_check import SystemHealthChecker
        health = SystemHealthChecker.run_all_checks()
        return {
            'status'   : health['status'],
            'version'  : '2.0',
            'timestamp': timezone.now().isoformat(),
        }

    @staticmethod
    def get_server_info() -> dict:
        """Server metadata for routing decisions."""
        return {
            'hostname': socket.gethostname(),
            'pid'     : os.getpid(),
            'region'  : os.getenv('RAILWAY_REGION',
                         os.getenv('AWS_REGION',
                         os.getenv('FLY_REGION', 'unknown'))),
            'env'     : os.getenv('DJANGO_ENV', 'production'),
        }

    @staticmethod
    def warmup() -> dict:
        """
        Pre-warm caches after a new instance starts.
        Called by load balancer warmup probe or startup hook.
        """
        from api.offer_inventory.optimization_scale.query_optimizer import QueryOptimizer
        from api.offer_inventory.system_devops.db_indexer import DBIndexer
        QueryOptimizer.warm_offer_cache()
        DBIndexer.analyze_tables()
        logger.info('Load balancer warmup complete.')
        return {'warmed': True, 'timestamp': timezone.now().isoformat()}

    @staticmethod
    def is_ready() -> bool:
        """
        Kubernetes/Railway readiness probe.
        Returns True only when DB and Redis are available.
        """
        from api.offer_inventory.system_devops.health_check import SystemHealthChecker
        checks = SystemHealthChecker.run_all_checks()
        db_ok  = checks['checks'].get('database', {}).get('healthy', False)
        rd_ok  = checks['checks'].get('cache_redis', {}).get('healthy', False)
        return db_ok and rd_ok

    @staticmethod
    def get_sticky_session_key(user_id) -> str:
        """Generate consistent session affinity key."""
        import hashlib
        return hashlib.md5(str(user_id).encode()).hexdigest()[:8]
