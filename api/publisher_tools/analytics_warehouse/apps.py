# analytics_warehouse/apps.py
"""
Analytics Warehouse Django App.

publisher_tools/database_models/ থেকে migrate করা হয়েছে।
এই app টি একটি আলাদা read-replica বা analytics DB-এ point করে।

INSTALL:
  1. INSTALLED_APPS-এ যোগ করো:
        'analytics_warehouse',

  2. DB router যোগ করো settings.py-তে:
        DATABASE_ROUTERS = ['analytics_warehouse.db_router.AnalyticsRouter']

  3. analytics DB configure করো:
        DATABASES = {
            'default': { ... },
            'analytics': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME':   os.environ.get('ANALYTICS_DB_NAME', 'analytics_warehouse'),
                ...
            },
        }

  4. Migration চালাও:
        python manage.py migrate analytics_warehouse --database=analytics
"""
from django.apps import AppConfig


class AnalyticsWarehouseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name         = 'api.publisher_tools.analytics_warehouse'
    verbose_name = 'Analytics Warehouse'

    def ready(self):
        import logging
        logger = logging.getLogger(__name__)
        logger.debug('analytics_warehouse: app ready')
