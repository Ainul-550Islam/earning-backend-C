# analytics_warehouse/db_router.py
"""
Database router for analytics_warehouse app.

সব analytics_warehouse models analytics DB-এ যাবে,
বাকি সব default DB-তে থাকবে।

USAGE in settings.py:
    DATABASE_ROUTERS = ['analytics_warehouse.db_router.AnalyticsRouter']
"""


class AnalyticsRouter:
    """
    Route analytics_warehouse app models to the 'analytics' database.
    All other apps use the 'default' database.
    """

    ANALYTICS_APP = 'analytics_warehouse'
    ANALYTICS_DB  = 'analytics'

    def db_for_read(self, model, **hints):
        if model._meta.app_label == self.ANALYTICS_APP:
            return self.ANALYTICS_DB
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == self.ANALYTICS_APP:
            return self.ANALYTICS_DB
        return None

    def allow_relation(self, obj1, obj2, **hints):
        # analytics_warehouse objects can only relate to each other
        if (
            obj1._meta.app_label == self.ANALYTICS_APP
            or obj2._meta.app_label == self.ANALYTICS_APP
        ):
            return obj1._meta.app_label == obj2._meta.app_label
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == self.ANALYTICS_APP:
            return db == self.ANALYTICS_DB
        if db == self.ANALYTICS_DB:
            return False
        return None
