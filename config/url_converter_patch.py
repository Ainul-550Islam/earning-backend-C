"""Make Django URL converter registration idempotent (DRF format suffixes)."""

import django.urls
from django.urls import converters as _converters

_orig_register_converter = _converters.register_converter
_patched = False


def install_url_converter_patch() -> None:
    global _patched
    if _patched:
        return

    def _safe_register_converter(converter, type_name):
        if (
            type_name in _converters.REGISTERED_CONVERTERS
            or type_name in _converters.DEFAULT_CONVERTERS
        ):
            return
        _orig_register_converter(converter, type_name)

    _converters.register_converter = _safe_register_converter
    django.urls.register_converter = _safe_register_converter

    try:
        import rest_framework.urlpatterns as drf_urlpatterns

        drf_urlpatterns.register_converter = _safe_register_converter
    except ImportError:
        pass

    _patched = True
