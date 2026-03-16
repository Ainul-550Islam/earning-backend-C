# =============================================================================
# version_control/migrations/0001_initial.py
# =============================================================================

from __future__ import annotations

import uuid
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ----------------------------------------------------------------
        # AppUpdatePolicy
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name="AppUpdatePolicy",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False,
                    primary_key=True, serialize=False,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("platform", models.CharField(
                    choices=[
                        ("ios", "iOS"), ("android", "Android"), ("web", "Web"),
                        ("windows", "Windows"), ("macos", "macOS"), ("linux", "Linux"),
                    ],
                    db_index=True, max_length=16, verbose_name="Platform",
                )),
                ("min_version", models.CharField(
                    max_length=32,
                    validators=[django.core.validators.RegexValidator(
                        regex=r"^\d+\.\d+\.\d+(-[a-zA-Z0-9._-]+)?(\+[a-zA-Z0-9._-]+)?$"
                    )],
                    verbose_name="Minimum Affected Version",
                )),
                ("max_version", models.CharField(
                    blank=True, default="", max_length=32,
                    validators=[django.core.validators.RegexValidator(
                        regex=r"^\d+\.\d+\.\d+(-[a-zA-Z0-9._-]+)?(\+[a-zA-Z0-9._-]+)?$"
                    )],
                    verbose_name="Maximum Affected Version",
                )),
                ("target_version", models.CharField(
                    max_length=32,
                    validators=[django.core.validators.RegexValidator(
                        regex=r"^\d+\.\d+\.\d+(-[a-zA-Z0-9._-]+)?(\+[a-zA-Z0-9._-]+)?$"
                    )],
                    verbose_name="Target Version",
                )),
                ("update_type", models.CharField(
                    choices=[
                        ("optional", "Optional"),
                        ("required", "Required"),
                        ("critical", "Critical (Blocking)"),
                    ],
                    db_index=True, default="optional", max_length=16,
                )),
                ("release_notes",     models.TextField(blank=True, default="")),
                ("release_notes_url", models.URLField(blank=True, default="", max_length=2048)),
                ("force_update_after", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(
                    choices=[
                        ("draft", "Draft"), ("active", "Active"),
                        ("inactive", "Inactive"), ("archived", "Archived"),
                    ],
                    db_index=True, default="draft", max_length=16,
                )),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="created_update_policies",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "verbose_name": "App Update Policy",
                "verbose_name_plural": "App Update Policies",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="appupdatepolicy",
            index=models.Index(fields=["platform", "status"], name="vc_aup_plat_status_idx"),
        ),
        migrations.AddIndex(
            model_name="appupdatepolicy",
            index=models.Index(fields=["update_type", "status"], name="vc_aup_type_status_idx"),
        ),
        migrations.AddIndex(
            model_name="appupdatepolicy",
            index=models.Index(fields=["target_version"], name="vc_aup_target_idx"),
        ),
        migrations.AddConstraint(
            model_name="appupdatepolicy",
            constraint=models.UniqueConstraint(
                fields=["platform", "min_version", "target_version"],
                condition=models.Q(status="active"),
                name="unique_active_policy_per_platform_version",
            ),
        ),

        # ----------------------------------------------------------------
        # MaintenanceSchedule
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name="MaintenanceSchedule",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False,
                    primary_key=True, serialize=False,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title",       models.CharField(max_length=200)),
                ("description", models.TextField(blank=True, default="")),
                ("platforms",   models.JSONField(default=list)),
                ("status", models.CharField(
                    choices=[
                        ("scheduled", "Scheduled"), ("active", "Active"),
                        ("completed", "Completed"), ("cancelled", "Cancelled"),
                    ],
                    db_index=True, default="scheduled", max_length=16,
                )),
                ("scheduled_start", models.DateTimeField(db_index=True)),
                ("scheduled_end",   models.DateTimeField(db_index=True)),
                ("actual_start",    models.DateTimeField(blank=True, null=True)),
                ("actual_end",      models.DateTimeField(blank=True, null=True)),
                ("bypass_token",    models.CharField(blank=True, default="", max_length=128)),
                ("notify_users",    models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Maintenance Schedule",
                "verbose_name_plural": "Maintenance Schedules",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="maintenanceschedule",
            index=models.Index(
                fields=["status", "scheduled_start"], name="vc_ms_status_start_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="maintenanceschedule",
            index=models.Index(
                fields=["scheduled_start", "scheduled_end"], name="vc_ms_window_idx"
            ),
        ),

        # ----------------------------------------------------------------
        # PlatformRedirect
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name="PlatformRedirect",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False,
                    primary_key=True, serialize=False,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("platform", models.CharField(
                    choices=[
                        ("ios", "iOS"), ("android", "Android"), ("web", "Web"),
                        ("windows", "Windows"), ("macos", "macOS"), ("linux", "Linux"),
                    ],
                    db_index=True, max_length=16, unique=True,
                )),
                ("redirect_type", models.CharField(
                    choices=[
                        ("store", "App Store / Play Store"), ("web", "Web URL"),
                        ("download", "Direct Download"), ("custom", "Custom"),
                    ],
                    default="store", max_length=16,
                )),
                ("url",       models.URLField(max_length=2048)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("notes",     models.TextField(blank=True, default="")),
            ],
            options={
                "verbose_name": "Platform Redirect",
                "verbose_name_plural": "Platform Redirects",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="platformredirect",
            index=models.Index(
                fields=["platform", "is_active"], name="vc_pr_plat_active_idx"
            ),
        ),
    ]
