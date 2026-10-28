"""
Logging configuration for Real-time Dashboard Backend.

ADDED (v1.4.0): production-grade structured logging, selectable via the
LOG_FORMAT environment variable:

    LOG_FORMAT=json   — one JSON object per line (ndjson). Intended for
                        production: machine-parseable by Datadog,
                        CloudWatch Logs, Loki, ELK/Fluentd, etc. without a
                        custom grok/regex pattern.
    LOG_FORMAT=text   — human-readable single-line format. Intended for
                        local development and CI output. This is the
                        default when LOG_FORMAT is unset.

Applied from RealtimeDashboardConfig.ready() (apps.py) as a fallback for
any deployment that doesn't define its own settings.LOGGING — see that
method's docstring for why AppConfig.ready() is the right hook: Daphne
(`daphne config.asgi:application`, per Dockerfile/docker-compose.yml) and
Celery workers (`celery -A config.celery worker`) both bypass manage.py,
so Django's own `django.setup() -> configure_logging(settings.LOGGING)`
step never gets a chance to run against a host-supplied LOGGING in some
startup paths. AppConfig.ready() fires for every startup path (manage.py,
daphne, celery worker, pytest) since it always runs after django.setup(),
making it the one reliable place to guarantee logging gets configured.

Usage from a host project's config/settings.py (preferred when the
process always starts via manage.py or gunicorn/daphne through manage.py
compatible bootstrapping, since Django then applies it at the correct
point in django.setup() automatically, before any app's ready() runs):

    from api.realtime_dashboard.logging_config import get_logging_config
    LOGGING = get_logging_config()

If settings.LOGGING is already set (by the host project, or by
tests/settings.py for quiet test output), RealtimeDashboardConfig.ready()
will NOT call dictConfig() again — an explicitly configured LOGGING is
always respected instead of being silently overwritten.
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

#: LogRecord attributes already surfaced explicitly by JSONFormatter.format()
#: — anything else on the record (i.e. keys passed via `extra={...}`) is
#: copied into the JSON payload as additional structured fields.
_RESERVED_RECORD_ATTRS = frozenset({
    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
    'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
    'created', 'msecs', 'relativeCreated', 'thread', 'threadName',
    'processName', 'process', 'message', 'asctime', 'taskName',
})

_VALID_LEVELS = frozenset({'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET'})


class JSONFormatter(logging.Formatter):
    """
    Renders each LogRecord as a single JSON line (ndjson).

    Fields:
        timestamp   ISO-8601 UTC, e.g. "2026-07-09T10:15:30.123456+00:00"
        level       "INFO", "ERROR", etc.
        logger      logger name, e.g. "api.realtime_dashboard.services"
        message     the formatted log message (record.getMessage())
        module      source module (record.module)
        function    source function (record.funcName)
        line        source line number (record.lineno)
        exception   traceback text, only present if exc_info was passed
        stack       stack text, only present if stack_info=True was passed
        ...plus any JSON-serializable fields passed via extra={...}
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)
        if record.stack_info:
            payload['stack'] = self.formatStack(record.stack_info)

        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_ATTRS or key.startswith('_'):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)

        return json.dumps(payload, default=str)


def _resolve_format(log_format: Optional[str]) -> str:
    value = (log_format if log_format is not None else os.environ.get('LOG_FORMAT', 'text'))
    value = (value or 'text').strip().lower()
    return 'json' if value == 'json' else 'text'


def _resolve_level(log_level: Optional[str]) -> str:
    value = (log_level if log_level is not None else os.environ.get('LOG_LEVEL', 'INFO'))
    value = (value or 'INFO').strip().upper()
    return value if value in _VALID_LEVELS else 'INFO'


def get_logging_config(
    log_format: Optional[str] = None,
    log_level: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a Django/logging.config.dictConfig-compatible LOGGING dict.

    Args:
        log_format: 'json' or 'text'. Defaults to the LOG_FORMAT env var,
                    falling back to 'text' if unset or unrecognized.
        log_level:  Root/app log level ('DEBUG', 'INFO', 'WARNING',
                    'ERROR', 'CRITICAL'). Defaults to the LOG_LEVEL env
                    var, falling back to 'INFO' if unset or unrecognized.

    Returns:
        A plain dict, safe to pass directly to logging.config.dictConfig()
        or to assign to settings.LOGGING.
    """
    resolved_format = _resolve_format(log_format)
    resolved_level = _resolve_level(log_level)

    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'json': {
                '()': 'api.realtime_dashboard.logging_config.JSONFormatter',
            },
            'text': {
                'format': '[{asctime}] {levelname:<8} {name} {module}.{funcName}:{lineno} — {message}',
                'style': '{',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': resolved_format,
            },
        },
        'root': {
            'handlers': ['console'],
            'level': resolved_level,
        },
        'loggers': {
            'django': {
                'handlers': ['console'],
                'level': resolved_level,
                'propagate': False,
            },
            'django.request': {
                'handlers': ['console'],
                'level': 'ERROR',
                'propagate': False,
            },
            'django.security': {
                'handlers': ['console'],
                'level': 'WARNING',
                'propagate': False,
            },
            'api.realtime_dashboard': {
                'handlers': ['console'],
                'level': resolved_level,
                'propagate': False,
            },
            # Celery workers normally configure their own logging via the
            # `-l INFO` CLI flag, but when CELERYD_HIJACK_ROOT_LOGGER=False
            # (recommended so Celery shares this structured config instead
            # of installing its own colored formatter), tasks.py log calls
            # route through here too.
            'celery': {
                'handlers': ['console'],
                'level': resolved_level,
                'propagate': False,
            },
        },
    }
