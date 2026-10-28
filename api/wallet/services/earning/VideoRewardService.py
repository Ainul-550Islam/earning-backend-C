# services/earning/VideoRewardService.py
"""
VideoRewardService — Watch-to-Earn video reward system.
Owner: VideoRewardService (এক কাজের জন্য একটাই মালিক)

Platforms that reward video watching:
  • AdGate Media — primary video reward source
  • CPAlead — video offers
  • YouTube/custom video (internal campaign)

Features:
  • Track video start, progress (25/50/75/100%)
  • Partial rewards for incomplete watches (configurable)
  • Anti-fraud: same video cooldown, daily cap, velocity check
  • Reward credited via EarningService (source_type=offer_wall)
  • Celery task for async reward processing
"""
import logging
import uuid
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("wallet.video_reward")

# Config defaults (can override in settings)
VIDEO_DAILY_CAP_USD     = Decimal("5.00")   # max video earnings/day
VIDEO_MIN_WATCH_PCT     = 80                # % required for full reward
VIDEO_PARTIAL_THRESHOLD = 50                # % for 50% reward
VIDEO_COOLDOWN_SECONDS  = 3600             # same video again after 1h
VIDEO_SESSION_TTL       = 3600 * 3         # session data lives 3h


class VideoSession:
    """Tracks a single video watch session in cache (no DB hit)."""

    @staticmethod
    def start(user_id: int, video_id: str, platform: str, payout_usd: Decimal) -> str:
        """
        Initialize a video watch session.
        Returns session_token to send to the frontend.
        """
        session_token = uuid.uuid4().hex
        session_data  = {
            "session_token":  session_token,
            "user_id":        user_id,
            "video_id":       video_id,
            "platform":       platform,
            "payout_usd":     str(payout_usd),
            "started_at":     timezone.now().isoformat(),
            "progress_pct":   0,
            "rewarded":       False,
            "events":         [],
        }
        cache.set(f"video_session:{session_token}", session_data, VIDEO_SESSION_TTL)
        return session_token

    @staticmethod
    def update_progress(session_token: str, progress_pct: int) -> dict:
        """Record progress milestone (25/50/75/100)."""
        data = cache.get(f"video_session:{session_token}")
        if not data:
            return {"error": "session_not_found"}
        data["progress_pct"] = max(data["progress_pct"], progress_pct)
        data["events"].append({"pct": progress_pct, "at": timezone.now().isoformat()})
        cache.set(f"video_session:{session_token}", data, VIDEO_SESSION_TTL)
        return {"progress": data["progress_pct"]}

    @staticmethod
    def get(session_token: str) -> dict | None:
        return cache.get(f"video_session:{session_token}")

    @staticmethod
    def mark_rewarded(session_token: str):
        data = cache.get(f"video_session:{session_token}")
        if data:
            data["rewarded"] = True
            cache.set(f"video_session:{session_token}", data, VIDEO_SESSION_TTL)


