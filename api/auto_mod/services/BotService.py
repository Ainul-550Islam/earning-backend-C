# =============================================================================
# auto_mod/services/BotService.py
# =============================================================================
"""BotService — full bot lifecycle + scan initiation for tests."""
from __future__ import annotations
import logging
from django.db import transaction
from django.utils import timezone
from django.db.models import Count, Avg

from ..choices import BotStatus, ScanStatus, ScanType, TaskType
from ..exceptions import (
    BotAlreadyRunningError, BotNotReadyError, OCRExtractionError,
    ScanFailedError, SubmissionNotFoundError,
)
from ..models import ProofScanner, SuspiciousSubmission, TaskBot

logger = logging.getLogger(__name__)
OVERDUE_HOURS = 24
DEPLOY_ACCURACY_THRESHOLD = 0.80


class BotService:
    """TaskBot lifecycle management + scan initiation."""

    # ------------------------------------------------------------------
    # Bot CRUD / lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    def create_bot(*, name: str, bot_type: str, created_by=None,
                   max_retries: int = 3, config: dict | None = None) -> TaskBot:
        valid = [c[0] for c in TaskType.choices]
        if bot_type not in valid:
            raise ValueError(f"Invalid bot_type {bot_type!r}. Choose from {valid}")
        return TaskBot.objects.create(
            name=name, bot_type=bot_type, created_by=created_by,
            max_retries=max_retries, config=config or {},
            status=BotStatus.IDLE,
        )

    @staticmethod
    @transaction.atomic
    def start_bot(bot: TaskBot) -> dict:
        if bot.status == BotStatus.RUNNING:
            raise BotAlreadyRunningError()
        bot.start()
        return {"success": True, "status": BotStatus.RUNNING}

    @staticmethod
    @transaction.atomic
    def stop_bot(bot: TaskBot) -> dict:
        bot.stop()
        return {"success": True, "status": BotStatus.STOPPED}

    @staticmethod
    @transaction.atomic
    def restart_bot(bot: TaskBot) -> dict:
        bot.restart()
        return {"success": True, "status": BotStatus.RUNNING}

    @staticmethod
    @transaction.atomic
    def execute_bot_task(bot: TaskBot, task_data: dict | None = None) -> dict:
        type_map = {
            TaskType.IMAGE_SCANNER: BotService._execute_image_scan,
            TaskType.TEXT_SCANNER:  BotService._execute_text_scan,
            TaskType.OCR_SCANNER:   BotService._execute_ocr_scan,
        }
        executor = type_map.get(bot.bot_type)
        if executor is None:
            raise ValueError(f"No executor for bot_type {bot.bot_type!r}")
        if task_data is None:
            raise BotNotReadyError()
        try:
            result = executor(task_data)
            # Update submission statuses based on results
            from ..choices import ModerationStatus
            from ..models import SuspiciousSubmission
            for item in result.get("results", []):
                sid = item.get("submission_id")
                item_status = item.get("status", "")
                if sid:
                    status_map = {
                        "approved": ModerationStatus.AUTO_APPROVED,
                        "rejected": ModerationStatus.AUTO_REJECTED,
                        "flagged":  ModerationStatus.HUMAN_REVIEW,
                        "escalated": ModerationStatus.ESCALATED,
                    }
                    new_status = status_map.get(item_status)
                    if new_status:
                        SuspiciousSubmission.objects.filter(pk=sid).update(status=new_status)
            # Update totals
            TaskBot.objects.filter(pk=bot.pk).update(
                total_processed=bot.total_processed + result.get("processed", 0)
            )
            bot.refresh_from_db()
            if bot.status == BotStatus.RUNNING:
                bot.status = BotStatus.IDLE
                bot.save(update_fields=["status", "updated_at"])
            return {"success": True, **result}
        except Exception as exc:
            bot.increment_retry()
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Internal executors (mockable)
    # ------------------------------------------------------------------

    @staticmethod
    def _execute_image_scan(task_data: dict) -> dict:
        return BotService.run_image_scan(task_data)

    @staticmethod
    def _execute_text_scan(task_data: dict) -> dict:
        return BotService.run_text_analysis(task_data)

    @staticmethod
    def _execute_ocr_scan(task_data: dict) -> dict:
        return BotService.run_ocr_scan(task_data)

    # Stub methods (will be mocked in tests)
    @staticmethod
    def run_image_scan(task_data):
        return {"status": "success", "processed": 0, "results": []}

    @staticmethod
    def run_ocr_scan(submission_or_data):
        return {"status": "success", "extracted_text": "", "confidence": 0.0}

    @staticmethod
    def run_image_analysis(submission):
        return {"status": "success", "analysis": {}}

    @staticmethod
    def run_text_analysis(submission_or_data):
        return {"status": "success", "analysis": {}}

    # ------------------------------------------------------------------
    # Scan initiation
    # ------------------------------------------------------------------

    @staticmethod
    def initiate_ocr_scan(submission: SuspiciousSubmission, initiated_by=None) -> ProofScanner:
        from django.utils import timezone as _tz
        scanner = ProofScanner.objects.create(
            submission=submission,
            scan_type=ScanType.OCR,
            status=ScanStatus.RUNNING,
            initiated_by=initiated_by,
            started_at=_tz.now(),
        )
        try:
            result = BotService.run_ocr_scan(submission)
            scanner.mark_completed(ScanStatus.SUCCESS, result)
            if "extracted_text" in result:
                meta = dict(submission.metadata)
                meta["ocr_text"] = result["extracted_text"]
                submission.scan_metadata = meta
                submission.save(update_fields=["scan_metadata", "updated_at"])
        except OCRExtractionError as exc:
            scanner.mark_completed(ScanStatus.FAILED, {"error": str(exc)})
        except (TimeoutError, Exception) as exc:
            err = str(exc)
            scanner.mark_completed(ScanStatus.FAILED, {
                "error": err,
                "timeout": "timeout" in err.lower() or isinstance(exc, TimeoutError),
            })
        return scanner

    @staticmethod
    def initiate_image_analysis(submission: SuspiciousSubmission, initiated_by=None) -> ProofScanner:
        from django.utils import timezone as _tz
        scanner = ProofScanner.objects.create(
            submission=submission,
            scan_type=ScanType.IMAGE_ANALYSIS,
            status=ScanStatus.RUNNING,
            initiated_by=initiated_by,
            started_at=_tz.now(),
        )
        try:
            result = BotService.run_image_analysis(submission)
            scanner.mark_completed(ScanStatus.SUCCESS, result)
            if "analysis" in result:
                meta = dict(submission.metadata)
                meta["image_analysis"] = result["analysis"]
                submission.scan_metadata = meta
                submission.save(update_fields=["scan_metadata", "updated_at"])
        except (ScanFailedError, Exception) as exc:
            scanner.mark_completed(ScanStatus.FAILED, {"error": str(exc)})
        return scanner

    @staticmethod
    def initiate_text_analysis(submission: SuspiciousSubmission, initiated_by=None) -> ProofScanner:
        from django.utils import timezone as _tz
        scanner = ProofScanner.objects.create(
            submission=submission,
            scan_type=ScanType.TEXT_ANALYSIS,
            status=ScanStatus.RUNNING,
            initiated_by=initiated_by,
            started_at=_tz.now(),
        )
        try:
            result = BotService.run_text_analysis(submission)
            scanner.mark_completed(ScanStatus.SUCCESS, result)
        except Exception as exc:
            scanner.mark_completed(ScanStatus.FAILED, {"error": str(exc)})
        return scanner

    @staticmethod
    def initiate_scan(submission: SuspiciousSubmission, scan_type: str, initiated_by=None) -> ProofScanner:
        valid = [c[0] for c in ScanType.choices]
        if scan_type not in valid:
            raise ValueError(f"Invalid scan_type {scan_type!r}")
        method_map = {
            ScanType.OCR:           BotService.initiate_ocr_scan,
            ScanType.IMAGE_ANALYSIS: BotService.initiate_image_analysis,
            ScanType.TEXT_ANALYSIS: BotService.initiate_text_analysis,
        }
        fn = method_map.get(scan_type, BotService.initiate_ocr_scan)
        return fn(submission, initiated_by)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    @staticmethod
    def get_scan_statistics() -> dict:
        from ..models import ProofScanner
        qs = ProofScanner.objects.all()
        total = qs.count()
        status_bd = dict(qs.values("status").annotate(c=Count("id")).values_list("status", "c"))
        type_bd   = dict(qs.values("scan_type").annotate(c=Count("id")).values_list("scan_type", "c"))
        avg_dur   = qs.aggregate(a=Avg("duration_ms"))["a"] or 0
        return {
            "total_scans":     total,
            "status_breakdown": status_bd,
            "type_breakdown":   type_bd,
            "avg_duration":     avg_dur,
        }

    @staticmethod
    def get_bot_statistics() -> dict:
        qs    = TaskBot.objects.all()
        total = qs.count()
        status_bd = dict(qs.values("status").annotate(c=Count("id")).values_list("status", "c"))
        type_bd   = dict(qs.values("bot_type").annotate(c=Count("id")).values_list("bot_type", "c"))
        healthy = TaskBot.objects.healthy().count()
        active  = TaskBot.objects.active().count()
        return {
            "total_bots":      total,
            "status_breakdown": status_bd,
            "type_breakdown":   type_bd,
            "healthy_bots":     healthy,
            "active_bots":      active,
        }

    @staticmethod
    def get_bots_by_type(bot_type: str):
        return list(TaskBot.objects.by_type(bot_type))

    @staticmethod
    def get_healthy_bots():
        return list(TaskBot.objects.healthy())

    @staticmethod
    def health_check_all_bots() -> list:
        return [
            {
                "bot_id":    str(b.pk),
                "name":      b.name,
                "status":    b.status,
                "is_healthy": b.is_healthy(),
            }
            for b in TaskBot.objects.all()
        ]

    @staticmethod
    @transaction.atomic
    def cleanup_failed_bots() -> dict:
        failed = TaskBot.objects.filter(status=BotStatus.FAILED)
        count = failed.count()
        failed.update(status=BotStatus.IDLE, current_retry=0)
        return {"cleaned": count}

    # ------------------------------------------------------------------
    # Legacy heartbeat helpers (called from ModerationService.BotService)
    # ------------------------------------------------------------------

    @staticmethod
    def heartbeat(bot: TaskBot) -> None:
        bot.update_heartbeat()

    @staticmethod
    def record_error(bot: TaskBot, error: str) -> TaskBot:
        bot.last_error = error[:500]
        bot.increment_retry()
        return bot

    @staticmethod
    def process_pending_batch(bot: TaskBot, batch_size: int = 50) -> int:
        from ..models import SuspiciousSubmission
        from ..choices import ModerationStatus
        subs = (SuspiciousSubmission.objects
                .filter(status=ModerationStatus.PENDING)
                .order_by("created_at")[:batch_size])
        processed = 0
        for sub in subs:
            try:
                BotService.initiate_ocr_scan(sub)
                processed += 1
                BotService.heartbeat(bot)
            except Exception as exc:
                BotService.record_error(bot, str(exc))
        TaskBot.objects.filter(pk=bot.pk).update(
            total_processed=bot.total_processed + processed
        )
        return processed
