# api/admin_panel/admin/__init__.py

from .legacy_admin import *

# যেহেতু নাম আন্ডারস্কোর (_) দিয়ে শুরু, তাই এটিকে ম্যানুয়ালি ইমপোর্ট করতে হবে
try:
    from .legacy_admin import _sync_all_apps_to_modern_site
except ImportError:
    pass

"""Admin panel Django Admin registrations sub-package."""
from django.contrib import admin
admin_site = admin.site