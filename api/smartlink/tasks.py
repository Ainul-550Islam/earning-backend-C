"""
SmartLink Tasks — master import file.
All Celery tasks are imported here so they are discovered by the worker.
"""
from .tasks.click_processing_tasks import *    # noqa: F401, F403
from .tasks.stat_rollup_tasks import *         # noqa: F401, F403
from .tasks.epc_update_tasks import *          # noqa: F401, F403
from .tasks.cap_reset_tasks import *           # noqa: F401, F403
from .tasks.fraud_scan_tasks import *          # noqa: F401, F403
from .tasks.ab_test_tasks import *             # noqa: F401, F403
from .tasks.offer_score_tasks import *         # noqa: F401, F403
from .tasks.domain_check_tasks import *        # noqa: F401, F403
from .tasks.cache_warmup_tasks import *        # noqa: F401, F403
from .tasks.heatmap_tasks import *             # noqa: F401, F403
from .tasks.cleanup_tasks import *             # noqa: F401, F403
from .tasks.report_tasks import *              # noqa: F401, F403
from .tasks.smartlink_health_tasks import *    # noqa: F401, F403
from .tasks.scheduler_tasks import *      # noqa: F401, F403
