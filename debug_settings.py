import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

print("[1] Testing if settings module can be imported...")
try:
    from django.conf import settings
    print("[OK] Settings module imported")
    print("[INFO] INSTALLED_APPS length: {}".format(len(settings.INSTALLED_APPS)))
    print("[INFO] First 5 apps:")
    for app in settings.INSTALLED_APPS[:5]:
        print("  - {}".format(app))
except Exception as e:
    print("[ERROR] Failed to import settings: {}".format(e))
    import traceback
    traceback.print_exc()

print("\n[2] Testing Django setup...")
try:
    import django
    django.setup()
    print("[OK] Django setup completed")
except Exception as e:
    print("[ERROR] Django setup failed: {}".format(e))
    import traceback
    traceback.print_exc()

print("\n[3] Checking app registry after setup...")
try:
    from django.apps import apps
    print("[INFO] Total apps: {}".format(len(list(apps.get_app_configs()))))
    print("[INFO] App labels: {}".format([app.label for app in apps.get_app_configs()]))
except Exception as e:
    print("[ERROR] Failed to check registry: {}".format(e))
    import traceback
    traceback.print_exc()

print("\n[4] Checking config.settings module...")
try:
    import config.settings
    print("[OK] config.settings module exists")
    print("[INFO] Settings module path: {}".format(config.settings.__file__))
except Exception as e:
    print("[ERROR] config.settings not found: {}".format(e))
