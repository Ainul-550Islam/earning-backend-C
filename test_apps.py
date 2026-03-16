import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django
django.setup()

from django.apps import apps

print("Loaded apps:")
for app in apps.get_app_configs():
    print("  - {} (label: {})".format(app.name, app.label))
