# api/admin_panel/signals/__init__.py
"""Admin panel signals sub-package."""

import importlib
import logging

logger = logging.getLogger(__name__)


def connect_all_signals():
    """Connect all admin_panel signal handler modules."""
    sub_signals = [
        'activity_signals',
        'config_signals',
        'feature_flag_signals',
        'maintenance_signals',
        'report_signals',
        'session_signals',
        'endpoint_toggle_signals',
    ]

    for name in sub_signals:
        try:
            importlib.import_module(f'.{name}', package='api.admin_panel.signals')
        except ImportError:
            logger.debug(f"Signal module not yet available: {name}")
        except Exception as e:
            logger.warning(f"Error loading signal module {name}: {e}")
