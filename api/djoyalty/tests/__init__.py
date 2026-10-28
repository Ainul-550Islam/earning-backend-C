# api/djoyalty/tests/__init__.py
"""
Djoyalty Tests Package -- UPDATED।

FIX: Both tests.py (flat) AND tests/ (folder) existed simultaneously।
Django's test runner loads both, causing duplicate test execution।

Resolution:
  1. All test content moved to tests/ package (this folder)।
  2. Flat tests.py content migrated to tests/test_legacy.py (see that file)।
  3. This __init__.py imports nothing -- Django discovers tests via file scan।

New test files added in this audit:
  test_cashout.py             -- CashoutService, CashoutViewSet, CashoutSerializer
  test_gamification.py        -- SpinWheel, ScratchCard, Lottery, Quiz, Season
  test_ai_personalization.py  -- CustomerAIProfile, PersonalizedOffer, ChurnAlert
  test_eco_family.py          -- Family, Eco, Charity, Consent, Receipt
  test_viewsets_http.py       -- HTTP smoke tests for all 20 new viewsets
  test_tasks_extended.py      -- Missing task imports + new task scenarios
  test_serializers_extended.py -- Legacy aliases + new serializer validation
  test_integration_system.py  -- HealthCheck, EventBus, CircuitBreaker, Bridge
  test_signals_extended.py    -- Points, Tier, Streak, Badge, Cashout, Gamification signals
  test_webhooks_extended.py   -- Dispatcher, retry, inbound handler, outbound delivery

Coverage target after this audit: ~72% (up from ~38%)
"""

# Intentionally empty -- Django discovers test_*.py files automatically।
# Do NOT import from here -- it causes double-execution।
