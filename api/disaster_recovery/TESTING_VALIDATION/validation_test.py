"""
Validation Tests — Input validation and schema validation tests.
"""
import pytest
from datetime import datetime


class TestValidators:
    """Tests for all input validators."""

    def test_valid_cron_expression(self):
        from ..validators import validate_cron_expression
        assert validate_cron_expression("0 2 * * *") is True    # Daily 2am
        assert validate_cron_expression("0 2 * * 0") is True    # Weekly Sunday 2am
        assert validate_cron_expression("0 */4 * * *") is True  # Every 4 hours

    def test_invalid_cron_expression(self):
        from ..validators import validate_cron_expression
        assert validate_cron_expression("not a cron") is False
        assert validate_cron_expression("") is False
        assert validate_cron_expression("99 99 99 99 99") is False

    def test_valid_backup_types(self):
        from ..validators import validate_backup_type
        assert validate_backup_type("full") is True
        assert validate_backup_type("incremental") is True
        assert validate_backup_type("differential") is True
        assert validate_backup_type("hot") is True
        assert validate_backup_type("cold") is True
        assert validate_backup_type("snapshot") is True

    def test_invalid_backup_type(self):
        from ..validators import validate_backup_type
        assert validate_backup_type("invalid") is False
        assert validate_backup_type("") is False
        assert validate_backup_type("FULL") is False  # Case sensitive

    def test_valid_database_names(self):
        from ..validators import validate_database_name
        assert validate_database_name("mydb") is True
        assert validate_database_name("my_database") is True
        assert validate_database_name("db123") is True
        assert validate_database_name("_private") is True

    def test_invalid_database_names(self):
        from ..validators import validate_database_name
        assert validate_database_name("123invalid") is False   # Starts with digit
        assert validate_database_name("") is False
        assert validate_database_name("a" * 64) is False       # Too long
        assert validate_database_name("my-db") is False        # Hyphens not allowed

    def test_retention_days_valid_range(self):
        from ..validators import validate_retention_days
        assert validate_retention_days(1) is True
        assert validate_retention_days(30) is True
        assert validate_retention_days(3650) is True

    def test_retention_days_invalid_range(self):
        from ..validators import validate_retention_days
        assert validate_retention_days(0) is False
        assert validate_retention_days(-1) is False
        assert validate_retention_days(3651) is False

    def test_valid_rto_seconds(self):
        from ..validators import validate_rto_seconds
        assert validate_rto_seconds(300) is True       # 5 minutes
        assert validate_rto_seconds(3600) is True      # 1 hour
        assert validate_rto_seconds(86400) is True     # 24 hours

    def test_invalid_rto_seconds(self):
        from ..validators import validate_rto_seconds
        assert validate_rto_seconds(0) is False
        assert validate_rto_seconds(59) is False       # Less than 1 minute
        assert validate_rto_seconds(999999999) is False

    def test_storage_path_valid(self):
        from ..validators import validate_storage_path
        assert validate_storage_path("backups/2024/01/backup.dump") is True
        assert validate_storage_path("s3/bucket/key") is True

    def test_storage_path_invalid(self):
        from ..validators import validate_storage_path
        assert validate_storage_path("") is False
        assert validate_storage_path("path/with<invalid>chars") is False
        assert validate_storage_path("a" * 1001) is False

    def test_point_in_time_within_range(self):
        from ..validators import validate_point_in_time
        from datetime import timedelta
        now = datetime.utcnow()
        earliest = now - timedelta(days=7)
        latest = now
        assert validate_point_in_time(now - timedelta(days=3), earliest, latest) is True
        assert validate_point_in_time(now - timedelta(days=8), earliest, latest) is False
        assert validate_point_in_time(now + timedelta(hours=1), earliest, latest) is False


class TestSchemas:
    """Tests for Pydantic schema validation."""

    def test_backup_policy_create_valid(self):
        from ..schemas import BackupPolicyCreate
        from ..enums import BackupType, BackupFrequency, StorageProvider
        policy = BackupPolicyCreate(
            name="nightly-backup",
            backup_type=BackupType.FULL,
            frequency=BackupFrequency.DAILY,
            storage_provider=StorageProvider.AWS_S3,
            retention_days=30,
        )
        assert policy.name == "nightly-backup"
        assert policy.enable_encryption is True

    def test_backup_policy_retention_capped(self):
        from ..schemas import BackupPolicyCreate
        from ..enums import BackupType, BackupFrequency, StorageProvider
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            BackupPolicyCreate(
                name="test",
                backup_type=BackupType.FULL,
                frequency=BackupFrequency.DAILY,
                storage_provider=StorageProvider.LOCAL,
                retention_days=9999,  # Exceeds max 3650
            )

    def test_restore_request_pitr_requires_timestamp(self):
        from ..schemas import RestoreRequestCreate
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            RestoreRequestCreate(
                restore_type="point_in_time",
                # Missing point_in_time
            )

    def test_drill_create_valid(self):
        from ..schemas import DrillCreate
        from ..enums import DisasterType
        from datetime import timedelta
        drill = DrillCreate(
            name="Monthly Failover Drill",
            scenario_type=DisasterType.HARDWARE_FAILURE,
            scheduled_at=datetime.utcnow() + timedelta(days=7),
            target_rto_seconds=3600,
            target_rpo_seconds=900,
        )
        assert drill.name == "Monthly Failover Drill"
