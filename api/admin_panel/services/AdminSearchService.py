# api/admin_panel/services/AdminSearchService.py
"""Global search service across all admin models."""
import logging
from django.apps import apps
from django.db.models import Q

logger = logging.getLogger(__name__)

SEARCH_REGISTRY = [
    {'model': 'auth.User', 'fields': ['username', 'email', 'first_name', 'last_name'], 'label': 'Users'},
    {'model': 'admin_panel.SiteContent', 'fields': ['title', 'identifier', 'content'], 'label': 'Site Content'},
    {'model': 'admin_panel.SiteNotification', 'fields': ['title', 'message'], 'label': 'Notifications'},
    {'model': 'admin_panel.SystemConfig', 'fields': ['key', 'label', 'description'], 'label': 'System Config'},
    {'model': 'admin_panel.FeatureFlag', 'fields': ['flag_key', 'label', 'description'], 'label': 'Feature Flags'},
]


class AdminSearchService:

    @staticmethod
    def search(query: str, model_filter: str = '', limit: int = 20) -> list:
        """Perform global search. Returns list of {model, label, count, items}."""
        if len(query.strip()) < 2:
            return []
        results = []
        for entry in SEARCH_REGISTRY:
            model_path = entry['model']
            if model_filter and model_filter.lower() not in model_path.lower():
                continue
            try:
                app_label, model_name = model_path.split('.')
                Model = apps.get_model(app_label, model_name)
                q = Q()
                for field in entry['fields']:
                    q |= Q(**{f'{field}__icontains': query})
                items = list(Model.objects.filter(q).values()[:limit])
                safe = []
                for item in items:
                    row = {}
                    for k, v in item.items():
                        if hasattr(v, 'isoformat'):
                            row[k] = v.isoformat()
                        elif isinstance(v, (str, int, float, bool, type(None))):
                            row[k] = v
                        else:
                            row[k] = str(v)
                    safe.append(row)
                if safe:
                    results.append({'model': model_path, 'label': entry['label'],
                                    'count': len(safe), 'items': safe})
            except Exception as e:
                logger.debug(f"Search error for {model_path}: {e}")
        return results

    @staticmethod
    def log_search(user, query: str, model: str, result_count: int, ip: str = ''):
        try:
            from ..models.activity import AdminSearch
            AdminSearch.objects.create(
                query=query, model=model, result_count=result_count,
                user=user if user and user.is_authenticated else None, ip=ip,
            )
        except Exception:
            pass