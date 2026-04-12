"""
INTEGRATIONS/crm_integration.py — CRM Integration (HubSpot / local CRM)
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class CRMBase:
    def create_contact(self, email: str, name: str, phone: str = "", **props) -> dict:
        raise NotImplementedError

    def update_contact(self, contact_id: str, **props) -> dict:
        raise NotImplementedError

    def log_deal(self, contact_id: str, amount: float, product: str) -> dict:
        raise NotImplementedError


class HubSpotCRM(CRMBase):
    BASE_URL = "https://api.hubapi.com"

    def __init__(self, api_key: str):
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def create_contact(self, email: str, name: str, phone: str = "", **props) -> dict:
        first, *rest = name.split(" ", 1)
        last = rest[0] if rest else ""
        data = {
            "properties": {
                "email": email, "firstname": first, "lastname": last,
                "phone": phone, **{k: str(v) for k, v in props.items()}
            }
        }
        try:
            resp = requests.post(f"{self.BASE_URL}/crm/v3/objects/contacts", json=data,
                                  headers=self.headers, timeout=10)
            return resp.json()
        except Exception as e:
            logger.error("[CRM] HubSpot create_contact error: %s", e)
            return {"error": str(e)}

    def update_contact(self, contact_id: str, **props) -> dict:
        data = {"properties": {k: str(v) for k, v in props.items()}}
        try:
            resp = requests.patch(
                f"{self.BASE_URL}/crm/v3/objects/contacts/{contact_id}",
                json=data, headers=self.headers, timeout=10,
            )
            return resp.json()
        except Exception as e:
            logger.error("[CRM] HubSpot update error: %s", e)
            return {"error": str(e)}

    def log_deal(self, contact_id: str, amount: float, product: str) -> dict:
        data = {
            "properties": {
                "dealname": f"Purchase: {product}",
                "amount":   str(amount),
                "dealstage":"closedwon",
            }
        }
        try:
            resp = requests.post(
                f"{self.BASE_URL}/crm/v3/objects/deals",
                json=data, headers=self.headers, timeout=10,
            )
            return resp.json()
        except Exception as e:
            logger.error("[CRM] HubSpot log_deal error: %s", e)
            return {"error": str(e)}


def get_crm() -> CRMBase:
    api_key = getattr(settings, "HUBSPOT_API_KEY", "")
    if api_key:
        return HubSpotCRM(api_key)
    logger.warning("[CRM] No CRM API key configured. CRM sync disabled.")
    return None


def sync_buyer_to_crm(user, tenant):
    """Sync buyer profile to CRM after first purchase."""
    crm = get_crm()
    if not crm:
        return
    try:
        crm.create_contact(
            email=user.email,
            name=user.get_full_name() or user.username,
            phone=getattr(user, "phone_number", ""),
            marketplace_tenant=tenant.name,
        )
    except Exception as e:
        logger.error("[CRM] sync_buyer_to_crm error: %s", e)
