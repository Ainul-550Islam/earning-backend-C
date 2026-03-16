import os
import importlib.util
import sys

def check_app_integrity():
    print("[START] Starting EarnMaster AI System Diagnosis...\n")

    # Setup Django first
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        import django
        django.setup()
        print("[OK] Django setup completed\n")
    except Exception as e:
        print("[FATAL] Django setup failed: {}".format(e))
        import traceback
        traceback.print_exc()
        return

    # Debug: List all loaded apps
    print("[DEBUG] Checking registered apps in Django...")
    try:
        from django.apps import apps
        print("Total apps loaded: {}".format(len(list(apps.get_app_configs()))))
        for app in apps.get_app_configs():
            if 'user' in app.label or 'wallet' in app.label or 'security' in app.label:
                print("  - {} (label: {})".format(app.name, app.label))
    except Exception as e:
        print("[ERROR] Failed to list apps: {}".format(e))

    errors_found = 0

    # Check service classes
    print("\n[CHECK] Checking api.security.services...")
    try:
        from api.security.services import SecurityService, RateLimitService
        print("[OK] Found: SecurityService")
        print("[OK] Found: RateLimitService")
    except Exception as e:
        print("[ERROR] Failed to import security services: {}".format(e))
        errors_found += 1

    # Check models using Django's apps registry
    print("[CHECK] Checking api.users models...")
    try:
        from django.apps import apps
        try:
            user_model = apps.get_model('users', 'User')
            print("[OK] Found: User model")
        except LookupError as e:
            print("[ERROR] User model lookup failed: {}".format(e))
            # Try direct import as fallback
            print("[FALLBACK] Trying direct import...")
            from api.users.models import User
            print("[OK] Direct import of User model succeeded")
    except Exception as e:
        print("[ERROR] Failed to load users models: {}".format(e))
        import traceback
        traceback.print_exc()
        errors_found += 1

    print("[CHECK] Checking api.wallet models...")
    try:
        from django.apps import apps
        try:
            wallet_model = apps.get_model('wallet', 'Wallet')
            print("[OK] Found: Wallet model")
        except LookupError as e:
            print("[ERROR] Wallet model lookup failed: {}".format(e))
            # Try direct import as fallback
            print("[FALLBACK] Trying direct import...")
            from api.wallet.models import Wallet
            print("[OK] Direct import of Wallet model succeeded")
    except Exception as e:
        print("[ERROR] Failed to load wallet models: {}".format(e))
        import traceback
        traceback.print_exc()
        errors_found += 1

    print("\n[RESULT] --- Diagnosis Complete: {} errors found ---".format(errors_found))
    if errors_found > 0:
        print("[ADVICE] There are errors above that need to be fixed.")
    else:
        print("[SUCCESS] All critical components are working correctly!")

if __name__ == "__main__":
    check_app_integrity()