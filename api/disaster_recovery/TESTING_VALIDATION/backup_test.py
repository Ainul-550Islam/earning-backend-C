"""
Backup Tests — Comprehensive pytest test suite for backup operations.
"""
import pytest
import os
import hashlib
import tempfile
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch, Mock


class TestBackupExecutor:
    """Tests for the backup executor."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            "target_database": "test_db",
            "database_url": "postgresql://localhost/test_db",
            "source_path": self.temp_dir,
        }

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_backup_creates_file(self):
        from ..BACKUP_MANAGEMENT.backup_executor import BackupExecutor
        from ..enums import BackupType
        job_id = str(uuid.uuid4())
        executor = BackupExecutor(job_id, BackupType.FULL, self.config)
        # Create test source file
        test_file = os.path.join(self.temp_dir, "test_data.txt")
        with open(test_file, "w") as f:
            f.write("test backup data " * 1000)
        result = executor._backup_filesystem(self.temp_dir, os.path.join(self.temp_dir, "backup.tar.gz"))
        assert "local_path" in result
        assert result["size_bytes"] > 0
        executor.cleanup()

    def test_checksum_computation(self):
        from ..BACKUP_MANAGEMENT.backup_executor import BackupExecutor
        from ..enums import BackupType
        test_file = os.path.join(self.temp_dir, "checksum_test.bin")
        with open(test_file, "wb") as f:
            f.write(os.urandom(1024))
        checksum = BackupExecutor._compute_checksum(test_file)
        assert len(checksum) == 64  # SHA256 hex
        # Same file = same checksum
        checksum2 = BackupExecutor._compute_checksum(test_file)
        assert checksum == checksum2


class TestBackupCompressor:
    """Tests for backup compression."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_gzip_compress_and_decompress(self):
        from ..BACKUP_MANAGEMENT.backup_compressor import BackupCompressor
        # Create test file
        src = os.path.join(self.temp_dir, "source.txt")
        with open(src, "w") as f:
            f.write("compress me! " * 10000)
        original_size = os.path.getsize(src)
        compressor = BackupCompressor(algorithm="gzip", level=6)
        compressed_path = src + ".gz"
        result = compressor.compress(src, compressed_path)
        assert result["original_size_bytes"] == original_size
        assert result["compressed_size_bytes"] < original_size
        assert result["compression_ratio"] < 1.0
        assert os.path.exists(compressed_path)
        # Decompress and verify content
        decompressed = os.path.join(self.temp_dir, "decompressed.txt")
        compressor.decompress(compressed_path, decompressed)
        with open(src) as f1, open(decompressed) as f2:
            assert f1.read() == f2.read()

    def test_invalid_algorithm_raises(self):
        from ..BACKUP_MANAGEMENT.backup_compressor import BackupCompressor
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            BackupCompressor(algorithm="invalid_algo")

    def test_compression_ratio_reasonable(self):
        from ..BACKUP_MANAGEMENT.backup_compressor import BackupCompressor
        src = os.path.join(self.temp_dir, "compressible.txt")
        with open(src, "w") as f:
            f.write("AAAA" * 50000)  # Highly compressible
        compressor = BackupCompressor("gzip")
        result = compressor.compress(src)
        assert result["compression_ratio"] < 0.1  # Should compress >90%
        if os.path.exists(result["output_path"]):
            os.remove(result["output_path"])


