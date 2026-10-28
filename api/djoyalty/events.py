# api/djoyalty/events.py
"""
AUDIT FIX (v2) -- SHADOW FILE RESOLVED।

THIS FILE IS A COMPATIBILITY SHIM। DO NOT ADD DOMAIN EVENT DEFINITIONS HERE।

Root cause:
  Python resolves `events/` (the package) over `events.py` (this flat
  file) when both exist।  This flat file is NEVER imported at runtime।
  All domain event dataclasses live in events/__init__.py and sub-modules।

Action: this file may safely be deleted।  No runtime behaviour changes।

Canonical event locations:
  events/domain_events.py    -- PointsEarnedEvent, TierChangedEvent, ...
  events/webhook_events.py   -- WebhookEvent, WebhookPayload
  events/__init__.py         -- re-exports all event classes
"""
# Unreachable at runtime (package wins over flat file)।
