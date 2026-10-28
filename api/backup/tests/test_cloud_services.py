"""
Test Cloud & Storage Backup Services
Covers: AzureBackupService, GCSBackupService, LocalBackupService,
        BackupNotificationService, BackupCompressionService, BackupEncryptionService
"""

import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock, mock_open, PropertyMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


def _make_storage_location(storage_type="s3", config=None):
    """Helper: build a mock storage location"""
    loc = MagicMock()
    loc.storage_type = storage_type
    loc.config = config or {}
    loc.name = f"Test {storage_type.upper()} Storage"
    return loc


def _make_backup():
    """Helper: build a mock backup object"""
    b = MagicMock()
    b.id = "bk-test-001"
    b.name = "test_backup_2026"
    b.size = 1024 * 1024  # 1 MB
    b.created_at = datetime.utcnow()
    return b


# ---------------------------------------------------------------------------
# Azure Backup Service Tests
# ---------------------------------------------------------------------------

class AzureBackupServiceInitTest(TestCase):

    def test_import_azure_service(self):
        from api.backup.services.AzureBackupService import AzureBackupService
        self.assertTrue(callable(AzureBackupService))

    def test_inherits_base_backup_service(self):
        from api.backup.services.AzureBackupService import AzureBackupService
        from api.backup.services.BaseBackupService import BaseBackupService
        self.assertTrue(issubclass(AzureBackupService, BaseBackupService))

    @patch("backup.services.AzureBackupService.BlobServiceClient")
    def test_init_with_connection_string(self, mock_blob_client):
        from api.backup.services.AzureBackupService import AzureBackupService
        mock_blob_client.from_connection_string.return_value = MagicMock()
        loc = _make_storage_location(
            "azure",
            {"connection_string": "DefaultEndpointsProtocol=https;...", "container_name": "backups"},
        )
        svc = AzureBackupService(loc)
        self.assertIsNotNone(svc)

    @patch("backup.services.AzureBackupService.BlobServiceClient")
    def test_init_with_account_credentials(self, mock_blob_client):
        from api.backup.services.AzureBackupService import AzureBackupService
        mock_blob_client.return_value = MagicMock()
        loc = _make_storage_location(
            "azure",
            {
                "account_name": "myaccount",
                "account_key": "base64key==",
                "container_name": "backups",
            },
        )
        svc = AzureBackupService(loc)
        self.assertIsNotNone(svc)

    @patch("backup.services.AzureBackupService.BlobServiceClient")
    def test_upload_backup_calls_blob_upload(self, mock_blob_client):
        from api.backup.services.AzureBackupService import AzureBackupService
        mock_container = MagicMock()
        mock_blob_client.from_connection_string.return_value = MagicMock(
            get_container_client=Mock(return_value=mock_container)
        )
        loc = _make_storage_location(
            "azure",
            {"connection_string": "conn_str", "container_name": "backups"},
        )
        svc = AzureBackupService(loc)
        svc.container_client = mock_container
        backup = _make_backup()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".sql") as f:
            f.write(b"backup data")
            tmp_path = f.name
        try:
            mock_container.upload_blob = Mock(return_value=MagicMock())
            with open(tmp_path, "rb") as fp:
                svc.upload_file(fp, f"backup_{backup.id}.sql")
            mock_container.upload_blob.assert_called_once()
        finally:
            os.unlink(tmp_path)

    @patch("backup.services.AzureBackupService.BlobServiceClient")
    def test_list_backups_returns_list(self, mock_blob_client):
        from api.backup.services.AzureBackupService import AzureBackupService
        mock_container = MagicMock()
        mock_blob1 = MagicMock(name="backup_001.sql", size=1024)
        mock_blob2 = MagicMock(name="backup_002.sql", size=2048)
        mock_container.list_blobs.return_value = [mock_blob1, mock_blob2]
        loc = _make_storage_location(
            "azure",
            {"connection_string": "conn_str", "container_name": "backups"},
        )
        svc = AzureBackupService(loc)
        svc.container_client = mock_container
        result = svc.list_backups()
        self.assertIsInstance(result, list)

    @patch("backup.services.AzureBackupService.BlobServiceClient")
    def test_delete_backup_calls_delete_blob(self, mock_blob_client):
        from api.backup.services.AzureBackupService import AzureBackupService
        mock_container = MagicMock()
        loc = _make_storage_location(
            "azure",
            {"connection_string": "conn_str", "container_name": "backups"},
        )
        svc = AzureBackupService(loc)
        svc.container_client = mock_container
        svc.delete_backup("backup_001.sql")
        mock_container.delete_blob.assert_called_once_with("backup_001.sql")


