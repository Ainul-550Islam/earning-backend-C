# publisher_tools/integrations/__init__.py
# ============================================================
# Exports third-party SDK & analytics integrations.
# All integration classes are loaded lazily to avoid import
# overhead at startup. Use get_integration() to load by name.
#
# Usage:
#   from .integrations import get_integration, AVAILABLE_INTEGRATIONS
#   cls = get_integration('amplitude')
#   instance = cls.objects.get(publisher=publisher)
# ============================================================
import importlib

# ── Integration registry ──────────────────────────────────────────────────────
# Maps slug → (module, class_name)
INTEGRATION_REGISTRY = {
    'amplitude':        ('amplitude_integration',            'AmplitudeAnalyticsIntegration'),
    'mixpanel':         ('mixpanel_integration',             'MixpanelAnalyticsIntegration'),
    'segment':          ('segment_integration',              'SegmentioIntegration'),
    'mparticle':        ('mparticle_integration',            'mParticleIntegration'),
    'google_analytics': ('google_analytics_integration',     'GoogleAnalyticsIntegration'),
    'google_tag_manager':('google_tag_manager',              'GoogleTagManagerIntegration'),
    'facebook_pixel':   ('facebook_pixel',                   'FacebookPixelIntegration'),
    'wordpress':        ('wordpress_plugin',                 'WordPressPluginIntegration'),
    'woocommerce':      ('woocommerce_plugin',               'WooCommercePluginIntegration'),
    'shopify':          ('shopify_app',                      'ShopifyAppIntegration'),
    'drupal':           ('drupal_module',                    'DrupalModuleIntegration'),
    'joomla':           ('joomla_extension',                 'JoomlaExtensionIntegration'),
    'react_sdk':        ('react_sdk',                        'ReactSDKIntegration'),
    'vue_sdk':          ('vue_sdk',                          'VuejsSDKIntegration'),
    'angular_sdk':      ('angular_sdk',                      'AngularSDKIntegration'),
}

AVAILABLE_INTEGRATIONS = list(INTEGRATION_REGISTRY.keys())


def get_integration(slug: str):
    """
    Dynamically load an integration model class by slug.

    Example:
        AmplitudeModel = get_integration('amplitude')
        instance = AmplitudeModel.objects.filter(publisher=publisher).first()
    """
    entry = INTEGRATION_REGISTRY.get(slug.lower())
    if not entry:
        raise ValueError(
            f'Unknown integration: {slug!r}. '
            f'Available: {AVAILABLE_INTEGRATIONS}'
        )
    module_name, class_name = entry
    mod = importlib.import_module(
        f'.{module_name}',
        package='publisher_tools.integrations',
    )
    return getattr(mod, class_name)


def get_all_integration_classes():
    """Returns dict of {slug: ModelClass} for all integrations."""
    return {slug: get_integration(slug) for slug in AVAILABLE_INTEGRATIONS}


__all__ = [
    'get_integration',
    'get_all_integration_classes',
    'AVAILABLE_INTEGRATIONS',
    'INTEGRATION_REGISTRY',
]
