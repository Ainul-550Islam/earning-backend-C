# =============================================================================
# behavior_analytics/migrations/0001_initial.py
# =============================================================================
"""
Initial migration for behavior_analytics.

Creates tables for:
  - UserPath
  - ClickMetric
  - StayTime
  - EngagementScore
"""

from __future__ import annotations

import uuid
from decimal import Decimal

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
        # UserPath
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name="UserPath",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="analytics_paths",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="User",
                )),
                ("session_id", models.CharField(
                    db_index=True, max_length=128, verbose_name="Session ID"
                )),
                ("nodes", models.JSONField(default=list, verbose_name="Path Nodes")),
                ("device_type", models.CharField(
                    choices=[
                        ("desktop", "Desktop"), ("mobile", "Mobile"),
                        ("tablet", "Tablet"), ("unknown", "Unknown"),
                    ],
                    default="unknown", max_length=16, verbose_name="Device Type",
                )),
                ("status", models.CharField(
                    choices=[
                        ("active", "Active"), ("completed", "Completed"),
                        ("bounced", "Bounced"), ("expired", "Expired"),
                    ],
                    db_index=True, default="active", max_length=16, verbose_name="Session Status",
                )),
                ("entry_url", models.URLField(blank=True, default="", max_length=2048)),
                ("exit_url",  models.URLField(blank=True, default="", max_length=2048)),
                ("ip_address", models.GenericIPAddressField(
                    blank=True, null=True, protocol="both", unpack_ipv4=True
                )),
                ("user_agent", models.TextField(blank=True, default="")),
            ],
            options={
                "verbose_name": "User Path",
                "verbose_name_plural": "User Paths",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="userpath",
            index=models.Index(fields=["user", "session_id"], name="ba_up_user_sess_idx"),
        ),
        migrations.AddIndex(
            model_name="userpath",
            index=models.Index(fields=["status", "created_at"], name="ba_up_status_ts_idx"),
        ),
        migrations.AddIndex(
            model_name="userpath",
            index=models.Index(fields=["device_type"], name="ba_up_device_idx"),
        ),
        migrations.AddConstraint(
            model_name="userpath",
            constraint=models.UniqueConstraint(
                fields=["user", "session_id"],
                name="unique_user_session_path",
            ),
        ),

        # ----------------------------------------------------------------
        # ClickMetric
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name="ClickMetric",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("path", models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="click_metrics",
                    to="behavior_analytics.userpath",
                    verbose_name="User Path",
                )),
                ("page_url", models.URLField(max_length=2048, verbose_name="Page URL")),
                ("element_selector", models.CharField(
                    blank=True, default="", max_length=512, verbose_name="CSS Selector"
                )),
                ("element_text", models.CharField(
                    blank=True, default="", max_length=256, verbose_name="Element Text"
                )),
                ("category", models.CharField(
                    choices=[
                        ("navigation", "Navigation"), ("cta", "Call-to-Action"),
                        ("link", "Hyperlink"), ("button", "Button"),
                        ("form", "Form Element"), ("media", "Media Control"),
                        ("other", "Other"),
                    ],
                    db_index=True, default="other", max_length=16, verbose_name="Click Category",
                )),
                ("x_position",      models.PositiveIntegerField(blank=True, null=True)),
                ("y_position",      models.PositiveIntegerField(blank=True, null=True)),
                ("viewport_width",  models.PositiveSmallIntegerField(blank=True, null=True)),
                ("viewport_height", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("clicked_at", models.DateTimeField(
                    db_index=True, verbose_name="Clicked At"
                )),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "verbose_name": "Click Metric",
                "verbose_name_plural": "Click Metrics",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="clickmetric",
            index=models.Index(fields=["path", "clicked_at"], name="ba_cm_path_ts_idx"),
        ),
        migrations.AddIndex(
            model_name="clickmetric",
            index=models.Index(fields=["category", "clicked_at"], name="ba_cm_cat_ts_idx"),
        ),
        migrations.AddIndex(
            model_name="clickmetric",
            index=models.Index(fields=["page_url"], name="ba_cm_url_idx"),
        ),

        # ----------------------------------------------------------------
        # StayTime
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name="StayTime",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("path", models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="stay_times",
                    to="behavior_analytics.userpath",
                    verbose_name="User Path",
                )),
                ("page_url", models.URLField(max_length=2048, verbose_name="Page URL")),
                ("duration_seconds", models.PositiveIntegerField(
                    validators=[
                        django.core.validators.MinValueValidator(0),
                        django.core.validators.MaxValueValidator(86400),
                    ],
                    verbose_name="Duration (seconds)",
                )),
                ("is_active_time", models.BooleanField(default=True)),
                ("scroll_depth_percent", models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    validators=[django.core.validators.MaxValueValidator(100)],
                )),
            ],
            options={
                "verbose_name": "Stay Time",
                "verbose_name_plural": "Stay Times",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="staytime",
            index=models.Index(fields=["path", "created_at"], name="ba_st_path_ts_idx"),
        ),
        migrations.AddIndex(
            model_name="staytime",
            index=models.Index(fields=["page_url"], name="ba_st_url_idx"),
        ),
        migrations.AddIndex(
            model_name="staytime",
            index=models.Index(fields=["duration_seconds"], name="ba_st_dur_idx"),
        ),

        # ----------------------------------------------------------------
        # EngagementScore
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name="EngagementScore",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="engagement_scores",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="User",
                )),
                ("date",  models.DateField(db_index=True, verbose_name="Date")),
                ("score", models.DecimalField(
                    decimal_places=2, max_digits=5,
                    validators=[
                        django.core.validators.MinValueValidator(Decimal("0")),
                        django.core.validators.MaxValueValidator(Decimal("100")),
                    ],
                    verbose_name="Engagement Score",
                )),
                ("tier", models.CharField(
                    choices=[
                        ("low", "Low (0–30)"), ("medium", "Medium (31–60)"),
                        ("high", "High (61–85)"), ("elite", "Elite (86–100)"),
                    ],
                    db_index=True, default="low", max_length=8, verbose_name="Tier",
                )),
                ("click_count",    models.PositiveIntegerField(default=0)),
                ("total_stay_sec", models.PositiveIntegerField(default=0)),
                ("path_depth",     models.PositiveSmallIntegerField(default=0)),
                ("return_visits",  models.PositiveSmallIntegerField(default=0)),
                ("breakdown_json", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "verbose_name": "Engagement Score",
                "verbose_name_plural": "Engagement Scores",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="engagementscore",
            index=models.Index(fields=["user", "date"], name="ba_es_user_date_idx"),
        ),
        migrations.AddIndex(
            model_name="engagementscore",
            index=models.Index(fields=["tier", "date"], name="ba_es_tier_date_idx"),
        ),
        migrations.AddIndex(
            model_name="engagementscore",
            index=models.Index(fields=["score"], name="ba_es_score_idx"),
        ),
        migrations.AddConstraint(
            model_name="engagementscore",
            constraint=models.UniqueConstraint(
                fields=["user", "date"],
                name="unique_user_daily_engagement",
            ),
        ),
    ]
