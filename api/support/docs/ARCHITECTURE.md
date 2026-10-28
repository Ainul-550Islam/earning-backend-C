# Support System Architecture

## Clean Architecture Layers

```
Views/API  →  Use Cases  →  Services  →  Repositories  →  Models
              (use_cases.py) (services.py) (repositories.py)
```

### Layer Responsibilities
- **Views** (`views.py`, `viewset.py`): HTTP request/response only
- **Use Cases** (`use_cases.py`): Single atomic business operations
- **Services** (`services.py`): Complex business logic orchestration
- **Selectors** (`selectors.py`): Read-only database queries
- **Repositories** (`repositories.py`): Data access abstraction
- **Models** (`models.py`): Database schema only

### Integration Layer
```
Support → Adapters → Other Apps
```
- `integrations/integ_adapter.py` — 8 adapters (wallet, fraud, kyc, etc.)
- `integrations/integ_handler.py` — Main orchestrator
- `integrations/event_bus.py` — Pub/sub events
- `integrations/project_specific/` — Your app-specific integrations

### Architecture Rules (ONE MASTER)
1. Support CALLS other apps, never COPIES their logic
2. `wallet.credit(amount)` ✅ vs `wallet.balance += amount` ❌
3. `fraud_service.flag_user(user)` ✅ vs `FraudProfile.is_flagged = True` ❌
4. All cross-app reads go through adapters
5. All cross-app writes go through other app's own service methods
