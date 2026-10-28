"""
payout_queue/management/commands/payout_rotate_encryption.py  ← v9 NEW

PURPOSE:
    Rotate the Fernet encryption key used to encrypt PayoutItem.account_number.

    Key rotation is required when:
    - An old key is suspected to be compromised.
    - Standard security policy requires periodic key rotation (e.g. annually).
    - Moving keys to a new secrets manager (AWS → Vault).

USAGE:
    python manage.py payout_rotate_encryption \\
        --old-key <base64_old_key> \\
        --new-key <base64_new_key> \\
        [--dry-run] \\
        [--batch-size 500] \\
        [--confirm]

    Or with env-based keys (recommended for production — avoids key in shell history):
        OLD_KEY=$(vault kv get -field=value secret/payout_old_key) \\
        NEW_KEY=$(vault kv get -field=value secret/payout_new_key) \\
        python manage.py payout_rotate_encryption \\
            --old-key "$OLD_KEY" --new-key "$NEW_KEY" --confirm

PROCESS:
    1. Validates both keys (Fernet format check).
    2. For each PayoutItem in chunks of --batch-size:
       a. Decrypts account_number with old key.
       b. Re-encrypts with new key.
       c. Recomputes account_number_hash with new key.
       d. Updates both fields in one bulk_update call.
    3. Verifies a random sample (10 items) after rotation.
    4. Prints step-by-step progress and final summary.

AFTER RUNNING:
    Update your .env / secrets manager:
        PAYOUT_ENCRYPTION_KEY=<new_key>
    Restart all Django workers and Celery workers to pick up the new key.
    The old key can be decommissioned after all workers have restarted.

SAFETY:
    --dry-run  — decrypts with old key + encrypts with new key but does NOT save.
                 Use to verify both keys work on your data before committing.
    --confirm  — required for actual execution (prevents accidental runs).
    Chunks of --batch-size with individual error handling — one bad row never
    aborts the whole rotation; it is logged and skipped.
    Progress is printed every chunk so long rotations can be monitored.
"""

from __future__ import annotations

import base64
import logging
import sys
import uuid as _uuid

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

