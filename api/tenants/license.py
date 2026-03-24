"""
EarningApp License Validator
Codecanyon Purchase Code Verification
"""
import hashlib
import requests
from django.conf import settings
from django.core.cache import cache


class LicenseValidator:
    ENVATO_API = "https://api.envato.com/v3/market/author/sale"

    @staticmethod
    def verify_purchase_code(purchase_code: str) -> dict:
        cache_key = f"license_{purchase_code}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        token = getattr(settings, 'ENVATO_API_TOKEN', '')
        if not token:
            # Demo mode - no token set
            return {"valid": True, "demo": True, "item": "EarningApp"}

        try:
            resp = requests.get(
                LicenseValidator.ENVATO_API,
                params={"code": purchase_code},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                result = {
                    "valid": True,
                    "buyer": data.get("buyer"),
                    "item": data.get("item", {}).get("name"),
                    "sale_id": data.get("id"),
                    "supported_until": data.get("supported_until"),
                }
                cache.set(cache_key, result, 86400)  # cache 24h
                return result
        except Exception:
            pass

        return {"valid": False, "error": "Invalid purchase code"}

    @staticmethod
    def activate_tenant(tenant, purchase_code: str) -> bool:
        result = LicenseValidator.verify_purchase_code(purchase_code)
        if result.get("valid"):
            from .models import TenantSettings
            settings_obj, _ = TenantSettings.objects.get_or_create(tenant=tenant)
            tenant.is_active = True
            tenant.save()
            return True
        return False
