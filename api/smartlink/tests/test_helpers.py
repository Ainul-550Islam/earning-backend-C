"""
SmartLink Test Helpers — Single Source of Truth
================================================
ALL test utility / factory functions live here. Test files import from this
module instead of redefining them locally.

Before this file: _make_user() was defined 6× across test files,
_make_click() 5×, _make_offer() 5×, _make_smartlink/sl 3–6×, etc.

Usage:
    from api.smartlink.tests.test_helpers import (
        make_user, make_offer, make_smartlink, make_click,
        make_payout_record, make_profile, make_wallet,
        make_offer_pool_entry, make_batch, auth_client,
    )

All functions are prefixed with `make_` (no leading underscore) to make them
clearly importable. Legacy `_make_*` names are kept as aliases for existing
test files until they are migrated.
"""
import uuid
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

User = get_user_model()


# ─── Core object factories ────────────────────────────────────────────────────

def make_user(username: str = None, is_staff: bool = False, email: str = None) -> User:
    """Create and return a User. Generates unique username/email if not supplied."""
    username = username or f"u_{uuid.uuid4().hex[:8]}"
    email    = email or f"{username}@test.local"
    return User.objects.create_user(
        username=username, email=email, password="pass", is_staff=is_staff,
    )


def make_offer(name: str = None):
    """Create and return an offer_inventory.Offer with a unique name."""
    from django.apps import apps
    Offer = apps.get_model("offer_inventory", "Offer")
    return Offer.objects.create(name=name or f"Offer_{uuid.uuid4().hex[:6]}")


def make_smartlink(publisher, slug: str = None, active: bool = True):
    """Create and return a SmartLink owned by *publisher*."""
    from api.smartlink.models import SmartLink
    slug = slug or f"sl-{uuid.uuid4().hex[:8]}"
    return SmartLink.objects.create(
        name=f"SL {slug}", slug=slug,
        publisher=publisher, is_active=active,
    )


def make_click(
    smartlink,
    *,
    ip:           str     = "1.2.3.4",
    country:      str     = "US",
    device_type:  str     = "desktop",
    is_unique:    bool    = True,
    is_fraud:     bool    = False,
    is_bot:       bool    = False,
    is_converted: bool    = False,
    payout:       Decimal = Decimal("0"),
    offer        = None,
    days_ago:     int     = 0,
):
    """
    Create and return a Click.

    If *offer* is not supplied a fresh one is created automatically.
    Use *days_ago* to back-date the click's created_at timestamp.
    """
    from api.smartlink.models import Click
    if offer is None:
        offer = make_offer()
    click = Click.objects.create(
        smartlink=smartlink, offer=offer,
        ip=ip, user_agent="TestAgent/1.0",
        country=country, device_type=device_type,
        is_unique=is_unique, is_fraud=is_fraud,
        is_bot=is_bot, is_converted=is_converted,
        payout=payout,
    )
    if days_ago:
        old_ts = timezone.now() - datetime.timedelta(days=days_ago)
        Click.objects.filter(pk=click.pk).update(created_at=old_ts)
        click.refresh_from_db()
    return click


def make_profile(publisher, *, attribution_window_days: int = None, **kwargs):
    """
    Get-or-create a PublisherProfile for *publisher*.

    Optional keyword args are saved on the profile, e.g.:
        make_profile(pub, payment_method='wise', payout_currency='EUR')
    """
    from api.smartlink.models.billing import PublisherProfile
    defaults = dict(
        payment_method="paypal",
        payment_email=publisher.email,
        payout_currency="USD",
        min_payout=Decimal("20"),
        gdpr_consent=True,
    )
    defaults.update(kwargs)
    if attribution_window_days is not None:
        defaults["attribution_window_days"] = attribution_window_days
    profile, _ = PublisherProfile.objects.get_or_create(
        publisher=publisher, defaults=defaults,
    )
    if kwargs or attribution_window_days is not None:
        for k, v in defaults.items():
            setattr(profile, k, v)
        profile.save()
    return profile


def make_wallet(publisher, balance: Decimal = Decimal("0")):
    """Get-or-create a PublisherWallet with the given balance."""
    from api.smartlink.models.billing import PublisherWallet
    wallet, _ = PublisherWallet.objects.get_or_create(
        publisher=publisher,
        defaults={"balance": balance, "currency": "USD"},
    )
    if wallet.balance != balance:
        wallet.balance = balance
        wallet.save(update_fields=["balance"])
    return wallet


def make_payout_record(
    publisher,
    *,
    payment_method:  str     = "paypal",
    payment_address: str     = "pub@paypal.com",
    net_amount:      str     = "200.00",
    rec_status:      str     = "approved",
    transaction_ref: str     = "",
    period_from:     datetime.date = None,
    period_to:       datetime.date = None,
):
    """Create and return a PayoutRecord with sensible test defaults."""
    from api.smartlink.models.billing import PayoutRecord
    period_from = period_from or datetime.date(2026, 5, 1)
    period_to   = period_to   or datetime.date(2026, 5, 31)
    amount = Decimal(net_amount)
    return PayoutRecord.objects.create(
        publisher       = publisher,
        reference_id    = uuid.uuid4(),
        period_from     = period_from,
        period_to       = period_to,
        gross_amount    = amount,
        scrub_amount    = Decimal("0"),
        net_amount      = amount,
        currency        = "USD",
        fx_rate         = Decimal("1.000000"),
        local_amount    = amount,
        total_clicks    = 1000,
        total_conversions = 50,
        status          = rec_status,
        payment_method  = payment_method,
        payment_address = payment_address,
        transaction_ref = transaction_ref,
    )


def make_batch(publisher, label: str = "Test Batch"):
    """Create and return a PayoutBatch."""
    from api.smartlink.models.billing import PayoutBatch
    return PayoutBatch.objects.create(
        label       = label,
        period_from = datetime.date(2024, 3, 1),
        period_to   = datetime.date(2024, 3, 31),
        created_by  = publisher,
    )


def make_offer_pool_entry(smartlink, *, weight: int = 100, priority: int = 0):
    """Create an OfferPool + OfferPoolEntry for *smartlink*."""
    from api.smartlink.models import OfferPool, OfferPoolEntry
    pool, _ = OfferPool.objects.get_or_create(smartlink=smartlink)
    offer   = make_offer()
    return OfferPoolEntry.objects.create(
        pool=pool, offer=offer, weight=weight, priority=priority, is_active=True,
    )


# ─── Auth shortcut ────────────────────────────────────────────────────────────

def auth_client(user) -> APIClient:
    """Return a DRF APIClient force-authenticated as *user*."""
    client = APIClient()
    client.force_authenticate(user)
    return client


# ─── Backwards-compatible aliases (legacy names kept until migration) ─────────
# Once all test files are updated to use the `make_*` names, these can be
# removed. They exist so that existing tests that import `_make_*` still work.

_make_user              = make_user
_make_offer             = make_offer
_make_smartlink         = make_smartlink
_make_sl                = make_smartlink       # short alias used in floating tests
_make_click             = make_click
_make_profile           = make_profile
_make_wallet            = make_wallet
_make_payout_record     = make_payout_record
_make_batch             = make_batch
_make_offer_pool_entry  = make_offer_pool_entry
