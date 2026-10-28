"""
Backup Module Test Factories
factory_boy factories for generating test data for backup models.
"""

import uuid
import factory
import factory.fuzzy
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
    is_active = True


class AdminUserFactory(UserFactory):
    is_staff = True
    is_superuser = True
    username = factory.Sequence(lambda n: f"admin_{n}")


class BackupStorageLocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "backup.BackupStorageLocation"

    name = factory.Sequence(lambda n: f"Storage Location {n}")
    storage_type = factory.fuzzy.FuzzyChoice(["s3", "azure", "gcs", "local"])
    endpoint = factory.LazyAttribute(lambda obj: f"{obj.storage_type}.example.com/bucket")
    is_active = True
    is_default = False
    config = factory.LazyFunction(lambda: {"bucket_name": "test-bucket", "region": "us-east-1"})


class DefaultStorageLocationFactory(BackupStorageLocationFactory):
    is_default = True
    storage_type = "s3"


class BackupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "backup.Backup"

    name = factory.Sequence(lambda n: f"backup_{n:04d}")
    status = "completed"
    backup_type = "full"
    size_bytes = factory.fuzzy.FuzzyInteger(1024, 1024 * 1024 * 500)
    created_by = factory.SubFactory(UserFactory)
    storage_location = factory.SubFactory(BackupStorageLocationFactory)
    retention_days = 30
    created_at = factory.LazyFunction(timezone.now)
    file_path = factory.LazyAttribute(lambda obj: f"/backups/{obj.name}.sql.gz")


class PendingBackupFactory(BackupFactory):
    status = "pending"
    size_bytes = None


class RunningBackupFactory(BackupFactory):
    status = "running"
    started_at = factory.LazyFunction(timezone.now)


class FailedBackupFactory(BackupFactory):
    status = "failed"
    error_message = "Disk quota exceeded"


class ExpiredBackupFactory(BackupFactory):
    retention_days = 1
    created_at = factory.LazyAttribute(lambda obj: timezone.now() - timedelta(days=10))


class BackupScheduleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "backup.BackupSchedule"

    name = factory.Sequence(lambda n: f"Schedule {n}")
    cron_expression = "0 2 * * *"
    is_active = True
    retention_days = 30
    storage_location = factory.SubFactory(BackupStorageLocationFactory)
    created_by = factory.SubFactory(UserFactory)
    next_run_at = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=2))


class DailyScheduleFactory(BackupScheduleFactory):
    cron_expression = "0 0 * * *"
    name = factory.Sequence(lambda n: f"Daily Schedule {n}")


class WeeklyScheduleFactory(BackupScheduleFactory):
    cron_expression = "0 0 * * 0"
    name = factory.Sequence(lambda n: f"Weekly Schedule {n}")


class BackupVerificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "backup.BackupVerification"

    backup = factory.SubFactory(BackupFactory)
    status = "completed"
    checksum_valid = True
    size_valid = True
    restore_test_passed = True
    verified_at = factory.LazyFunction(timezone.now)
    verified_by = factory.SubFactory(UserFactory)


class BackupAlertFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "backup.BackupAlert"

    alert_type = factory.fuzzy.FuzzyChoice(["failure", "warning", "storage_full"])
    severity = factory.fuzzy.FuzzyChoice(["low", "medium", "high", "critical"])
    message = factory.Sequence(lambda n: f"Alert message {n}")
    is_resolved = False
    created_at = factory.LazyFunction(timezone.now)


class ResolvedAlertFactory(BackupAlertFactory):
    is_resolved = True
    resolved_at = factory.LazyFunction(timezone.now)
