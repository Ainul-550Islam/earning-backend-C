"""apps.py – AppConfig for the postback module."""
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PostbackConfig(AppConfig):
    name = 'api.postback'
    label = "postback"
    verbose_name = _("Postback & Security Tracking")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import api.postback.admin
        from . import receivers
        from .signals import (
            postback_received,
            postback_validated,
            postback_rejected,
            postback_rewarded,
            postback_duplicate,
            postback_failed,
        )
        postback_received.connect(
            receivers.on_postback_received,
            dispatch_uid="postback.on_received",
        )
        postback_rejected.connect(
            receivers.on_postback_rejected,
            dispatch_uid="postback.on_rejected",
        )
        postback_rewarded.connect(
            receivers.on_postback_rewarded,
            dispatch_uid="postback.on_rewarded",
        )
        postback_duplicate.connect(
            receivers.on_postback_duplicate,
            dispatch_uid="postback.on_duplicate",
        )
        postback_failed.connect(
            receivers.on_postback_failed,
            dispatch_uid="postback.on_failed",
        )
        try:
            from api.postback.admin import _force_register_postback
            _force_register_postback()
        except Exception as e:
            pass
