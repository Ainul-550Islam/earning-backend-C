"""
Tests for observability additions (ADDED v1.4.0):
  - api/realtime_dashboard/logging_config.py (JSON/text structured logging)
  - RealtimeDashboardConfig._configure_logging() / _init_sentry() (apps.py)

These were added alongside drf-spectacular/k8s/locust in the same
production-readiness pass and had near-zero coverage from the existing
suite (nothing exercises apps.py's ready() helpers directly, and nothing
in the suite ever runs with settings.LOGGING unset, since tests/settings.py
deliberately sets its own LOGGING to keep test output quiet).

NOTE: TestConfigureLogging/TestInitSentry test the *methods* directly
rather than the full RealtimeDashboardConfig.ready() lifecycle, and do
not call logging.config.dictConfig() for real — dictConfig() mutates
GLOBAL logging state (handlers, formatters, levels), and doing that for
real inside a shared test run would leak into every test that runs
afterward, potentially reintroducing the log noise tests/settings.py's
own LOGGING dict is specifically there to suppress. Every dictConfig()
call is therefore mocked here; the config dict's *content* being valid
dictConfig input is verified separately and structurally.
"""
import json
import logging
import sys
from unittest.mock import patch

import pytest
from django.test import override_settings

from api.realtime_dashboard.apps import RealtimeDashboardConfig
from api.realtime_dashboard.logging_config import JSONFormatter, get_logging_config


def _make_record(**overrides):
    defaults = dict(
        name='api.realtime_dashboard.test', level=logging.INFO, pathname=__file__,
        lineno=10, msg='hello %s', args=('world',), exc_info=None,
    )
    defaults.update(overrides)
    return logging.LogRecord(
        defaults['name'], defaults['level'], defaults['pathname'], defaults['lineno'],
        defaults['msg'], defaults['args'], defaults['exc_info'],
    )


class TestJSONFormatter:

    def test_format_produces_valid_json_with_expected_fields(self):
        record = _make_record()
        payload = json.loads(JSONFormatter().format(record))
        assert payload['level'] == 'INFO'
        assert payload['logger'] == 'api.realtime_dashboard.test'
        assert payload['message'] == 'hello world'
        assert payload['line'] == 10
        assert 'timestamp' in payload

    def test_format_includes_exception_traceback(self):
        try:
            1 / 0
        except ZeroDivisionError:
            record = _make_record(level=logging.ERROR, msg='boom', args=(), exc_info=sys.exc_info())
        payload = json.loads(JSONFormatter().format(record))
        assert 'exception' in payload
        assert 'ZeroDivisionError' in payload['exception']

    def test_format_includes_stack_info_when_present(self):
        record = _make_record(msg='msg', args=())
        record.stack_info = 'Stack (most recent call last):\n  fake stack frame'
        payload = json.loads(JSONFormatter().format(record))
        assert 'stack' in payload

    def test_format_includes_extra_fields_passed_via_extra_kwarg(self):
        record = _make_record(msg='widget cached', args=())
        record.widget_id = 42
        record.cache_key = 'rtd:widget:42'
        payload = json.loads(JSONFormatter().format(record))
        assert payload['widget_id'] == 42
        assert payload['cache_key'] == 'rtd:widget:42'

    def test_format_never_raises_on_non_json_serializable_extra(self):
        record = _make_record(msg='msg', args=())
        record.weird = object()  # not JSON-serializable
        payload = json.loads(JSONFormatter().format(record))  # must not raise
        assert 'weird' in payload
        assert isinstance(payload['weird'], str)  # fell back to repr()


class TestGetLoggingConfig:

    def test_defaults_to_text_format_when_unset(self, monkeypatch):
        monkeypatch.delenv('LOG_FORMAT', raising=False)
        config = get_logging_config()
        assert config['handlers']['console']['formatter'] == 'text'

    def test_json_format_selected_explicitly(self):
        assert get_logging_config(log_format='json')['handlers']['console']['formatter'] == 'json'

    def test_env_var_selects_json_format(self, monkeypatch):
        monkeypatch.setenv('LOG_FORMAT', 'json')
        assert get_logging_config()['handlers']['console']['formatter'] == 'json'

    def test_unrecognized_format_falls_back_to_text(self):
        assert get_logging_config(log_format='xml')['handlers']['console']['formatter'] == 'text'

    def test_invalid_level_falls_back_to_info(self):
        assert get_logging_config(log_level='NOT_A_REAL_LEVEL')['root']['level'] == 'INFO'

    def test_valid_level_is_respected_case_insensitively(self):
        assert get_logging_config(log_level='debug')['root']['level'] == 'DEBUG'

    def test_output_has_every_key_dictconfig_requires(self):
        """
        Structural completeness check, not a real dictConfig() call (see
        module docstring for why) — still catches a missing/renamed key
        that would break logging.config.dictConfig() at runtime.
        """
        config = get_logging_config(log_format='json', log_level='INFO')
        assert config['version'] == 1
        assert 'json' in config['formatters'] and 'text' in config['formatters']
        assert 'console' in config['handlers']
        assert config['handlers']['console']['class'] == 'logging.StreamHandler'
        assert 'root' in config and 'handlers' in config['root']
        for logger_name in ('django', 'django.request', 'api.realtime_dashboard', 'celery'):
            assert logger_name in config['loggers']


