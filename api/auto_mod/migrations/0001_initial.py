# =============================================================================
# auto_mod/migrations/0001_initial.py
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

        # ── AutoApprovalRule ────────────────────────────────────────────
        migrations.CreateModel(
            name="AutoApprovalRule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200, unique=True)),
                ("description", models.TextField(blank=True, default="")),
                ("submission_type", models.CharField(
                    choices=[
                        ("task_proof","Task Proof"),("user_content","User Content"),
                        ("profile","Profile"),("report","Report"),
                        ("comment","Comment"),("media","Media Upload"),
                    ], db_index=True, max_length=20,
                )),
                ("priority", models.PositiveSmallIntegerField(
                    default=50,
                    validators=[
                        django.core.validators.MinValueValidator(1),
                        django.core.validators.MaxValueValidator(100),
                    ],
                    db_index=True,
                )),
                ("conditions", models.JSONField(default=list)),
                ("action", models.CharField(
                    choices=[
                        ("approve","Auto-Approve"),("reject","Auto-Reject"),
                        ("flag","Flag for Review"),("escalate","Escalate"),
                        ("request_proof","Request Additional Proof"),
                        ("notify_admin","Notify Admin"),
                    ], max_length=20,
                )),
                ("confidence_threshold", models.FloatField(
                    default=0.9,
                    validators=[
                        django.core.validators.MinValueValidator(0.0),
                        django.core.validators.MaxValueValidator(1.0),
                    ],
                )),
                ("is_active",  models.BooleanField(default=True, db_index=True)),
                ("is_system",  models.BooleanField(default=False)),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="created_mod_rules",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={"ordering": ["-created_at"], "verbose_name": "Auto-Approval Rule"},
        ),
        migrations.AddIndex(
            model_name="autoapprovalrule",
            index=models.Index(
                fields=["submission_type", "is_active", "priority"],
                name="am_aar_type_active_pri_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="autoapprovalrule",
            index=models.Index(fields=["action", "is_active"], name="am_aar_action_idx"),
        ),

        # ── SuspiciousSubmission ────────────────────────────────────────
        migrations.CreateModel(
            name="SuspiciousSubmission",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("content_type", models.CharField(max_length=100, db_index=True)),
                ("content_id",   models.CharField(max_length=128, db_index=True)),
                ("submission_type", models.CharField(
                    choices=[
                        ("task_proof","Task Proof"),("user_content","User Content"),
                        ("profile","Profile"),("report","Report"),
                        ("comment","Comment"),("media","Media Upload"),
                    ], db_index=True, max_length=20,
                )),
                ("submitted_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="suspicious_submissions",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("status", models.CharField(
                    choices=[
                        ("pending","Pending"),("scanning","AI Scanning"),
                        ("auto_approved","Auto-Approved"),("auto_rejected","Auto-Rejected"),
                        ("human_review","Awaiting Human Review"),
                        ("human_approved","Human-Approved"),("human_rejected","Human-Rejected"),
                        ("escalated","Escalated"),("expired","Expired"),
                    ], default="pending", db_index=True, max_length=20,
                )),
                ("ai_confidence", models.FloatField(
                    blank=True, null=True,
                    validators=[
                        django.core.validators.MinValueValidator(0.0),
                        django.core.validators.MaxValueValidator(1.0),
                    ],
                )),
                ("risk_score", models.FloatField(
                    blank=True, null=True,
                    validators=[
                        django.core.validators.MinValueValidator(0.0),
                        django.core.validators.MaxValueValidator(1.0),
                    ],
                )),
                ("risk_level", models.CharField(
                    choices=[("low","Low"),("medium","Medium"),("high","High"),("critical","Critical")],
                    default="low", db_index=True, max_length=10,
                )),
                ("flag_reason", models.CharField(
                    choices=[
                        ("spam","Spam"),("fake_proof","Fake Proof"),
                        ("inappropriate","Inappropriate Content"),
                        ("duplicate","Duplicate Submission"),
                        ("policy_violation","Policy Violation"),
                        ("suspicious_pattern","Suspicious Pattern"),
                        ("low_quality","Low Quality"),("other","Other"),
                    ], default="other", max_length=25,
                )),
                ("ai_explanation", models.TextField(blank=True, default="")),
                ("scan_metadata",  models.JSONField(blank=True, default=dict)),
                ("matched_rule", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="flagged_submissions",
                    to="auto_mod.autoapprovalrule",
                )),
                ("reviewed_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="reviewed_submissions",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("reviewed_at",   models.DateTimeField(blank=True, null=True)),
                ("reviewer_note", models.TextField(blank=True, default="")),
                ("final_status",  models.CharField(blank=True, default="", max_length=20)),
                ("escalated_to", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="escalated_submissions",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-created_at"], "verbose_name": "Suspicious Submission"},
        ),
        migrations.AddIndex(
            model_name="suspicioussubmission",
            index=models.Index(fields=["status","risk_level","created_at"], name="am_ss_status_risk_ts_idx"),
        ),
        migrations.AddIndex(
            model_name="suspicioussubmission",
            index=models.Index(fields=["content_type","content_id"], name="am_ss_content_idx"),
        ),
        migrations.AddIndex(
            model_name="suspicioussubmission",
            index=models.Index(fields=["submitted_by","status"], name="am_ss_user_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="suspicioussubmission",
            constraint=models.UniqueConstraint(
                fields=["content_type","content_id"],
                name="unique_submission_per_content",
            ),
        ),

        # ── ProofScanner ────────────────────────────────────────────────
        migrations.CreateModel(
            name="ProofScanner",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("submission", models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="scans",
                    to="auto_mod.suspicioussubmission",
                )),
                ("scan_type", models.CharField(
                    choices=[("image","Image Scan"),("text","Text Analysis"),
                             ("ocr","OCR Extraction"),("combined","Combined")],
                    db_index=True, max_length=10,
                )),
                ("file_url",    models.URLField(blank=True, default="", max_length=2048)),
                ("input_text",  models.TextField(blank=True, default="")),
                ("confidence",  models.FloatField(
                    blank=True, null=True,
                    validators=[
                        django.core.validators.MinValueValidator(0.0),
                        django.core.validators.MaxValueValidator(1.0),
                    ],
                )),
                ("is_flagged",     models.BooleanField(blank=True, null=True)),
                ("labels",         models.JSONField(blank=True, default=list)),
                ("ocr_text",       models.TextField(blank=True, default="")),
                ("raw_result",     models.JSONField(blank=True, default=dict)),
                ("error_message",  models.CharField(blank=True, default="", max_length=500)),
                ("duration_ms",    models.PositiveIntegerField(blank=True, null=True)),
                ("model_version",  models.CharField(blank=True, default="", max_length=64)),
            ],
            options={"ordering": ["-created_at"], "verbose_name": "Proof Scanner"},
        ),
        migrations.AddIndex(
            model_name="proofscanner",
            index=models.Index(fields=["submission","scan_type"], name="am_ps_sub_type_idx"),
        ),
        migrations.AddIndex(
            model_name="proofscanner",
            index=models.Index(fields=["is_flagged","created_at"], name="am_ps_flagged_ts_idx"),
        ),

        # ── TaskBot ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name="TaskBot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at",  models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at",  models.DateTimeField(auto_now=True)),
                ("name",        models.CharField(max_length=200, unique=True)),
                ("description", models.TextField(blank=True, default="")),
                ("submission_type", models.CharField(
                    choices=[
                        ("task_proof","Task Proof"),("user_content","User Content"),
                        ("profile","Profile"),("report","Report"),
                        ("comment","Comment"),("media","Media Upload"),
                    ], db_index=True, max_length=20,
                )),
                ("status", models.CharField(
                    choices=[("idle","Idle"),("running","Running"),("paused","Paused"),
                             ("error","Error"),("disabled","Disabled")],
                    default="idle", db_index=True, max_length=12,
                )),
                ("config",           models.JSONField(blank=True, default=dict)),
                ("total_processed",  models.PositiveIntegerField(default=0)),
                ("total_approved",   models.PositiveIntegerField(default=0)),
                ("total_rejected",   models.PositiveIntegerField(default=0)),
                ("total_escalated",  models.PositiveIntegerField(default=0)),
                ("total_errors",     models.PositiveIntegerField(default=0)),
                ("last_heartbeat",   models.DateTimeField(blank=True, null=True)),
                ("last_error",       models.TextField(blank=True, default="")),
                ("retry_count",      models.PositiveSmallIntegerField(default=0)),
                ("assigned_to", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="assigned_bots",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-created_at"], "verbose_name": "Task Bot"},
        ),
        migrations.AddIndex(
            model_name="taskbot",
            index=models.Index(fields=["status","submission_type"], name="am_tb_status_type_idx"),
        ),
        migrations.AddIndex(
            model_name="taskbot",
            index=models.Index(fields=["last_heartbeat"], name="am_tb_heartbeat_idx"),
        ),
    ]
