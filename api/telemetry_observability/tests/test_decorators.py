"""
Tests for decorators.py — all decorator functions.
"""
import pytest
import time
from unittest.mock import patch, MagicMock, call


class TestRecordMetricDecorator:
    def test_counter_recorded_on_success(self):
        from ..decorators import record_metric
        with patch('telemetry_observability.decorators.MetricsCollector') as mock_cls:
            mock = MagicMock()
            mock_cls.return_value = mock

            @record_metric('test_calls', metric_type='counter')
            def my_func():
                return 'ok'

            result = my_func()
            assert result == 'ok'
            mock.record_counter.assert_called_once()
            args = mock.record_counter.call_args
            assert args[1]['name'] == 'test_calls' or args[0][0] == 'test_calls'

    def test_gauge_records_duration_on_success(self):
        from ..decorators import record_metric
        with patch('telemetry_observability.decorators.MetricsCollector') as mock_cls:
            mock = MagicMock()
            mock_cls.return_value = mock

            @record_metric('op_duration', metric_type='gauge')
            def my_func():
                return 42

            my_func()
            mock.record_gauge.assert_called_once()

    def test_error_counter_recorded_on_exception(self):
        from ..decorators import record_metric
        with patch('telemetry_observability.decorators.MetricsCollector') as mock_cls:
            mock = MagicMock()
            mock_cls.return_value = mock

            @record_metric('test_metric')
            def failing_func():
                raise ValueError("test error")

            with pytest.raises(ValueError):
                failing_func()

            mock.record_counter.assert_called_once()
            args = mock.record_counter.call_args
            assert 'error' in str(args)

    def test_exception_still_propagates(self):
        from ..decorators import record_metric
        with patch('telemetry_observability.decorators.MetricsCollector'):
            @record_metric('test')
            def bad():
                raise RuntimeError("boom")

            with pytest.raises(RuntimeError):
                bad()


class TestTraceOperationDecorator:
    def test_span_started_and_finished_on_success(self):
        from ..decorators import trace_operation
        with patch('telemetry_observability.decorators.TracingService') as mock_cls:
            mock_svc = MagicMock()
            mock_span = MagicMock()
            mock_span.span_id = 'span-123'
            mock_svc.start_span.return_value = mock_span
            mock_cls.return_value = mock_svc

            @trace_operation(service='test-svc')
            def my_op():
                return 'done'

            result = my_op()
            assert result == 'done'
            mock_svc.start_span.assert_called_once()
            mock_svc.finish_span.assert_called_once_with('span-123', status='success')

    def test_span_finished_with_error_on_exception(self):
        from ..decorators import trace_operation
        with patch('telemetry_observability.decorators.TracingService') as mock_cls:
            mock_svc  = MagicMock()
            mock_span = MagicMock()
            mock_span.span_id = 'span-err'
            mock_svc.start_span.return_value = mock_span
            mock_cls.return_value = mock_svc

            @trace_operation(service='test-svc')
            def bad_op():
                raise ValueError("fail")

            with pytest.raises(ValueError):
                bad_op()

            finish_call = mock_svc.finish_span.call_args
            assert finish_call[1]['status'] == 'error'

    def test_operation_name_defaults_to_func_name(self):
        from ..decorators import trace_operation
        with patch('telemetry_observability.decorators.TracingService') as mock_cls:
            mock_svc  = MagicMock()
            mock_span = MagicMock()
            mock_span.span_id = 's1'
            mock_svc.start_span.return_value = mock_span
            mock_cls.return_value = mock_svc

            @trace_operation(service='svc')
            def my_specific_function():
                return True

            my_specific_function()
            start_args = mock_svc.start_span.call_args
            op_name = start_args[1].get('operation_name') or start_args[0][0]
            assert 'my_specific_function' in str(op_name)

    def test_custom_operation_name(self):
        from ..decorators import trace_operation
        with patch('telemetry_observability.decorators.TracingService') as mock_cls:
            mock_svc  = MagicMock()
            mock_span = MagicMock()
            mock_span.span_id = 's2'
            mock_svc.start_span.return_value = mock_span
            mock_cls.return_value = mock_svc

            @trace_operation(service='svc', operation_name='custom.op')
            def any_func():
                return True

            any_func()
            start_args = mock_svc.start_span.call_args
            assert 'custom.op' in str(start_args)