# ---------------------------------------------------------------------------
# GCS Backup Service Tests
# ---------------------------------------------------------------------------

class GCSBackupServiceInitTest(TestCase):

    def test_import_gcs_service(self):
        from api.backup.services.GCSBackupService import GCSBackupService
        self.assertTrue(callable(GCSBackupService))

    def test_inherits_base_backup_service(self):
        from api.backup.services.GCSBackupService import GCSBackupService
        from api.backup.services.BaseBackupService import BaseBackupService
        self.assertTrue(issubclass(GCSBackupService, BaseBackupService))

    @patch("backup.services.GCSBackupService.storage")
    def test_init_with_service_account(self, mock_storage):
        from api.backup.services.GCSBackupService import GCSBackupService
        mock_client = MagicMock()
        mock_storage.Client.return_value = mock_client
        mock_client.bucket.return_value = MagicMock()
        loc = _make_storage_location(
            "gcs",
            {"project_id": "my-project", "bucket_name": "my-backup-bucket"},
        )
        svc = GCSBackupService(loc)
        self.assertIsNotNone(svc)

    @patch("backup.services.GCSBackupService.storage")
    def test_upload_to_gcs_bucket(self, mock_storage):
        from api.backup.services.GCSBackupService import GCSBackupService
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        loc = _make_storage_location(
            "gcs", {"project_id": "proj", "bucket_name": "bucket"}
        )
        svc = GCSBackupService(loc)
        svc.client = mock_client
        svc.bucket = mock_bucket
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"gcs backup")
            tmp = f.name
        try:
            with open(tmp, "rb") as fp:
                svc.upload_file(fp, "test_backup.sql")
            mock_bucket.blob.assert_called()
        finally:
            os.unlink(tmp)

    @patch("backup.services.GCSBackupService.storage")
    def test_list_blobs_returns_list(self, mock_storage):
        from api.backup.services.GCSBackupService import GCSBackupService
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_storage.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.list_blobs.return_value = [MagicMock(), MagicMock()]
        loc = _make_storage_location(
            "gcs", {"project_id": "proj", "bucket_name": "bucket"}
        )
        svc = GCSBackupService(loc)
        svc.client = mock_client
        svc.bucket = mock_bucket
        result = svc.list_backups()
        self.assertIsInstance(result, list)

    @patch("backup.services.GCSBackupService.storage")
    def test_delete_blob(self, mock_storage):
        from api.backup.services.GCSBackupService import GCSBackupService
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        loc = _make_storage_location(
            "gcs", {"project_id": "proj", "bucket_name": "bucket"}
        )
        svc = GCSBackupService(loc)
        svc.client = mock_client
        svc.bucket = mock_bucket
        svc.delete_backup("old_backup.sql")
        mock_blob.delete.assert_called_once()


# ---------------------------------------------------------------------------
# Local Backup Service Tests
# ---------------------------------------------------------------------------

