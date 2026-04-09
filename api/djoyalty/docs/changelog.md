# Changelog — Djoyalty

All notable changes to the Djoyalty loyalty system.

---

## [1.0.0] — 2026-04-06

### 🎉 Initial Release — World 1 Complete

#### Added — Core System
- `Customer` model with User link, referral_code, birth_date, is_active
- `Txn` model with reference field and custom managers (txn_full, txn_discount, spending, recent)
- `Event` model with metadata JSONField and custom managers
- `choices.py` — all CharField choices in one place
- `constants.py` — all magic numbers as named constants
- `enums.py` — type-safe Python Enum classes
- `exceptions.py` — 30+ structured exceptions with HTTP status codes
- `permissions.py` — IsTenantMember, IsLoyaltyAdmin, IsOwnerOrAdmin, IsPublicAPIClient
- `managers.py` — 30+ custom Django Model Managers
- `validators.py` — field-level and serializer validators
- `utils.py` — pure helper functions (points calc, tier helpers, HMAC, formatting)
- `filters.py` — django-filter FilterSet classes for all models
- `pagination.py` — Page, Cursor, LimitOffset, Leaderboard pagination

#### Added — Points Engine
- `LoyaltyPoints` — real-time balance with lifetime tracking
- `PointsLedger` — immutable credit/debit audit trail with expiry
- `PointsExpiry` — scheduled expiry with warning system
- `PointsTransfer` — P2P transfer with ledger entries
- `PointsConversion` — points ↔ currency conversion
- `PointsReservation` — checkout hold/confirm/release
- `PointsRate` — per-tenant earn rate configuration
- `PointsAdjustment` — admin manual adjustment log
- `PointsEngine` — core earn processing with tier multiplier
- `PointsExpiryService` — batch expiry processing
- `PointsTransferService` — atomic P2P transfer
- `PointsReservationService` — hold/confirm/release flow

#### Added — Tier System
- `LoyaltyTier` — Bronze → Diamond tier definitions
- `UserTier` — customer tier assignments with history
- `TierBenefit` — tier perks (shipping, support, etc.)
- `TierHistory` — upgrade/downgrade audit trail
- `TierConfig` — per-tenant evaluation settings
- `TierEvaluationService` — automatic tier assignment from lifetime_earned
- `TierUpgradeService` — upgrade logic + progress tracking + force upgrade
- `TierDowngradeService` — downgrade with protection period + force downgrade
- `TierBenefitService` — retrieve and manage tier benefits

#### Added — Earn Rules
- `EarnRule` — configurable earn rule (fixed, percentage, multiplier, bonus, category)
- `EarnRuleCondition` — additional conditions per rule
- `EarnRuleTierMultiplier` — tier-specific multiplier override
- `EarnTransaction` — earn event log per rule
- `BonusEvent` — manual/automated bonus points log
- `EarnRuleLog` — evaluation debug log
- `EarnRuleEngine` — rule matching and points calculation
- `EarnRuleEvaluator` — end-to-end earn processing
- `BonusEventService` — award bonus points with ledger entry
- `ReferralPointsService` — referrer + referee bonus processing

#### Added — Redemption
- `RedemptionRule` — configurable reward catalog
- `RedemptionRequest` — customer redemption with status flow
- `RedemptionHistory` — status change audit trail
- `Voucher` — discount vouchers (percent, fixed, free_shipping, bogo)
- `VoucherRedemption` — voucher use log
- `GiftCard` — partial redemption gift cards
- `RedemptionService` — create/approve/reject with auto ledger
- `RedemptionApprovalService` — auto-approve below threshold
- `VoucherService` — generate and validate vouchers
- `GiftCardService` — issue and partial redeem
- `RewardCatalogService` — filter available rewards for customer

#### Added — Engagement
- `DailyStreak` — daily activity tracking with longest streak
- `StreakReward` — milestone reward log (7/30/90/365 days)
- `Badge` — achievement badge definitions
- `UserBadge` — customer earned badges
- `Challenge` — time-bound loyalty challenges
- `ChallengeParticipant` — participation and progress tracking
- `Milestone` — cumulative milestone definitions
- `UserMilestone` — customer reached milestones
- `StreakService` — record activity, detect milestones, award rewards
- `BadgeService` — trigger-based badge evaluation and awarding
- `ChallengeService` — join, progress update, completion logic
- `MilestoneService` — threshold-based milestone checking
- `LeaderboardService` — top customer ranking by lifetime earned

#### Added — Campaigns & Advanced
- `LoyaltyCampaign` — points multiplier, bonus, double points campaigns
- `CampaignSegment` — targeted customer segments
- `CampaignParticipant` — campaign enrollment
- `ReferralPointsRule` — configurable referral bonuses
- `PartnerMerchant` — coalition partner API integration
- `LoyaltyNotification` — multi-channel customer notifications
- `PointsAlert` — expiry warning log
- `LoyaltySubscription` — premium subscription with monthly bonuses
- `LoyaltyFraudRule` — fraud detection rules
- `PointsAbuseLog` — fraud incident log with risk levels
- `LoyaltyInsight` — daily/weekly/monthly analytics reports
- `CoalitionEarn` — cross-partner earn transactions

#### Added — Infrastructure
- 14 Celery tasks (expiry, tier eval, streak reset, campaigns, fraud scan, insights, etc.)
- 8 Signal handlers (customer register, transaction, tier change, badge, streak, etc.)
- 7 Event bus files (dispatcher, registry, handlers, middleware)
- 6 Webhook files (dispatcher, payloads, retry with exponential backoff, HMAC security)
- 12 Admin panels (beautiful format_html displays, actions, inlines)
- 10 Management commands (expire_points, seed_tiers, seed_badges, recalculate_balances, etc.)
- 25 Test files (unit + integration + performance tests)
- 4 Full Django migrations (0003–0006)
- 8 Documentation files

#### Fixed
- `Customer` related_name conflicts → `djoyalty_customer_tenant`
- `Txn` related_name → `transactions` (was wrong)
- `Event` related_name → `events`
- All model `related_name` now unique and conflict-free
- `signals.py` bare `except:` → specific exception handling with logging

#### Models count: 47 models across 8 model files
#### API endpoints: 40+ endpoints across 20 viewsets
#### Total files: 217 (209 Python + 8 Markdown)

---

## [0.1.0] — Original

- Basic Customer, Txn, Event models
- Simple CRUD viewsets
- Basic admin registration