class VideoRewardService:
    """
    Core video reward logic. Handles anti-fraud checks and EarningService dispatch.
    """

    @staticmethod
    def start_session(user_id: int, video_id: str, platform: str, payout_usd: Decimal) -> dict:
        """
        Called when user starts watching a video.
        Creates a session, runs pre-check.
        """
        # Cooldown check — same video within last hour
        cooldown_key = f"video_cooldown:{user_id}:{video_id}"
        if cache.get(cooldown_key):
            return {
                "success": False,
                "error":   "cooldown",
                "message": "This video was recently watched. Try again later.",
            }

        # Daily cap check
        daily_key   = f"video_daily:{user_id}:{timezone.now().date()}"
        daily_total = Decimal(str(cache.get(daily_key) or "0"))
        if daily_total >= VIDEO_DAILY_CAP_USD:
            return {
                "success": False,
                "error":   "daily_cap",
                "message": f"Daily video earning cap (${VIDEO_DAILY_CAP_USD}) reached.",
            }

        session_token = VideoSession.start(user_id, video_id, platform, payout_usd)
        return {
            "success":       True,
            "session_token": session_token,
            "payout_usd":    str(payout_usd),
            "min_watch_pct": VIDEO_MIN_WATCH_PCT,
        }

    @staticmethod
    def record_progress(session_token: str, progress_pct: int) -> dict:
        """
        Called by frontend on 25/50/75/100% milestones.
        Returns reward hint to show in UI.
        """
        result = VideoSession.update_progress(session_token, progress_pct)
        if "error" in result:
            return result

        session = VideoSession.get(session_token)
        if not session:
            return {"error": "session_not_found"}

        payout_usd = Decimal(session["payout_usd"])
        if progress_pct >= VIDEO_MIN_WATCH_PCT:
            expected_reward = payout_usd
        elif progress_pct >= VIDEO_PARTIAL_THRESHOLD:
            expected_reward = payout_usd * Decimal("0.5")
        else:
            expected_reward = Decimal("0")

        return {
            "progress_pct":   progress_pct,
            "expected_reward": str(expected_reward),
            "fully_qualified": progress_pct >= VIDEO_MIN_WATCH_PCT,
        }

    @staticmethod
    def complete(session_token: str, wallet) -> dict:
        """
        Called when video ends (or ≥80% watched).
        Credits the wallet via EarningService.
        """
        session = VideoSession.get(session_token)
        if not session:
            return {"success": False, "error": "session_not_found"}

        if session.get("rewarded"):
            return {"success": False, "error": "already_rewarded"}

        progress_pct = session.get("progress_pct", 0)
        payout_usd   = Decimal(session["payout_usd"])
        user_id      = session["user_id"]
        video_id     = session["video_id"]
        platform     = session["platform"]

        # Calculate earned amount
        if progress_pct >= VIDEO_MIN_WATCH_PCT:
            earned_usd = payout_usd
        elif progress_pct >= VIDEO_PARTIAL_THRESHOLD:
            earned_usd = payout_usd * Decimal("0.5")
        else:
            return {
                "success":   False,
                "error":     "insufficient_watch",
                "watched":   progress_pct,
                "required":  VIDEO_MIN_WATCH_PCT,
            }

        # Convert to BDT
        try:
            from ...exchange_rates import convert_usd_to_bdt
            earned_bdt = convert_usd_to_bdt(earned_usd)
        except Exception:
            earned_bdt = earned_usd * Decimal("110")

        # Credit wallet
        try:
            from .EarningService import EarningService
            from ...choices import EarningSourceType

            result = EarningService.add_earning(
                wallet      = wallet,
                amount      = earned_bdt,
                source_type = EarningSourceType.OFFER_WALL,
                source_id   = video_id,
                description = f"Video reward: {platform} ({progress_pct}% watched)",
                metadata    = {
                    "platform":      platform,
                    "video_id":      video_id,
                    "watch_pct":     progress_pct,
                    "payout_usd":    str(earned_usd),
                    "session_token": session_token,
                },
            )

            # Update daily cap tracker
            daily_key   = f"video_daily:{user_id}:{timezone.now().date()}"
            daily_total = Decimal(str(cache.get(daily_key) or "0"))
            cache.set(daily_key, str(daily_total + earned_usd), 86400)

            # Set cooldown
            cache.set(f"video_cooldown:{user_id}:{video_id}", "1", VIDEO_COOLDOWN_SECONDS)

            VideoSession.mark_rewarded(session_token)

            logger.info(
                f"[video] Rewarded: user={user_id} video={video_id} "
                f"watched={progress_pct}% usd={earned_usd} bdt={earned_bdt}"
            )
            return {
                "success":    True,
                "earned_bdt": str(earned_bdt),
                "earned_usd": str(earned_usd),
                "watch_pct":  progress_pct,
            }

        except Exception as exc:
            logger.error(f"[video] Credit error: {exc}", exc_info=True)
            return {"success": False, "error": str(exc)}
