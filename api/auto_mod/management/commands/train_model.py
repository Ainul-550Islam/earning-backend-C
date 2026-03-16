# =============================================================================
# auto_mod/management/commands/train_model.py
# =============================================================================

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Trigger ML model retraining from labelled submission data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            choices=["image", "text", "all"],
            default="all",
            help="Which model to retrain.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Show what would be trained without actually training.",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            dest="use_async",
            help="Enqueue as Celery task instead of running synchronously.",
        )

    def handle(self, *args, **options):
        from auto_mod.constants import ML_IMAGE_MODEL_NAME, ML_TEXT_MODEL_NAME
        from auto_mod.tasks import retrain_model

        models_to_train = {
            "image": [ML_IMAGE_MODEL_NAME],
            "text":  [ML_TEXT_MODEL_NAME],
            "all":   [ML_IMAGE_MODEL_NAME, ML_TEXT_MODEL_NAME],
        }[options["model"]]

        dry_run   = options["dry_run"]
        use_async = options["use_async"]

        for model_name in models_to_train:
            self.stdout.write(f"{'[DRY RUN] ' if dry_run else ''}Training: {model_name}")
            try:
                if use_async:
                    retrain_model.delay(model_name, dry_run=dry_run)
                    self.stdout.write(self.style.SUCCESS(f"  Queued: {model_name}"))
                else:
                    result = retrain_model(model_name, dry_run=dry_run)
                    if result.get("status") == "ok":
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  Done: {model_name} — {result.get('samples', 0)} samples"
                            )
                        )
                    else:
                        self.stdout.write(self.style.ERROR(f"  Failed: {result.get('reason')}"))
            except Exception as exc:
                raise CommandError(f"Training failed for {model_name}: {exc}") from exc
