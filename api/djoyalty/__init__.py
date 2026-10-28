# api/djoyalty/__init__.py
"""
Djoyalty -- Full-featured Django Loyalty System।

FIXED: default_app_config was 'djoyalty.apps.DjoyaltyConfig'
       which points to a non-existent top-level 'djoyalty' module।
       Corrected to 'api.djoyalty.apps.DjoyaltyConfig' to match
       the actual Python module path when the app lives at api/djoyalty/
       and INSTALLED_APPS contains "api.djoyalty"।
"""
default_app_config = 'api.djoyalty.apps.DjoyaltyConfig'
