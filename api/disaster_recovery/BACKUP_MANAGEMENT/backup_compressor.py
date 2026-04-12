"""
Backup Compressor — Compresses backup files using gzip/zstd/lz4
"""
import gzip
import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class BackupCompressor:
    ALGORITHMS = ("gzip", "zstd", "lz4")

    def __init__(self, algorithm: str = "gzip", level: int = 6):
        if algorithm not in self.ALGORITHMS:
            raise ValueError(f"Unsupported algorithm: {algorithm}. Choose from {self.ALGORITHMS}")
        self.algorithm = algorithm
        self.level = level

    def compress(self, source_path: str, output_path: str = None) -> dict:
        if not output_path:
            output_path = source_path + self._extension()
        logger.info(f"Compressing {source_path} -> {output_path} ({self.algorithm})")
        original_size = os.path.getsize(source_path)
        if self.algorithm == "gzip":
            self._gzip_compress(source_path, output_path)
        elif self.algorithm == "zstd":
            self._zstd_compress(source_path, output_path)
        elif self.algorithm == "lz4":
            self._lz4_compress(source_path, output_path)
        compressed_size = os.path.getsize(output_path)
        ratio = round(compressed_size / original_size, 4) if original_size else 1.0
        logger.info(f"Compression complete: {original_size} -> {compressed_size} bytes (ratio={ratio})")
        return {
            "output_path": output_path,
            "original_size_bytes": original_size,
            "compressed_size_bytes": compressed_size,
            "compression_ratio": ratio,
            "algorithm": self.algorithm,
        }

    def decompress(self, source_path: str, output_path: str) -> str:
        logger.info(f"Decompressing {source_path} -> {output_path}")
        if source_path.endswith(".gz"):
            with gzip.open(source_path, "rb") as f_in, open(output_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        elif source_path.endswith(".zst"):
            subprocess.run(["zstd", "-d", source_path, "-o", output_path], check=True)
        elif source_path.endswith(".lz4"):
            subprocess.run(["lz4", "-d", source_path, output_path], check=True)
        else:
            shutil.copy2(source_path, output_path)
        return output_path

    def _gzip_compress(self, src: str, dst: str):
        with open(src, "rb") as f_in, gzip.open(dst, "wb", compresslevel=self.level) as f_out:
            shutil.copyfileobj(f_in, f_out)

    def _zstd_compress(self, src: str, dst: str):
        try:
            subprocess.run(["zstd", f"-{self.level}", src, "-o", dst, "-f"], check=True, capture_output=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            self._gzip_compress(src, dst.replace(".zst", ".gz"))

    def _lz4_compress(self, src: str, dst: str):
        try:
            subprocess.run(["lz4", f"-{self.level}", src, dst], check=True, capture_output=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            self._gzip_compress(src, dst.replace(".lz4", ".gz"))

    def _extension(self) -> str:
        return {"gzip": ".gz", "zstd": ".zst", "lz4": ".lz4"}.get(self.algorithm, ".gz")