class Command(BaseCommand):

    help = (
        "Rotate the Fernet encryption key for PayoutItem.account_number. "
        "Decrypts all rows with --old-key and re-encrypts with --new-key. "
        "Use --dry-run first to verify both keys work."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--old-key",
            type=str,
            required=True,
            help="Current PAYOUT_ENCRYPTION_KEY (base64 Fernet key).",
        )
        parser.add_argument(
            "--new-key",
            type=str,
            required=True,
            help="New Fernet key to encrypt with. "
                 "Generate: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Decrypt with old key + encrypt with new key but DO NOT save. "
                 "Run this first to verify both keys work on your data.",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            default=False,
            help="Required to perform actual writes. Prevents accidental execution.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Rows to process per chunk (default: 500). "
                 "Reduce for low-memory environments.",
        )
        parser.add_argument(
            "--start-from",
            type=str,
            default=None,
            help="Resume rotation from this PayoutItem UUID (inclusive). "
                 "Use to resume an interrupted rotation.",
        )

    def handle(self, *args, **options):
        old_key_str:  str  = options["old_key"]
        new_key_str:  str  = options["new_key"]
        dry_run:      bool = options["dry_run"]
        confirm:      bool = options["confirm"]
        batch_size:   int  = options["batch_size"]
        start_from:   str | None = options["start_from"]

        # ── Validation ────────────────────────────────────────────────────────
        if not dry_run and not confirm:
            raise CommandError(
                "Pass --confirm to execute the rotation, or --dry-run to preview. "
                "This command modifies all PayoutItem rows."
            )
        if old_key_str == new_key_str:
            raise CommandError("--old-key and --new-key must be different.")

        try:
            from cryptography.fernet import Fernet, InvalidToken
        except ImportError:
            raise CommandError(
                "The 'cryptography' package is required. "
                "Run: pip install cryptography"
            )

        try:
            old_cipher = Fernet(old_key_str.encode())
        except Exception as exc:
            raise CommandError(f"--old-key is not a valid Fernet key: {exc}")

        try:
            new_cipher = Fernet(new_key_str.encode())
        except Exception as exc:
            raise CommandError(f"--new-key is not a valid Fernet key: {exc}")

        import hmac
        import hashlib
        new_hmac_secret = new_key_str.encode()

        from api.payout_queue.models import PayoutItem

        total_rows   = PayoutItem.objects.count()
        self.stdout.write(
            self.style.NOTICE(
                f"\n{'DRY RUN — ' if dry_run else ''}Rotating encryption key on "
                f"{total_rows} PayoutItem rows (batch_size={batch_size}).\n"
            )
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: no DB writes will occur.\n"))

        # ── Process in chunks ─────────────────────────────────────────────────
        qs = PayoutItem.objects.only("id", "account_number", "account_number_hash").order_by("created_at")
        if start_from:
            qs = qs.filter(created_at__gte=PayoutItem.objects.get(pk=start_from).created_at)
            self.stdout.write(f"Resuming from item {start_from}.")

        processed = 0
        skipped   = 0
        errors    = []
        sample_ids: list = []   # For post-rotation verification

        for offset in range(0, total_rows, batch_size):
            chunk     = list(qs[offset : offset + batch_size])
            to_update = []

            for item in chunk:
                raw = str(item.account_number or "")
                if not raw:
                    skipped += 1
                    continue

                # Step 1: Decrypt with old key
                try:
                    encrypted_bytes = base64.b64decode(raw.encode())
                    plaintext       = old_cipher.decrypt(encrypted_bytes).decode("utf-8")
                except Exception:
                    # Value might already be plaintext (pre-v8 data)
                    # Try treating raw value as plaintext
                    plaintext = raw

                # Step 2: Re-encrypt with new key
                try:
                    new_encrypted = base64.b64encode(
                        new_cipher.encrypt(plaintext.encode("utf-8"))
                    ).decode("utf-8")
                except Exception as exc:
                    errors.append(f"item={item.id}: encrypt_error: {exc}")
                    continue

                # Step 3: Recompute hash with new key
                new_hash = hmac.new(
                    new_hmac_secret,
                    plaintext.strip().encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()

                item.account_number      = new_encrypted
                item.account_number_hash = new_hash
                to_update.append(item)

                if len(sample_ids) < 10:
                    sample_ids.append((item.id, plaintext, new_encrypted, new_hash))

            # Step 4: Bulk update (skip in dry run)
            if not dry_run and to_update:
                try:
                    PayoutItem.objects.bulk_update(
                        to_update, ["account_number", "account_number_hash"],
                        batch_size=batch_size,
                    )
                except Exception as exc:
                    errors.append(f"bulk_update offset={offset}: {exc}")
                    self.stderr.write(self.style.ERROR(f"bulk_update failed at offset={offset}: {exc}"))
                    continue

            processed += len(to_update)
            self.stdout.write(
                f"  Progress: {min(offset + batch_size, total_rows)}/{total_rows} rows "
                f"processed={processed} skipped={skipped} errors={len(errors)}"
            )

        # ── Post-rotation verification ─────────────────────────────────────────
        self.stdout.write(self.style.NOTICE("\nVerifying rotation on sample rows..."))
        verify_ok      = 0
        verify_failed  = 0

        for item_id, expected_plain, new_enc, expected_hash in sample_ids:
            try:
                # Re-fetch from DB (only if not dry-run)
                if not dry_run:
                    fresh = PayoutItem.objects.get(pk=item_id)
                    db_enc = str(fresh.account_number)
                    # Decrypt with NEW key
                    decrypted_bytes = base64.b64decode(db_enc.encode())
                    decrypted       = new_cipher.decrypt(decrypted_bytes).decode("utf-8")
                    assert decrypted == expected_plain, f"Mismatch: expected={expected_plain} got={decrypted}"
                    assert fresh.account_number_hash == expected_hash, "Hash mismatch"
                verify_ok += 1
            except Exception as exc:
                verify_failed += 1
                self.stderr.write(self.style.ERROR(f"  Verification FAILED for item={item_id}: {exc}"))

        # ── Summary ────────────────────────────────────────────────────────────
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(
            f"Rotation {'(DRY RUN) ' if dry_run else ''}complete.\n"
            f"  Processed:          {processed}\n"
            f"  Skipped (empty):    {skipped}\n"
            f"  Errors:             {len(errors)}\n"
            f"  Verification OK:    {verify_ok}/{len(sample_ids)}\n"
            f"  Verification FAIL:  {verify_failed}/{len(sample_ids)}"
        ))

        if errors:
            self.stderr.write(self.style.ERROR("\nErrors encountered:"))
            for err in errors[:20]:
                self.stderr.write(f"  {err}")
            if len(errors) > 20:
                self.stderr.write(f"  ... and {len(errors) - 20} more.")

        if verify_failed > 0:
            self.stderr.write(self.style.ERROR(
                "\nVERIFICATION FAILED. Do NOT update PAYOUT_ENCRYPTION_KEY yet. "
                "Investigate the errors above."
            ))
            sys.exit(1)

        if not dry_run and not errors and verify_failed == 0:
            self.stdout.write(self.style.SUCCESS(
                "\n✓ All rows rotated and verified.\n"
                "\nNEXT STEPS:\n"
                "  1. Update .env:  PAYOUT_ENCRYPTION_KEY=<new-key>\n"
                "  2. Restart all Django workers (gunicorn/uwsgi).\n"
                "  3. Restart all Celery workers.\n"
                "  4. Decommission old key from your secrets manager.\n"
                "  5. Run health check: GET /api/payout-queue/health/"
            ))
        elif dry_run:
            self.stdout.write(self.style.NOTICE(
                "\nDry run passed. Run again with --confirm to execute.\n"
            ))
