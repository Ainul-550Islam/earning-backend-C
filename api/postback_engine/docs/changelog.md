# PostbackEngine Changelog

## v2.0.0 — Production Complete

### New Features
- Full 11-step postback processing pipeline
- 18+ CPA network adapters (CPALead, AdGate, OfferToro, AppLovin, Unity, IronSource, AdMob, Facebook, Google, TikTok, Snapchat, Twitter, Impact, CAKE, HasOffers, LinkTrust, Everflow + generic)
- Two-layer idempotency: Redis SETNX + DB SELECT FOR UPDATE
- Composite fraud scoring (0–100) with 7 signal types
- Velocity checking: 5 conversions/minute from same IP = hard block
- Exponential backoff retry: 1m → 5m → 30m → 2h → 6h
- Dead letter queue with admin replay
- Real-time dashboard (Redis counters, sub-second latency)
- Zapier + Make.com integrations
- Plugin system for extending without modifying core
- Event bus for domain events
- Hook registry for pipeline injection points
- Full test suite (unit, integration, load, stress, benchmark)

### Architecture
- `postback_handlers/` — 15 handler classes
- `network_adapters/` — 20 adapter files (1 per network)
- `conversion_tracking/` — 12 files (full lifecycle)
- `click_tracking/` — 10 files (click → attribution)
- `fraud_detection/` — 12 files (composite scoring)
- `analytics_reporting/` — 12 files (hourly through monthly)
- `queue_management/` — 10 files (Redis, RabbitMQ, Kafka, SQS)
- `database_models/` — 15 files (typed proxies)
- `validation_engines/` — 10 files (Pydantic + business rules)
- `security/` — 8 files (encryption, signing, rate limiting)
- `webhook_manager/` — 10 files (outbound webhooks)
- `testing/` — 12 files (comprehensive test suite)
- `scripts/` — 10 management scripts
- `docs/` — 8 documentation files

### Total: 174 Python files + 8 markdown docs
