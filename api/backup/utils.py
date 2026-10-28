"""
🛠️ Backup Utilities Module

This module provides comprehensive utility functions and helper classes for the backup system.
It includes file operations, data processing, format conversions, validation helpers,
and other common utilities used throughout the backup module.

Features:
- File and directory utilities
- Data format conversions
- Hash and checksum utilities
- Size and time formatting
- Configuration helpers
- Validation utilities
- Performance monitoring helpers
- Logging utilities
"""
from django.core.exceptions import ImproperlyConfigured

import os
import hashlib
import json
import time
import datetime
import logging
import mimetypes
import tempfile
import shutil
import gzip
import zipfile
import tarfile
from typing import Any, Dict, List, Optional, Union, Tuple, BinaryIO, TextIO
from pathlib import Path
from decimal import Decimal
from dataclasses import dataclass, field
from enum import Enum
import uuid
import re
from contextlib import contextmanager
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


class FileSizeUnit(Enum):
    """Enumeration of file size units."""
    BYTES = "B"
    KILOBYTES = "KB"
    MEGABYTES = "MB"
    GIGABYTES = "GB"
    TERABYTES = "TB"
    PETABYTES = "PB"


class CompressionFormat(Enum):
    """Enumeration of compression formats."""
    ZIP = "zip"
    GZIP = "gzip"
    TAR = "tar"
    TAR_GZ = "tar.gz"
    TAR_BZ2 = "tar.bz2"
    TAR_XZ = "tar.xz"
    LZMA = "lzma"
    ZSTD = "zstd"


class HashAlgorithm(Enum):
    """Enumeration of hash algorithms."""
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA512 = "sha512"
    BLAKE2B = "blake2b"
    BLAKE2S = "blake2s"


@dataclass
class FileMetadata:
    """Metadata information about a file."""
    filename: str
    filepath: str
    size_bytes: int
    size_human: str
    mime_type: str
    encoding: Optional[str] = None
    created_at: Optional[datetime.datetime] = None
    modified_at: Optional[datetime.datetime] = None
    checksums: Dict[str, str] = field(default_factory=dict)
    is_compressed: bool = False
    compression_format: Optional[str] = None
    is_encrypted: bool = False
    encryption_algorithm: Optional[str] = None


