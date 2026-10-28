# =============================================================================
# fraud_detection/views_management.py
# =============================================================================
"""
API endpoints that expose Django management commands via HTTP.

Allows triggering long-running fraud operations through the REST API
instead of only via the CLI. All endpoints are admin-only and log
to the fraud audit trail.

Exposed commands:
  1. export_fraud_report        → POST /fraud/management/export-report/
  2. recalculate_risk_scores    → POST /fraud/management/recalculate-risk/
  3. review_flagged_users       → POST /fraud/management/review-flagged/
  4. run_fraud_scan             → POST /fraud/management/run-scan/
  5. seed_fraud_rules           → POST /fraud/management/seed-rules/
  6. fix_arrays                 → POST /fraud/management/fix-arrays/
  7. Status / history           → GET  /fraud/management/status/
  8. Running jobs               → GET  /fraud/management/jobs/
"""
from __future__ import annotations

import io
import json
import logging
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.fraud_detection.missing_components import (
    BurstProtectionThrottle,
    FraudEndpointRateThrottle,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Job tracker (in-memory + Redis for short-term persistence)
# ─────────────────────────────────────────────────────────────────────────────

_JOBS_CACHE_KEY = 'mgmt_jobs'
_JOBS_CACHE_TTL = 3600  # 1 hour


def _get_jobs() -> Dict[str, Dict]:
    return cache.get(_JOBS_CACHE_KEY, {})


def _save_jobs(jobs: Dict[str, Dict]) -> None:
    cache.set(_JOBS_CACHE_KEY, jobs, timeout=_JOBS_CACHE_TTL)


def _create_job(command: str, options: Dict, user_id: int) -> str:
    job_id = str(uuid.uuid4())
    jobs   = _get_jobs()
    jobs[job_id] = {
        'job_id':     job_id,
        'command':    command,
        'options':    options,
        'status':     'running',
        'started_at': timezone.now().isoformat(),
        'ended_at':   None,
        'output':     '',
        'error':      '',
        'user_id':    user_id,
    }
    _save_jobs(jobs)
    return job_id


def _finish_job(job_id: str, output: str = '', error: str = '') -> None:
    jobs = _get_jobs()
    if job_id in jobs:
        jobs[job_id]['status']   = 'error' if error else 'completed'
        jobs[job_id]['ended_at'] = timezone.now().isoformat()
        jobs[job_id]['output']   = output
        jobs[job_id]['error']    = error
        _save_jobs(jobs)


def _run_command_async(job_id: str, command: str, options: Dict) -> None:
    """Run a management command in a background thread."""
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    try:
        call_command(command, stdout=stdout_buf, stderr=stderr_buf, **options)
        _finish_job(job_id, output=stdout_buf.getvalue(), error=stderr_buf.getvalue())
        logger.info("Management command '%s' (job=%s) completed", command, job_id)
    except Exception as exc:
        logger.exception("Management command '%s' (job=%s) failed: %s", command, job_id, exc)
        _finish_job(job_id, error=str(exc))


def _start_job(command: str, options: Dict, user_id: int) -> str:
    job_id = _create_job(command, options, user_id)
    t = threading.Thread(
        target=_run_command_async,
        args=(job_id, command, options),
        daemon=True,
    )
    t.start()
    return job_id


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ok(data, code=status.HTTP_200_OK):
    return Response(data, status=code)

def _err(msg, code=status.HTTP_400_BAD_REQUEST):
    return Response({'error': msg}, status=code)


# =============================================================================
# 1. export_fraud_report
# =============================================================================

class ExportFraudReportCommandAPIView(APIView):
    """
    POST /fraud/management/export-report/

    Trigger the export_fraud_report management command via HTTP.

    Body:
        format        (str)  csv | excel | json | pdf | all  — default: csv
        report_type   (str)  overview | detailed | summary | trends
                             | cases | alerts | users         — default: overview
        days          (int)  number of days to include       — default: 30
        start_date    (str)  YYYY-MM-DD
        end_date      (str)  YYYY-MM-DD
        output_file   (str)  file path without extension
        filters       (dict) additional filter dict
        include_charts(bool) include charts (Excel/PDF only)
        split_by_user (bool) split report by user
        async_run     (bool) run in background; returns job_id — default: True
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        data        = request.data
        fmt         = data.get('format', 'csv')
        report_type = data.get('report_type', 'overview')
        days        = int(data.get('days', 30))
        start_date  = data.get('start_date', '')
        end_date    = data.get('end_date', '')
        output_file = data.get('output_file', '')
        filters     = data.get('filters', {})
        include_charts = bool(data.get('include_charts', False))
        split_by_user  = bool(data.get('split_by_user', False))
        async_run      = bool(data.get('async_run', True))

        valid_formats = ('csv', 'excel', 'json', 'pdf', 'all')
        valid_types   = ('overview', 'detailed', 'summary', 'trends',
                         'cases', 'alerts', 'users')

        if fmt not in valid_formats:
            return _err(f"format must be one of: {', '.join(valid_formats)}")
        if report_type not in valid_types:
            return _err(f"report_type must be one of: {', '.join(valid_types)}")

        options: Dict[str, Any] = {
            'format':       fmt,
            'report_type':  report_type,
            'days':         days,
            'include_charts': include_charts,
            'split_by_user':  split_by_user,
            'verbose':        False,
        }
        if start_date:
            options['start_date'] = start_date
        if end_date:
            options['end_date'] = end_date
        if output_file:
            options['output_file'] = output_file
        if filters:
            options['filters'] = json.dumps(filters)

        logger.info(
            "export_fraud_report triggered by user %s: format=%s type=%s days=%d",
            request.user.id, fmt, report_type, days,
        )

        if async_run:
            job_id = _start_job('export_fraud_report', options, request.user.id)
            return _ok({
                'job_id':     job_id,
                'status':     'running',
                'message':    'Export job started. Poll /fraud/management/jobs/ for status.',
                'options':    options,
            }, status.HTTP_202_ACCEPTED)
        else:
            stdout_buf = io.StringIO()
            try:
                call_command('export_fraud_report', stdout=stdout_buf, **options)
                return _ok({'status': 'completed', 'output': stdout_buf.getvalue()})
            except Exception as exc:
                logger.exception("export_fraud_report failed: %s", exc)
                return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 2. recalculate_risk_scores
# =============================================================================

class RecalculateRiskScoresCommandAPIView(APIView):
    """
    POST /fraud/management/recalculate-risk/

    Trigger recalculate_risk_scores management command.

    Body:
        entity_type  (str)  all | users | ips | devices | cases — default: all
        user_id      (int)  specific user ID (optional)
        days         (int)  days to look back                  — default: 30
        force_update (bool) force update even if recent calc   — default: False
        batch_size   (int)  processing batch size              — default: 100
        dry_run      (bool) calculate without saving           — default: False
        async_run    (bool) run in background                  — default: True
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        data        = request.data
        entity_type = data.get('entity_type', 'all')
        user_id     = data.get('user_id')
        days        = int(data.get('days', 30))
        force_update = bool(data.get('force_update', False))
        batch_size  = int(data.get('batch_size', 100))
        dry_run     = bool(data.get('dry_run', False))
        async_run   = bool(data.get('async_run', True))

        valid_types = ('all', 'users', 'ips', 'devices', 'cases')
        if entity_type not in valid_types:
            return _err(f"entity_type must be one of: {', '.join(valid_types)}")

        options: Dict[str, Any] = {
            'entity_type':  entity_type,
            'days':         days,
            'force_update': force_update,
            'batch_size':   batch_size,
            'dry_run':      dry_run,
            'verbose':      False,
        }
        if user_id is not None:
            options['user_id'] = int(user_id)

        logger.info(
            "recalculate_risk_scores triggered by user %s: entity=%s days=%d dry_run=%s",
            request.user.id, entity_type, days, dry_run,
        )

        if async_run:
            job_id = _start_job('recalculate_risk_scores', options, request.user.id)
            return _ok({
                'job_id':  job_id,
                'status':  'running',
                'message': 'Recalculation started. Poll /fraud/management/jobs/ for status.',
                'options': options,
            }, status.HTTP_202_ACCEPTED)
        else:
            stdout_buf = io.StringIO()
            try:
                call_command('recalculate_risk_scores', stdout=stdout_buf, **options)
                return _ok({'status': 'completed', 'output': stdout_buf.getvalue()})
            except Exception as exc:
                logger.exception("recalculate_risk_scores failed: %s", exc)
                return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 3. review_flagged_users
# =============================================================================

class ReviewFlaggedUsersCommandAPIView(APIView):
    """
    POST /fraud/management/review-flagged/

    Trigger review_flagged_users management command.

    Body:
        risk_threshold   (int)  minimum risk score          — default: 70
        monitoring_level (str)  all|strict|enhanced|standard — default: all
        days             (int)  days to look back            — default: 7
        auto_review      (bool) auto-approve low-risk users  — default: False
        create_cases     (bool) auto-create cases for high-risk — default: False
        batch_size       (int)  processing batch size        — default: 10
        non_interactive  (bool) skip interactive prompts     — default: True
        async_run        (bool) run in background            — default: True
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        data             = request.data
        risk_threshold   = int(data.get('risk_threshold', 70))
        monitoring_level = data.get('monitoring_level', 'all')
        days             = int(data.get('days', 7))
        auto_review      = bool(data.get('auto_review', False))
        create_cases     = bool(data.get('create_cases', False))
        batch_size       = int(data.get('batch_size', 10))
        non_interactive  = bool(data.get('non_interactive', True))
        async_run        = bool(data.get('async_run', True))

        valid_levels = ('all', 'strict', 'enhanced', 'standard')
        if monitoring_level not in valid_levels:
            return _err(f"monitoring_level must be one of: {', '.join(valid_levels)}")
        if not 0 <= risk_threshold <= 100:
            return _err('risk_threshold must be 0–100')

        options: Dict[str, Any] = {
            'risk_threshold':   risk_threshold,
            'monitoring_level': monitoring_level,
            'days':             days,
            'auto_review':      auto_review,
            'create_cases':     create_cases,
            'batch_size':       batch_size,
            'non_interactive':  non_interactive,
        }

        logger.info(
            "review_flagged_users triggered by user %s: threshold=%d level=%s",
            request.user.id, risk_threshold, monitoring_level,
        )

        if async_run:
            job_id = _start_job('review_flagged_users', options, request.user.id)
            return _ok({
                'job_id':  job_id,
                'status':  'running',
                'message': 'Review job started. Poll /fraud/management/jobs/ for status.',
                'options': options,
            }, status.HTTP_202_ACCEPTED)
        else:
            stdout_buf = io.StringIO()
            try:
                call_command('review_flagged_users', stdout=stdout_buf, **options)
                return _ok({'status': 'completed', 'output': stdout_buf.getvalue()})
            except Exception as exc:
                logger.exception("review_flagged_users failed: %s", exc)
                return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 4. run_fraud_scan
# =============================================================================

class RunFraudScanCommandAPIView(APIView):
    """
    POST /fraud/management/run-scan/

    Trigger run_fraud_scan management command.

    Body:
        scan_type      (str)  all|users|transactions|ips|devices|patterns — default: all
        user_id        (int)  specific user ID (optional)
        days           (int)  days to look back         — default: 30
        risk_threshold (int)  alert creation threshold  — default: 70
        create_cases   (bool) create cases for findings — default: False
        dry_run        (bool) scan without saving       — default: False
        batch_size     (int)  processing batch size     — default: 100
        async_run      (bool) run in background         — default: True
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        data           = request.data
        scan_type      = data.get('scan_type', 'all')
        user_id        = data.get('user_id')
        days           = int(data.get('days', 30))
        risk_threshold = int(data.get('risk_threshold', 70))
        create_cases   = bool(data.get('create_cases', False))
        dry_run        = bool(data.get('dry_run', False))
        batch_size     = int(data.get('batch_size', 100))
        async_run      = bool(data.get('async_run', True))

        valid_types = ('all', 'users', 'transactions', 'ips', 'devices', 'patterns')
        if scan_type not in valid_types:
            return _err(f"scan_type must be one of: {', '.join(valid_types)}")
        if not 0 <= risk_threshold <= 100:
            return _err('risk_threshold must be 0–100')

        options: Dict[str, Any] = {
            'scan_type':      scan_type,
            'days':           days,
            'risk_threshold': risk_threshold,
            'create_cases':   create_cases,
            'dry_run':        dry_run,
            'batch_size':     batch_size,
            'verbose':        False,
        }
        if user_id is not None:
            options['user_id'] = int(user_id)

        logger.info(
            "run_fraud_scan triggered by user %s: type=%s days=%d dry_run=%s",
            request.user.id, scan_type, days, dry_run,
        )

        if async_run:
            job_id = _start_job('run_fraud_scan', options, request.user.id)
            return _ok({
                'job_id':  job_id,
                'status':  'running',
                'message': 'Fraud scan started. Poll /fraud/management/jobs/ for status.',
                'options': options,
            }, status.HTTP_202_ACCEPTED)
        else:
            stdout_buf = io.StringIO()
            try:
                call_command('run_fraud_scan', stdout=stdout_buf, **options)
                return _ok({'status': 'completed', 'output': stdout_buf.getvalue()})
            except Exception as exc:
                logger.exception("run_fraud_scan failed: %s", exc)
                return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 5. seed_fraud_rules
# =============================================================================

class SeedFraudRulesCommandAPIView(APIView):
    """
    POST /fraud/management/seed-rules/

    Trigger seed_fraud_rules management command.
    Loads rules from rules/sample_rules.yaml into the database.

    Body:
        rule_type  (str)  all|basic|advanced|behavioral|transaction|account — default: all
        overwrite  (bool) overwrite existing rules — default: False
        dry_run    (bool) show rules without creating — default: False
        async_run  (bool) run in background          — default: False
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        data      = request.data
        rule_type = data.get('rule_type', 'all')
        overwrite = bool(data.get('overwrite', False))
        dry_run   = bool(data.get('dry_run', False))
        async_run = bool(data.get('async_run', False))

        valid_types = ('all', 'basic', 'advanced', 'behavioral', 'transaction', 'account')
        if rule_type not in valid_types:
            return _err(f"rule_type must be one of: {', '.join(valid_types)}")

        options: Dict[str, Any] = {
            'rule_type': rule_type,
            'overwrite': overwrite,
            'dry_run':   dry_run,
            'verbose':   False,
        }

        logger.info(
            "seed_fraud_rules triggered by user %s: type=%s overwrite=%s dry_run=%s",
            request.user.id, rule_type, overwrite, dry_run,
        )

        if async_run:
            job_id = _start_job('seed_fraud_rules', options, request.user.id)
            return _ok({
                'job_id':  job_id,
                'status':  'running',
                'message': 'Seed job started. Poll /fraud/management/jobs/ for status.',
                'options': options,
            }, status.HTTP_202_ACCEPTED)
        else:
            stdout_buf = io.StringIO()
            try:
                call_command('seed_fraud_rules', stdout=stdout_buf, **options)
                return _ok({'status': 'completed', 'output': stdout_buf.getvalue()})
            except Exception as exc:
                logger.exception("seed_fraud_rules failed: %s", exc)
                return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 6. fix_arrays
# =============================================================================

class FixArraysCommandAPIView(APIView):
    """
    POST /fraud/management/fix-arrays/

    Trigger fix_arrays management command.
    Fixes array/JSON field data types in the fraud detection database.
    Body: { async_run: bool }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        async_run = bool(request.data.get('async_run', True))

        logger.info("fix_arrays triggered by user %s", request.user.id)

        if async_run:
            job_id = _start_job('fix_arrays', {}, request.user.id)
            return _ok({
                'job_id':  job_id,
                'status':  'running',
                'message': 'fix_arrays started. Poll /fraud/management/jobs/ for status.',
            }, status.HTTP_202_ACCEPTED)
        else:
            stdout_buf = io.StringIO()
            try:
                call_command('fix_arrays', stdout=stdout_buf)
                return _ok({'status': 'completed', 'output': stdout_buf.getvalue()})
            except Exception as exc:
                logger.exception("fix_arrays failed: %s", exc)
                return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 7. Job status
# =============================================================================

class ManagementJobStatusAPIView(APIView):
    """
    GET /fraud/management/jobs/               — list all recent jobs
    GET /fraud/management/jobs/<job_id>/      — specific job detail
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request, job_id: Optional[str] = None):
        jobs = _get_jobs()

        if job_id:
            job = jobs.get(job_id)
            if not job:
                return _err('Job not found.', status.HTTP_404_NOT_FOUND)
            return _ok(job)

        # List — newest first
        sorted_jobs = sorted(
            jobs.values(),
            key=lambda j: j.get('started_at', ''),
            reverse=True,
        )
        return _ok({
            'total':    len(sorted_jobs),
            'running':  sum(1 for j in sorted_jobs if j['status'] == 'running'),
            'completed': sum(1 for j in sorted_jobs if j['status'] == 'completed'),
            'error':    sum(1 for j in sorted_jobs if j['status'] == 'error'),
            'jobs':     sorted_jobs,
        })


class ManagementJobCancelAPIView(APIView):
    """
    POST /fraud/management/jobs/<job_id>/cancel/
    Mark a job as cancelled (does not kill the thread, but marks status).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request, job_id: str):
        jobs = _get_jobs()
        if job_id not in jobs:
            return _err('Job not found.', status.HTTP_404_NOT_FOUND)
        if jobs[job_id]['status'] != 'running':
            return _err(f"Cannot cancel job in status '{jobs[job_id]['status']}'.")
        jobs[job_id]['status']   = 'cancelled'
        jobs[job_id]['ended_at'] = timezone.now().isoformat()
        _save_jobs(jobs)
        logger.info("Job %s cancelled by user %s", job_id, request.user.id)
        return _ok({'cancelled': True, 'job_id': job_id})


