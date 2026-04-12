# api/offer_inventory/security_fraud/__init__.py
"""
Security & Fraud Detection Package.
Exports all security classes for easy import.

Usage:
    from api.offer_inventory.security_fraud import BotDetector, IPBlacklistManager
    from api.offer_inventory.security_fraud import ClickSignatureManager, HoneypotManager
"""

from .bot_detection            import BotDetector
from .ip_blacklist             import IPBlacklistManager
from .user_agent_parser        import UserAgentParser, ParsedUA
from .click_signature          import ClickSignatureManager
from .duplicate_click_prevention import DuplicateClickPrevention
from .session_validator        import SessionValidator
from .honeypot                 import HoneypotManager, HONEYPOT_URLS
from .device_fingerprint       import DeviceFingerprintAnalyzer

__all__ = [
    'BotDetector',
    'IPBlacklistManager',
    'UserAgentParser',
    'ParsedUA',
    'ClickSignatureManager',
    'DuplicateClickPrevention',
    'SessionValidator',
    'HoneypotManager',
    'HONEYPOT_URLS',
    'DeviceFingerprintAnalyzer',
]
