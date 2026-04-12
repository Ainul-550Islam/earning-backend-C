"""AD_FORMATS/push_notification.py — Push notification ad format."""
from dataclasses import dataclass
from typing import Optional
import json


@dataclass
class PushNotificationAd:
    title: str
    body: str
    icon_url: str = ""
    image_url: str = ""
    click_url: str = ""
    action_label: str = "Open"
    badge_count: int = 0
    sound: str = "default"
    ttl_seconds: int = 86400        # 24 hours


class PushNotificationAdHandler:
    """Builds and validates push notification ad payloads."""

    MAX_TITLE_LEN = 65
    MAX_BODY_LEN  = 240

    @classmethod
    def build(cls, title: str, body: str, click_url: str = "",
               icon_url: str = "") -> PushNotificationAd:
        return PushNotificationAd(
            title=title[:cls.MAX_TITLE_LEN],
            body=body[:cls.MAX_BODY_LEN],
            click_url=click_url,
            icon_url=icon_url,
        )

    @classmethod
    def to_fcm_payload(cls, ad: PushNotificationAd,
                        token: str) -> dict:
        return {
            "to": token,
            "notification": {
                "title": ad.title,
                "body":  ad.body,
                "icon":  ad.icon_url or "",
                "image": ad.image_url or "",
                "click_action": ad.click_url,
            },
            "data": {"url": ad.click_url, "type": "push_ad"},
            "android": {"ttl": f"{ad.ttl_seconds}s"},
        }

    @classmethod
    def validate(cls, ad: PushNotificationAd) -> list:
        errors = []
        if not ad.title:
            errors.append("title required")
        if not ad.body:
            errors.append("body required")
        if len(ad.title) > cls.MAX_TITLE_LEN:
            errors.append(f"title max {cls.MAX_TITLE_LEN} chars")
        return errors
