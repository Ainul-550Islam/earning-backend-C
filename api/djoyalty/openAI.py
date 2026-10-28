# api/djoyalty/openAI.py
"""
AUDIT FIX (v2) -- DEAD FILE RESOLVED।

THIS FILE IS A COMPATIBILITY SHIM। DO NOT ADD LOGIC HERE।

openAI.py (capital A) previously defined `LoyaltyOpenAI` with 6 extended
methods but had zero external references (dead file)।  All methods have
been merged into openai.py (lowercase) as methods of LoyaltyAI।

This shim re-exports LoyaltyAI as LoyaltyOpenAI for backward compatibility
should any future caller import using the capital-A module name।

Action: this file may safely be deleted।  Use `from .openai import LoyaltyAI`।
"""
from .openai import LoyaltyAI as LoyaltyOpenAI  # noqa: F401
from .openai import LoyaltyAI                   # noqa: F401
