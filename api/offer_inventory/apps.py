from django.apps import AppConfig


class OfferInventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.offer_inventory'
    verbose_name = 'Offer Inventory'

    def ready(self):
        import api.offer_inventory.signals  # noqa: F401
