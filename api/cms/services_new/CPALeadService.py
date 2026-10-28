# api/cms/services_new/CPALeadService.py
"""
CPALeadService — Production CPAlead integration.
Real postback params from official CPAlead docs (2024/2025):
  subid={subid} payout={payout} lead_id={lead_id} password={password}
"""
import hashlib, hmac, logging, time
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple
from django.utils import timezone
from django.core.cache import cache
logger = logging.getLogger(__name__)


def _get_config():
    from api.cms.models_new.extras import CPALeadConfig
    return CPALeadConfig.get_active()


def _get_offerwall():
    from api.cms.models_new.cpalead import OfferWallConfig
    try:
        return OfferWallConfig.objects.filter(is_active=True).select_related("currency").latest("created_at")
    except Exception:
        return None


class CPALeadService:
    # Alias for tests
    process_postback = None  # set below

    """CPAlead network integration."""
    OFFER_FEED = "https://api.cpalead.com/offers.php"

    @staticmethod
    def get_config():
        return _get_config()

    @staticmethod
    def get_offerwall():
        return _get_offerwall()

    # ── Postback Handler ──────────────────────────────────────────
    @staticmethod
    def handle_postback(request_data: Dict[str, Any], request_ip: str = "") -> Tuple[bool, str]:
        """
        Handle CPAlead postback. Official params (from cpalead.com/blog/tutorials/):
            subid     = your user_id passed in tracking URL
            payout    = USD reward (e.g. "0.50")
            lead_id   = CPAlead unique conversion ID (deduplicate on this!)
            password  = your postback secret for validation
        Postback URL to set in CPAlead dashboard:
            https://yoursite.com/api/cms/webhooks/cpalead/
                ?subid={subid}&payout={payout}&lead_id={lead_id}&password={password}
        """
        config = _get_config()
        if not config:
            return False, "no_config"

        # Official CPAlead postback params
        subid       = str(request_data.get("subid", "")).strip()
        payout_str  = str(request_data.get("payout", "0")).strip()
        lead_id     = str(request_data.get("lead_id", "")).strip()
        password    = str(request_data.get("password", "")).strip()
        campaign_id = str(request_data.get("campaign_id", "")).strip()
        user_ip     = str(request_data.get("ip", request_ip)).strip()

        logger.info(f"CPAlead postback: subid={subid} lead_id={lead_id} payout={payout_str}")

        # Validate password
        if config.postback_secret:
            if not hmac.compare_digest(password, config.postback_secret):
                return False, "invalid_password"

        if not subid:
            return False, "missing_subid"
        if not lead_id:
            return False, "missing_lead_id"

        try:
            payout = Decimal(payout_str)
        except Exception:
            return False, "invalid_payout"
        if payout <= 0:
            return False, "invalid_payout"

        # Deduplicate by lead_id (critical — CPAlead may retry)
        from api.cms.models_new.cpalead import ConversionLog
        if ConversionLog.is_duplicate(lead_id):
            logger.info(f"Duplicate lead_id={lead_id}")
            return True, "duplicate_ok"

        # Create ConversionLog
        conv = ConversionLog.objects.create(
            subid=subid, lead_id=lead_id, payout_usd=payout,
            campaign_id=campaign_id, ip_address=user_ip or None,
            raw_postback_data=dict(request_data), status="pending",
        )

        # Mark ClickLog converted
        try:
            from api.cms.models_new.cpalead import ClickLog
            click = ClickLog.objects.filter(click_id=subid, has_converted=False).first()
            if click:
                click.mark_converted(payout)
        except Exception:
            pass

        # Resolve user
        user = CPALeadService._resolve_user(subid)
        if user:
            conv.user = user
            conv.save(update_fields=["user"])

        # Fraud check
        if config.enable_fraud_detection:
            is_fraud, reason = FraudDetectionService.check_postback(user, user_ip, payout, config)
            if is_fraud:
                conv.reject(f"fraud:{reason}")
                return False, f"fraud:{reason}"

        # Daily cap
        if user:
            can, remaining = EarningCapService.can_earn(user, payout, config)
            if not can:
                conv.reject("cap_exceeded")
                return False, "cap_exceeded"

        # Award reward
        virtual, usd = CPALeadService._award_reward(user, subid, payout, lead_id, campaign_id, config)
        conv.approve(virtual, usd)

        # Notify
        if user:
            try:
                from api.cms.services_new.NotificationService import NotificationService
                ow = _get_offerwall()
                cur = ow.currency if ow and ow.currency else "Coins"
                NotificationService.notify_offer_completed(
                    user=user, offer_name=f"Campaign {campaign_id}" if campaign_id else "Offer",
                    amount=virtual if virtual > 0 else payout,
                    currency=cur if virtual > 0 else "USD",
                )
            except Exception:
                pass

        # Update CPAlead stats
        try:
            from api.cms.models_new.extras import CPALeadConfig
            from django.db.models import F
            CPALeadConfig.objects.filter(id=config.id).update(
                total_rewards_paid=F("total_rewards_paid") + payout,
                total_offers_completed=F("total_offers_completed") + 1,
            )
        except Exception:
            pass

        logger.info(f"CPAlead SUCCESS lead={lead_id} user={user} payout=${payout} virtual={virtual}")
        # Award referral bonus to referrer (5% of credited amount)
        try:
            from .ReferralService import ReferralService
            from decimal import Decimal as _D
            ReferralService.award_referral_bonus(
                user, _D(str(payout)), source='offer_complete', lead_id=lead_id
            )
        except Exception as _ref_exc:
            logger.warning(f"[Referral] award_referral_bonus failed: {_ref_exc}")
        return True, "1"

    @staticmethod
    def _resolve_user(subid: str):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            if subid.isdigit():
                return User.objects.get(id=int(subid))
            return User.objects.get(username=subid)
        except Exception:
            return None

    @staticmethod
    def _award_reward(user, subid, payout_usd, lead_id, campaign_id, config):
        virtual = Decimal("0")
        usd = Decimal("0")
        # Virtual currency
        if user:
            try:
                from api.cms.models_new.cpalead import VirtualCurrency, UserVirtualBalance, VirtualTransaction
                vc = VirtualCurrency.get_active()
                if vc:
                    amount = vc.usd_to_virtual(payout_usd)
                    bal, _ = UserVirtualBalance.objects.get_or_create(
                        user=user, defaults={"currency": vc, "balance": 0}
                    )
                    if bal.add_coins(amount, reason=f"Offer:{lead_id}"):
                        bal.refresh_from_db()
                        VirtualTransaction.objects.create(
                            user=user, tx_type="earn_offer", amount=amount,
                            balance_after=bal.balance, usd_equivalent=payout_usd,
                            description="CPAlead offer", cpalead_lead_id=lead_id,
                            cpalead_campaign_id=campaign_id,
                            metadata={"subid": subid, "payout_usd": str(payout_usd)},
                        )
                        virtual = amount
            except Exception as e:
                logger.warning(f"Virtual award failed: {e}")
        # Wallet — direct lazy import to api.wallet (owned by api.wallet, CMS does not bridge)
        if user:
            try:
                from api.wallet.models import WalletTransaction  # noqa: lazy import
                WalletTransaction.objects.create(
                    user=user,
                    amount=payout_usd,
                    tx_type='offer_reward',
                    reference_id=lead_id,
                    description=f'CPAlead offer: {campaign_id}',
                    metadata={'lead_id': lead_id, 'subid': subid, 'campaign_id': campaign_id},
                )
                usd = payout_usd
            except Exception as e:
                logger.warning(f"Wallet award failed: {e}")
        return virtual, usd

    # ── Click Tracking ────────────────────────────────────────────
    @staticmethod
    def track_click(user=None, offer_id="", ip="", user_agent="",
                    device="desktop", click_source="offerwall"):
        config = _get_config()
        if not config:
            return True, "no_config"
        if config.enable_fraud_detection:
            fraud, reason = FraudDetectionService.check_click(user, ip, config)
            if fraud:
                return False, reason
        if user and config.daily_click_limit_per_user > 0:
            key = f"cpalead_clicks_{user.id}_{timezone.now().date()}"
            n = cache.get(key, 0)
            if n >= config.daily_click_limit_per_user:
                return False, "daily_limit"
            cache.set(key, n + 1, 86400)
        try:
            from api.cms.models_new.cpalead import ClickLog
            click = ClickLog.create_click(
                user=user, offer_id=offer_id, click_source=click_source,
                ip=ip, user_agent=user_agent, device_type=device,
            )
            return True, click.click_id
        except Exception as e:
            logger.error(f"ClickLog failed: {e}")
            return True, str(user.id if user else "anon")

    # ── Offer Feed API ────────────────────────────────────────────
    @staticmethod
    def fetch_offers(user_ip="", device="desktop", country="", limit=20, offer_types=None):
        """Fetch from CPAlead JSON API: https://api.cpalead.com/offers.php?pub={pub}&user_ip={ip}&device={device}"""
        ow = _get_offerwall()
        if not ow or not ow.publisher_id:
            return CPALeadService._get_cached_offers(country, device, offer_types, limit)
        cache_key = f"cpalead_offers_{user_ip}_{device}_{country}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            import urllib.request, json
            url = f"{CPALeadService.OFFER_FEED}?pub={ow.publisher_id}&user_ip={user_ip}&device={device}&limit={limit}"
            if country:
                url += f"&country={country.upper()}"
            with urllib.request.urlopen(url, timeout=5) as r:
                data = json.loads(r.read())
            offers = CPALeadService._parse_feed(data, ow)
            cache.set(cache_key, offers, 1800)
            return offers
        except Exception as e:
            logger.warning(f"Offer feed failed: {e}")
            return CPALeadService._get_cached_offers(country, device, offer_types, limit)

    @staticmethod
    def _parse_feed(data, ow):
        from api.cms.models_new.cpalead import OfferCache
        if not isinstance(data, list):
            data = data.get("offers", data.get("data", []))
        vc = ow.currency if ow else None
        out = []
        for item in data:
            try:
                oid = str(item.get("id", item.get("offer_id", "")))
                p = Decimal(str(item.get("payout", item.get("earn", "0"))))
                v = vc.usd_to_virtual(p) if vc else p * 100
                ot = item.get("type", "").lower()
                offer_type = "quiz" if "quiz" in ot else ("cpi" if "install" in ot else "cpa")
                oc, _ = OfferCache.objects.update_or_create(
                    offerwall=ow, offer_id=oid,
                    defaults={
                        "offer_type": offer_type, "title": item.get("name", "Offer"),
                        "payout_usd": p, "payout_virtual": v,
                        "icon_url": item.get("icon", ""), "is_active": True,
                        "is_quiz": offer_type == "quiz", "countries": item.get("countries", []),
                        "raw_data": item, "fetched_at": timezone.now(),
                    }
                )
                out.append(oc)
            except Exception:
                pass
        return out

    @staticmethod
    def _get_cached_offers(country="", device="", offer_types=None, limit=20):
        from api.cms.models_new.cpalead import OfferCache
        qs = OfferCache.objects.filter(is_active=True)
        if offer_types:
            qs = qs.filter(offer_type__in=offer_types)
        return list(qs.order_by("-is_featured", "-payout_usd")[:limit])

    # ── Offerwall Embed ───────────────────────────────────────────
    @staticmethod
    def generate_offerwall_embed(user=None, page_url=""):
        ow = _get_offerwall()
        if not ow:
            return {"error": "No offerwall configured", "embed_code": "", "offers": []}
        return {
            "embed_code": ow.generate_embed_code(user=user),
            "offerwall_title": ow.offerwall_title,
            "currency_name": ow.currency if ow.currency else "Coins",
            "currency_symbol": ow.currency if ow.currency else "🪙",
            "currency_ratio": float(ow.currency.usd_ratio) if ow.currency else 100,
            "publisher_id": ow.publisher_id,
            "user_subid": str(user.id) if user and user.is_authenticated else "anonymous",
        }

    # ── Content Locker ────────────────────────────────────────────
    @staticmethod
    def check_content_locked(locker_id, user=None, session_key=""):
        from api.cms.models_new.cpalead import ContentLocker
        try:
            locker = ContentLocker.objects.select_related("offerwall").get(id=locker_id, is_active=True)
            locker.record_view()
            is_locked = locker.is_locked_for_user(user=user, session_key=session_key)
            result = {
                "is_locked": is_locked, "locker_id": locker.id,
                "title": locker.title, "zero_hours_mode": locker.zero_hours_mode,
                "blur_preview": locker.blur_preview, "blur_amount": locker.blur_amount,
            }
            if not is_locked:
                result["unlocked_content"] = locker.locked_content
            else:
                result["preview"] = locker.preview_content
                result["offerwall"] = CPALeadService.generate_offerwall_embed(user=user)
            return result
        except Exception:
            return {"error": "Locker not found", "is_locked": True}

    @staticmethod
    def unlock_content(locker_id, user=None, session_key="", lead_id="", payout_usd=None, ip=""):
        from api.cms.models_new.cpalead import ContentLocker, LockerUnlock
        from datetime import timedelta
        try:
            locker = ContentLocker.objects.get(id=locker_id, is_active=True)
            mode = locker.unlock_mode
            expires = None
            if mode == "24h":
                expires = timezone.now() + timedelta(hours=24)
            elif mode == "7d":
                expires = timezone.now() + timedelta(days=7)
            elif mode == "session":
                expires = timezone.now() + timedelta(hours=2)
            if not locker.zero_hours_mode:
                LockerUnlock.objects.update_or_create(
                    locker=locker, user=user,
                    defaults={
                        "session_key": session_key, "unlock_source": "cpalead_postback" if lead_id else "cpalead_offer",
                        "cpalead_lead_id": lead_id, "payout_usd": payout_usd,
                        "expires_at": expires, "ip_address": ip or None, "is_valid": True,
                    }
                )
                locker.record_unlock()
            return {"unlocked": True, "content": locker.locked_content, "locker_type": locker.locker_type}
        except Exception:
            return {"unlocked": False, "error": "Locker not found"}


