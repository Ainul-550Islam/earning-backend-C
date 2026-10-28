"""
tasks/services/TaskExportService.py
Export task history and performance data to CSV/JSON files.
"""
import logging
import csv
import json
import io
import os
import uuid
from typing import Dict, Any, List
from decimal import Decimal
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)

EXPORT_DIR = getattr(settings, 'EXPORT_DIR', '/tmp/task_exports/')


class TaskExportService:
    """Exports task data to downloadable files."""

    def _ensure_dir(self):
        os.makedirs(EXPORT_DIR, exist_ok=True)

    def _new_filename(self, prefix: str, ext: str = 'csv') -> str:
        ts = timezone.now().strftime('%Y%m%d_%H%M%S')
        return f"{prefix}_{uuid.uuid4().hex[:8]}_{ts}.{ext}"

    def export_performance_logs(
        self,
        task_name: str = None,
        days: int = 30,
        fmt: str = 'csv',
    ) -> Dict[str, Any]:
        """Export TaskPerformanceLog records to CSV or JSON."""
        self._ensure_dir()
        try:
            from api.tasks.models.monitoring import TaskPerformanceLog
            from datetime import timedelta

            cutoff = timezone.now() - timedelta(days=days)
            qs     = TaskPerformanceLog.objects.filter(created_at__gte=cutoff)
            if task_name:
                qs = qs.filter(task_name=task_name)

            rows = list(qs.values(
                'task_id', 'task_name', 'queue', 'worker',
                'result', 'duration_seconds', 'error',
                'retry_count', 'cpu_seconds', 'memory_mb', 'created_at',
            ))

            # Serialize datetimes
            for row in rows:
                row['created_at'] = str(row.get('created_at', ''))

            filename = self._new_filename('perf_logs', fmt)
            filepath = os.path.join(EXPORT_DIR, filename)

            if fmt == 'json':
                with open(filepath, 'w') as f:
                    json.dump(rows, f, indent=2)
            else:
                if rows:
                    with open(filepath, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                        writer.writeheader()
                        writer.writerows(rows)

            return {'success': True, 'filename': filename, 'row_count': len(rows)}

        except Exception as e:
            logger.error(f"[ERROR] TaskExportService.export_performance_logs: {e}")
            return {'success': False, 'error': str(e)}

    def export_insights(self, days: int = 30, fmt: str = 'csv') -> Dict[str, Any]:
        """Export TaskInsight rows to CSV or JSON."""
        self._ensure_dir()
        try:
            from api.tasks.models.analytics import TaskInsight
            from datetime import timedelta

            cutoff = timezone.now().date() - timedelta(days=days)
            rows   = list(
                TaskInsight.objects.filter(date__gte=cutoff)
                .order_by('-date', 'task_name')
                .values(
                    'date', 'task_name', 'run_count', 'success_count',
                    'failure_count', 'avg_duration', 'p95_duration',
                )
            )
            for row in rows:
                row['date'] = str(row.get('date', ''))

            filename = self._new_filename('task_insights', fmt)
            filepath = os.path.join(EXPORT_DIR, filename)

            if fmt == 'json':
                with open(filepath, 'w') as f:
                    json.dump(rows, f, indent=2)
            else:
                if rows:
                    with open(filepath, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                        writer.writeheader()
                        writer.writerows(rows)

            return {'success': True, 'filename': filename, 'row_count': len(rows)}

        except Exception as e:
            logger.error(f"[ERROR] TaskExportService.export_insights: {e}")
            return {'success': False, 'error': str(e)}

    def export_dlq(self, fmt: str = 'csv') -> Dict[str, Any]:
        """Export all DLQ entries to CSV or JSON."""
        self._ensure_dir()
        try:
            from api.tasks.models.queue import TaskDeadLetterQueue

            rows = list(
                TaskDeadLetterQueue.objects.order_by('-failed_at').values(
                    'id', 'task_name', 'task_id', 'error', 'failure_reason',
                    'retry_count', 'failed_at', 'queue_name', 'reprocess_status',
                )
            )
            for row in rows:
                row['failed_at'] = str(row.get('failed_at', ''))

            filename = self._new_filename('dlq_export', fmt)
            filepath = os.path.join(EXPORT_DIR, filename)

            if fmt == 'json':
                with open(filepath, 'w') as f:
                    json.dump(rows, f, indent=2)
            else:
                if rows:
                    with open(filepath, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                        writer.writeheader()
                        writer.writerows(rows)

            return {'success': True, 'filename': filename, 'row_count': len(rows)}

        except Exception as e:
            logger.error(f"[ERROR] TaskExportService.export_dlq: {e}")
            return {'success': False, 'error': str(e)}

    def get_download_path(self, filename: str) -> str:
        """Return the full filesystem path for a given export filename."""
        return os.path.join(EXPORT_DIR, filename)
