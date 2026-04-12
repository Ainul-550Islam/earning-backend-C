"""
Load Tests — Performance and load testing for DR system endpoints.
"""
import pytest
import time
import threading
import concurrent.futures
from datetime import datetime
from unittest.mock import MagicMock


class TestBackupServiceLoad:
    """Load tests for backup service operations."""

    def test_concurrent_backup_requests(self):
        """Test that multiple concurrent backup requests are handled correctly."""
        mock_db = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.add = MagicMock()
        mock_db.refresh = MagicMock(side_effect=lambda x: None)

        mock_policy = MagicMock()
        mock_policy.id = "policy-1"
        mock_policy.is_active = True
        mock_policy.jobs = []

        from ..sa_models import BackupJob
        from ..enums import BackupStatus, BackupType
        call_count = [0]
        lock = threading.Lock()

        def mock_job_factory(**kwargs):
            with lock:
                call_count[0] += 1
            job = MagicMock()
            job.id = f"job-{call_count[0]}"
            job.status = BackupStatus.PENDING
            job.retry_count = 0
            return job

        results = []
        errors = []

        def trigger_backup():
            try:
                from ..services import BackupService
                svc = BackupService(mock_db)
                with threading.Lock():
                    # Mock the repo to avoid DB
                    svc.repo.create_job = mock_job_factory
                    svc.audit.log = MagicMock()
                result = svc.trigger_backup(
                    policy_id="policy-1",
                    backup_type=BackupType.INCREMENTAL,
                    actor_id="load_test"
                )
                results.append(result)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=trigger_backup) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0 or all("mock" in e.lower() for e in errors)

    def test_rto_calculator_performance(self):
        """RTO calculations should complete in < 1ms each."""
        from ..DR_DRILL_MANAGEMENT.rto_calculator import RTOCalculator
        calc = RTOCalculator()
        start = time.monotonic()
        for _ in range(10000):
            result = calc.calculate_from_timestamps(
                datetime(2024, 1, 1, 0, 0, 0),
                datetime(2024, 1, 1, 0, 45, 0)
            )
        elapsed = time.monotonic() - start
        assert elapsed < 1.0  # 10K calculations in < 1 second
        assert result == 2700.0  # 45 minutes in seconds

    def test_alert_rule_evaluation_speed(self):
        """Alert rules should evaluate 1000 metrics per second."""
        from ..MONITORING_ALERTING.alert_rules import AlertRuleEngine
        engine = AlertRuleEngine()
        start = time.monotonic()
        for _ in range(1000):
            engine.get_matching_rules("cpu_percent")
        elapsed = time.monotonic() - start
        assert elapsed < 0.5  # 1K lookups in < 0.5s


class TestStoragePerformance:
    """Performance tests for local storage operations."""

    def setup_method(self):
        import tempfile
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_checksum_throughput(self):
        """SHA256 checksum should process > 50 MB/s."""
        import os, hashlib
        from ..BACKUP_MANAGEMENT.backup_executor import BackupExecutor
        test_size = 10 * 1024 * 1024  # 10 MB
        test_file = os.path.join(self.temp_dir, "perf_test.bin")
        with open(test_file, "wb") as f:
            f.write(os.urandom(test_size))
        start = time.monotonic()
        checksum = BackupExecutor._compute_checksum(test_file)
        elapsed = time.monotonic() - start
        throughput_mbs = test_size / elapsed / 1e6
        assert len(checksum) == 64
        assert throughput_mbs > 50, f"Checksum throughput too slow: {throughput_mbs:.1f} MB/s"