class FraudDetectionService:
    @staticmethod
    def check_click(user, ip, config):
        try:
            key = f"cpalead_ip_{ip}_{timezone.now().strftime('%Y%m%d%H')}"
            n = cache.get(key, 0)
            if n >= config.max_clicks_per_ip_per_hour:
                return True, "ip_rate_limit"
            cache.set(key, n + 1, 3600)
            if user:
                lkey = f"cpalead_last_click_{user.id}"
                last = cache.get(lkey)
                if last and time.time() - last < config.min_time_between_clicks_seconds:
                    return True, "too_fast"
                cache.set(lkey, time.time(), 3600)
            return False, "ok"
        except Exception:
            return False, "ok"

    @staticmethod
    def check_postback(user, ip, payout, config):
        try:
            if payout > Decimal("50"):
                return True, "suspicious_amount"
            key = f"cpalead_pb_{ip}_{timezone.now().strftime('%Y%m%d')}"
            n = cache.get(key, 0)
            if n > 100:
                return True, "postback_spam"
            cache.set(key, n + 1, 86400)
            return False, "ok"
        except Exception:
            return False, "ok"


class EarningCapService:
    @staticmethod
    def can_earn(user, amount, config):
        if not config or config.daily_earning_cap_per_user <= 0:
            return True, Decimal("999999")
        try:
            key = f"earn_cap_{user.id}_{timezone.now().date()}"
            earned = Decimal(str(cache.get(key, "0")))
            cap = Decimal(str(config.daily_earning_cap_per_user))
            remaining = cap - earned
            if amount > remaining:
                return False, remaining
            cache.set(key, str(earned + amount), 86400)
            return True, remaining - amount
        except Exception:
            return True, Decimal("999999")

    @staticmethod
    def get_today_earnings(user):
        return Decimal(str(cache.get(f"earn_cap_{user.id}_{timezone.now().date()}", "0")))

    @staticmethod
    def get_cap_info(user, config=None):
        if not config:
            config = _get_config()
        cap = Decimal(str(config.daily_earning_cap_per_user)) if config else Decimal("0")
        earned = EarningCapService.get_today_earnings(user)
        return {
            "daily_cap_usd": float(cap),
            "earned_today_usd": float(earned),
            "remaining_usd": float(max(Decimal("0"), cap - earned)),
            "percentage_used": round(float(earned / cap * 100) if cap > 0 else 0, 1),
            "can_still_earn": earned < cap,
            "reset_time": "midnight UTC",
        }

    @staticmethod
    def reset_daily_caps():
        logger.info("[CPAlead] Daily caps reset")
        return True


