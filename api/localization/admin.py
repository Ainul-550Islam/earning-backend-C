# admin.py — World #1 Localization Admin
# All admin classes are in admin/ folder, registered here
from django.contrib import admin
from .admin import *

# Also import original admin.py content for backward compat
import logging
logger = logging.getLogger(__name__)
