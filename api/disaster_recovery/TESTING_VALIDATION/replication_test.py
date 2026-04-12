"""Tests for Replication Management — lag detection, failover."""
import pytest
from ..REPLICATION_MANAGEMENT.replication_lag_detector import ReplicationLagDetector
from ..REPLICATION_MANAGEMENT.read_replica_manager import ReadReplicaManager
from ..REPLICATION_MANAGEMENT.write_replica_manager import WriteReplicaManager


class TestReplicationLagDetector:
    def setup_method(self):
        self.detector = ReplicationLagDetector(warning_seconds=30, critical_seconds=120)

    def test_healthy_lag(self):
        result = self.detector.assess(5.0)
        assert result["level"] == "ok"

    def test_warning_lag(self):
        result = self.detector.assess(45.0)
        assert result["level"] == "warning"

    def test_critical_lag(self):
        result = self.detector.assess(200.0)
        assert result["level"] == "critical"

    def test_zero_lag_is_healthy(self):
        result = self.detector.assess(0.0)
        assert result["level"] == "ok"


class TestReadReplicaManager:
    def setup_method(self):
        self.manager = ReadReplicaManager(
            replicas=[
                {"host": "replica-1", "port": 5432, "healthy": True},
                {"host": "replica-2", "port": 5432, "healthy": True},
                {"host": "replica-3", "port": 5432, "healthy": True},
            ],
            strategy="round_robin"
        )

    def test_get_replica_returns_healthy(self):
        replica = self.manager.get_replica()
        assert replica["healthy"] is True

    def test_round_robin_cycles_through_replicas(self):
        seen = set()
        for _ in range(6):
            r = self.manager.get_replica()
            seen.add(r["host"])
        assert len(seen) == 3

    def test_unhealthy_replica_excluded(self):
        self.manager.mark_unhealthy("replica-1")
        for _ in range(10):
            r = self.manager.get_replica()
            assert r["host"] != "replica-1"

    def test_no_healthy_replicas_raises(self):
        for r in self.manager.replicas:
            r["healthy"] = False
        with pytest.raises(Exception):
            self.manager.get_replica()


class TestWriteReplicaManager:
    def setup_method(self):
        self.manager = WriteReplicaManager(
            primary_config={"host": "primary", "port": 5432},
            failover_primary={"host": "failover", "port": 5432}
        )

    def test_get_write_target_returns_primary(self):
        target = self.manager.get_write_target()
        assert target["host"] == "primary"

    def test_switch_to_failover(self):
        self.manager.switch_to_failover()
        target = self.manager.get_write_target()
        assert target["host"] == "failover"

    def test_switch_back_to_primary(self):
        self.manager.switch_to_failover()
        self.manager.switch_to_primary()
        target = self.manager.get_write_target()
        assert target["host"] == "primary"