@dataclass
class BackupOperationResult:
    """Result of a backup operation."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[Exception] = None
    duration_seconds: Optional[float] = None
    files_processed: int = 0
    bytes_processed: int = 0


class FileUtils:
    """Utility class for file operations."""
    
    @staticmethod
    def ensure_directory_exists(directory_path: Union[str, Path]) -> Path:
        """Ensure a directory exists, creating it if necessary."""
        path = Path(directory_path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @staticmethod
    def get_file_metadata(file_path: Union[str, Path], include_checksums: bool = False, 
                         checksum_algorithms: Optional[List[HashAlgorithm]] = None) -> FileMetadata:
        """Get comprehensive metadata about a file."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        stat = path.stat()
        
        # Get MIME type
        mime_type, encoding = mimetypes.guess_type(str(path))
        mime_type = mime_type or 'application/octet-stream'
        
        # Get checksums
        checksums = {}
        if include_checksums:
            checksum_algorithms = checksum_algorithms or [HashAlgorithm.SHA256]
            for algorithm in checksum_algorithms:
                checksums[algorithm.value] = FileUtils.calculate_checksum(file_path, algorithm)
        
        # Check if compressed
        is_compressed, compression_format = FileUtils.detect_compression(file_path)
        
        return FileMetadata(
            filename=path.name,
            filepath=str(path.absolute()),
            size_bytes=stat.st_size,
            size_human=FileUtils.format_file_size(stat.st_size),
            mime_type=mime_type,
            encoding=encoding,
            created_at=datetime.datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.datetime.fromtimestamp(stat.st_mtime),
            checksums=checksums,
            is_compressed=is_compressed,
            compression_format=compression_format,
            is_encrypted=FileUtils.is_encrypted_file(file_path),
        )
    
    @staticmethod
    def calculate_checksum(file_path: Union[str, Path], algorithm: HashAlgorithm = HashAlgorithm.SHA256,
                          chunk_size: int = 8192) -> str:
        """Calculate checksum of a file."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        hash_func = getattr(hashlib, algorithm.value)()
        
        with open(path, 'rb') as f:
            while chunk := f.read(chunk_size):
                hash_func.update(chunk)
        
        return hash_func.hexdigest()
    
    @staticmethod
    def verify_checksum(file_path: Union[str, Path], expected_checksum: str,
                       algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> bool:
        """Verify file checksum matches expected value."""
        actual_checksum = FileUtils.calculate_checksum(file_path, algorithm)
        return actual_checksum.lower() == expected_checksum.lower()
    
    @staticmethod
    def format_file_size(size_bytes: int, precision: int = 2) -> str:
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"
        
        units = [FileSizeUnit.BYTES, FileSizeUnit.KILOBYTES, FileSizeUnit.MEGABYTES,
                FileSizeUnit.GIGABYTES, FileSizeUnit.TERABYTES, FileSizeUnit.PETABYTES]
        
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024.0 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1
        
        return f"{size:.{precision}f} {units[unit_index].value}"
    
    @staticmethod
    def parse_file_size(size_str: str) -> int:
        """Parse human-readable file size string to bytes."""
        size_str = size_str.strip().upper()
        
        # Match pattern like "1.5 GB" or "1024 MB"
        match = re.match(r'^([\d.]+)\s*([KMGT]?B)?$', size_str)
        if not match:
            raise ValueError(f"Invalid file size format: {size_str}")
        
        size = float(match.group(1))
        unit = match.group(2) or 'B'
        
        multipliers = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 ** 2,
            'GB': 1024 ** 3,
            'TB': 1024 ** 4,
            'PB': 1024 ** 5,
        }
        
        if unit not in multipliers:
            raise ValueError(f"Unknown file size unit: {unit}")
        
        return int(size * multipliers[unit])
    
    @staticmethod
    def detect_compression(file_path: Union[str, Path]) -> Tuple[bool, Optional[str]]:
        """Detect if a file is compressed and return the compression format."""
        path = Path(file_path)
        filename = path.name.lower()
        
        compression_patterns = {
            CompressionFormat.ZIP: ['.zip'],
            CompressionFormat.GZIP: ['.gz', '.gzip'],
            CompressionFormat.TAR: ['.tar'],
            CompressionFormat.TAR_GZ: ['.tar.gz', '.tgz'],
            CompressionFormat.TAR_BZ2: ['.tar.bz2', '.tbz2'],
            CompressionFormat.TAR_XZ: ['.tar.xz', '.txz'],
            CompressionFormat.LZMA: ['.lzma', '.xz'],
            CompressionFormat.ZSTD: ['.zstd'],
        }
        
        for format_name, extensions in compression_patterns.items():
            if any(filename.endswith(ext) for ext in extensions):
                return True, format_name.value
        
        return False, None
    
    @staticmethod
    def is_encrypted_file(file_path: Union[str, Path]) -> bool:
        """Check if a file appears to be encrypted."""
        path = Path(file_path)
        
        # Check file extension
        encrypted_extensions = ['.enc', '.encrypted', '.aes', '.gpg']
        if path.suffix.lower() in encrypted_extensions:
            return True
        
        # Check file content (basic heuristic)
        try:
            with open(path, 'rb') as f:
                # Read first few bytes
                header = f.read(1024)
                
                # Check for common encryption headers
                # AES-256-GCM: Usually starts with random-looking data
                # This is a very basic check - real detection would be more complex
                entropy = FileUtils.calculate_entropy(header)
                
                # High entropy suggests encryption
                return entropy > 7.5
        except Exception:
            pass
        
        return False
    
    @staticmethod
    def calculate_entropy(data: bytes) -> float:
        """Calculate Shannon entropy of data."""
        if not data:
            return 0.0
        
        # Count byte frequencies
        byte_counts = {}
        for byte in data:
            byte_counts[byte] = byte_counts.get(byte, 0) + 1
        
        # Calculate entropy
        data_len = len(data)
        entropy = 0.0
        
        for count in byte_counts.values():
            probability = count / data_len
            entropy -= probability * (probability.bit_length() - 1)
        
        return entropy
    
    @staticmethod
    def safe_filename(filename: str) -> str:
        """Generate a safe filename by removing/replacing problematic characters."""
        # Remove or replace problematic characters
        safe_chars = re.sub(r'[<>:"/\\|?*]', '_', filename)
        safe_chars = re.sub(r'\s+', '_', safe_chars)
        safe_chars = safe_chars.strip('._')
        
        # Ensure it's not empty
        if not safe_chars:
            safe_chars = f"file_{int(time.time())}"
        
        # Limit length
        if len(safe_chars) > 255:
            name, ext = os.path.splitext(safe_chars)
            safe_chars = name[:255-len(ext)] + ext
        
        return safe_chars
    
    @staticmethod
    def create_temp_file(suffix: str = '', prefix: str = 'backup_', 
                        directory: Optional[str] = None) -> str:
        """Create a temporary file and return its path."""
        fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=directory)
        os.close(fd)  # Close the file descriptor
        return temp_path
    
    @staticmethod
    @contextmanager
    def temp_directory(prefix: str = 'backup_'):
        """Create a temporary directory and clean it up afterwards."""
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        try:
            yield temp_dir
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    @staticmethod
    def copy_file_with_progress(src: Union[str, Path], dst: Union[str, Path],
                              chunk_size: int = 8192, callback: Optional[callable] = None) -> int:
        """Copy file with progress tracking."""
        src_path = Path(src)
        dst_path = Path(dst)
        
        if not src_path.exists():
            raise FileNotFoundError(f"Source file not found: {src}")
        
        # Ensure destination directory exists
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        
        total_size = src_path.stat().st_size
        bytes_copied = 0
        
        with open(src_path, 'rb') as src_file, open(dst_path, 'wb') as dst_file:
            while chunk := src_file.read(chunk_size):
                dst_file.write(chunk)
                bytes_copied += len(chunk)
                
                if callback:
                    callback(bytes_copied, total_size)
        
        return bytes_copied


class CompressionUtils:
    """Utility class for compression operations."""
    
    @staticmethod
    def compress_file(file_path: Union[str, Path], format: CompressionFormat = CompressionFormat.ZIP,
                      output_path: Optional[Union[str, Path]] = None, 
                      compression_level: int = 6) -> str:
        """Compress a file using the specified format."""
        src_path = Path(file_path)
        
        if not src_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if output_path is None:
            output_path = src_path.with_suffix(f".{format.value}")
        
        dst_path = Path(output_path)
        
        if format == CompressionFormat.ZIP:
            with zipfile.ZipFile(dst_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=compression_level) as zipf:
                zipf.write(src_path, src_path.name)
        
        elif format == CompressionFormat.GZIP:
            with open(src_path, 'rb') as src_file:
                with gzip.open(dst_path, 'wb', compresslevel=compression_level) as dst_file:
                    shutil.copyfileobj(src_file, dst_file)
        
        elif format == CompressionFormat.TAR:
            with tarfile.open(dst_path, 'w') as tarf:
                tarf.add(src_path, arcname=src_path.name)
        
        elif format == CompressionFormat.TAR_GZ:
            with tarfile.open(dst_path, 'w:gz', compresslevel=compression_level) as tarf:
                tarf.add(src_path, arcname=src_path.name)
        
        else:
            raise ValueError(f"Unsupported compression format: {format}")
        
        return str(dst_path)
    
    @staticmethod
    def decompress_file(file_path: Union[str, Path], output_path: Optional[Union[str, Path]] = None) -> List[str]:
        """Decompress a file and return list of extracted files."""
        src_path = Path(file_path)
        
        if not src_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if output_path is None:
            output_path = src_path.parent
        else:
            output_path = Path(output_path)
        
        output_path.mkdir(parents=True, exist_ok=True)
        extracted_files = []
        
        # Detect compression format
        is_compressed, format_name = FileUtils.detect_compression(src_path)
        
        if not is_compressed:
            raise ValueError(f"File is not compressed: {file_path}")
        
        if format_name == 'zip':
            with zipfile.ZipFile(src_path, 'r') as zipf:
                for member in zipf.namelist():
                    zipf.extract(member, output_path)
                    extracted_files.append(str(output_path / member))
        
        elif format_name in ['gzip', 'gz']:
            output_file = output_path / src_path.stem
            with gzip.open(src_path, 'rb') as src_file:
                with open(output_file, 'wb') as dst_file:
                    shutil.copyfileobj(src_file, dst_file)
            extracted_files.append(str(output_file))
        
        elif format_name in ['tar', 'tar.gz', 'tgz', 'tar.bz2', 'tbz2', 'tar.xz', 'txz']:
            with tarfile.open(src_path, 'r:*') as tarf:
                members = tarf.getmembers()
                for member in members:
                    tarf.extract(member, output_path)
                    extracted_files.append(str(output_path / member.name))
        
        else:
            raise ValueError(f"Unsupported compression format: {format_name}")
        
        return extracted_files
    
    @staticmethod
    def get_compression_ratio(original_path: Union[str, Path], compressed_path: Union[str, Path]) -> float:
        """Calculate compression ratio."""
        original_size = Path(original_path).stat().st_size
        compressed_size = Path(compressed_path).stat().st_size
        
        if original_size == 0:
            return 0.0
        
        return (1 - compressed_size / original_size) * 100


class TimeUtils:
    """Utility class for time and date operations."""
    
    @staticmethod
    def format_duration(seconds: float, precision: int = 2) -> str:
        """Format duration in human-readable format."""
        if seconds < 1:
            return f"{seconds * 1000:.{precision}f} ms"
        elif seconds < 60:
            return f"{seconds:.{precision}f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.{precision}f} minutes"
        else:
            hours = seconds / 3600
            return f"{hours:.{precision}f} hours"
    
    @staticmethod
    def format_timestamp(timestamp: Union[datetime.datetime, float, int], 
                       format_string: str = "%Y-%m-%d %H:%M:%S") -> str:
        """Format timestamp to string."""
        if isinstance(timestamp, (float, int)):
            dt = datetime.datetime.fromtimestamp(timestamp)
        else:
            dt = timestamp
        
        return dt.strftime(format_string)
    
    @staticmethod
    def parse_duration(duration_str: str) -> float:
        """Parse duration string to seconds."""
        duration_str = duration_str.strip().lower()
        
        # Match patterns like "1h 30m", "45 minutes", "2.5 hours"
        patterns = [
            (r'(?:(\d+(?:\.\d+)?)\s*h)?\s*(?:(\d+(?:\.\d+)?)\s*m)?\s*(?:(\d+(?:\.\d+)?)\s*s)?', 
             lambda h, m, s: (float(h or 0) * 3600) + (float(m or 0) * 60) + float(s or 0)),
            (r'(\d+(?:\.\d+)?)\s*(hour|hours|minute|minutes|second|seconds)', 
             lambda amount, unit: float(amount) * {
                 'hour': 3600, 'hours': 3600,
                 'minute': 60, 'minutes': 60,
                 'second': 1, 'seconds': 1
             }[unit]),
        ]
        
        for pattern, converter in patterns:
            match = re.match(pattern, duration_str)
            if match:
                return converter(*match.groups())
        
        # Try to parse as plain number (seconds)
        try:
            return float(duration_str)
        except ValueError:
            raise ValueError(f"Invalid duration format: {duration_str}")
    
    @staticmethod
    def get_age_string(created_at: datetime.datetime, reference_time: Optional[datetime.datetime] = None) -> str:
        """Get human-readable age string."""
        if reference_time is None:
            reference_time = timezone.now()
        
        if isinstance(created_at, datetime.datetime) and timezone.is_aware(created_at):
            created_at = timezone.localtime(created_at)
        
        if isinstance(reference_time, datetime.datetime) and timezone.is_aware(reference_time):
            reference_time = timezone.localtime(reference_time)
        
        delta = reference_time - created_at
        seconds = delta.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 2592000:  # 30 days
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif seconds < 31536000:  # 1 year
            months = int(seconds / 2592000)
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = int(seconds / 31536000)
            return f"{years} year{'s' if years != 1 else ''} ago"


class ValidationUtils:
    """Utility class for validation operations."""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email address format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format."""
        pattern = r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?$'
        return re.match(pattern, url) is not None
    
    @staticmethod
    def validate_filename(filename: str) -> bool:
        """Validate filename for safety."""
        # Check for invalid characters
        invalid_chars = '<>:"/\\|?*'
        if any(char in filename for char in invalid_chars):
            return False
        
        # Check for reserved names (Windows)
        reserved_names = ['CON', 'PRN', 'AUX', 'NUL'] + [f'COM{i}' for i in range(1, 10)] + [f'LPT{i}' for i in range(1, 10)]
        if filename.upper() in reserved_names:
            return False
        
        # Check length
        if len(filename) > 255:
            return False
        
        return True
    
    @staticmethod
    def validate_cron_expression(cron_expr: str) -> bool:
        """Validate cron expression format."""
        # Basic cron validation (5 fields: minute hour day month weekday)
        pattern = r'^(\*|[0-5]?\d|\*/\d+) (\*|[01]?\d|2[0-3]|\*/\d+) (\*|[12]?\d|3[01]|\*/\d+) (\*|[01]?\d|\*/\d+) (\*|[0-6]|\*/\d+)$'
        return re.match(pattern, cron_expr) is not None
    
    @staticmethod
    def sanitize_string(text: str, max_length: Optional[int] = None, 
                       allow_html: bool = False) -> str:
        """Sanitize string for safe storage."""
        if not text:
            return ""
        
        # Remove control characters except newlines and tabs
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        if not allow_html:
            # Remove HTML tags
            sanitized = re.sub(r'<[^>]+>', '', sanitized)
        
        # Normalize whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        # Truncate if needed
        if max_length and len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip()
        
        return sanitized


