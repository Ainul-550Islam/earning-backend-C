# Integration Setup Guide

## Available Integrations

### wallet app
- Adapter: `WalletAdapter` in `integ_adapter.py`
- Calls: `wallet.credit()`, `wallet.freeze()`, `wallet.unfreeze()`
- Reads: balance, transactions

### fraud_detection app
- Adapter: `FraudAdapter`
- Calls: `fraud_service.flag_user(user, reason)`
- Reads: risk score, flagged status

### postback app
- Adapter: `PostbackAdapter`
- Reads: postback logs for offer verification (READ ONLY)

### offerwall app
- Adapter: `OfferwallAdapter`
- Reads: offer details, user completions (READ ONLY)

### notifications app / messaging app
- Adapter: `NotificationsAdapter`
- Calls: `notifications_service.send(user, title, body)`

### kyc app
- Adapter: `KYCAdapter`
- Reads: verification status (READ ONLY)

### Project-Specific
Located in `integrations/project_specific/`:
- `messaging_bridge.py` — messaging.SupportThread sync
- `ai_engine_adapter.py` — NLP/chatbot/OCR
- `auto_mod_adapter.py` — AutoApprovalRule, ProofScanner
- `subscription_sla.py` — Premium user SLA adjustment
- `gamification_bridge.py` — Loyalty points
- `security_check.py` — VPN/proxy detection
- `behavior_tracker.py` — Behavior analytics
- `auto_approval_engine.py` — Multi-signal dispute approval

## Adding a New Integration
1. Create adapter class in `integ_adapter.py`
2. Register in `setup_adapters()` function
3. Add constants in `integ_constants.py`
4. Add health check in `health_check.py`
5. Add circuit breaker in `fallback_logic.py`