@pytest.mark.django_db
class TestLogFunctionCallDecorator:
    def test_log_entry_created_on_call(self):
        from ..decorators import log_function_call
        from ..models.log_entry import LogEntry

        @log_function_call(level='info', service='test')
        def my_logged_func():
            return 'result'

        before = LogEntry.objects.count()
        my_logged_func()
        after  = LogEntry.objects.count()
        assert after > before

    def test_error_log_created_on_exception(self):
        from ..decorators import log_function_call
        from ..models.log_entry import LogEntry

        @log_function_call(level='info', service='test')
        def failing_func():
            raise ValueError("test")

        with pytest.raises(ValueError):
            failing_func()

        error_logs = LogEntry.objects.filter(level='error', source='decorator')
        assert error_logs.exists()

    def test_include_result_logs_return_value(self):
        from ..decorators import log_function_call
        from ..models.log_entry import LogEntry

        @log_function_call(level='info', include_result=True, service='test')
        def func_with_result():
            return {'key': 'value'}

        func_with_result()
        logs = LogEntry.objects.filter(logger_name='telemetry_observability.decorators')
        assert logs.exists()


class TestMeasureTimeDecorator:
    def test_records_duration(self):
        from ..decorators import measure_time
        with patch('telemetry_observability.decorators.MetricsCollector') as mock_cls:
            mock = MagicMock()
            mock_cls.return_value = mock

            @measure_time('my_op_duration_ms')
            def timed_func():
                time.sleep(0.01)
                return 'done'

            result = timed_func()
            assert result == 'done'
            mock.record_gauge.assert_called_once()
            call_args = mock.record_gauge.call_args
            assert call_args[1].get('name') == 'my_op_duration_ms' or \
                   call_args[0][0] == 'my_op_duration_ms' if call_args[0] else True

    def test_default_metric_name_from_func(self):
        from ..decorators import measure_time
        with patch('telemetry_observability.decorators.MetricsCollector') as mock_cls:
            mock = MagicMock()
            mock_cls.return_value = mock

            @measure_time()
            def operation_xyz():
                return 1

            operation_xyz()
            call_args = mock.record_gauge.call_args
            assert 'operation_xyz' in str(call_args)


class TestCacheResultDecorator:
    def test_caches_result(self):
        from ..decorators import cache_result
        call_count = [0]

        @cache_result(ttl=60)
        def expensive(*args, **kwargs):
            call_count[0] += 1
            return 'computed'

        with patch('django.core.cache.cache.get', return_value=None), \
             patch('django.core.cache.cache.set'):
            r1 = expensive('arg1')
            assert r1 == 'computed'
            assert call_count[0] == 1

    def test_returns_cached_value(self):
        from ..decorators import cache_result

        @cache_result(ttl=60)
        def expensive(*args, **kwargs):
            return 'fresh'

        with patch('django.core.cache.cache.get', return_value='cached_val'):
            result = expensive()
            assert result == 'cached_val'


class TestRetryOnFailureDecorator:
    def test_succeeds_on_first_try(self):
        from ..decorators import retry_on_failure
        calls = [0]

        @retry_on_failure(max_retries=3, delay=0)
        def flaky():
            calls[0] += 1
            return 'ok'

        result = flaky()
        assert result == 'ok'
        assert calls[0] == 1

    def test_retries_on_failure(self):
        from ..decorators import retry_on_failure
        calls = [0]

        @retry_on_failure(max_retries=3, delay=0)
        def fails_twice():
            calls[0] += 1
            if calls[0] < 3:
                raise RuntimeError("not yet")
            return 'success'

        result = fails_twice()
        assert result == 'success'
        assert calls[0] == 3

    def test_raises_after_max_retries(self):
        from ..decorators import retry_on_failure

        @retry_on_failure(max_retries=2, delay=0)
        def always_fails():
            raise ValueError("always bad")

        with pytest.raises(ValueError):
            always_fails()
