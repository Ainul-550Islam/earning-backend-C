# engagement/test_user_model.py
# ─────────────────────────────────────────────────────────────────────────────
# TEST ONLY — এই model শুধু unit tests-এ ব্যবহার হয়।
# Production কোড বা models/__init__.py তে import করা নিষেধ।
# ─────────────────────────────────────────────────────────────────────────────
from django.contrib.auth.models import AbstractUser
from django.db import models


class EngagementTestUser(AbstractUser):
    """Minimal test user with coin_balance — only for test environments."""
    coin_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        app_label = "engagement"

    @property
    def tenant(self):
        return None