class ConfigUtils:
    """Utility class for configuration operations."""
    
    @staticmethod
    def get_setting(key: str, default: Any = None, required: bool = False) -> Any:
        """Get Django setting with validation."""
        value = getattr(settings, key, default)
        
        if required and value is None:
            raise ImproperlyConfigured(f"Required setting '{key}' is not configured")
        
        return value
    
    @staticmethod
    def validate_backup_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate backup configuration."""
        errors = []
        
        # Check required fields
        required_fields = ['backup_type', 'storage_type']
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")
        
        # Validate backup type
        valid_backup_types = ['full', 'incremental', 'differential', 'delta']
        if 'backup_type' in config and config['backup_type'] not in valid_backup_types:
            errors.append(f"Invalid backup type: {config['backup_type']}")
        
        # Validate storage type
        valid_storage_types = ['local', 's3', 'azure', 'gcs']
        if 'storage_type' in config and config['storage_type'] not in valid_storage_types:
            errors.append(f"Invalid storage type: {config['storage_type']}")
        
        # Validate retention settings
        if 'retention_days' in config:
            try:
                retention_days = int(config['retention_days'])
                if retention_days < 1:
                    errors.append("retention_days must be at least 1")
            except (ValueError, TypeError):
                errors.append("retention_days must be a valid integer")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two configuration dictionaries."""
        merged = base_config.copy()
        merged.update(override_config)
        return merged
    
    @staticmethod
    def encrypt_sensitive_data(data: str, key: str) -> str:
        """Encrypt sensitive configuration data."""
        from cryptography.fernet import Fernet
        import base64
        
        # Ensure key is properly formatted
        if len(key) < 32:
            key = key.ljust(32, '0')[:32]
        
        fernet_key = base64.urlsafe_b64encode(key.encode())
        cipher = Fernet(fernet_key)
        encrypted_data = cipher.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted_data).decode()
    
    @staticmethod
    def decrypt_sensitive_data(encrypted_data: str, key: str) -> str:
        """Decrypt sensitive configuration data."""
        from cryptography.fernet import Fernet
        import base64
        
        # Ensure key is properly formatted
        if len(key) < 32:
            key = key.ljust(32, '0')[:32]
        
        fernet_key = base64.urlsafe_b64encode(key.encode())
        cipher = Fernet(fernet_key)
        
        try:
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = cipher.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt data: {e}")


