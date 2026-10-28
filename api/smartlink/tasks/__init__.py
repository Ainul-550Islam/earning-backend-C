"""
SmartLink Celery Tasks Package
================================
All task modules are imported here so that Celery's autodiscover_tasks()
(configured in celery_config/celery.py) registers every task when the worker
starts. Without these imports the package __init__ is empty and tasks inside
sub-modules are only discovered if the worker explicitly imports each file.
"""

from .click_processing_tasks import *   # noqa: F401, F403
from .stat_rollup_tasks import *        # noqa: F401, F403
from .epc_update_tasks import *         # noqa: F401, F403
from .cap_reset_tasks import *          # noqa: F401, F403
from .fraud_scan_tasks import *         # noqa: F401, F403
from .ab_test_tasks import *            # noqa: F401, F403
from .offer_score_tasks import *        # noqa: F401, F403
from .domain_check_tasks import *       # noqa: F401, F403
from .cache_warmup_tasks import *       # noqa: F401, F403
from .heatmap_tasks import *            # noqa: F401, F403
from .cleanup_tasks import *            # noqa: F401, F403
from .billing_tasks import *            # noqa: F401, F403
from .scheduler_tasks import *          # noqa: F401, F403
from .smartlink_health_tasks import *   # noqa: F401, F403
from .report_tasks import *             # noqa: F401, F403
from .webhook_tasks import *            # noqa: F401, F403
