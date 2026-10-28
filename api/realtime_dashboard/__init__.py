"""
Real-time Dashboard Backend - Django app for real-time dashboard functionality.
"""
# NOTE: `default_app_config` has been a no-op since Django 3.2 (Django now
# auto-discovers the AppConfig subclass defined in apps.py). It is kept
# here, with the corrected dotted path, only for backwards compatibility
# with any tooling that may still read it. The path previously read
# 'api.apirealtime_dashboard...' which did not match the app's real
# location (api.realtime_dashboard) used everywhere else in this codebase,
# including apps.py and the entire test suite.
default_app_config = 'api.realtime_dashboard.apps.RealtimeDashboardConfig'

__version__ = '1.0.0'