class PerformanceUtils:
    """Utility class for performance monitoring."""
    
    @staticmethod
    @contextmanager
    def timer(operation_name: str = "operation", logger_instance: Optional[logging.Logger] = None):
        """Context manager for timing operations."""
        start_time = time.time()
        try:
            yield
        finally:
            end_time = time.time()
            duration = end_time - start_time
            
            message = f"{operation_name} completed in {TimeUtils.format_duration(duration)}"
            
            if logger_instance:
                logger_instance.info(message)
            else:
                logger.info(message)
    
    @staticmethod
    def measure_memory_usage() -> Dict[str, float]:
        """Measure current memory usage."""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                'rss': memory_info.rss / 1024 / 1024,  # MB
                'vms': memory_info.vms / 1024 / 1024,  # MB
                'percent': process.memory_percent(),
            }
        except ImportError:
            return {}
    
    @staticmethod
    def format_memory_usage(memory_info: Dict[str, float]) -> str:
        """Format memory usage information."""
        if not memory_info:
            return "Memory usage info not available"
        
        parts = []
        if 'rss' in memory_info:
            parts.append(f"RSS: {memory_info['rss']:.1f} MB")
        if 'vms' in memory_info:
            parts.append(f"VMS: {memory_info['vms']:.1f} MB")
        if 'percent' in memory_info:
            parts.append(f"Percent: {memory_info['percent']:.1f}%")
        
        return ", ".join(parts)


