# Djoyalty Security Patches

## ⚠️ Critical Vulnerabilities Fixed

---

### 1. Race Condition — Double Earn / Double Spend
**Files:** `services/points/PointsEngine.py`, `services/redemption/RedemptionService.py`, `services/points/PointsTransferService.py`

**Problem:** `LoyaltyPoints` balance was read and written without a database row lock. Two concurrent requests (e.g. two parallel API calls) could both read the same balance, both pass the balance check, and both debit — resulting in negative balance or double-earned points.

**Fix:** All balance reads before credit/debit now use `select_for_update()` inside `@transaction.atomic`. This places a DB-level row lock so concurrent requests queue up safely.

---

### 2. Duplicate Earn (Replay Attack)
**Files:** `services/points/PointsEngine.py`, `viewsets/points/PointsViewSet.py`

**Problem:** The same `txn_id` / purchase could be submitted multiple times (e.g. via network retry or intentional replay) and earn points each time — no idempotency check existed.

**Fix:**
- `process_earn()` now accepts a required `reference_id` parameter.
- Before crediting, it checks `PointsLedger` for an existing entry with the same `customer + reference_id + source`. If found, it skips and returns `0`.
- The `/earn` endpoint now **requires** `reference_id` in the request body.

---

### 3. Unauthorized Earn — Any User Could Earn for Any Customer
**Files:** `viewsets/points/PointsViewSet.py`

**Problem:** The `/earn` endpoint had `permission_classes = [IsAuthenticated]`. Any logged-in user could POST `{"customer_id": X, "spend_amount": 99999}` and credit points to any account.

**Fix:** `/earn` now requires `IsLoyaltyAdmin`. It is an internal/backend-only endpoint, not exposed to end users.

---

### 4. Unauthorized Transfer — Any User Could Transfer From Any Account
**Files:** `viewsets/points/PointsTransferViewSet.py`

**Problem:** The `/transfer` endpoint accepted any `from_customer_id` without checking if the authenticated user owns that customer account. A user could drain points from any other customer.

**Fix:** Ownership check added — `from_customer.user` must equal `request.user`, unless the requester is an admin.

---

### 5. Unauthorized Redemption — Any User Could Redeem for Any Customer
**Files:** `viewsets/redemption/RedemptionViewSet.py`

**Problem:** Same pattern — `/redeem` accepted any `customer_id` without ownership verification.

**Fix:** Ownership check added — `customer.user` must equal `request.user`.

---

### 6. Frozen Balance Not Respected on Transfer & Redemption
**Files:** `services/points/PointsTransferService.py`, `services/redemption/RedemptionService.py`

**Problem:** `lp.balance` was checked directly. `frozen_balance` (points on fraud hold) was ignored, allowing fraudulently frozen points to be transferred or redeemed.

**Fix:** Both services now check `lp.available_balance` (= `balance - frozen_balance`) instead of raw `balance`.

---

### 7. Deadlock Risk in P2P Transfer
**Files:** `services/points/PointsTransferService.py`

**Problem:** If two users simultaneously transfer to each other, both transactions would try to lock wallets in different orders — classic deadlock scenario.

**Fix:** Both wallet PKs are sorted before acquiring locks (`select_for_update`), ensuring consistent lock ordering across all concurrent transfers.

---

### 8. API Key Leaking in URL Logs
**Files:** `permissions.py`

**Problem:** `IsPublicAPIClient` accepted `api_key` from `request.query_params` and `request.data`. Keys in query strings appear in server access logs, proxy logs, CDN logs, and browser history.

**Fix:** API key accepted **only** from the `X-Loyalty-API-Key` HTTP header.

---

### 9. `IsTenantMember` Was Always Returning True
**Files:** `permissions.py`

**Problem:** The `IsTenantMember` permission had a `# TODO` comment and always returned `True` — no actual tenant membership was enforced.

**Fix:** Now queries `Customer.objects.filter(user=request.user, tenant=tenant).exists()`.

---

### 10. Missing Throttles on High-Risk Endpoints
**Files:** `viewsets/points/PointsViewSet.py`, `viewsets/redemption/RedemptionViewSet.py`, `viewsets/points/PointsTransferViewSet.py`

**Problem:** `/earn`, `/redeem`, and `/transfer` had no throttle — open to brute-force or burst abuse.

**Fix:** `DjoyaltyBurstThrottle` (60/min) applied to all three endpoints. `DjoyaltyUserThrottle` (1000/hr) applied at viewset level.

---

### 11. Fraud Check Missing on Earn & Transfer
**Files:** `services/points/PointsEngine.py`, `services/points/PointsTransferService.py`

**Problem:** `LoyaltyFraudService.check_rapid_transactions()` existed but was never called during earn or transfer — only checked externally.

**Fix:** Fraud check integrated at service layer for both earn and transfer, before any balance modification.

---

### 12. New Constant: `MAX_DAILY_TRANSFER_POINTS`
**Files:** `constants.py`

Added `MAX_DAILY_TRANSFER_POINTS = Decimal('5000')` to cap daily P2P transfers per customer. Enforced in `PointsTransferService`.

---

## Summary Table

| # | Vulnerability | Severity | Fixed In |
|---|---|---|---|
| 1 | Race condition / double spend | 🔴 Critical | PointsEngine, RedemptionService, TransferService |
| 2 | Duplicate earn / replay attack | 🔴 Critical | PointsEngine, PointsViewSet |
| 3 | Any user earns for any customer | 🔴 Critical | PointsViewSet |
| 4 | Any user transfers from any account | 🔴 Critical | PointsTransferViewSet |
| 5 | Any user redeems for any customer | 🔴 Critical | RedemptionViewSet |
| 6 | Frozen balance ignored | 🟠 High | TransferService, RedemptionService |
| 7 | Deadlock in P2P transfer | 🟠 High | PointsTransferService |
| 8 | API key in URL logs | 🟠 High | permissions.py |
| 9 | IsTenantMember always True | 🟠 High | permissions.py |
| 10 | No throttle on critical endpoints | 🟡 Medium | PointsViewSet, RedemptionViewSet, TransferViewSet |
| 11 | Fraud check not integrated | 🟡 Medium | PointsEngine, PointsTransferService |
| 12 | No daily transfer cap | 🟡 Medium | constants.py, PointsTransferService |