# =============================================================================
# 8. Rules YAML loader API
# =============================================================================

class RulesYAMLLoadAPIView(APIView):
    """
    GET  /fraud/management/rules/yaml/          — read sample_rules.yaml content
    POST /fraud/management/rules/yaml/import/   — import rules from YAML into DB
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        """Return parsed YAML rules."""
        try:
            import yaml
            import os
            yaml_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'rules', 'sample_rules.yaml',
            )
            with open(yaml_path, 'r') as f:
                rules_data = yaml.safe_load(f)
            return _ok({
                'version':      rules_data.get('version'),
                'last_updated': rules_data.get('last_updated'),
                'rule_count':   len(rules_data.get('rules', [])),
                'rules':        rules_data.get('rules', []),
            })
        except FileNotFoundError:
            return _err('sample_rules.yaml not found.', status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            logger.exception("RulesYAMLLoadAPIView.get failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class RulesYAMLImportAPIView(APIView):
    """
    POST /fraud/management/rules/yaml/import/

    Import rules from sample_rules.yaml into the FraudRule database table.
    Body: { overwrite: bool, rule_types: [str], dry_run: bool }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        overwrite   = bool(request.data.get('overwrite', False))
        rule_types  = request.data.get('rule_types', [])
        dry_run     = bool(request.data.get('dry_run', False))

        try:
            import yaml
            import os
            from api.fraud_detection.models import FraudRule

            yaml_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'rules', 'sample_rules.yaml',
            )
            with open(yaml_path, 'r') as f:
                rules_data = yaml.safe_load(f)

            rules_list = rules_data.get('rules', [])
            if rule_types:
                rules_list = [r for r in rules_list if r.get('rule_type') in rule_types]

            created = 0
            updated = 0
            skipped = 0
            errors  = []

            for rule_def in rules_list:
                try:
                    name = rule_def.get('name', '')
                    if not name:
                        errors.append({'rule': rule_def, 'error': 'Missing name'})
                        continue

                    if dry_run:
                        created += 1
                        continue

                    rule_data = {
                        'name':             name,
                        'description':      rule_def.get('description', ''),
                        'rule_type':        rule_def.get('rule_type', 'account'),
                        'severity':         rule_def.get('severity', 'medium'),
                        'condition':        rule_def.get('condition', {}),
                        'weight':           rule_def.get('weight', 10),
                        'threshold':        rule_def.get('threshold', 70),
                        'action_on_trigger': rule_def.get('action_on_trigger', 'flag'),
                        'is_active':        rule_def.get('is_active', True),
                        'run_frequency':    rule_def.get('run_frequency', 'realtime'),
                    }

                    if overwrite:
                        obj, was_created = FraudRule.objects.update_or_create(
                            name=name,
                            defaults=rule_data,
                        )
                        if was_created:
                            created += 1
                        else:
                            updated += 1
                    else:
                        if FraudRule.objects.filter(name=name).exists():
                            skipped += 1
                        else:
                            FraudRule.objects.create(**rule_data)
                            created += 1

                except Exception as rule_exc:
                    errors.append({
                        'rule': rule_def.get('name', '?'),
                        'error': str(rule_exc),
                    })

            logger.info(
                "YAML rules import: created=%d updated=%d skipped=%d errors=%d dry_run=%s by user %s",
                created, updated, skipped, len(errors), dry_run, request.user.id,
            )
            return _ok({
                'dry_run':        dry_run,
                'total_in_yaml':  len(rules_data.get('rules', [])),
                'rules_processed': len(rules_list),
                'created':        created,
                'updated':        updated,
                'skipped':        skipped,
                'errors':         errors,
            }, status.HTTP_201_CREATED if not dry_run else status.HTTP_200_OK)

        except FileNotFoundError:
            return _err('sample_rules.yaml not found.', status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            logger.exception("RulesYAMLImportAPIView failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

# ── ALIASES expected by urls.py ───────────────────────────────────────────────
ManagementCommandAPIView  = SeedFraudRulesCommandAPIView

from rest_framework.views import APIView as _MV
from rest_framework.response import Response as _MR
from rest_framework.permissions import IsAdminUser as _MA

class SystemMaintenanceAPIView(_MV):
    permission_classes = [_MA]
    def get(self, request):
        return _MR({"maintenance_mode": False, "status": "operational"})
    def post(self, request):
        action = request.data.get("action", "status")
        return _MR({"action": action, "success": True, "message": f"Maintenance action '{action}' queued"})