class LoggingUtils:
    """Utility class for logging operations."""
    
    @staticmethod
    def setup_structured_logger(name: str, level: int = logging.INFO) -> logging.Logger:
        """Set up a structured logger."""
        logger_instance = logging.getLogger(name)
        logger_instance.setLevel(level)
        
        # Create console handler with structured format
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        # Add handler if not already present
        if not logger_instance.handlers:
            logger_instance.addHandler(handler)
        
        return logger_instance
    
    @staticmethod
    def log_operation_start(logger_instance: logging.Logger, operation: str, 
                          **context) -> None:
        """Log the start of an operation."""
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        logger_instance.info(f"Starting {operation} - {context_str}")
    
    @staticmethod
    def log_operation_end(logger_instance: logging.Logger, operation: str, 
                         success: bool, duration: Optional[float] = None, 
                         **context) -> None:
        """Log the end of an operation."""
        status = "SUCCESS" if success else "FAILED"
        parts = [f"Completed {operation} - {status}"]
        
        if duration is not None:
            parts.append(f"duration={TimeUtils.format_duration(duration)}")
        
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        if context_str:
            parts.append(context_str)
        
        message = " - ".join(parts)
        
        if success:
            logger_instance.info(message)
        else:
            logger_instance.error(message)
    
    @staticmethod
    def create_error_context(error: Exception, **additional_context) -> Dict[str, Any]:
        """Create structured error context for logging."""
        context = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'error_module': error.__class__.__module__,
        }
        
        if hasattr(error, '__traceback__') and error.__traceback__:
            import traceback
            context['traceback'] = traceback.format_exc()
        
        context.update(additional_context)
        return context