@pytest.mark.django_db
class TestConfigureLogging:

    def test_skips_dictconfig_when_settings_logging_already_set(self):
        """tests/settings.py sets its own LOGGING — this must never be overridden."""
        with override_settings(LOGGING={'version': 1, 'disable_existing_loggers': False}):
            with patch('logging.config.dictConfig') as mock_dictconfig:
                RealtimeDashboardConfig._configure_logging()
                mock_dictconfig.assert_not_called()

    def test_applies_fallback_when_settings_logging_is_empty(self):
        with override_settings(LOGGING={}):
            with patch('logging.config.dictConfig') as mock_dictconfig:
                RealtimeDashboardConfig._configure_logging()
                mock_dictconfig.assert_called_once()
                applied_config = mock_dictconfig.call_args[0][0]
                assert applied_config['version'] == 1
                assert 'console' in applied_config['handlers']


class TestInitSentry:

    def test_noops_when_dsn_not_set(self, monkeypatch):
        monkeypatch.delenv('SENTRY_DSN', raising=False)
        with patch('sentry_sdk.init') as mock_init:
            RealtimeDashboardConfig._init_sentry()
            mock_init.assert_not_called()

    def test_calls_sentry_init_with_expected_kwargs_when_dsn_set(self, monkeypatch):
        monkeypatch.setenv('SENTRY_DSN', 'https://fakepublickey@o0.ingest.sentry.io/0')
        monkeypatch.setenv('SENTRY_ENVIRONMENT', 'staging')
        with patch('sentry_sdk.init') as mock_init:
            RealtimeDashboardConfig._init_sentry()
            mock_init.assert_called_once()
            _, kwargs = mock_init.call_args
            assert kwargs['dsn'] == 'https://fakepublickey@o0.ingest.sentry.io/0'
            assert kwargs['environment'] == 'staging'
            # PII must be opt-in, not default-on — see apps.py comment (KYC-adjacent platform).
            assert kwargs['send_default_pii'] is False
            assert len(kwargs['integrations']) == 4

    def test_defaults_environment_to_production(self, monkeypatch):
        monkeypatch.setenv('SENTRY_DSN', 'https://fakepublickey@o0.ingest.sentry.io/0')
        monkeypatch.delenv('SENTRY_ENVIRONMENT', raising=False)
        with patch('sentry_sdk.init') as mock_init:
            RealtimeDashboardConfig._init_sentry()
            assert mock_init.call_args.kwargs['environment'] == 'production'

    def test_sentry_init_exception_is_caught_not_raised(self, monkeypatch):
        """Error-tracking init failing must never take the app down with it."""
        monkeypatch.setenv('SENTRY_DSN', 'https://fakepublickey@o0.ingest.sentry.io/0')
        with patch('sentry_sdk.init', side_effect=RuntimeError('simulated init failure')):
            RealtimeDashboardConfig._init_sentry()  # must not raise

    def test_noops_gracefully_when_sentry_sdk_package_not_installed(self, monkeypatch):
        """
        Defense-in-depth branch: SENTRY_DSN is set but the sentry-sdk
        package itself is unavailable. Forces this otherwise-hard-to-reach
        ImportError branch the same way rate_shaper_sentinel's platform
        guard branches are tested: inserting None into sys.modules makes
        Python's import system raise ImportError for that name, and
        patch.dict restores the real (already-imported) module afterward.
        """
        monkeypatch.setenv('SENTRY_DSN', 'https://fakepublickey@o0.ingest.sentry.io/0')
        with patch.dict(sys.modules, {'sentry_sdk': None}):
            RealtimeDashboardConfig._init_sentry()  # must not raise ImportError
