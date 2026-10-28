#!/usr/bin/env python3
# publisher_tools/apply_throttle_patch.py
"""
Throttle patch — সব sensitive endpoint-এ throttle_classes যোগ করে।

Run করো:
    cd earning_backend/
    python publisher_tools/apply_throttle_patch.py

What it does:
  1. views_payout.py         → PayoutThrottle on request_payout
  2. views_publisher_advanced.py → KycSubmitThrottle on kyc_submit
  3. views_fraud_report.py   → FraudCheckThrottle on all velocity/geo actions
  4. views_reporting.py      → ExportThrottle on export_report
  5. views_webhooks_extended.py → WebhookReplayThrottle on replay_all_failed
  6. views_payment_advanced.py  → PayoutThrottle on validate_payment_details

After patch, each sensitive @action will have:
    @action(..., throttle_classes=[<ThrottleClass>])
"""

import re
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))


def patch_file(path: str, patches: list[tuple[str, str]]) -> int:
    """Apply (old_str, new_str) patches to a file. Returns number applied."""
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    applied = 0
    for old, new in patches:
        if old in content and new not in content:
            content = content.replace(old, new, 1)
            applied += 1
        elif new in content:
            applied += 1  # already applied

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

    return applied


def ensure_throttle_import(path: str, throttle_classes: list[str]) -> None:
    """Add throttle import to file if missing."""
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    existing = re.findall(r'from \.throttling import ([^\n]+)', content)
    existing_classes = set()
    for line in existing:
        existing_classes.update(c.strip() for c in line.split(','))

    needed = [c for c in throttle_classes if c not in existing_classes]
    if not needed:
        return

    if existing:
        # Append to existing import
        last_import = f"from .throttling import {', '.join(sorted(existing_classes))}"
        new_import  = f"from .throttling import {', '.join(sorted(existing_classes | set(needed)))}"
        content = content.replace(last_import, new_import, 1)
    else:
        # Add after the last 'from' import block
        insert_after = re.search(
            r'((?:^from |^import )[^\n]+\n)+', content, re.MULTILINE
        )
        if insert_after:
            pos = insert_after.end()
            new_line = f"from .throttling import {', '.join(sorted(needed))}\n"
            content = content[:pos] + new_line + content[pos:]

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def main():
    patches = {
        # ── views_payout.py ─────────────────────────────────────────────────
        'views_payout.py': {
            'imports': ['PayoutThrottle'],
            'replacements': [
                (
                    "@action(detail=False, methods=['post'], url_path='request')\n    def request_payout",
                    "@action(detail=False, methods=['post'], url_path='request', throttle_classes=[PayoutThrottle])\n    def request_payout",
                ),
            ],
        },

        # ── views_publisher_advanced.py ──────────────────────────────────────
        'views_publisher_advanced.py': {
            'imports': ['KycSubmitThrottle'],
            'replacements': [
                (
                    "@action(detail=False, methods=['post'], url_path='kyc-submit')\n    def kyc_submit",
                    "@action(detail=False, methods=['post'], url_path='kyc-submit', throttle_classes=[KycSubmitThrottle])\n    def kyc_submit",
                ),
            ],
        },

        # ── views_fraud_report.py ─────────────────────────────────────────────
        'views_fraud_report.py': {
            'imports': ['FraudCheckThrottle'],
            'replacements': [
                (
                    "@action(detail=False, methods=['post'], url_path='geo-validate')\n    def geo_validate",
                    "@action(detail=False, methods=['post'], url_path='geo-validate', throttle_classes=[FraudCheckThrottle])\n    def geo_validate",
                ),
                (
                    "@action(detail=False, methods=['post'], url_path='velocity-check')\n    def velocity_check",
                    "@action(detail=False, methods=['post'], url_path='velocity-check', throttle_classes=[FraudCheckThrottle])\n    def velocity_check",
                ),
                (
                    "@action(detail=False, methods=['post'], url_path='click-velocity')\n    def click_velocity",
                    "@action(detail=False, methods=['post'], url_path='click-velocity', throttle_classes=[FraudCheckThrottle])\n    def click_velocity",
                ),
                (
                    "@action(detail=False, methods=['post'], url_path='impression-velocity')\n    def impression_velocity",
                    "@action(detail=False, methods=['post'], url_path='impression-velocity', throttle_classes=[FraudCheckThrottle])\n    def impression_velocity",
                ),
                (
                    "@action(detail=False, methods=['post'], url_path='conversion-velocity')\n    def conversion_velocity",
                    "@action(detail=False, methods=['post'], url_path='conversion-velocity', throttle_classes=[FraudCheckThrottle])\n    def conversion_velocity",
                ),
                (
                    "@action(detail=False, methods=['post'], url_path='impossible-travel')\n    def impossible_travel",
                    "@action(detail=False, methods=['post'], url_path='impossible-travel', throttle_classes=[FraudCheckThrottle])\n    def impossible_travel",
                ),
            ],
        },

        # ── views_reporting.py ───────────────────────────────────────────────
        'views_reporting.py': {
            'imports': ['ExportThrottle'],
            'replacements': [
                (
                    "@action(detail=False, methods=['post'], url_path='export')\n    def export_report",
                    "@action(detail=False, methods=['post'], url_path='export', throttle_classes=[ExportThrottle])\n    def export_report",
                ),
            ],
        },

        # ── views_webhooks_extended.py ───────────────────────────────────────
        'views_webhooks_extended.py': {
            'imports': ['WebhookReplayThrottle'],
            'replacements': [
                (
                    "@action(detail=False, methods=['post'], url_path='replay-all-failed')\n    def replay_all_failed",
                    "@action(detail=False, methods=['post'], url_path='replay-all-failed', throttle_classes=[WebhookReplayThrottle])\n    def replay_all_failed",
                ),
                (
                    "@action(detail=True, methods=['post'], url_path='replay')\n    def replay",
                    "@action(detail=True, methods=['post'], url_path='replay', throttle_classes=[WebhookReplayThrottle])\n    def replay",
                ),
            ],
        },

        # ── views_payment_advanced.py ────────────────────────────────────────
        'views_payment_advanced.py': {
            'imports': ['PayoutThrottle'],
            'replacements': [
                (
                    "@action(detail=False, methods=['post'], url_path='validate-payment-details')\n    def validate_payment_details",
                    "@action(detail=False, methods=['post'], url_path='validate-payment-details', throttle_classes=[PayoutThrottle])\n    def validate_payment_details",
                ),
            ],
        },

        # ── views_fraud_extended.py ───────────────────────────────────────────
        'views_fraud_extended.py': {
            'imports': ['FraudCheckThrottle'],
            'replacements': [
                (
                    "@action(detail=False, methods=['post'], url_path='check-device')\n    def check_device",
                    "@action(detail=False, methods=['post'], url_path='check-device', throttle_classes=[FraudCheckThrottle])\n    def check_device",
                ),
                (
                    "@action(detail=False, methods=['post'], url_path='report')\n    def report_traffic",
                    "@action(detail=False, methods=['post'], url_path='report', throttle_classes=[FraudCheckThrottle])\n    def report_traffic",
                ),
            ],
        },

        # ── views_analytics_extended.py ──────────────────────────────────────
        'views_analytics_extended.py': {
            'imports': ['ExportThrottle'],
            'replacements': [
                (
                    "@action(detail=False, methods=['post'], url_path='export-csv')\n    def export_csv",
                    "@action(detail=False, methods=['post'], url_path='export-csv', throttle_classes=[ExportThrottle])\n    def export_csv",
                ),
            ],
        },
    }

    total_applied = 0
    total_errors  = 0

    for filename, spec in patches.items():
        path = os.path.join(BASE, filename)
        if not os.path.exists(path):
            print(f'  ⚠️  SKIP (not found): {filename}')
            continue

        try:
            ensure_throttle_import(path, spec['imports'])
            n = patch_file(path, spec['replacements'])
            total_applied += n
            status = '✅' if n > 0 else '⚪'
            print(f'  {status} {filename}: {n}/{len(spec["replacements"])} throttles applied')
        except Exception as e:
            print(f'  ❌ ERROR in {filename}: {e}')
            total_errors += 1

    print(f'\nDone — {total_applied} throttle decorators applied, {total_errors} errors.')
    return 0 if total_errors == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
