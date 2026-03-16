from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class InventoryConfig(AppConfig):
    name = 'api.inventory'
    label = "inventory"
    verbose_name = _("Reward Inventory")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import api.inventory.admin
        from . import receivers
        from .signals import (
            item_delivered,
            item_delivery_failed,
            item_expiring_soon,
            low_stock_alert,
            stock_depleted,
            code_redeemed,
        )
        item_delivered.connect(receivers.on_item_delivered, dispatch_uid="inventory.on_item_delivered")
        item_delivery_failed.connect(receivers.on_item_delivery_failed, dispatch_uid="inventory.on_delivery_failed")
        item_expiring_soon.connect(receivers.on_item_expiring_soon, dispatch_uid="inventory.on_expiring_soon")
        low_stock_alert.connect(receivers.on_low_stock_alert, dispatch_uid="inventory.on_low_stock")
        stock_depleted.connect(receivers.on_stock_depleted, dispatch_uid="inventory.on_stock_depleted")
        code_redeemed.connect(receivers.on_code_redeemed, dispatch_uid="inventory.on_code_redeemed")
