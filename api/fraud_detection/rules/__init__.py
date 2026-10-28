# =============================================================================
# fraud_detection/rules/__init__.py
# =============================================================================
"""
Fraud Detection Rules Package.

This package contains rule definitions and configurations for the fraud detection system:
- Sample rules for different fraud patterns
- Rule validation and management utilities
"""

import yaml
import os
from typing import Dict, List, Any

def load_sample_rules() -> Dict[str, Any]:
    """Load sample fraud detection rules from YAML file."""
    try:
        rules_file = os.path.join(os.path.dirname(__file__), 'sample_rules.yaml')
        with open(rules_file, 'r', encoding='utf-8', newline='') as f:
            content = f.read().replace('\r\n', '\n').replace('\r', '\n')
            return yaml.safe_load(content) or {}
    except Exception:
        return {}

__all__ = [
    'load_sample_rules',
]
