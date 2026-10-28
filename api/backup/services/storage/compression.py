"""
Backup Compression Module
Provides compression utilities for backup files to reduce storage costs and bandwidth.
"""

import logging
import gzip
import zipfile
import tarfile
import io
import os
from typing import Dict, Any, Optional, BinaryIO, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class CompressionResult:
    """Result of compression operation."""
    success: bool
    original_size: int
    compressed_size: int
    compression_ratio: float
    compression_time: datetime
    compressed_file_path: Optional[str] = None
    compressed_file_obj: Optional[BinaryIO] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert compression result to dictionary."""
        return {
            'success': self.success,
            'original_size': self.original_size,
            'compressed_size': self.compressed_size,
            'compression_ratio': self.compression_ratio,
            'compression_time': self.compression_time.isoformat(),
            'compressed_file_path': self.compressed_file_path,
            'error_message': self.error_message
        }


@dataclass
class CompressionConfig:
    """Configuration for backup compression."""
    algorithm: str = 'gzip'  # gzip, zip, tar.gz
    compression_level: int = 6  # 1-9 for gzip, 0-9 for zip
    include_metadata: bool = True
    chunk_size: int = 8192
    temp_dir: Optional[str] = None
    delete_original: bool = False


class BackupCompressor:
    """
    Compresses backup files using various algorithms.
    Supports gzip, zip, and tar.gz compression formats.
    """
    
    def __init__(self, config: CompressionConfig = None):
        """Initialize backup compressor."""
        self.config = config or CompressionConfig()
        self.supported_algorithms = ['gzip', 'zip', 'tar.gz']
        logger.info(f"Backup compressor initialized with algorithm: {self.config.algorithm}")
    
    def compress_file(self, file_path: str, output_path: str = None) -> CompressionResult:
        """
        Compress a file on disk.
        
        Args:
            file_path: Path to file to compress
            output_path: Output path for compressed file (optional)
            
        Returns:
            CompressionResult: Compression result
        """
        try:
            # Get original file size
            original_size = os.path.getsize(file_path)
            
            # Generate output path if not provided
            if not output_path:
                output_path = self._generate_output_path(file_path)
            
            # Compress based on algorithm
            start_time = datetime.now()
            
            if self.config.algorithm == 'gzip':
                compressed_path = self._compress_gzip_file(file_path, output_path)
            elif self.config.algorithm == 'zip':
                compressed_path = self._compress_zip_file(file_path, output_path)
            elif self.config.algorithm == 'tar.gz':
                compressed_path = self._compress_tar_gz_file(file_path, output_path)
            else:
                raise ValueError(f"Unsupported compression algorithm: {self.config.algorithm}")
            
            # Get compressed file size
            compressed_size = os.path.getsize(compressed_path)
            compression_ratio = (original_size - compressed_size) / original_size * 100 if original_size > 0 else 0
            
            # Delete original if configured
            if self.config.delete_original:
                os.remove(file_path)
                logger.info(f"Deleted original file: {file_path}")
            
            result = CompressionResult(
                success=True,
                original_size=original_size,
                compressed_size=compressed_size,
                compression_ratio=compression_ratio,
                compression_time=start_time,
                compressed_file_path=compressed_path
            )
            
            logger.info(f"Compressed {file_path} -> {compressed_path} "
                       f"({compression_ratio:.1f}% reduction)")
            return result
            
        except Exception as e:
            logger.error(f"Failed to compress file {file_path}: {e}")
            return CompressionResult(
                success=False,
                original_size=0,
                compressed_size=0,
                compression_ratio=0.0,
                compression_time=datetime.now(),
                error_message=str(e)
            )
    
    def compress_file_obj(self, file_obj: BinaryIO, filename: str = None) -> CompressionResult:
        """
        Compress a file-like object in memory.
        
        Args:
            file_obj: File-like object to compress
            filename: Original filename (optional)
            
        Returns:
            CompressionResult: Compression result
        """
        try:
            # Get original size
            current_pos = file_obj.tell()
            file_obj.seek(0, 2)
            original_size = file_obj.tell()
            file_obj.seek(current_pos)
            
            # Compress based on algorithm
            start_time = datetime.now()
            
            if self.config.algorithm == 'gzip':
                compressed_obj = self._compress_gzip_obj(file_obj)
            elif self.config.algorithm == 'zip':
                compressed_obj = self._compress_zip_obj(file_obj, filename or 'backup.sql')
            elif self.config.algorithm == 'tar.gz':
                compressed_obj = self._compress_tar_gz_obj(file_obj, filename or 'backup.sql')
            else:
                raise ValueError(f"Unsupported compression algorithm: {self.config.algorithm}")
            
            # Get compressed size
            compressed_obj.seek(0, 2)
            compressed_size = compressed_obj.tell()
            compressed_obj.seek(0)
            
            compression_ratio = (original_size - compressed_size) / original_size * 100 if original_size > 0 else 0
            
            result = CompressionResult(
                success=True,
                original_size=original_size,
                compressed_size=compressed_size,
                compression_ratio=compression_ratio,
                compression_time=start_time,
                compressed_file_obj=compressed_obj
            )
            
            logger.info(f"Compressed file object ({compression_ratio:.1f}% reduction)")
            return result
            
        except Exception as e:
            logger.error(f"Failed to compress file object: {e}")
            return CompressionResult(
                success=False,
                original_size=0,
                compressed_size=0,
                compression_ratio=0.0,
                compression_time=datetime.now(),
                error_message=str(e)
            )
    
    def decompress_file(self, compressed_path: str, output_path: str = None) -> CompressionResult:
        """
        Decompress a compressed file.
        
        Args:
            compressed_path: Path to compressed file
            output_path: Output path for decompressed file (optional)
            
        Returns:
            CompressionResult: Decompression result
        """
        try:
            # Get compressed file size
            compressed_size = os.path.getsize(compressed_path)
            
            # Generate output path if not provided
            if not output_path:
                output_path = self._generate_decompress_output_path(compressed_path)
            
            # Decompress based on algorithm
            start_time = datetime.now()
            
            if compressed_path.endswith('.gz'):
                output_path = self._decompress_gzip_file(compressed_path, output_path)
            elif compressed_path.endswith('.zip'):
                output_path = self._decompress_zip_file(compressed_path, output_path)
            elif compressed_path.endswith('.tar.gz'):
                output_path = self._decompress_tar_gz_file(compressed_path, output_path)
            else:
                raise ValueError(f"Unsupported compression format for file: {compressed_path}")
            
            # Get decompressed file size
            original_size = os.path.getsize(output_path)
            compression_ratio = (original_size - compressed_size) / original_size * 100 if original_size > 0 else 0
            
            result = CompressionResult(
                success=True,
                original_size=original_size,
                compressed_size=compressed_size,
                compression_ratio=compression_ratio,
                compression_time=start_time,
                compressed_file_path=output_path
            )
            
            logger.info(f"Decompressed {compressed_path} -> {output_path}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to decompress file {compressed_path}: {e}")
            return CompressionResult(
                success=False,
                original_size=0,
                compressed_size=0,
                compression_ratio=0.0,
                compression_time=datetime.now(),
                error_message=str(e)
            )
    
    def decompress_file_obj(self, compressed_obj: BinaryIO) -> CompressionResult:
        """
        Decompress a compressed file-like object.
        
        Args:
            compressed_obj: Compressed file-like object
            
        Returns:
            CompressionResult: Decompression result
        """
        try:
            # Get compressed size
            current_pos = compressed_obj.tell()
            compressed_obj.seek(0, 2)
            compressed_size = compressed_obj.tell()
            compressed_obj.seek(current_pos)
            
            # Decompress based on algorithm
            start_time = datetime.now()
            
            if self.config.algorithm == 'gzip':
                decompressed_obj = self._decompress_gzip_obj(compressed_obj)
            elif self.config.algorithm == 'zip':
                decompressed_obj = self._decompress_zip_obj(compressed_obj)
            elif self.config.algorithm == 'tar.gz':
                decompressed_obj = self._decompress_tar_gz_obj(compressed_obj)
            else:
                raise ValueError(f"Unsupported compression algorithm: {self.config.algorithm}")
            
            # Get decompressed size
            decompressed_obj.seek(0, 2)
            original_size = decompressed_obj.tell()
            decompressed_obj.seek(0)
            
            compression_ratio = (original_size - compressed_size) / original_size * 100 if original_size > 0 else 0
            
            result = CompressionResult(
                success=True,
                original_size=original_size,
                compressed_size=compressed_size,
                compression_ratio=compression_ratio,
                compression_time=start_time,
                compressed_file_obj=decompressed_obj
            )
            
            logger.info(f"Decompressed file object")
            return result
            
        except Exception as e:
            logger.error(f"Failed to decompress file object: {e}")
            return CompressionResult(
                success=False,
                original_size=0,
                compressed_size=0,
                compression_ratio=0.0,
                compression_time=datetime.now(),
                error_message=str(e)
            )
    
    def _compress_gzip_file(self, file_path: str, output_path: str) -> str:
        """Compress file using gzip."""
        with open(file_path, 'rb') as f_in:
            with gzip.open(output_path, 'wb', compresslevel=self.config.compression_level) as f_out:
                while True:
                    chunk = f_in.read(self.config.chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)
        return output_path
    
    def _compress_zip_file(self, file_path: str, output_path: str) -> str:
        """Compress file using zip."""
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED, 
                          compresslevel=self.config.compression_level) as zip_file:
            zip_file.write(file_path, os.path.basename(file_path))
        return output_path
    
    def _compress_tar_gz_file(self, file_path: str, output_path: str) -> str:
        """Compress file using tar.gz."""
        with tarfile.open(output_path, 'w:gz', compresslevel=self.config.compression_level) as tar_file:
            tar_file.add(file_path, arcname=os.path.basename(file_path))
        return output_path
    
    def _compress_gzip_obj(self, file_obj: BinaryIO) -> BinaryIO:
        """Compress file object using gzip."""
        compressed_obj = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed_obj, mode='wb', 
                          compresslevel=self.config.compression_level) as gzip_file:
            current_pos = file_obj.tell()
            file_obj.seek(0)
            while True:
                chunk = file_obj.read(self.config.chunk_size)
                if not chunk:
                    break
                gzip_file.write(chunk)
            file_obj.seek(current_pos)
        
        compressed_obj.seek(0)
        return compressed_obj
    
    def _compress_zip_obj(self, file_obj: BinaryIO, filename: str) -> BinaryIO:
        """Compress file object using zip."""
        compressed_obj = io.BytesIO()
        with zipfile.ZipFile(compressed_obj, 'w', zipfile.ZIP_DEFLATED,
                          compresslevel=self.config.compression_level) as zip_file:
            # Read file object into memory
            current_pos = file_obj.tell()
            file_obj.seek(0)
            file_data = file_obj.read()
            file_obj.seek(current_pos)
            
            # Create zip entry
            zip_info = zipfile.ZipInfo(filename=filename)
            zip_info.compress_type = zipfile.ZIP_DEFLATED
            zip_file.writestr(zip_info, file_data)
        
        compressed_obj.seek(0)
        return compressed_obj
    
    def _compress_tar_gz_obj(self, file_obj: BinaryIO, filename: str) -> BinaryIO:
        """Compress file object using tar.gz."""
        compressed_obj = io.BytesIO()
        with tarfile.open(fileobj=compressed_obj, mode='w:gz',
                          compresslevel=self.config.compression_level) as tar_file:
            # Read file object into memory
            current_pos = file_obj.tell()
            file_obj.seek(0)
            file_data = file_obj.read()
            file_obj.seek(current_pos)
            
            # Create tar entry
            tar_info = tarfile.TarInfo(name=filename)
            tar_info.size = len(file_data)
            tar_info.mtime = datetime.now().timestamp()
            
            tar_file.addfile(tar_info, io.BytesIO(file_data))
        
        compressed_obj.seek(0)
        return compressed_obj
    
    def _decompress_gzip_file(self, compressed_path: str, output_path: str) -> str:
        """Decompress gzip file."""
        with gzip.open(compressed_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                while True:
                    chunk = f_in.read(self.config.chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)
        return output_path
    
    def _decompress_zip_file(self, compressed_path: str, output_path: str) -> str:
        """Decompress zip file."""
        with zipfile.ZipFile(compressed_path, 'r') as zip_file:
            # Extract first file
            file_list = zip_file.namelist()
            if file_list:
                with zip_file.open(file_list[0]) as extracted_file:
                    with open(output_path, 'wb') as f_out:
                        while True:
                            chunk = extracted_file.read(self.config.chunk_size)
                            if not chunk:
                                break
                            f_out.write(chunk)
        return output_path
    
    def _decompress_tar_gz_file(self, compressed_path: str, output_path: str) -> str:
        """Decompress tar.gz file."""
        with tarfile.open(compressed_path, 'r:gz') as tar_file:
            # Extract first file
            member = tar_file.next()
            if member:
                with tar_file.extractfile(member) as extracted_file:
                    with open(output_path, 'wb') as f_out:
                        while True:
                            chunk = extracted_file.read(self.config.chunk_size)
                            if not chunk:
                                break
                            f_out.write(chunk)
        return output_path
    
    def _decompress_gzip_obj(self, compressed_obj: BinaryIO) -> BinaryIO:
        """Decompress gzip object."""
        decompressed_obj = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed_obj, mode='rb') as gzip_file:
            while True:
                chunk = gzip_file.read(self.config.chunk_size)
                if not chunk:
                    break
                decompressed_obj.write(chunk)
        
        decompressed_obj.seek(0)
        return decompressed_obj
    
    def _decompress_zip_obj(self, compressed_obj: BinaryIO) -> BinaryIO:
        """Decompress zip object."""
        decompressed_obj = io.BytesIO()
        with zipfile.ZipFile(compressed_obj, 'r') as zip_file:
            file_list = zip_file.namelist()
            if file_list:
                with zip_file.open(file_list[0]) as extracted_file:
                    while True:
                        chunk = extracted_file.read(self.config.chunk_size)
                        if not chunk:
                            break
                        decompressed_obj.write(chunk)
        
        decompressed_obj.seek(0)
        return decompressed_obj
    
    def _decompress_tar_gz_obj(self, compressed_obj: BinaryIO) -> BinaryIO:
        """Decompress tar.gz object."""
        decompressed_obj = io.BytesIO()
        with tarfile.open(fileobj=compressed_obj, mode='r:gz') as tar_file:
            member = tar_file.next()
            if member:
                with tar_file.extractfile(member) as extracted_file:
                    while True:
                        chunk = extracted_file.read(self.config.chunk_size)
                        if not chunk:
                            break
                        decompressed_obj.write(chunk)
        
        decompressed_obj.seek(0)
        return decompressed_obj
    
    def _generate_output_path(self, input_path: str) -> str:
        """Generate output path for compressed file."""
        base_name = os.path.splitext(input_path)[0]
        
        if self.config.algorithm == 'gzip':
            return f"{base_name}.gz"
        elif self.config.algorithm == 'zip':
            return f"{base_name}.zip"
        elif self.config.algorithm == 'tar.gz':
            return f"{base_name}.tar.gz"
        else:
            return f"{base_name}.compressed"
    
    def _generate_decompress_output_path(self, compressed_path: str) -> str:
        """Generate output path for decompressed file."""
        if compressed_path.endswith('.gz'):
            return compressed_path[:-3]
        elif compressed_path.endswith('.zip'):
            return compressed_path[:-4] + '.sql'
        elif compressed_path.endswith('.tar.gz'):
            return compressed_path[:-7] + '.sql'
        else:
            return compressed_path + '.decompressed'
    
    def get_supported_algorithms(self) -> list:
        """Get list of supported compression algorithms."""
        return self.supported_algorithms.copy()
    
    def estimate_compression_ratio(self, file_path: str, sample_size: int = 1024*1024) -> float:
        """
        Estimate compression ratio by sampling file content.
        
        Args:
            file_path: Path to file
            sample_size: Size of sample to use for estimation
            
        Returns:
            float: Estimated compression ratio (0-100)
        """
        try:
            with open(file_path, 'rb') as f:
                sample = f.read(sample_size)
            
            # Compress sample
            if self.config.algorithm == 'gzip':
                compressed_sample = gzip.compress(sample, compresslevel=self.config.compression_level)
            else:
                # For other algorithms, use gzip as approximation
                compressed_sample = gzip.compress(sample, compresslevel=self.config.compression_level)
            
            # Calculate ratio
            ratio = (len(sample) - len(compressed_sample)) / len(sample) * 100
            return max(0, min(100, ratio))
            
        except Exception as e:
            logger.error(f"Failed to estimate compression ratio: {e}")
            return 0.0


# Convenience functions
def create_compressor(algorithm: str = 'gzip', compression_level: int = 6) -> BackupCompressor:
    """
    Create a backup compressor with specified settings.
    
    Args:
        algorithm: Compression algorithm
        compression_level: Compression level
        
    Returns:
        BackupCompressor: Configured compressor
    """
    config = CompressionConfig(
        algorithm=algorithm,
        compression_level=compression_level
    )
    return BackupCompressor(config)


def quick_compress(file_obj: BinaryIO, algorithm: str = 'gzip') -> BinaryIO:
    """
    Quick compression of file object.
    
    Args:
        file_obj: File-like object to compress
        algorithm: Compression algorithm
        
    Returns:
        BinaryIO: Compressed file object
    """
    compressor = create_compressor(algorithm)
    result = compressor.compress_file_obj(file_obj)
    
    if result.success:
        return result.compressed_file_obj
    else:
        raise Exception(f"Compression failed: {result.error_message}")


def quick_decompress(compressed_obj: BinaryIO, algorithm: str = 'gzip') -> BinaryIO:
    """
    Quick decompression of file object.
    
    Args:
        compressed_obj: Compressed file-like object
        algorithm: Compression algorithm
        
    Returns:
        BinaryIO: Decompressed file object
    """
    compressor = create_compressor(algorithm)
    result = compressor.decompress_file_obj(compressed_obj)
    
    if result.success:
        return result.compressed_file_obj
    else:
        raise Exception(f"Decompression failed: {result.error_message}")
