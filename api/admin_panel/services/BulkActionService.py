# api/admin_panel/services/BulkActionService.py
"""Service wrapper for bulk actions."""
import logging
logger = logging.getLogger(__name__)


class BulkActionService:
    @staticmethod
    def execute(model_path: str, action: str, ids: list, params: dict, actor) -> dict:
        from ..viewsets.BulkActionViewSet import BulkActionViewSet
        from django.apps import apps
        vset = BulkActionViewSet()
        app_label, model_name = model_path.split('.')
        Model = apps.get_model(app_label, model_name)
        handler = vset._get_handler(action)
        if not handler:
            raise ValueError(f"Unknown action: {action}")
        return handler(Model, ids, params, actor)