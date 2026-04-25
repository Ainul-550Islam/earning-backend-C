# api/wallet/openai_integration.py
"""
OpenAI integration for wallet — AI-powered features.
  1. Fraud pattern analysis (GPT-4 explains fraud signals)
  2. Customer support bot (answers wallet FAQ)
  3. Anomaly explanation (explain why transaction was flagged)
  4. Dispute summarization (auto-summarize dispute cases)

Install: pip install openai
settings.py: OPENAI_API_KEY = "sk-..."
"""
import logging
from django.conf import settings

logger = logging.getLogger("wallet.openai")


class WalletAI:
    """OpenAI-powered wallet intelligence."""

    MODEL = "gpt-4o-mini"  # Cost-effective for production

    @classmethod
    def _client(cls):
        try:
            from openai import OpenAI
            return OpenAI(api_key=getattr(settings, "OPENAI_API_KEY", ""))
        except ImportError:
            raise ImportError("pip install openai")

    @classmethod
    def explain_fraud_signals(cls, signals: list, score: float, user_id: int) -> str:
        """AI explanation of why a transaction was flagged as fraud."""
        try:
            client = cls._client()
            prompt = (
                f"A wallet transaction was flagged with fraud score {score}/100. "
                f"Signals detected: {signals}. "
                f"Explain in 2-3 sentences what these signals mean and why this is suspicious. "
                f"Be clear but non-technical for a customer support agent."
            )
            resp = client.chat.completions.create(
                model=cls.MODEL,
                messages=[{"role":"user","content":prompt}],
                max_tokens=200,
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI fraud explain error: {e}")
            return f"Fraud signals detected: {signals}"

    @classmethod
    def answer_support_question(cls, question: str, user_balance: float = None,
                                 pending_withdrawal: bool = False) -> str:
        """AI customer support for wallet questions."""
        try:
            client = cls._client()
            context = f"User balance: {user_balance} BDT. " if user_balance else ""
            if pending_withdrawal:
                context += "User has a pending withdrawal. "
            system = (
                "You are a helpful wallet support agent for a CPAlead-style affiliate platform. "
                "Answer questions about earnings, withdrawals (bKash, Nagad, USDT), KYC, and account issues. "
                "Keep answers concise and friendly. Currency is BDT (Bangladeshi Taka)."
            )
            resp = client.chat.completions.create(
                model=cls.MODEL,
                messages=[
                    {"role":"system","content":system},
                    {"role":"user","content":context + question},
                ],
                max_tokens=300,
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI support error: {e}")
            return "Please contact support at support@platform.com"

    @classmethod
    def summarize_dispute(cls, dispute_reason: str, amount: float, evidence: str = "") -> str:
        """AI summarization of a dispute case for admin review."""
        try:
            client = cls._client()
            prompt = (
                f"Summarize this wallet dispute for admin review. "
                f"Amount: {amount} BDT. Reason: {dispute_reason}. "
                f"Evidence provided: {evidence[:500] if evidence else 'None'}. "
                f"Provide: 1) Brief summary 2) Recommended action. Max 150 words."
            )
            resp = client.chat.completions.create(
                model=cls.MODEL,
                messages=[{"role":"user","content":prompt}],
                max_tokens=200,
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI dispute summarize error: {e}")
            return dispute_reason

    @classmethod
    def categorize_transaction(cls, description: str, amount: float) -> str:
        """AI categorization of a transaction for better analytics."""
        try:
            client = cls._client()
            prompt = (
                f"Categorize this wallet transaction: '{description}' amount {amount} BDT. "
                f"Return one word only from: earning, withdrawal, bonus, referral, fee, transfer, other"
            )
            resp = client.chat.completions.create(
                model=cls.MODEL,
                messages=[{"role":"user","content":prompt}],
                max_tokens=10,
            )
            result = resp.choices[0].message.content.strip().lower()
            valid = {"earning","withdrawal","bonus","referral","fee","transfer","other"}
            return result if result in valid else "other"
        except Exception as e:
            logger.debug(f"OpenAI categorize skip: {e}")
            return "other"
