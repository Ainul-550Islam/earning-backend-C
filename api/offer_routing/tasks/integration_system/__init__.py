"""
tasks/integration_system — Task classes for integration-system background jobs.
These are class-based task wrappers (not @shared_task decorated),
used by the Celery beat schedule or called manually.
"""
from .ab_test_tasks import ABTestTask
from .affinity_update_tasks import AffinityUpdateTask
from .analytics_tasks import AnalyticsTask
from .cache_warmup_tasks import CacheWarmupTask
from .cap_reset_tasks import CapResetTask
from .exposure_stat_tasks import ExposureStatTask
from .fallback_health_tasks import FallbackHealthTask
from .preference_vector_tasks import PreferenceVectorTask
from .rank_update_tasks import RankUpdateTask
from .score_update_tasks import ScoreUpdateTask

__all__ = [
    'ABTestTask', 'AffinityUpdateTask', 'AnalyticsTask',
    'CacheWarmupTask', 'CapResetTask', 'ExposureStatTask',
    'FallbackHealthTask', 'PreferenceVectorTask',
    'RankUpdateTask', 'ScoreUpdateTask',
]