class LocalBackupServiceTest(TestCase):

    def test_import_local_service(self):
        from api.backup.services.LocalBackupService import LocalBackupService
        self.assertTrue(callable(LocalBackupService))

    def test_inherits_base_backup_service(self):
        from api.backup.services.LocalBackupService import LocalBackupService
        from api.backup.services.BaseBackupService import BaseBackupService
        self.assertTrue(issubclass(LocalBackupService, BaseBackupService))

    def test_init_with_local_path(self):
        from api.backup.services.LocalBackupService import LocalBackupService
        with tempfile.TemporaryDirectory() as tmpdir:
            loc = _make_storage_location("local", {"backup_path": tmpdir})
            svc = LocalBackupService(loc)
            self.assertIsNotNone(svc)

    def test_upload_saves_file_locally(self):
        from api.backup.services.LocalBackupService import LocalBackupService
        with tempfile.TemporaryDirectory() as tmpdir:
            loc = _make_storage_location("local", {"backup_path": tmpdir})
            svc = LocalBackupService(loc)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".sql") as src:
                src.write(b"local backup content")
                src_path = src.name
            try:
                with open(src_path, "rb") as fp:
                    svc.upload_file(fp, "local_backup.sql")
                dest = os.path.join(tmpdir, "local_backup.sql")
                self.assertTrue(os.path.exists(dest))
            finally:
                os.unlink(src_path)

    def test_list_local_backups(self):
        from api.backup.services.LocalBackupService import LocalBackupService
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                open(os.path.join(tmpdir, f"backup_{i}.sql"), "w").close()
            loc = _make_storage_location("local", {"backup_path": tmpdir})
            svc = LocalBackupService(loc)
            result = svc.list_backups()
            self.assertIsInstance(result, list)
            self.assertGreaterEqual(len(result), 3)

    def test_delete_local_backup(self):
        from api.backup.services.LocalBackupService import LocalBackupService
        with tempfile.TemporaryDirectory() as tmpdir:
            fname = "to_delete.sql"
            fpath = os.path.join(tmpdir, fname)
            open(fpath, "w").close()
            loc = _make_storage_location("local", {"backup_path": tmpdir})
            svc = LocalBackupService(loc)
            svc.delete_backup(fname)
            self.assertFalse(os.path.exists(fpath))


# ---------------------------------------------------------------------------
# Backup Notification Service Tests
# ---------------------------------------------------------------------------

class BackupNotificationServiceTest(TestCase):

    def test_import_notification_service(self):
        from api.backup.services.BackupNotificationService import BackupNotificationService
        self.assertTrue(callable(BackupNotificationService))

    @patch("backup.services.BackupNotificationService.send_mail", create=True)
    def test_send_email_notification(self, mock_send_mail):
        from api.backup.services.BackupNotificationService import BackupNotificationService
        svc = BackupNotificationService()
        svc.send_email(
            recipients=["admin@example.com"],
            subject="Backup Completed",
            body="Backup bk-001 completed successfully.",
        )
        mock_send_mail.assert_called_once()

    def test_notification_service_has_send_methods(self):
        from api.backup.services.BackupNotificationService import BackupNotificationService
        svc = BackupNotificationService()
        for method in ["send_email", "send_slack", "send_webhook"]:
            self.assertTrue(
                hasattr(svc, method),
                f"BackupNotificationService should have {method}()",
            )

    @patch("backup.services.BackupNotificationService.requests", create=True)
    def test_send_webhook_notification(self, mock_requests):
        from api.backup.services.BackupNotificationService import BackupNotificationService
        mock_requests.post.return_value = MagicMock(status_code=200)
        svc = BackupNotificationService()
        svc.send_webhook(
            url="https://hooks.example.com/notify",
            payload={"event": "backup_completed", "backup_id": "bk-001"},
        )
        mock_requests.post.assert_called_once()

    @patch("backup.services.BackupNotificationService.requests", create=True)
    def test_send_slack_notification(self, mock_requests):
        from api.backup.services.BackupNotificationService import BackupNotificationService
        mock_requests.post.return_value = MagicMock(status_code=200)
        svc = BackupNotificationService()
        svc.send_slack(
            webhook_url="https://hooks.slack.com/services/xxx",
            message="✅ Backup completed successfully",
        )
        mock_requests.post.assert_called_once()


# ---------------------------------------------------------------------------
# Backup Compression Service Tests
# ---------------------------------------------------------------------------

