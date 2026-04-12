# api/publisher_tools/hooks.py
"""Publisher Tools — Lifecycle hooks. Pre/post operation hooks।"""
import logging
from typing import Callable, Dict, List, Any
from django.utils import timezone

logger = logging.getLogger(__name__)

_hooks: Dict[str, List[Callable]] = {}


def register_hook(hook_name: str, callback: Callable):
    """Hook register করে।"""
    if hook_name not in _hooks:
        _hooks[hook_name] = []
    _hooks[hook_name].append(callback)


def run_hooks(hook_name: str, **context) -> List[Any]:
    """সব registered hooks run করে।"""
    results = []
    for hook in _hooks.get(hook_name, []):
        try:
            result = hook(**context)
            results.append(result)
        except Exception as e:
            logger.error(f'Hook error [{hook_name}]: {e}')
    return results


# ── Pre-operation hooks ────────────────────────────────────────────────────────
def pre_publisher_create(publisher_data: dict) -> dict:
    results = run_hooks('pre_publisher_create', data=publisher_data)
    return publisher_data


def pre_site_register(site_data: dict) -> dict:
    results = run_hooks('pre_site_register', data=site_data)
    return site_data


def pre_earning_record(earning_data: dict) -> dict:
    results = run_hooks('pre_earning_record', data=earning_data)
    return earning_data


def pre_invoice_generate(publisher, year: int, month: int) -> bool:
    results = run_hooks('pre_invoice_generate', publisher=publisher, year=year, month=month)
    return all(r is not False for r in results)


def pre_payout_process(publisher, amount) -> bool:
    results = run_hooks('pre_payout_process', publisher=publisher, amount=amount)
    return all(r is not False for r in results)


# ── Post-operation hooks ───────────────────────────────────────────────────────
def post_publisher_create(publisher):
    run_hooks('post_publisher_create', publisher=publisher)


def post_site_verify(site, success: bool):
    run_hooks('post_site_verify', site=site, success=success)


def post_earning_finalized(publisher, year: int, month: int):
    run_hooks('post_earning_finalized', publisher=publisher, year=year, month=month)


def post_invoice_paid(invoice):
    run_hooks('post_invoice_paid', invoice=invoice)


def post_fraud_detected(log):
    run_hooks('post_fraud_detected', log=log)


# ── Built-in default hooks ─────────────────────────────────────────────────────
def _check_publisher_blacklist(data: dict) -> dict:
    """Email blacklist check।"""
    blacklisted_emails = []  # production-এ DB থেকে load করো
    if data.get('contact_email', '').lower() in blacklisted_emails:
        raise ValueError('Email address is blacklisted.')
    return data


def _send_welcome_email_hook(publisher):
    """Publisher তৈরির পর welcome email পাঠায়।"""
    logger.info(f'Welcome email queued for: {publisher.contact_email}')


# Register default hooks
register_hook('pre_publisher_create', _check_publisher_blacklist)
register_hook('post_publisher_create', _send_welcome_email_hook)
