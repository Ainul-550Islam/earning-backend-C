"""
api/ai_engine/NLP_ENGINES/chatbot_engine.py
============================================
Chatbot Engine — intelligent customer support ও user engagement chatbot।
Rule-based + Intent classification + Optional LLM fallback।
Earning app specific responses — withdrawal, offers, rewards, support।
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ChatbotEngine:
    """
    Multi-turn conversational chatbot।
    Intent detection → response generation → escalation।
    """

    # Earning app specific response templates
    RESPONSE_TEMPLATES = {
        "withdrawal": {
            "keywords": ["withdraw", "withdrawal", "cash", "money", "টাকা", "উত্তোলন", "পেমেন্ট"],
            "response": "উইথড্রয়াল সাধারণত ১-৩ কার্যদিবসের মধ্যে প্রক্রিয়া হয়। বর্তমান Status দেখতে Wallet → History তে যান।",
            "follow_up": ["How much is my balance?", "What is the minimum withdrawal?"],
        },
        "offer_help": {
            "keywords": ["offer", "task", "complete", "অফার", "টাস্ক", "কাজ", "reward"],
            "response": "অফার complete করতে: ১) অফার select করুন ২) নির্দেশ অনুযায়ী কাজ করুন ৩) Proof submit করুন। সাধারণত ২৪ ঘণ্টায় approve হয়।",
            "follow_up": ["Show me available offers", "Why was my offer rejected?"],
        },
        "referral": {
            "keywords": ["refer", "referral", "friend", "invite", "রেফার", "বন্ধু"],
            "response": "রেফারেল করে আপনি এবং আপনার বন্ধু উভয়ই বোনাস পাবেন! আপনার রেফারেল লিংক Profile → Referral এ আছে।",
            "follow_up": ["How much referral bonus will I get?", "How many referrals can I make?"],
        },
        "account_issue": {
            "keywords": ["account", "login", "password", "block", "banned", "একাউন্ট", "লগইন", "পাসওয়ার্ড"],
            "response": "Account সংক্রান্ত সমস্যার জন্য support@example.com এ যোগাযোগ করুন অথবা Settings → Help Center ব্যবহার করুন।",
            "follow_up": ["Reset my password", "My account is blocked"],
        },
        "balance": {
            "keywords": ["balance", "coin", "earned", "ব্যালেন্স", "কয়েন", "আয়"],
            "response": "আপনার বর্তমান balance ও earning history Wallet section এ দেখতে পাবেন।",
            "follow_up": ["Show my earnings", "Why did my balance decrease?"],
        },
        "kyc": {
            "keywords": ["kyc", "verify", "verification", "id", "nid", "passport", "ভেরিফিকেশন"],
            "response": "KYC verify করতে Settings → Verification এ যান এবং জাতীয় পরিচয়পত্র বা পাসপোর্ট এর ছবি upload করুন।",
            "follow_up": ["Why do I need KYC?", "How long does KYC take?"],
        },
        "complaint": {
            "keywords": ["problem", "issue", "wrong", "error", "bug", "সমস্যা", "ত্রুটি", "ভুল"],
            "response": "আপনার সমস্যার জন্য দুঃখিত। আমাদের support team শীঘ্রই আপনার সাথে যোগাযোগ করবে। Ticket Number: #{ticket_id}",
            "follow_up": ["Track my complaint", "Escalate to manager"],
            "escalate": True,
        },
        "streak": {
            "keywords": ["streak", "daily", "bonus", "check-in", "স্ট্রিক", "ডেইলি"],
            "response": "প্রতিদিন login করে Daily Streak maintain করুন। ৭ দিনের streak এ বিশেষ bonus পাবেন!",
            "follow_up": ["What are streak rewards?", "I missed a day"],
        },
        "appreciation": {
            "keywords": ["thanks", "good", "great", "love", "ধন্যবাদ", "ভালো", "সুন্দর"],
            "response": "আপনার মতামতের জন্য ধন্যবাদ! আমরা সেরা অভিজ্ঞতা দিতে সর্বদা চেষ্টা করি। 😊",
            "follow_up": [],
        },
        "general": {
            "keywords": [],
            "response": "আপনার বার্তার জন্য ধন্যবাদ। আরও সাহায্যের জন্য Support → Chat অথবা support@example.com এ যোগাযোগ করুন।",
            "follow_up": ["View FAQ", "Contact support"],
        },
    }

    def __init__(self):
        from .intent_classifier import IntentClassifier
        from .entity_extractor import EntityExtractor
        from .sentiment_analyzer import SentimentAnalyzer
        self.intent_classifier  = IntentClassifier()
        self.entity_extractor   = EntityExtractor()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.conversation_history: List[Dict] = []

    def respond(self, message: str, user=None,
                 context: dict = None, session_id: str = None) -> dict:
        """
        User message এ respond করো।
        Full conversation context maintain করো।
        """
        context = context or {}

        # Analyze input
        intent_result   = self.intent_classifier.classify(message)
        entities        = self.entity_extractor.extract(message)
        sentiment       = self.sentiment_analyzer.analyze(message)

        intent          = intent_result.get("intent", "general")
        confidence      = intent_result.get("intent_confidence", 0.5)
        sentiment_label = sentiment.get("sentiment", "neutral")

        # Map intent to template
        template_key = self._map_intent_to_template(intent, message)
        template     = self.RESPONSE_TEMPLATES.get(template_key, self.RESPONSE_TEMPLATES["general"])

        # Generate response
        response_text = self._generate_response(template, user, entities, context)

        # Determine if escalation needed
        needs_human = (
            template.get("escalate", False) or
            confidence < 0.40 or
            sentiment_label == "negative" and confidence > 0.70
        )

        # Build response
        result = {
            "response":        response_text,
            "intent":          intent,
            "template_used":   template_key,
            "confidence":      confidence,
            "sentiment":       sentiment_label,
            "entities":        entities,
            "follow_up":       template.get("follow_up", [])[:3],
            "needs_human":     needs_human,
            "session_id":      session_id,
        }

        # Add escalation message
        if needs_human:
            result["escalation_message"] = "এই বিষয়টি আমাদের support team এর কাছে পাঠানো হচ্ছে।"
            result["escalation_ticket"]  = self._create_support_ticket(user, message)

        # Log conversation
        self.conversation_history.append({
            "user_message":    message,
            "bot_response":    response_text,
            "intent":          intent,
            "sentiment":       sentiment_label,
        })

        return result

    def _map_intent_to_template(self, intent: str, message: str) -> str:
        """Intent → template mapping।"""
        message_lower = message.lower()

        # Direct keyword matching (more reliable than intent for specific topics)
        for template_key, template in self.RESPONSE_TEMPLATES.items():
            for kw in template["keywords"]:
                if kw in message_lower:
                    return template_key

        # Intent-based fallback mapping
        intent_mapping = {
            "complaint":    "complaint",
            "withdrawal":   "withdrawal",
            "inquiry":      "offer_help",
            "appreciation": "appreciation",
            "referral":     "referral",
        }
        return intent_mapping.get(intent, "general")

    def _generate_response(self, template: dict, user, entities: list, context: dict) -> str:
        """Template থেকে personalized response তৈরি করো।"""
        response = template["response"]

        # Personalization
        if user:
            username = getattr(user, "username", "") or getattr(user, "full_name", "")
            if username:
                response = f"হ্যালো {username}! " + response

        # Entity substitution
        import uuid
        response = response.replace("{ticket_id}", str(uuid.uuid4())[:8].upper())

        return response

    def _create_support_ticket(self, user, message: str) -> str:
        """Support ticket create করো।"""
        import uuid
        ticket_id = f"TKT-{str(uuid.uuid4())[:8].upper()}"
        logger.info(f"Support ticket created: {ticket_id} for user {user.id if user else 'anonymous'}")
        return ticket_id

    def get_quick_replies(self, current_intent: str) -> List[str]:
        """Quick reply buttons এর suggestions।"""
        replies = {
            "withdrawal":  ["Check balance", "Withdrawal history", "Add bank account"],
            "offer_help":  ["Browse offers", "Pending offers", "Rejected offers"],
            "complaint":   ["Track complaint", "Escalate", "Call support"],
            "general":     ["Withdrawal help", "Offer help", "Account issue", "Referral info"],
        }
        return replies.get(current_intent, replies["general"])

    def faq_search(self, query: str) -> List[Dict]:
        """FAQ থেকে relevant answers খুঁজো।"""
        faqs = [
            {"q": "Minimum withdrawal amount?", "a": "Minimum withdrawal is 500 coins."},
            {"q": "How long does withdrawal take?", "a": "1-3 business days."},
            {"q": "How do I complete an offer?", "a": "Select offer → Follow instructions → Submit proof."},
            {"q": "How to refer friends?", "a": "Go to Profile → Referral → Share your link."},
            {"q": "Why was my offer rejected?", "a": "Offers are rejected if proof is insufficient or task incomplete."},
        ]

        query_lower = query.lower()
        relevant = []
        for faq in faqs:
            if any(word in faq["q"].lower() for word in query_lower.split()):
                relevant.append(faq)

        return relevant[:3] if relevant else faqs[:3]
