"""
Backup Compression Service
Comprehensive compression service for backup files with multiple algorithms
"""

import os
import gzip
import bz2
import lzma
import zipfile
import zstandard as zstd
import logging
from datetime import datetime
from django.core.files.base import ContentFile
from django.conf import settings

logger = logging.getLogger(__name__)


class BackupCompressionService:
    """
    Service for compressing and decompressing backup files
    Supports multiple compression algorithms with level control
    """
    
    SUPPORTED_ALGORITHMS = [
        'gzip',
        'bzip2',
        'lzma',
        'zip',
        'zstd'
    ]
    
    def __init__(self, algorithm='gzip', compression_level=None):
        """
        Initialize compression service
        
        Args:
            algorithm (str): Compression algorithm to use
            compression_level (int): Compression level (algorithm-specific)
        """
        if algorithm not in self.SUPPORTED_ALGORITHMS:
            raise ValueError(f"Unsupported compression algorithm: {algorithm}")
        
        self.algorithm = algorithm
        self.compression_level = self._get_default_compression_level(algorithm, compression_level)
    
    def _get_default_compression_level(self, algorithm, level):
        """Get default compression level for algorithm"""
        if level is not None:
            return level
        
        # Algorithm-specific defaults
        defaults = {
            'gzip': 6,
            'bzip2': 6,
            'lzma': 6,
            'zip': 6,
            'zstd': 3
        }
        
        return defaults.get(algorithm, 6)
    
    def compress_file(self, input_file_path, output_file_path):
        """
        Compress a file using the configured algorithm
        
        Args:
            input_file_path (str): Path to input file
            output_file_path (str): Path to output file
            
        Returns:
            dict: Compression results
        """
        try:
            # Get input file size
            input_size = os.path.getsize(input_file_path)
            
            # Compress based on algorithm
            if self.algorithm == 'gzip':
                output_size = self._compress_gzip(input_file_path, output_file_path)
            elif self.algorithm == 'bzip2':
                output_size = self._compress_bzip2(input_file_path, output_file_path)
            elif self.algorithm == 'lzma':
                output_size = self._compress_lzma(input_file_path, output_file_path)
            elif self.algorithm == 'zip':
                output_size = self._compress_zip(input_file_path, output_file_path)
            elif self.algorithm == 'zstd':
                output_size = self._compress_zstd(input_file_path, output_file_path)
            else:
                raise ValueError(f"Compression not implemented for {self.algorithm}")
            
            # Calculate compression ratio
            compression_ratio = output_size / input_size if input_size > 0 else 0
            
            return {
                'success': True,
                'input_size': input_size,
                'output_size': output_size,
                'compression_ratio': compression_ratio,
                'space_saved': input_size - output_size,
                'algorithm': self.algorithm,
                'compression_level': self.compression_level,
                'compression_percentage': (1 - compression_ratio) * 100
            }
            
        except Exception as e:
            logger.error(f"File compression failed with {self.algorithm}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'algorithm': self.algorithm
            }
    
    def _compress_gzip(self, input_path, output_path):
        """Compress file using gzip"""
        with open(input_path, 'rb') as f_in:
            with gzip.open(output_path, 'wb', compresslevel=self.compression_level) as f_out:
                f_out.writelines(f_in)
        
        return os.path.getsize(output_path)
    
    def _compress_bzip2(self, input_path, output_path):
        """Compress file using bzip2"""
        with open(input_path, 'rb') as f_in:
            with bz2.open(output_path, 'wb', compresslevel=self.compression_level) as f_out:
                f_out.writelines(f_in)
        
        return os.path.getsize(output_path)
    
    def _compress_lzma(self, input_path, output_path):
        """Compress file using LZMA"""
        with open(input_path, 'rb') as f_in:
            with lzma.open(output_path, 'wb', preset=lzma.PRESET_EXTREME, format=lzma.FORMAT_XZ) as f_out:
                f_out.writelines(f_in)
        
        return os.path.getsize(output_path)
    
    def _compress_zip(self, input_path, output_path):
        """Compress file using ZIP"""
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=self.compression_level) as zipf:
            zipf.write(input_path, os.path.basename(input_path))
        
        return os.path.getsize(output_path)
    
    def _compress_zstd(self, input_path, output_path):
        """Compress file using Zstandard"""
        compressor = zstd.ZstdCompressor(level=self.compression_level)
        
        with open(input_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                for chunk in iter(lambda: f_in.read(8192), b''):
                    compressed = compressor.compress(chunk)
                    f_out.write(compressed)
                
                # Write any remaining compressed data
                remaining = compressor.flush()
                if remaining:
                    f_out.write(remaining)
        
        return os.path.getsize(output_path)
    
    def decompress_file(self, input_file_path, output_file_path):
        """
        Decompress a file using the configured algorithm
        
        Args:
            input_file_path (str): Path to compressed file
            output_file_path (str): Path to output file
            
        Returns:
            dict: Decompression results
        """
        try:
            # Determine compression algorithm from file extension
            algorithm = self._detect_algorithm_from_file(input_file_path)
            
            if not algorithm:
                raise ValueError("Cannot determine compression algorithm from file extension")
            
            # Decompress based on algorithm
            if algorithm == 'gzip':
                self._decompress_gzip(input_file_path, output_file_path)
            elif algorithm == 'bzip2':
                self._decompress_bzip2(input_file_path, output_file_path)
            elif algorithm == 'lzma':
                self._decompress_lzma(input_file_path, output_file_path)
            elif algorithm == 'zip':
                self._decompress_zip(input_file_path, output_file_path)
            elif algorithm == 'zstd':
                self._decompress_zstd(input_file_path, output_file_path)
            else:
                raise ValueError(f"Decompression not implemented for {algorithm}")
            
            # Get file sizes
            input_size = os.path.getsize(input_file_path)
            output_size = os.path.getsize(output_file_path)
            
            return {
                'success': True,
                'input_size': input_size,
                'output_size': output_size,
                'algorithm': algorithm,
                'decompression_ratio': output_size / input_size if input_size > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"File decompression failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _decompress_gzip(self, input_path, output_path):
        """Decompress gzip file"""
        with gzip.open(input_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                f_out.writelines(f_in)
    
    def _decompress_bzip2(self, input_path, output_path):
        """Decompress bzip2 file"""
        with bz2.open(input_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                f_out.writelines(f_in)
    
    def _decompress_lzma(self, input_path, output_path):
        """Decompress LZMA file"""
        with lzma.open(input_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                f_out.writelines(f_in)
    
    def _decompress_zip(self, input_path, output_path):
        """Decompress ZIP file"""
        with zipfile.ZipFile(input_path, 'r') as zipf:
            # Extract all files
            zipf.extractall(os.path.dirname(output_path))
    
    def _decompress_zstd(self, input_path, output_path):
        """Decompress Zstandard file"""
        with open(input_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                decompressor = zstd.ZstdDecompressor()
                
                for chunk in iter(lambda: f_in.read(8192), b''):
                    try:
                        decompressed = decompressor.decompress(chunk)
                        f_out.write(decompressed)
                    except zstd.ZstdError:
                        # Handle end of stream
                        remaining = decompressor.flush()
                        if remaining:
                            f_out.write(remaining)
                        break
    
    def _detect_algorithm_from_file(self, file_path):
        """Detect compression algorithm from file extension"""
        _, ext = os.path.splitext(file_path)
        
        # Map extensions to algorithms
        extension_map = {
            '.gz': 'gzip',
            '.bz2': 'bzip2',
            '.xz': 'lzma',
            '.zip': 'zip',
            '.zst': 'zstd'
        }
        
        return extension_map.get(ext.lower())
    
    def compress_data(self, data):
        """
        Compress data in memory using the configured algorithm
        
        Args:
            data (bytes): Data to compress
            
        Returns:
            bytes: Compressed data
        """
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        
        try:
            if self.algorithm == 'gzip':
                return self._compress_data_gzip(data)
            elif self.algorithm == 'bzip2':
                return self._compress_data_bzip2(data)
            elif self.algorithm == 'lzma':
                return self._compress_data_lzma(data)
            elif self.algorithm == 'zip':
                return self._compress_data_zip(data)
            elif self.algorithm == 'zstd':
                return self._compress_data_zstd(data)
            else:
                raise ValueError(f"Compression not implemented for {self.algorithm}")
                
        except Exception as e:
            logger.error(f"Data compression failed with {self.algorithm}: {str(e)}")
            raise
    
    def _compress_data_gzip(self, data):
        """Compress data using gzip"""
        import io
        buffer = io.BytesIO()
        with gzip.GzipFile(buffer, 'wb', compresslevel=self.compression_level) as gz_file:
            gz_file.write(data)
        return buffer.getvalue()
    
    def _compress_data_bzip2(self, data):
        """Compress data using bzip2"""
        return bz2.compress(data, compresslevel=self.compression_level)
    
    def _compress_data_lzma(self, data):
        """Compress data using LZMA"""
        return lzma.compress(data, preset=lzma.PRESET_EXTREME, format=lzma.FORMAT_XZ)
    
    def _compress_data_zip(self, data):
        """Compress data using ZIP"""
        import io
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=self.compression_level) as zipf:
            zipf.writestr('data', data)
        return buffer.getvalue()
    
    def _compress_data_zstd(self, data):
        """Compress data using Zstandard"""
        compressor = zstd.ZstdCompressor(level=self.compression_level)
        return compressor.compress(data)
    
    def decompress_data(self, compressed_data):
        """
        Decompress data in memory using the configured algorithm
        
        Args:
            compressed_data (bytes): Compressed data
            
        Returns:
            bytes: Decompressed data
        """
        try:
            if self.algorithm == 'gzip':
                return self._decompress_data_gzip(compressed_data)
            elif self.algorithm == 'bzip2':
                return self._decompress_data_bzip2(compressed_data)
            elif self.algorithm == 'lzma':
                return self._decompress_data_lzma(compressed_data)
            elif self.algorithm == 'zip':
                return self._decompress_data_zip(compressed_data)
            elif self.algorithm == 'zstd':
                return self._decompress_data_zstd(compressed_data)
            else:
                raise ValueError(f"Decompression not implemented for {self.algorithm}")
                
        except Exception as e:
            logger.error(f"Data decompression failed: {str(e)}")
            raise
    
    def _decompress_data_gzip(self, compressed_data):
        """Decompress gzip data"""
        import io
        buffer = io.BytesIO(compressed_data)
        with gzip.GzipFile(buffer, 'rb') as gz_file:
            return gz_file.read()
    
    def _decompress_data_bzip2(self, compressed_data):
        """Decompress bzip2 data"""
        return bz2.decompress(compressed_data)
    
    def _decompress_data_lzma(self, compressed_data):
        """Decompress LZMA data"""
        return lzma.decompress(compressed_data)
    
    def _decompress_data_zip(self, compressed_data):
        """Decompress ZIP data"""
        import io
        buffer = io.BytesIO(compressed_data)
        with zipfile.ZipFile(buffer, 'r') as zipf:
            # Assuming single file in ZIP
            file_list = zipf.namelist()
            if file_list:
                return zipf.read(file_list[0])
        return b''
    
    def _decompress_data_zstd(self, compressed_data):
        """Decompress Zstandard data"""
        decompressor = zstd.ZstdDecompressor()
        return decompressor.decompress(compressed_data)
    
    def get_algorithm_info(self):
        """
        Get information about the current compression algorithm
        
        Returns:
            dict: Algorithm information
        """
        info = {
            'algorithm': self.algorithm,
            'compression_level': self.compression_level,
            'supported_levels': self._get_supported_levels(self.algorithm),
            'default_level': self._get_default_compression_level(self.algorithm, None),
            'file_extension': self._get_file_extension(self.algorithm),
            'mime_type': self._get_mime_type(self.algorithm),
            'description': self._get_algorithm_description(self.algorithm)
        }
        
        return info
    
    def _get_supported_levels(self, algorithm):
        """Get supported compression levels for algorithm"""
        levels = {
            'gzip': list(range(1, 10)),  # 1-9
            'bzip2': list(range(1, 10)),  # 1-9
            'lzma': list(range(0, 10)),  # 0-9
            'zip': list(range(0, 10)),  # 0-9
            'zstd': list(range(1, 23))   # 1-22
        }
        
        return levels.get(algorithm, list(range(1, 10)))
    
    def _get_file_extension(self, algorithm):
        """Get file extension for algorithm"""
        extensions = {
            'gzip': '.gz',
            'bzip2': '.bz2',
            'lzma': '.xz',
            'zip': '.zip',
            'zstd': '.zst'
        }
        
        return extensions.get(algorithm, '')
    
    def _get_mime_type(self, algorithm):
        """Get MIME type for algorithm"""
        mime_types = {
            'gzip': 'application/gzip',
            'bzip2': 'application/x-bzip2',
            'lzma': 'application/x-xz',
            'zip': 'application/zip',
            'zstd': 'application/zstd'
        }
        
        return mime_types.get(algorithm, 'application/octet-stream')
    
    def _get_algorithm_description(self, algorithm):
        """Get description of algorithm"""
        descriptions = {
            'gzip': 'GNU zip compression - good balance of speed and compression',
            'bzip2': 'Burrows-Wheeler block sorting - higher compression, slower',
            'lzma': 'LZMA2 compression - very high compression, very slow',
            'zip': 'ZIP archive format - widely supported',
            'zstd': 'Zstandard - fast compression with good ratio'
        }
        
        return descriptions.get(algorithm, f'Compression algorithm: {algorithm}')
    
    def benchmark_algorithms(self, test_data, output_dir=None):
        """
        Benchmark all compression algorithms with test data
        
        Args:
            test_data (bytes): Data to compress for benchmarking
            output_dir (str): Directory to save benchmark results
            
        Returns:
            dict: Benchmark results
        """
        results = {}
        original_size = len(test_data)
        
        for algorithm in self.SUPPORTED_ALGORITHMS:
            try:
                # Create compression service for algorithm
                compressor = BackupCompressionService(algorithm, 6)  # Use level 6 for fair comparison
                
                # Compress data
                start_time = datetime.now()
                compressed_data = compressor.compress_data(test_data)
                compress_time = (datetime.now() - start_time).total_seconds()
                
                # Decompress data
                start_time = datetime.now()
                decompressed_data = compressor.decompress_data(compressed_data)
                decompress_time = (datetime.now() - start_time).total_seconds()
                
                # Verify integrity
                integrity_check = test_data == decompressed_data
                
                # Calculate metrics
                compressed_size = len(compressed_data)
                compression_ratio = compressed_size / original_size
                compression_speed = original_size / compress_time if compress_time > 0 else 0
                decompression_speed = original_size / decompress_time if decompress_time > 0 else 0
                
                results[algorithm] = {
                    'original_size': original_size,
                    'compressed_size': compressed_size,
                    'compression_ratio': compression_ratio,
                    'compression_percentage': (1 - compression_ratio) * 100,
                    'compress_time': compress_time,
                    'decompress_time': decompress_time,
                    'compression_speed': compression_speed,
                    'decompression_speed': decompression_speed,
                    'integrity_check': integrity_check,
                    'success': True
                }
                
                # Save to file if output directory specified
                if output_dir:
                    result_file = os.path.join(output_dir, f'{algorithm}_benchmark.json')
                    with open(result_file, 'w') as f:
                        import json
                        json.dump(results[algorithm], f, indent=2)
                
            except Exception as e:
                results[algorithm] = {
                    'success': False,
                    'error': str(e)
                }
        
        # Sort by compression ratio (best compression first)
        sorted_results = dict(sorted(results.items(), key=lambda x: x[1].get('compression_ratio', float('inf'))))
        
        return {
            'test_data_size': original_size,
            'results': sorted_results,
            'best_compression': min(results.items(), key=lambda x: x[1].get('compression_ratio', float('inf')))[0],
            'fastest_compression': max(results.items(), key=lambda x: x[1].get('compression_speed', 0))[0],
            'fastest_decompression': max(results.items(), key=lambda x: x[1].get('decompression_speed', 0))[0]
        }
    
    def verify_compression(self, original_file, compressed_file):
        """
        Verify compression integrity by decompressing and comparing
        
        Args:
            original_file (str): Path to original file
            compressed_file (str): Path to compressed file
            
        Returns:
            dict: Verification results
        """
        try:
            # Read original file
            with open(original_file, 'rb') as f:
                original_data = f.read()
            
            # Decompress compressed file
            temp_output = compressed_file + '_verify_temp'
            decompress_result = self.decompress_file(compressed_file, temp_output)
            
            if not decompress_result['success']:
                return {
                    'success': False,
                    'error': f"Decompression failed: {decompress_result.get('error')}"
                }
            
            # Read decompressed file
            with open(temp_output, 'rb') as f:
                decompressed_data = f.read()
            
            # Compare files
            integrity_check = original_data == decompressed_data
            
            # Clean up temp file
            if os.path.exists(temp_output):
                os.remove(temp_output)
            
            return {
                'success': True,
                'integrity_check': integrity_check,
                'original_size': len(original_data),
                'decompressed_size': len(decompressed_data),
                'size_match': len(original_data) == len(decompressed_data)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_optimal_algorithm(self, file_path, sample_size=1024*1024):
        """
        Determine optimal compression algorithm for a file by sampling
        
        Args:
            file_path (str): Path to file to analyze
            sample_size (int): Size of sample to analyze (default: 1MB)
            
        Returns:
            dict: Algorithm recommendation
        """
        try:
            # Read sample of file
            with open(file_path, 'rb') as f:
                sample_data = f.read(sample_size)
            
            # Benchmark with sample
            benchmark_results = self.benchmark_algorithms(sample_data)
            
            if not benchmark_results['results']:
                return {
                    'success': False,
                    'error': 'No benchmark results available'
                }
            
            # Get best algorithm based on compression ratio
            best_algorithm = benchmark_results['best_compression'][0]
            
            return {
                'success': True,
                'recommended_algorithm': best_algorithm,
                'expected_compression_ratio': benchmark_results['results'][best_algorithm]['compression_ratio'],
                'expected_compression_percentage': benchmark_results['results'][best_algorithm]['compression_percentage'],
                'benchmark_results': benchmark_results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