class TestBackupEncryptor:
    """Tests for backup encryption."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.master_key = "test-master-key-for-testing-only"

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_encrypt_decrypt_roundtrip(self):
        from ..BACKUP_MANAGEMENT.backup_encryptor import BackupEncryptor
        encryptor = BackupEncryptor(self.master_key)
        original_data = b"sensitive backup data " * 100
        src = os.path.join(self.temp_dir, "plaintext.dat")
        enc = os.path.join(self.temp_dir, "encrypted.dat.enc")
        dec = os.path.join(self.temp_dir, "decrypted.dat")
        with open(src, "wb") as f:
            f.write(original_data)
        encryptor.encrypt_file(src, enc)
        assert os.path.exists(enc)
        assert os.path.getsize(enc) > len(original_data)  # Encrypted is larger
        encryptor.decrypt_file(enc, dec)
        with open(dec, "rb") as f:
            decrypted_data = f.read()
        assert decrypted_data == original_data

    def test_is_encrypted_detection(self):
        from ..BACKUP_MANAGEMENT.backup_encryptor import BackupEncryptor
        encryptor = BackupEncryptor(self.master_key)
        plain = os.path.join(self.temp_dir, "plain.txt")
        enc = os.path.join(self.temp_dir, "enc.enc")
        with open(plain, "w") as f:
            f.write("not encrypted")
        encryptor.encrypt_file(plain, enc)
        assert encryptor.is_encrypted(enc) is True
        assert encryptor.is_encrypted(plain) is False

    def test_wrong_key_fails(self):
        from ..BACKUP_MANAGEMENT.backup_encryptor import BackupEncryptor
        encryptor = BackupEncryptor(self.master_key)
        src = os.path.join(self.temp_dir, "data.bin")
        enc = os.path.join(self.temp_dir, "data.enc")
        dec = os.path.join(self.temp_dir, "data_dec.bin")
        with open(src, "wb") as f:
            f.write(b"secret data")
        encryptor.encrypt_file(src, enc)
        wrong_encryptor = BackupEncryptor("wrong-key-entirely-different")
        with pytest.raises(Exception):
            wrong_encryptor.decrypt_file(enc, dec)


class TestBackupRetention:
    """Tests for GFS retention policy."""

    def test_gfs_retention_keeps_recent(self):
        from ..BACKUP_MANAGEMENT.backup_retention import BackupRetentionManager
        mgr = BackupRetentionManager(daily_count=7, weekly_count=4, monthly_count=12)
        from datetime import timedelta
        backups = [
            MagicMock(id=str(i), created_at=datetime.utcnow() - timedelta(days=i))
            for i in range(100)
        ]
        to_delete = mgr.get_backups_to_delete(backups)
        # Recent backups should be kept
        recent_ids = {str(i) for i in range(7)}
        delete_ids = {b.id for b in to_delete}
        assert not recent_ids.intersection(delete_ids), "Recent backups should NOT be deleted"

    def test_empty_list_returns_empty(self):
        from ..BACKUP_MANAGEMENT.backup_retention import BackupRetentionManager
        mgr = BackupRetentionManager()
        assert mgr.get_backups_to_delete([]) == []

    def test_summary_has_required_keys(self):
        from ..BACKUP_MANAGEMENT.backup_retention import BackupRetentionManager
        from datetime import timedelta
        mgr = BackupRetentionManager()
        backups = [
            MagicMock(id=str(i), created_at=datetime.utcnow() - timedelta(days=i))
            for i in range(20)
        ]
        summary = mgr.get_retention_summary(backups)
        assert "total_backups" in summary
        assert "to_delete" in summary
        assert "to_keep" in summary
        assert summary["total_backups"] == 20


class TestBackupVerifier:
    """Tests for backup integrity verification."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_valid_checksum_passes(self):
        from ..BACKUP_MANAGEMENT.backup_verifier import BackupVerifier
        verifier = BackupVerifier()
        test_file = os.path.join(self.temp_dir, "backup.dump")
        with open(test_file, "wb") as f:
            f.write(b"backup content " * 1000)
        checksum = hashlib.sha256(open(test_file, "rb").read()).hexdigest()
        result = verifier.verify(test_file, checksum)
        assert result["checksum_valid"] is True
        assert result["file_exists"] is True

    def test_wrong_checksum_fails(self):
        from ..BACKUP_MANAGEMENT.backup_verifier import BackupVerifier
        verifier = BackupVerifier()
        test_file = os.path.join(self.temp_dir, "backup.dump")
        with open(test_file, "wb") as f:
            f.write(b"backup content")
        result = verifier.verify(test_file, "wrong" * 16)
        assert result["checksum_valid"] is False
        assert len(result["errors"]) > 0

    def test_missing_file_returns_error(self):
        from ..BACKUP_MANAGEMENT.backup_verifier import BackupVerifier
        verifier = BackupVerifier()
        result = verifier.verify("/nonexistent/path/backup.dump", "abc123")
        assert result["file_exists"] is False
        assert len(result["errors"]) > 0