class BackupCompressionServiceTest(TestCase):

    def test_import_compression_service(self):
        from api.backup.services.BackupCompressionService import BackupCompressionService
        self.assertTrue(callable(BackupCompressionService))

    def test_compress_file(self):
        from api.backup.services.BackupCompressionService import BackupCompressionService
        svc = BackupCompressionService()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".sql") as f:
            f.write(b"SELECT * FROM backups; " * 1000)
            src = f.name
        out = src + ".gz"
        try:
            svc.compress(src, out)
            self.assertTrue(os.path.exists(out))
            self.assertLess(os.path.getsize(out), os.path.getsize(src))
        finally:
            os.unlink(src)
            if os.path.exists(out):
                os.unlink(out)

    def test_decompress_file(self):
        from api.backup.services.BackupCompressionService import BackupCompressionService
        import gzip
        svc = BackupCompressionService()
        original = b"backup data content " * 500
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gz") as f:
            with gzip.open(f.name, "wb") as gz:
                gz.write(original)
            gz_path = f.name
        out_path = gz_path.replace(".gz", "_restored.sql")
        try:
            svc.decompress(gz_path, out_path)
            self.assertTrue(os.path.exists(out_path))
            with open(out_path, "rb") as fp:
                self.assertEqual(fp.read(), original)
        finally:
            os.unlink(gz_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_compression_ratio(self):
        from api.backup.services.BackupCompressionService import BackupCompressionService
        svc = BackupCompressionService()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".sql") as f:
            f.write(b"A" * 10_000)
            src = f.name
        out = src + ".gz"
        try:
            svc.compress(src, out)
            ratio = svc.get_compression_ratio(src, out)
            self.assertGreater(ratio, 1.0)
        finally:
            os.unlink(src)
            if os.path.exists(out):
                os.unlink(out)


# ---------------------------------------------------------------------------
# Backup Encryption Service Tests
# ---------------------------------------------------------------------------

class BackupEncryptionServiceTest(TestCase):

    def test_import_encryption_service(self):
        from api.backup.services.BackupEncryptionService import BackupEncryptionService
        self.assertTrue(callable(BackupEncryptionService))

    def test_encrypt_and_decrypt_roundtrip(self):
        from api.backup.services.BackupEncryptionService import BackupEncryptionService
        svc = BackupEncryptionService()
        plaintext = b"sensitive backup data " * 100
        encrypted = svc.encrypt(plaintext)
        self.assertNotEqual(encrypted, plaintext)
        decrypted = svc.decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)

    def test_encrypted_data_is_bytes(self):
        from api.backup.services.BackupEncryptionService import BackupEncryptionService
        svc = BackupEncryptionService()
        result = svc.encrypt(b"test data")
        self.assertIsInstance(result, bytes)

    def test_encrypt_file(self):
        from api.backup.services.BackupEncryptionService import BackupEncryptionService
        svc = BackupEncryptionService()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".sql") as f:
            f.write(b"plaintext backup content")
            src = f.name
        enc_out = src + ".enc"
        try:
            svc.encrypt_file(src, enc_out)
            self.assertTrue(os.path.exists(enc_out))
            with open(enc_out, "rb") as fp:
                enc_data = fp.read()
            with open(src, "rb") as fp:
                orig_data = fp.read()
            self.assertNotEqual(enc_data, orig_data)
        finally:
            os.unlink(src)
            if os.path.exists(enc_out):
                os.unlink(enc_out)

    def test_decrypt_file(self):
        from api.backup.services.BackupEncryptionService import BackupEncryptionService
        svc = BackupEncryptionService()
        plaintext = b"important backup data"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".sql") as f:
            f.write(plaintext)
            src = f.name
        enc = src + ".enc"
        dec = src + ".dec"
        try:
            svc.encrypt_file(src, enc)
            svc.decrypt_file(enc, dec)
            with open(dec, "rb") as fp:
                self.assertEqual(fp.read(), plaintext)
        finally:
            for p in [src, enc, dec]:
                if os.path.exists(p):
                    os.unlink(p)

    def test_different_plaintexts_give_different_ciphertexts(self):
        from api.backup.services.BackupEncryptionService import BackupEncryptionService
        svc = BackupEncryptionService()
        e1 = svc.encrypt(b"data one")
        e2 = svc.encrypt(b"data two")
        self.assertNotEqual(e1, e2)
