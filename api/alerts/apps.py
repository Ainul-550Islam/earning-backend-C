from django.apps import AppConfig

class AlertsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.alerts'

    def ready(self):
        try:
            import api.alerts.signals  # noqa: F401
        except ImportError:
            pass

        try:
            import psycopg2.extras
            import psycopg2.extensions
            import json, uuid
            from decimal import Decimal
            from datetime import datetime, date

            class SafeJsonEncoder(json.JSONEncoder):
                def default(self, obj):
                    if isinstance(obj, uuid.UUID):
                        return str(obj)
                    if isinstance(obj, (datetime, date)):
                        return obj.isoformat()
                    if isinstance(obj, Decimal):
                        return float(obj)
                    if hasattr(obj, 'pk'):
                        return obj.pk
                    return str(obj)

            def safe_dumps(obj):
                return json.dumps(obj, cls=SafeJsonEncoder)

            psycopg2.extensions.register_adapter(
                dict,
                lambda d: psycopg2.extras.Json(d, dumps=safe_dumps)
            )
            psycopg2.extensions.register_adapter(
                list,
                lambda l: psycopg2.extras.Json(l, dumps=safe_dumps)
            )
        except Exception:
            pass
