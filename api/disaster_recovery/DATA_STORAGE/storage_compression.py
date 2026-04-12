"""
Storage Compression — Handles backup compression using gzip, zstd, and lz4.
"""
import logging
import gzip
import shutil
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class StorageCompressor:
    """
    Compresses and decompresses backup files.

    Supports: gzip (default), zstd, lz4
    Chooses algorithm based on config and available libraries.
    """

    SUPPORTED_ALGORITHMS = ["gzip", "zstd", "lz4"]

    def __init__(self, algorithm: str = "gzip", compression_level: int = 6):
        if algorithm not in self.SUPPORTED_ALGORITHMS:
            raise ValueError(f"Unsupported algorithm: {algorithm}. Use: {self.SUPPORTED_ALGORITHMS}")
        self.algorithm = algorithm
        self.level = compression_level

    def compress(self, input_path: str, output_path: str = None) -> dict:
        """Compress a file and return compression stats."""
        if not os.path.exists(input_path):
            return {"success": False, "error": f"File not found: {input_path}"}

        if output_path is None:
            ext = {"gzip": ".gz", "zstd": ".zst", "lz4": ".lz4"}.get(self.algorithm, ".gz")
            output_path = input_path + ext

        original_size = os.path.getsize(input_path)
        started = datetime.utcnow()

        try:
            if self.algorithm == "gzip":
                self._compress_gzip(input_path, output_path)
            elif self.algorithm == "zstd":
                self._compress_zstd(input_path, output_path)
            elif self.algorithm == "lz4":
                self._compress_lz4(input_path, output_path)

            compressed_size = os.path.getsize(output_path)
            ratio = round(original_size / max(compressed_size, 1), 2)
            duration = (datetime.utcnow() - started).total_seconds()

            logger.info(
                f"Compressed ({self.algorithm}): {original_size:,} -> {compressed_size:,} bytes "
                f"(ratio: {ratio:.1f}x, {duration:.1f}s)"
            )
            return {
                "success": True,
                "algorithm": self.algorithm,
                "input_path": input_path,
                "output_path": output_path,
                "original_size_bytes": original_size,
                "compressed_size_bytes": compressed_size,
                "compression_ratio": ratio,
                "savings_percent": round((1 - 1/ratio) * 100, 1) if ratio > 1 else 0,
                "duration_seconds": duration,
            }
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            return {"success": False, "error": str(e), "input_path": input_path}

    def decompress(self, input_path: str, output_path: str = None) -> dict:
        """Decompress a file."""
        if not os.path.exists(input_path):
            return {"success": False, "error": f"File not found: {input_path}"}

        if output_path is None:
            for ext in (".gz", ".zst", ".lz4"):
                if input_path.endswith(ext):
                    output_path = input_path[:-len(ext)]
                    break
            else:
                output_path = input_path + ".decompressed"

        try:
            if input_path.endswith(".gz"):
                self._decompress_gzip(input_path, output_path)
            elif input_path.endswith(".zst"):
                self._decompress_zstd(input_path, output_path)
            elif input_path.endswith(".lz4"):
                self._decompress_lz4(input_path, output_path)
            else:
                shutil.copy2(input_path, output_path)

            return {"success": True, "output_path": output_path,
                    "size_bytes": os.path.getsize(output_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _compress_gzip(self, input_path: str, output_path: str):
        with open(input_path, "rb") as f_in:
            with gzip.open(output_path, "wb", compresslevel=self.level) as f_out:
                shutil.copyfileobj(f_in, f_out)

    def _compress_zstd(self, input_path: str, output_path: str):
        try:
            import zstandard as zstd
            cctx = zstd.ZstdCompressor(level=self.level)
            with open(input_path, "rb") as f_in:
                with open(output_path, "wb") as f_out:
                    cctx.copy_stream(f_in, f_out)
        except ImportError:
            logger.warning("zstandard not installed, falling back to gzip")
            self._compress_gzip(input_path, output_path.replace(".zst", ".gz"))

    def _compress_lz4(self, input_path: str, output_path: str):
        try:
            import lz4.frame
            with open(input_path, "rb") as f_in:
                with lz4.frame.open(output_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        except ImportError:
            logger.warning("lz4 not installed, falling back to gzip")
            self._compress_gzip(input_path, output_path.replace(".lz4", ".gz"))

    def _decompress_gzip(self, input_path: str, output_path: str):
        with gzip.open(input_path, "rb") as f_in:
            with open(output_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

    def _decompress_zstd(self, input_path: str, output_path: str):
        try:
            import zstandard as zstd
            dctx = zstd.ZstdDecompressor()
            with open(input_path, "rb") as f_in:
                with open(output_path, "wb") as f_out:
                    dctx.copy_stream(f_in, f_out)
        except ImportError:
            shutil.copy2(input_path, output_path)

    def _decompress_lz4(self, input_path: str, output_path: str):
        try:
            import lz4.frame
            with lz4.frame.open(input_path, "rb") as f_in:
                with open(output_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        except ImportError:
            shutil.copy2(input_path, output_path)
