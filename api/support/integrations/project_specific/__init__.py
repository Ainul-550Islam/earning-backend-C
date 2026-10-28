# api/support/integrations/project_specific/__init__.py
"""
Project-specific integrations for YOUR apps.

These files connect support with your 50+ app ecosystem:
    messaging_bridge     → messaging.SupportThread sync
    ai_engine_adapter    → NLP, chatbot, sentiment, OCR
    auto_mod_adapter     → AutoApprovalRule, ProofScanner, TaskBot
    audit_log_bridge     → audit_logs.AuditLog
    behavior_tracker     → behavior_analytics
    subscription_sla     → premium subscribers get faster SLA
    gamification_bridge  → djoyalty/gamification rewards
    security_check       → VPN/proxy detection
    ai_sentiment_realtime→ real-time frustration detection
    auto_approval_engine → multi-signal dispute auto-approval
    churn_risk_support   → churn predictor integration
    proactive_support    → behavior-triggered support
    voice_ticket_handler → voice → ticket conversion
    ticket_collision     → agent collision detection
    customer_journey     → full user timeline for agents
"""
try:
    from .messaging_bridge      import messaging_bridge
    from .ai_engine_adapter     import ai_engine_adapter
    from .auto_mod_adapter      import auto_mod_adapter
    from .audit_log_bridge      import audit_bridge
    from .behavior_tracker      import behavior_tracker
    from .subscription_sla      import subscription_sla
    from .gamification_bridge   import gamification_bridge
    from .security_check        import security_check
    from .ai_sentiment_realtime import sentiment_analyzer
    from .auto_approval_engine  import auto_approval_engine
    from .churn_risk_support    import churn_risk_manager
    from .proactive_support     import proactive_support
    from .voice_ticket_handler  import voice_handler
    from .ticket_collision      import collision_detector
    from .customer_journey      import customer_journey
except ImportError as e:
    import logging
    logging.getLogger(__name__).debug(f"project_specific partial import: {e}")

__all__ = [
    "messaging_bridge", "ai_engine_adapter", "auto_mod_adapter",
    "audit_bridge", "behavior_tracker", "subscription_sla",
    "gamification_bridge", "security_check", "sentiment_analyzer",
    "auto_approval_engine", "churn_risk_manager", "proactive_support",
    "voice_handler", "collision_detector", "customer_journey",
]