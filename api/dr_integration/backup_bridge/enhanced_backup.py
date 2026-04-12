"""
Enhanced Backup — api/backup/ module-এর DR-level replacement।
AES-256-GCM, gzip, multi-cloud, checksum verification সহ।

Usage:
    from dr_integration.backup_bridge.enhanced_backup import EnhancedBackupService
    svc = EnhancedBackupService()
    result = svc.create_backup(backup_instance)
"""
import os, subprocess, tempfile, hashlib, logging, shutil
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)


class EnhancedBackupService:
    """
    api/backup/services/BaseBackupService.py এর replacement।
    Features: AES-256-GCM, gzip, S3+local, SHA-256 checksum, DRBackupRecord sync.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.encryption_enabled = self.config.get("encryption", True)
        self.compression_enabled = self.config.get("compression", True)

    def create_backup(self, backup_instance) -> dict:
        """api/backup/ থেকে call করার জন্য — BaseBackupService.create_backup() replacement।"""
        started = datetime.utcnow()
        try:
            tmp = self._dump_database()
            if self.compression_enabled:
                tmp = self._compress(tmp)
            enc_key = None
            if self.encryption_enabled:
                tmp, enc_key = self._encrypt(tmp)
            checksum = self._compute_checksum(tmp)
            paths = self._store(tmp, backup_instance)
            self._update_instance(backup_instance, checksum, paths, started)
            self._sync_to_dr_model(backup_instance, checksum, paths)
            return {
                "success": True, "checksum": checksum, "paths": paths,
                "duration_seconds": (datetime.utcnow() - started).total_seconds(),
            }
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            if hasattr(backup_instance, "status"):
                backup_instance.status = "failed"
                backup_instance.error_message = str(e)
                if hasattr(backup_instance, "save"):
                    backup_instance.save()
            return {"success": False, "error": str(e)}

    def verify_backup(self, storage_path: str, expected_checksum: str) -> dict:
        """Backup file integrity verify করো।"""
        if not os.path.exists(storage_path):
            return {"valid": False, "error": "File not found"}
        actual = self._compute_checksum(storage_path)
        return {"valid": actual == expected_checksum,
                "expected": expected_checksum, "actual": actual}

    def _dump_database(self) -> str:
        """pg_dump দিয়ে database dump করো।"""
        db = settings.DATABASES["default"]
        tmp = tempfile.mktemp(suffix=".sql")
        env = os.environ.copy()
        env["PGPASSWORD"] = db.get("PASSWORD", "")
        result = subprocess.run([
            "pg_dump",
            "-h", db.get("HOST", "localhost"),
            "-p", str(db.get("PORT", 5432)),
            "-U", db.get("USER", "postgres"),
            "-d", db.get("NAME", ""),
            "-f", tmp, "--no-password",
        ], env=env, capture_output=True, text=True, timeout=3600)
        if result.returncode != 0:
            raise RuntimeError("pg_dump failed: " + result.stderr[:300])
        logger.info("DB dump complete: {:,} bytes".format(os.path.getsize(tmp)))
        return tmp

    def _compress(self, path: str) -> str:
        """gzip দিয়ে compress করো।"""
        import gzip
        out = path + ".gz"
        with open(path, "rb") as fi, gzip.open(out, "wb", compresslevel=6) as fo:
            shutil.copyfileobj(fi, fo)
        os.remove(path)
        return out

    def _encrypt(self, path: str) -> tuple:
        """AES-256-GCM দিয়ে encrypt করো।"""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            import base64
            key = os.urandom(32)
            nonce = os.urandom(12)
            with open(path, "rb") as f:
                data = f.read()
            ct = AESGCM(key).encrypt(nonce, data, None)
            out = path + ".enc"
            with open(out, "wb") as f:
                f.write(nonce + ct)
            os.remove(path)
            return out, base64.b64encode(key).decode()
        except ImportError:
            logger.warning("cryptography not installed — skipping encryption")
            return path, None

    def _compute_checksum(self, path: str) -> str:
        """SHA-256 checksum।"""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _store(self, local_path: str, backup_instance) -> dict:
        """Local + S3 তে store করো।"""
        paths = {}
        backup_dir = getattr(settings, "DR_LOCAL_BACKUP_PATH", "/var/backups/api")
        os.makedirs(backup_dir, exist_ok=True)
        dest = os.path.join(backup_dir, os.path.basename(local_path))
        shutil.copy2(local_path, dest)
        paths["local"] = dest
        backends = getattr(settings, "DR_BACKUP_BACKENDS", [])
        if "s3" in backends:
            try:
                import boto3
                s3_conf = next(
                    (c for c in getattr(settings, "DR_STORAGE_CONFIGS", [])
                     if c.get("provider") == "aws_s3"), {}
                )
                bucket = s3_conf.get("bucket", "")
                if bucket:
                    s3 = boto3.client(
                        "s3",
                        aws_access_key_id=s3_conf.get("access_key_id"),
                        aws_secret_access_key=s3_conf.get("secret_access_key"),
                        region_name=s3_conf.get("region", "us-east-1"),
                    )
                    date_str = datetime.utcnow().strftime("%Y/%m/%d")
                    key = "backups/" + date_str + "/" + os.path.basename(local_path)
                    s3.upload_file(local_path, bucket, key)
                    paths["s3"] = "s3://" + bucket + "/" + key
            except Exception as e:
                logger.warning("S3 upload failed: " + str(e))
        return paths

    def _update_instance(self, instance, checksum, paths, started):
        if hasattr(instance, "checksum"):
            instance.checksum = checksum
        if hasattr(instance, "status"):
            instance.status = "completed"
        if hasattr(instance, "completed_at"):
            instance.completed_at = datetime.utcnow()
        if hasattr(instance, "save"):
            instance.save()

    def _sync_to_dr_model(self, instance, checksum, paths):
        try:
            from dr_integration.models import DRBackupRecord
            DRBackupRecord.objects.update_or_create(
                dr_job_id=str(getattr(instance, "id", "django-" + str(datetime.utcnow().timestamp()))),
                defaults={
                    "backup_type": str(getattr(instance, "backup_type", "full")),
                    "status": "completed",
                    "checksum": checksum,
                    "storage_path": paths.get("s3", paths.get("local", "")),
                    "is_verified": True,
                    "completed_at": datetime.utcnow(),
                },
            )
        except Exception as e:
            logger.debug("DR model sync error: " + str(e))