class BackupUtils:
    """Main utility class combining all backup-related utilities."""
    
    @staticmethod
    def generate_backup_name(prefix: str = "backup", include_timestamp: bool = True,
                           include_uuid: bool = False, extension: Optional[str] = None) -> str:
        """Generate a backup filename."""
        parts = [prefix]
        
        if include_timestamp:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            parts.append(timestamp)
        
        if include_uuid:
            parts.append(str(uuid.uuid4())[:8])
        
        filename = "_".join(parts)
        
        if extension:
            if not extension.startswith('.'):
                extension = '.' + extension
            filename += extension
        
        return FileUtils.safe_filename(filename)
    
    @staticmethod
    def create_backup_info_dict(backup_instance, include_metadata: bool = True) -> Dict[str, Any]:
        """Create a dictionary with backup information."""
        info = {
            'backup_id': str(backup_instance.backup_id),
            'name': backup_instance.name,
            'backup_type': backup_instance.backup_type,
            'storage_type': backup_instance.storage_type,
            'status': backup_instance.status,
            'created_at': backup_instance.created_at.isoformat(),
            'file_size': backup_instance.file_size,
            'file_size_human': FileUtils.format_file_size(backup_instance.file_size) if backup_instance.file_size else "N/A",
        }
        
        if include_metadata and backup_instance.metadata:
            info['metadata'] = backup_instance.metadata
        
        return info
    
    @staticmethod
    def calculate_backup_statistics(backups_query) -> Dict[str, Any]:
        """Calculate statistics for a queryset of backups."""
        if not backups_query.exists():
            return {
                'total_backups': 0,
                'total_size': 0,
                'total_size_human': "0 B",
                'average_size': 0,
                'average_size_human': "0 B",
                'latest_backup': None,
                'oldest_backup': None,
                'by_status': {},
                'by_type': {},
                'by_storage': {},
            }
        
        total_backups = backups_query.count()
        
        # Calculate sizes
        total_size = sum(backup.file_size or 0 for backup in backups_query)
        average_size = total_size / total_backups if total_backups > 0 else 0
        
        # Get latest and oldest
        latest_backup = backups_query.order_by('-created_at').first()
        oldest_backup = backups_query.order_by('created_at').first()
        
        # Group by various fields
        by_status = {}
        by_type = {}
        by_storage = {}
        
        for backup in backups_query:
            # By status
            status = backup.status or 'unknown'
            by_status[status] = by_status.get(status, 0) + 1
            
            # By type
            backup_type = backup.backup_type or 'unknown'
            by_type[backup_type] = by_type.get(backup_type, 0) + 1
            
            # By storage
            storage_type = backup.storage_type or 'unknown'
            by_storage[storage_type] = by_storage.get(storage_type, 0) + 1
        
        return {
            'total_backups': total_backups,
            'total_size': total_size,
            'total_size_human': FileUtils.format_file_size(total_size),
            'average_size': average_size,
            'average_size_human': FileUtils.format_file_size(average_size),
            'latest_backup': latest_backup.created_at.isoformat() if latest_backup else None,
            'oldest_backup': oldest_backup.created_at.isoformat() if oldest_backup else None,
            'by_status': by_status,
            'by_type': by_type,
            'by_storage': by_storage,
        }
    
    @staticmethod
    def validate_backup_prerequisites(storage_type: str, backup_type: str) -> Tuple[bool, List[str]]:
        """Validate prerequisites for a backup operation."""
        errors = []
        
        # Validate storage type
        valid_storage_types = ['local', 's3', 'azure', 'gcs']
        if storage_type not in valid_storage_types:
            errors.append(f"Invalid storage type: {storage_type}")
        
        # Validate backup type
        valid_backup_types = ['full', 'incremental', 'differential', 'delta']
        if backup_type not in valid_backup_types:
            errors.append(f"Invalid backup type: {backup_type}")
        
        # Check storage-specific requirements
        if storage_type == 's3':
            required_settings = ['AWS_S3_BUCKET', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']
            for setting in required_settings:
                if not getattr(settings, setting, None):
                    errors.append(f"S3 storage requires {setting}")
        
        elif storage_type == 'azure':
            required_settings = ['AZURE_ACCOUNT_NAME', 'AZURE_ACCOUNT_KEY']
            for setting in required_settings:
                if not getattr(settings, setting, None):
                    errors.append(f"Azure storage requires {setting}")
        
        elif storage_type == 'gcs':
            required_settings = ['GCS_BUCKET']
            for setting in required_settings:
                if not getattr(settings, setting, None):
                    errors.append(f"GCS storage requires {setting}")
        
        return len(errors) == 0, errors


# Convenience functions
def format_file_size(size_bytes: int, precision: int = 2) -> str:
    """Convenience function for formatting file size."""
    return FileUtils.format_file_size(size_bytes, precision)


def calculate_checksum(file_path: Union[str, Path], algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> str:
    """Convenience function for calculating checksum."""
    return FileUtils.calculate_checksum(file_path, algorithm)


def format_duration(seconds: float, precision: int = 2) -> str:
    """Convenience function for formatting duration."""
    return TimeUtils.format_duration(seconds, precision)


def generate_backup_name(prefix: str = "backup", **kwargs) -> str:
    """Convenience function for generating backup names."""
    return BackupUtils.generate_backup_name(prefix, **kwargs)
