import logging
from ...utils import parse_accept_language

logger = logging.getLogger('smartlink.targeting.language')


class LanguageTargetingService:
    """Browser language targeting via Accept-Language header."""

    def matches(self, language_targeting, language: str) -> bool:
        if language_targeting is None:
            return True
        return language_targeting.matches(language)

    def extract_language(self, accept_language_header: str) -> str:
        """Parse Accept-Language header to primary language code."""
        return parse_accept_language(accept_language_header) or ''
