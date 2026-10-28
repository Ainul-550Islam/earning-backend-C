# =============================================================================
# auto_mod/services/MLModelService.py
# =============================================================================
"""MLModelService — model version lifecycle management."""
from __future__ import annotations
import hashlib, logging
from django.db import transaction
from django.utils import timezone
from django.db.models import Count, Avg

from ..exceptions import (
    ModelAlreadyDeployedError, ModelPerformanceThresholdError,
    ModelTrainingError, ModelVersionError,
)
from ..models import MLModelVersion

logger = logging.getLogger(__name__)
VALID_MODEL_TYPES = {"image", "text", "ocr", "combined"}
DEPLOY_ACCURACY_THRESHOLD = 0.80


class MLModelService:

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_model_version(
        self,
        *,
        model_type: str,
        version: str,
        display_name: str,
        description: str = "",
        created_by=None,
        hyperparameters: dict | None = None,
        metadata: dict | None = None,
        model_file=None,
    ) -> MLModelVersion:
        if model_type not in VALID_MODEL_TYPES:
            raise ModelVersionError(f"Invalid model_type {model_type!r}. Choose from {VALID_MODEL_TYPES}")
        if MLModelVersion.objects.filter(model_type=model_type, version=version).exists():
            raise ModelVersionError(f"Version {version!r} already exists for {model_type!r}")

        checksum  = self._calculate_file_checksum(model_file) if model_file else ""
        file_path = self._save_model_file(model_file) if model_file else ""

        return MLModelVersion.objects.create(
            model_type=model_type,
            version=version,
            display_name=display_name,
            description=description,
            created_by=created_by,
            hyperparameters=hyperparameters or {},
            metadata=metadata or {},
            checksum=checksum,
            file_path=file_path,
            status="idle",
        )

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    @transaction.atomic
    def start_model_training(
        self,
        *,
        model_version: MLModelVersion,
        training_config: dict,
        training_data_version: str = "",
        created_by=None,
    ) -> MLModelVersion:
        if model_version.status != "idle":
            raise ModelTrainingError(f"Cannot start training: model is in {model_version.status!r} status")
        model_version.status = "training"
        model_version.training_data_version = training_data_version
        if training_config:
            hp = dict(model_version.hyperparameters or {})
            hp.update(training_config)
            model_version.hyperparameters = hp
        model_version.save()
        return model_version

    @transaction.atomic
    def complete_model_training(
        self,
        *,
        model_version: MLModelVersion,
        performance_metrics: dict,
        training_log: str = "",
        training_duration_hours: float = 0.0,
    ) -> MLModelVersion:
        model_version.accuracy   = performance_metrics.get("accuracy")
        model_version.precision  = performance_metrics.get("precision")
        model_version.recall     = performance_metrics.get("recall")
        model_version.f1_score   = performance_metrics.get("f1_score")
        model_version.training_log = training_log
        model_version.training_duration_hours = training_duration_hours

        accuracy = performance_metrics.get("accuracy", 0)
        if accuracy and accuracy >= DEPLOY_ACCURACY_THRESHOLD:
            model_version.mark_deployed()
        else:
            model_version.status = "validating"
            model_version.save()
        return model_version

    # ------------------------------------------------------------------
    # Deploy / retire
    # ------------------------------------------------------------------

    @transaction.atomic
    def deploy_model(
        self,
        *,
        model_version: MLModelVersion,
        deployed_by=None,
        deployment_config: dict | None = None,
    ) -> MLModelVersion:
        if model_version.is_deployed:
            raise ModelAlreadyDeployedError()
        if model_version.accuracy is not None and model_version.accuracy < DEPLOY_ACCURACY_THRESHOLD:
            raise ModelPerformanceThresholdError(
                f"Accuracy {model_version.accuracy:.2f} < threshold {DEPLOY_ACCURACY_THRESHOLD}"
            )
        if deployment_config:
            model_version.deployment_config = deployment_config
        model_version.mark_deployed()
        return model_version

    @transaction.atomic
    def retire_model(
        self,
        *,
        model_version: MLModelVersion,
        retirement_reason: str = "",
        retired_by=None,
    ) -> MLModelVersion:
        meta = dict(model_version.metadata or {})
        meta["retirement"] = {
            "reason":     retirement_reason,
            "retired_by": retired_by.username if retired_by else "",
            "retired_at": str(timezone.now()),
        }
        model_version.metadata = meta
        model_version.mark_retired()
        return model_version

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_active_models(self):
        return list(MLModelVersion.objects.filter(is_active=True))

    def get_best_model_for_type(self, model_type: str) -> MLModelVersion | None:
        return (
            MLModelVersion.objects.filter(model_type=model_type, is_active=True)
            .order_by("-accuracy")
            .first()
        )

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def check_model_health(self, model_version: MLModelVersion) -> dict:
        issues = []
        integrity = self._verify_file_integrity(model_version)
        if model_version.is_active and not integrity:
            issues.append("File integrity check failed")
        return {
            "health_status": "healthy" if not issues else "critical",
            "issues": issues,
        }

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_model_statistics(self) -> dict:
        qs      = MLModelVersion.objects.all()
        total   = qs.count()
        active  = qs.filter(is_active=True).count()
        deployed = qs.filter(status="deployed").count()
        training = qs.filter(status="training").count()
        type_bd  = dict(qs.values("model_type").annotate(c=Count("id")).values_list("model_type", "c"))
        status_bd = dict(qs.values("status").annotate(c=Count("id")).values_list("status", "c"))
        perf = qs.aggregate(
            avg_accuracy=Avg("accuracy"),
            avg_precision=Avg("precision"),
            avg_recall=Avg("recall"),
        )
        return {
            "total_models":      total,
            "active_models":     active,
            "deployed_models":   deployed,
            "training_models":   training,
            "type_breakdown":    type_bd,
            "status_breakdown":  status_bd,
            "avg_performance_metrics": perf,
        }

    def compare_model_versions(
        self, model1: MLModelVersion, model2: MLModelVersion
    ) -> dict:
        def safe(a, b):
            if a is None or b is None:
                return 0
            return round(b - a, 4)
        return {
            "version1": {
                "id": str(model1.pk), "version": model1.version,
                "accuracy": model1.accuracy, "precision": model1.precision,
                "recall": model1.recall,
            },
            "version2": {
                "id": str(model2.pk), "version": model2.version,
                "accuracy": model2.accuracy, "precision": model2.precision,
                "recall": model2.recall,
            },
            "improvements": {
                "accuracy":  safe(model1.accuracy,  model2.accuracy),
                "precision": safe(model1.precision, model2.precision),
                "recall":    safe(model1.recall,    model2.recall),
            },
        }

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _save_model_file(self, model_file) -> str:
        return f"/models/{id(model_file)}.pkl" if model_file else ""

    def _calculate_file_checksum(self, model_file) -> str:
        if not model_file:
            return ""
        return hashlib.sha256(str(id(model_file)).encode()).hexdigest()

    def _verify_file_integrity(self, model_version: MLModelVersion) -> bool:
        return bool(model_version.file_path and model_version.checksum)
