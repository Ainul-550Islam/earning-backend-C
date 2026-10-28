# api/referral/openAI.py
# Alias — capitalised import path for openai module
# Some parts of the project import as openAI (capital AI)
# ============================================================

# Full implementation is in openai.py
from api.referral.openai import ReferralAIService

__all__ = ['ReferralAIService']