class VirtualCurrencyService:
    @staticmethod
    def get_balance(user):
        from api.cms.models_new.cpalead import UserVirtualBalance, VirtualCurrency
        vc = VirtualCurrency.get_active()
        if not vc:
            return {"error": "No virtual currency"}
        try:
            bal = UserVirtualBalance.objects.get(user=user)
            return {
                "currency_name": vc.name, "currency_symbol": vc.symbol,
                "balance": float(bal.balance), "total_earned": float(bal.total_earned),
                "today_earned": float(bal.today_earned), "daily_cap": float(vc.daily_earn_cap),
                "usd_equivalent": float(vc.virtual_to_usd(bal.balance)),
            }
        except UserVirtualBalance.DoesNotExist:
            return {"currency_name": vc.name, "balance": 0, "today_earned": 0}

    @staticmethod
    def award_coins(user, amount, reason, tx_type="earn_bonus", source_id=""):
        from api.cms.models_new.cpalead import UserVirtualBalance, VirtualCurrency, VirtualTransaction
        vc = VirtualCurrency.get_active()
        if not vc:
            return False
        bal, _ = UserVirtualBalance.objects.get_or_create(user=user, currency=vc, defaults={"balance": Decimal('0')})
        ok = bal.add_coins(amount, reason=reason)
        if ok:
            bal.refresh_from_db()
            VirtualTransaction.objects.create(
                user=user, tx_type=tx_type, amount=amount,
                balance_after=bal.balance, description=reason, source_id=source_id,
            )
        return ok

    @staticmethod
    def get_transaction_history(user, limit=50):
        from api.cms.models_new.cpalead import VirtualTransaction
        return list(VirtualTransaction.objects.filter(user=user).order_by("-created_at")[:limit])


# Alias
CPALeadService.process_postback = staticmethod(CPALeadService.handle_postback)
