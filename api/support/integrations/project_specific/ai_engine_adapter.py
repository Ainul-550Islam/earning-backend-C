# api/support/integrations/project_specific/ai_engine_adapter.py
"""
AI Engine Adapter — uses YOUR ai_engine app for support intelligence.

YOUR ai_engine has:
  - NLP_ENGINES/intent_classifier.py
  - NLP_ENGINES/sentiment_analyzer.py
  - NLP_ENGINES/chatbot_engine.py
  - NLP_ENGINES/spam_detector.py
  - PREDICTION_ENGINES/churn_predictor.py
  - CV_ENGINES/document_validator.py (for KYC proof)
  - CV_ENGINES/ocr_engine.py (for receipt reading)
  - NLP_ENGINES/language_detector.py

This adapter uses all of them for support intelligence.
"""
import logging
from typing import Optional
logger = logging.getLogger(__name__)


class AIEngineAdapter:
    """Connects support system to your ai_engine app."""

    AI_ENGINE_BASE = "api.ai_engine"

    # ── Intent Classification ──────────────────────────────────
    def classify_ticket_intent(self, ticket) -> dict:
        """
        Use ai_engine intent_classifier to determine ticket intent.
        Maps to our categories: payment, coins, fraud, kyc, etc.
        """
        try:
            from api.ai_engine.NLP_ENGINES.intent_classifier import IntentClassifier
            clf = IntentClassifier()
            text = f"{ticket.subject or ''} {ticket.description or ''}"
            result = clf.classify(text)
            return {
                "intent":      result.get("intent", ticket.category),
                "confidence":  result.get("confidence", 0.5),
                "sub_intents": result.get("sub_intents", []),
            }
        except Exception as e:
            logger.debug(f"AIEngineAdapter.classify_ticket_intent: {e}")
            return {"intent": ticket.category or "other", "confidence": 0.5, "sub_intents": []}

    # ── Sentiment Analysis ────────────────────────────────────
    def analyze_message_sentiment(self, text: str) -> dict:
        """
        Real-time sentiment analysis on each ticket message.
        Returns frustration level — escalate if very negative.
        """
        try:
            from api.ai_engine.NLP_ENGINES.sentiment_analyzer import SentimentAnalyzer
            analyzer = SentimentAnalyzer()
            result   = analyzer.analyze(text)
            return {
                "sentiment":   result.get("sentiment", "neutral"),
                "score":       result.get("score", 0.0),
                "frustration": result.get("frustration_level", "low"),
                "should_escalate": result.get("score", 0) < -0.6,
            }
        except Exception as e:
            logger.debug(f"AIEngineAdapter.analyze_message_sentiment: {e}")
            return {"sentiment": "neutral", "score": 0.0, "frustration": "low", "should_escalate": False}

    # ── Chatbot ───────────────────────────────────────────────
    def get_chatbot_response(self, user_message: str, context: dict = None) -> Optional[str]:
        """
        Use ai_engine chatbot for live chat first-line response.
        Returns response string or None to hand off to human.
        """
        try:
            from api.ai_engine.NLP_ENGINES.chatbot_engine import ChatbotEngine
            bot = ChatbotEngine()
            response = bot.respond(
                message = user_message,
                context = context or {},
            )
            if response and response.get("handoff_to_human"):
                return None  # Hand off
            return response.get("reply") if response else None
        except Exception as e:
            logger.debug(f"AIEngineAdapter.get_chatbot_response: {e}")
            return None

    # ── Spam Detection ────────────────────────────────────────
    def is_spam_ticket(self, ticket) -> dict:
        """
        Detect spam/fake support tickets using ai_engine spam detector.
        """
        try:
            from api.ai_engine.NLP_ENGINES.spam_detector import SpamDetector
            detector = SpamDetector()
            text = f"{ticket.subject or ''} {ticket.description or ''}"
            result = detector.detect(text)
            return {
                "is_spam":    result.get("is_spam", False),
                "confidence": result.get("confidence", 0.0),
                "reason":     result.get("reason", ""),
            }
        except Exception as e:
            logger.debug(f"AIEngineAdapter.is_spam_ticket: {e}")
            return {"is_spam": False, "confidence": 0.0, "reason": ""}

    # ── Churn Prediction ──────────────────────────────────────
    def get_churn_risk(self, user) -> dict:
        """
        Predict if this user is at risk of churning.
        High-risk users → priority support handling.
        """
        try:
            from api.ai_engine.PREDICTION_ENGINES.churn_predictor import ChurnPredictor
            predictor = ChurnPredictor()
            result = predictor.predict_user(user.id)
            return {
                "churn_probability": result.get("probability", 0.0),
                "risk_level":        result.get("risk_level", "low"),
                "is_high_risk":      result.get("probability", 0) > 0.7,
                "factors":           result.get("top_factors", []),
            }
        except Exception as e:
            logger.debug(f"AIEngineAdapter.get_churn_risk: {e}")
            return {"churn_probability": 0.0, "risk_level": "low", "is_high_risk": False}

    # ── Document Validation (for KYC disputes) ────────────────
    def validate_dispute_proof(self, image_file) -> dict:
        """
        Use ai_engine CV document_validator to verify proof images in disputes.
        Receipt photos, screenshots, ID documents for KYC appeals.
        """
        try:
            from api.ai_engine.CV_ENGINES.document_validator import DocumentValidator
            validator = DocumentValidator()
            result = validator.validate(image_file)
            return {
                "is_valid":    result.get("is_valid", False),
                "doc_type":    result.get("document_type", "unknown"),
                "confidence":  result.get("confidence", 0.0),
                "extracted":   result.get("extracted_data", {}),
            }
        except Exception as e:
            logger.debug(f"AIEngineAdapter.validate_dispute_proof: {e}")
            return {"is_valid": False, "doc_type": "unknown", "confidence": 0.0}

    # ── OCR for Receipt Reading ───────────────────────────────
    def extract_receipt_data(self, image_file) -> dict:
        """
        OCR a payment receipt to extract transaction details for dispute verification.
        """
        try:
            from api.ai_engine.CV_ENGINES.ocr_engine import OCREngine
            ocr = OCREngine()
            result = ocr.extract(image_file)
            return {
                "text":            result.get("full_text", ""),
                "transaction_id":  result.get("transaction_id", ""),
                "amount":          result.get("amount", ""),
                "date":            result.get("date", ""),
                "confidence":      result.get("confidence", 0.0),
            }
        except Exception as e:
            logger.debug(f"AIEngineAdapter.extract_receipt_data: {e}")
            return {"text": "", "transaction_id": "", "amount": ""}

    # ── Language Detection ────────────────────────────────────
    def detect_language(self, text: str) -> str:
        """Detect ticket/message language for multi-language routing."""
        try:
            from api.ai_engine.NLP_ENGINES.language_detector import LanguageDetector
            detector = LanguageDetector()
            result = detector.detect(text)
            return result.get("language", "en")
        except Exception:
            return "en"

    # ── Auto-classify and update ticket ──────────────────────
    def process_ticket_with_ai(self, ticket) -> dict:
        """
        Run all AI checks on a newly created ticket.
        Returns actions to take.
        """
        results = {}

        # 1. Spam check
        spam = self.is_spam_ticket(ticket)
        if spam["is_spam"] and spam["confidence"] > 0.85:
            results["action"] = "mark_spam"
            results["reason"] = spam["reason"]
            return results

        # 2. Intent classification → update category
        intent = self.classify_ticket_intent(ticket)
        if intent["confidence"] > 0.7 and intent["intent"] != ticket.category:
            results["suggested_category"] = intent["intent"]

        # 3. Sentiment → check if should escalate
        sentiment = self.analyze_message_sentiment(ticket.description or "")
        if sentiment["should_escalate"]:
            results["suggest_escalate"] = True
            results["sentiment"] = sentiment["frustration"]

        # 4. Language
        results["language"] = self.detect_language(ticket.description or "")

        # 5. Churn risk
        churn = self.get_churn_risk(ticket.user)
        if churn["is_high_risk"]:
            results["churn_risk"] = "high"
            results["suggest_priority"] = "urgent"

        return results


ai_engine_adapter = AIEngineAdapter()