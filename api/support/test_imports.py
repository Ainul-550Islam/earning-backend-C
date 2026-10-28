"""
Quick import test — run before deploying.
python manage.py shell < test_imports.py
"""
print("Testing World #1 Support System imports...")
tests = [
    "from api.support.ai.ai_auto_responder import ai_auto_responder",
    "from api.support.ai.ai_ticket_classifier import ai_classifier",
    "from api.support.ai.ai_sentiment_analyzer import sentiment_analyzer",
    "from api.support.ai.ai_duplicate_detector import duplicate_detector",
    "from api.support.ai.ai_churn_predictor import churn_predictor",
    "from api.support.sla.advanced_sla_engine import advanced_sla_engine",
    "from api.support.sla.sla_breach_notifier import sla_notifier",
    "from api.support.sla.business_hours_calculator import business_hours_calculator",
    "from api.support.dashboard.realtime_dashboard import realtime_dashboard",
    "from api.support.notifications.email_notifier import email_notifier",
    "from api.support.notifications.sms_notifier import sms_notifier",
    "from api.support.notifications.notification_router import notification_router",
    "from api.support.multilang.language_detector import language_detector",
    "from api.support.multilang.auto_translator import auto_translator",
    "from api.support.multilang.bangla_processor import bangla_processor",
    "from api.support.reports.ticket_report import ticket_report",
    "from api.support.reports.agent_report import agent_report",
    "from api.support.reports.csat_report import csat_report",
    "from api.support.automation.workflow_builder import workflow_builder_api",
    "from api.support.automation.action_executor import action_executor",
    "from api.support.automation.macro_manager import macro_manager",
    "from api.support.livechat.proactive_triggers import proactive_trigger_engine",
    "from api.support.livechat.visitor_tracking import visitor_tracker",
    "from api.support.livechat.chatbot_runner import chatbot_runner",
    "from api.support.integrations.telegram_bot import telegram_bot",
    "from api.support.integrations.slack_integration import slack_integration",
    "from api.support.constants_extended import TicketPriority, TicketStatus, TicketCategory",
]

passed = 0
failed = 0
for test in tests:
    try:
        exec(test)
        print(f"  ✅ {test.split('import ')[-1]}")
        passed += 1
    except Exception as e:
        print(f"  ❌ {test.split('import ')[-1]}: {e}")
        failed += 1

print(f"\nResults: {passed} passed, {failed} failed")