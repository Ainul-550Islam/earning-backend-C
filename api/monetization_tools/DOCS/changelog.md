# Changelog

All notable changes to `monetization_tools` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.0.0] - 2025-01-01

### Added
- **50 Django Models** covering the complete monetization stack
- **Phase-2 Models:** MonetizationConfig, AdCreative, UserSegment, PostbackLog,
  PayoutMethod, PayoutRequest, ReferralProgram, ReferralLink, ReferralCommission,
  DailyStreak, SpinWheelConfig, PrizeConfig, FlashSale, Coupon, CouponUsage,
  FraudAlert, RevenueGoal, PublisherAccount, MonetizationNotificationTemplate
- **20 Folder Structure** for scalable project organization:
  CORE_FILES, AD_FORMATS, AD_PLACEMENTS, AD_NETWORKS, REVENUE_MODELS,
  AD_CREATIVES, AD_PERFORMANCE, A_B_TESTING, ANALYTICS_REPORTING,
  OPTIMIZATION_ENGINES, USER_MONETIZATION, PAYMENT_PROCESSING,
  AD_QUALITY, OFFERWALL_SPECIFIC, GAMIFICATION, INTEGRATIONS,
  DATABASE_MODELS, MIGRATIONS, TESTS, SCRIPTS, DOCS
- **Multi-level Referral System** (up to 5 levels with configurable commission %)
- **Daily Streak System** with milestone rewards (7/14/30/60/90/180/365 days)
- **Flash Sale Engine** with multiplier, bonus coins, and segment targeting
- **Coupon/Promo Code System** with first-time use, per-user limits, and type-based rewards
- **Fraud Alert System** with auto-blocking, severity levels, and resolution workflow
- **Revenue Goal Tracking** with progress percentage and multi-period support
- **Publisher Account Management** with KYC, credit limits, and revenue sharing
- **Notification Template System** with multi-channel, multi-language support
- **Payout System** supporting bKash, Nagad, Rocket, PayPal, Payoneer, Bank Transfer, Crypto
- **Header Bidding Engine** with second-price auction and parallel bid collection
- **A/B Testing Framework** with statistical significance testing (Z-test)
- **Seasonal Creative Management** with Eid, Ramadan, Black Friday themes
- **Geo/Time/Device Bid Optimization** with tier-based multipliers
- **Cohort Analysis** for user retention tracking
- **Revenue Forecasting** with linear regression trend analysis
- **10 Third-Party Integrations**: Facebook Pixel, GA4, Amplitude, Mixpanel,
  Adjust, AppsFlyer, Branch, Firebase, Segment, mParticle
- **8 Production Scripts** for operations, sync, optimization, and health checks
- **6 Ad Format Handlers**: Banner, Interstitial, Rewarded Video, Native,
  Video, Audio, Carousel, Playable, Push Notification, In-App Purchase
- **CPalead + Multi-network Offerwall Support** with deduplication, capping, expiry

### Changed
- `services.py` expanded from 7 to 30+ service classes
- `tasks.py` expanded from 8 to 30+ Celery tasks
- `signals.py` expanded from 5 to 40+ Django signals
- `validators.py` expanded with 35+ validators for all new models
- `enums.py` expanded with 40+ TextChoices enums

### Fixed
- Balance ledger invariant: `balance_before + amount == balance_after` enforced by DB constraint
- Double-credit prevention: UUID `transaction_id` unique constraint + partial UniqueConstraint
- Decimal precision: All money fields use `DecimalField` (zero floats)
- Counter overflow: All high-volume counters use `BigIntegerField`

---

## [1.5.0] - 2024-06-01

### Added
- Offerwall system with CPALead + custom network support
- Basic reward transaction ledger
- Subscription plans with auto-renewal
- AdMob + IronSource integration

### Changed
- Migrated from SQLite to PostgreSQL for production
- Added Redis cache backend

---

## [1.0.0] - 2024-01-01

### Added
- Initial monetization_tools app
- Basic ad campaign management
- Simple coin reward system
- Django admin interface

---

## Upcoming / Roadmap

### [2.1.0] - Planned
- [ ] Real-time bidding (RTB) via OpenRTB 2.6 protocol
- [ ] NFT/digital collectible rewards
- [ ] Live event bonus multipliers
- [ ] Advanced ML-based fraud detection
- [ ] Automated A/B test winner declaration via scheduled task
- [ ] Multi-currency payout (USDT, BTC)
- [ ] CPAGrip + OGads offerwall integration
- [ ] Stripe Connect for marketplace payouts
- [ ] Webhook notifications for all payout state changes
- [ ] GraphQL API layer
