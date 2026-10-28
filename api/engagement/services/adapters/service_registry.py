# engagement/services/service_registry.py
"""
EngagementServiceRegistry
=========================
Single facade that wires ALL adapters + bridges together.

Engagement services call ONLY this registry — never import adapters
or bridges directly inside business logic.

Pattern:
    from api.engagement.services.service_registry import registry

    # In checkin_service.py:
    registry.rate_limit.check_checkin(user, ip=ip)
    registry.fraud.check_before_reward(user, "checkin", amount, ip)
    registry.audit.log_checkin(user, streak, coins, ip)
    registry.analytics.track_checkin(user, streak, coins)
    registry.behavior.track_checkin(user, streak, coins, ip)
    registry.notification.checkin_reward(user, coins, streak)
    registry.referral.on_coins_earned(user, amount, source="checkin")
    registry.event_bus.emit_checkin(user, coins, streak)

Full stack for a spin action:
    1. registry.rate_limit.check_spin(user, ip)          → block if throttled
    2. registry.proxy_intel.check_before_reward(ip)      → block Tor/malicious IP
    3. registry.fraud.check_before_reward(user, "spin")  → block if score ≥ 80
    4. registry.security.check_bot(user, ip, ua)         → block bot traffic
    5. ... award the coins ...
    6. registry.wallet.credit_coins(user, amount, "spin")
    7. registry.referral.on_coins_earned(user, amount)
    8. registry.audit.log_spin(user, coins, idx, ip)
    9. registry.analytics.track_spin(user, coins)
    10. registry.behavior.track_spin(user, idx, coins, ip)
    11. registry.notification.spin_reward(user, coins, remaining)
    12. registry.event_bus.emit_spin(user, coins, idx, remaining)
"""


class _RegistryProxy:
    """Lazy loader — only imports on first access (avoids circular imports)."""

    def __init__(self, module_path: str, class_name: str):
        self._module_path = module_path
        self._class_name = class_name
        self._instance = None

    def __getattr__(self, name):
        if self._instance is None:
            import importlib
            mod = importlib.import_module(self._module_path)
            self._instance = getattr(mod, self._class_name)
        return getattr(self._instance, name)


