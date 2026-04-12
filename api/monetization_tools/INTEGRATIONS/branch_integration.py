"""INTEGRATIONS/branch_integration.py — Branch deep-link integration."""
import logging
logger = logging.getLogger(__name__)


class BranchIntegration:
    API_URL = "https://api2.branch.io/v1/event/standard"

    def __init__(self, branch_key: str = ""):
        self.branch_key = branch_key

    def log_event(self, developer_identity: str, event_name: str,
                   custom_data: dict = None) -> dict:
        payload = {
            "branch_key":          self.branch_key,
            "developer_identity":  developer_identity,
            "event":               event_name,
            "custom_data":         custom_data or {},
        }
        logger.info("Branch event: %s user=%s", event_name, developer_identity)
        return {"status": "ok"}

    def generate_referral_link(self, user_id: str, campaign: str = "referral") -> str:
        return f"https://yourapp.app.link/?ref={user_id}&campaign={campaign}&bk={self.branch_key[:8]}"
