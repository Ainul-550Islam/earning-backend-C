"""
validation_engines/macro_validator.py
───────────────────────────────────────
Validates macro-expanded URLs and postback URL templates.
Ensures all required macros are present in a template
and that expanded URLs are properly formed.
"""
from __future__ import annotations
import re
from typing import List, Tuple
from urllib.parse import urlparse
from ..exceptions import SchemaValidationException

# Regex to find all macros in a template
_MACRO_RE = re.compile(r'\{(\w+)\}')

# Standard macros supported by the engine
KNOWN_MACROS = {
    "click_id", "lead_id", "offer_id", "sub_id", "sub_id2",
    "payout", "currency", "user_id", "transaction_id",
    "timestamp", "status", "goal_id", "goal_value",
    "campaign_id", "publisher_id", "advertiser_id",
    "ip", "country", "device_type",
}


class MacroValidator:

    def validate_template(self, template: str, required_macros: List[str] = None) -> Tuple[bool, List[str]]:
        """
        Validate a postback URL template.
        Returns (is_valid, list_of_issues).
        """
        if not template:
            return True, []

        issues = []
        found_macros = set(_MACRO_RE.findall(template))

        # Check for unknown macros
        unknown = found_macros - KNOWN_MACROS
        if unknown:
            issues.append(f"Unknown macros in template: {', '.join(sorted(unknown))}")

        # Check required macros are in template
        if required_macros:
            missing = set(required_macros) - found_macros
            if missing:
                issues.append(f"Required macros missing from template: {', '.join(sorted(missing))}")

        # Validate URL structure
        try:
            # Replace macros with placeholder values for URL validation
            test_url = _MACRO_RE.sub("test_value", template)
            parsed = urlparse(test_url)
            if not parsed.scheme or not parsed.netloc:
                issues.append("Template does not appear to be a valid URL.")
        except Exception as exc:
            issues.append(f"URL parse error: {exc}")

        return len(issues) == 0, issues

    def assert_valid_template(self, template: str, required_macros: List[str] = None) -> None:
        is_valid, issues = self.validate_template(template, required_macros)
        if not is_valid:
            raise SchemaValidationException(
                f"Invalid postback URL template: {'; '.join(issues)}"
            )

    def get_macros_in_template(self, template: str) -> List[str]:
        """Extract list of macro names from a template string."""
        return _MACRO_RE.findall(template)

    def validate_expanded_url(self, url: str) -> bool:
        """Check that no unexpanded macros remain in a URL after expansion."""
        remaining = _MACRO_RE.findall(url)
        return len(remaining) == 0


macro_validator = MacroValidator()