class EngagementServiceRegistry:
    """
    Central registry for all engagement service dependencies.

    Attributes (all lazily loaded):
        rate_limit    — RateLimitAdapter
        fraud         — FraudDetectionAdapter
        security      — SecurityAdapter
        proxy_intel   — ProxyIntelAdapter
        kyc           — KYCAdapter
        audit         — AuditLogAdapter
        behavior      — BehaviorAnalyticsAdapter
        alerts        — AlertsAdapter
        auto_mod      — AutoModAdapter
        analytics     — AnalyticsAdapter
        wallet        — WalletBridge
        notification  — NotificationBridge
        referral      — ReferralBridge
        user          — UserBridge
        event_bus     — EngagementEventBus
        inbound       — EngagementBridge (inbound from other apps)
    """

    # ── External system adapters ──────────────────────────────────────────────
    rate_limit   = _RegistryProxy("api.engagement.services.adapters.rate_limit_adapter",      "RateLimitAdapter")
    fraud        = _RegistryProxy("api.engagement.services.adapters.fraud_detection_adapter", "FraudDetectionAdapter")
    security     = _RegistryProxy("api.engagement.services.adapters.security_adapter",        "SecurityAdapter")
    proxy_intel  = _RegistryProxy("api.engagement.services.adapters.proxy_intel_adapter",     "ProxyIntelAdapter")
    kyc          = _RegistryProxy("api.engagement.services.adapters.kyc_adapter",             "KYCAdapter")
    audit        = _RegistryProxy("api.engagement.services.adapters.audit_log_adapter",       "AuditLogAdapter")
    behavior     = _RegistryProxy("api.engagement.services.adapters.behavior_analytics_adapter", "BehaviorAnalyticsAdapter")
    alerts       = _RegistryProxy("api.engagement.services.adapters.alerts_adapter",          "AlertsAdapter")
    auto_mod     = _RegistryProxy("api.engagement.services.adapters.auto_mod_adapter",        "AutoModAdapter")
    analytics    = _RegistryProxy("api.engagement.services.adapters.analytics_adapter",       "AnalyticsAdapter")

    # ── Inter-app integration bridges ─────────────────────────────────────────
    wallet       = _RegistryProxy("api.engagement.services.integration.wallet_bridge",        "WalletBridge")
    notification = _RegistryProxy("api.engagement.services.integration.notification_bridge",  "NotificationBridge")
    referral     = _RegistryProxy("api.engagement.services.integration.referral_bridge",      "ReferralBridge")
    user         = _RegistryProxy("api.engagement.services.integration.user_bridge",          "UserBridge")
    event_bus    = _RegistryProxy("api.engagement.services.integration.event_bus",            "EngagementEventBus")
    inbound      = _RegistryProxy("api.engagement.services.integration.inbound_bridge",       "EngagementBridge")

    # ── Core engagement services ──────────────────────────────────────────────
    coins        = _RegistryProxy("api.engagement.services.coin_service",                     "CoinService")
    xp           = _RegistryProxy("api.engagement.services.xp_service",                       "XPService")
    checkin      = _RegistryProxy("api.engagement.services.checkin_service",                   "CheckInService")
    spin         = _RegistryProxy("api.engagement.services.spin_service",                      "SpinService")
    shop         = _RegistryProxy("api.engagement.services.shop_service",                      "ShopService")
    quests       = _RegistryProxy("api.engagement.services.quest_service",                     "QuestService")
    achievements = _RegistryProxy("api.engagement.services.achievement_service",               "AchievementService")
    leaderboard  = _RegistryProxy("api.engagement.services.leaderboard_service",               "LeaderboardService")
    battle_pass  = _RegistryProxy("api.engagement.services.battle_pass_service",               "BattlePassService")
    guild        = _RegistryProxy("api.engagement.services.guild_service",                     "GuildService")
    social       = _RegistryProxy("api.engagement.services.social_service",                    "SocialService")
    anti_cheat   = _RegistryProxy("api.engagement.services.anti_cheat_service",                "AntiCheatService")
    loot_box     = _RegistryProxy("api.engagement.services.loot_box_service",                  "LootBoxService")
    scratch      = _RegistryProxy("api.engagement.services.scratch_card_service",              "ScratchCardService")
    auction      = _RegistryProxy("api.engagement.services.auction_service",                   "AuctionService")
    campaign     = _RegistryProxy("api.engagement.services.campaign_service",                  "FeatureFlagService")

    # ── Convenience: full pre-action security check ───────────────────────────

    @staticmethod
    def pre_action_check(user, action: str, ip: str = None,
                          user_agent: str = None,
                          fingerprint: str = None,
                          amount: float = 0) -> dict:
        """
        Run ALL security checks before any engagement action.
        Call this at the START of checkin/spin/shop/auction views.

        Returns:
            {
                "allowed": bool,
                "reason": str,
                "checks": {
                    "rate_limit": {...},
                    "fraud":      {...},
                    "bot":        {...},
                    "proxy":      {...},
                    "banned":     bool,
                }
            }
        """
        checks = {}

        # 1. Rate limit
        rl = EngagementServiceRegistry.rate_limit.check_action(user, action, ip=ip)
        checks["rate_limit"] = rl
        if not rl["allowed"]:
            return {"allowed": False, "reason": "rate_limited",
                    "retry_after": rl.get("retry_after", 60), "checks": checks}

        # 2. Banned check
        is_banned = EngagementServiceRegistry.fraud.is_banned(user)
        checks["banned"] = is_banned
        if is_banned:
            return {"allowed": False, "reason": "user_banned", "checks": checks}

        # 3. Proxy / IP check (only for reward actions)
        if ip and action in ("checkin", "spin", "task", "referral", "scratch"):
            proxy = EngagementServiceRegistry.proxy_intel.check_before_reward(ip, action)
            checks["proxy"] = proxy
            if not proxy["allow"]:
                return {"allowed": False, "reason": f"ip_{proxy['reason']}",
                        "checks": checks}

        # 4. Bot detection (lightweight, async-safe)
        if ip and action in ("spin", "checkin", "task"):
            bot = EngagementServiceRegistry.security.check_bot(
                user, ip=ip, user_agent=user_agent, fingerprint=fingerprint
            )
            checks["bot"] = bot
            if bot["is_bot"] and bot["confidence"] > 0.85:
                return {"allowed": False, "reason": "bot_detected", "checks": checks}

        # 5. Fraud score (only for high-value or suspicious actions)
        if amount > 50 or action in ("referral", "leaderboard_claim"):
            fraud = EngagementServiceRegistry.fraud.check_before_reward(
                user, action, amount, ip
            )
            checks["fraud"] = fraud
            if not fraud["allow"]:
                return {"allowed": False, "reason": fraud["reason"],
                        "checks": checks}

        return {"allowed": True, "reason": "ok", "checks": checks}

    @staticmethod
    def post_action_track(user, action: str, result: dict,
                           ip: str = None) -> None:
        """
        Fire all post-action tracking after a successful engagement action.
        Non-blocking — all failures are silently logged.

        Call this AFTER successfully processing checkin/spin/quest/etc.
        """
        coins = result.get("coins_earned") or result.get("coins_won") or \
                result.get("coins", 0) or 0
        try:
            EngagementServiceRegistry.audit.log_generic(
                user, action, data=result, ip=ip
            )
        except Exception:
            pass
        try:
            EngagementServiceRegistry.analytics._send(action, user, result)
        except Exception:
            pass
        try:
            EngagementServiceRegistry.behavior.track_reward_received(
                user, float(coins), action,
                result.get("new_balance", 0) or result.get("new_coin_balance", 0)
            )
        except Exception:
            pass


# ── Module-level singleton ────────────────────────────────────────────────────
registry = EngagementServiceRegistry()
