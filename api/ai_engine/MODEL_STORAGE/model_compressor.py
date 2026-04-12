"""
api/ai_engine/MODEL_STORAGE/model_compressor.py
================================================
Model Compressor — model size reduction।
gzip, bz2, quantization-based compression।
Storage cost reduction, faster transfer।
"""
import os, gzip, bz2, shutil, logging
from typing import Optional
logger = logging.getLogger(__name__)

class ModelCompressor:
    """Model file compression engine।"""

    METHODS = ["gzip", "bz2", "lzma"]

    @staticmethod
    def compress(input_path: str, method: str = "gzip",
                 output_path: str = None) -> str:
        ext_map = {"gzip": ".gz", "bz2": ".bz2", "lzma": ".xz"}
        ext     = ext_map.get(method, ".gz")
        output_path = output_path or input_path + ext
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        if method == "gzip":
            with open(input_path, "rb") as f_in:
                with gzip.open(output_path, "wb", compresslevel=6) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif method == "bz2":
            with open(input_path, "rb") as f_in:
                with bz2.open(output_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif method == "lzma":
            import lzma
            with open(input_path, "rb") as f_in:
                with lzma.open(output_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

        orig_mb   = os.path.getsize(input_path)  / 1024 / 1024
        comp_mb   = os.path.getsize(output_path) / 1024 / 1024
        ratio     = round(comp_mb / max(orig_mb, 0.001) * 100, 2)
        logger.info(f"Compressed {orig_mb:.2f}MB → {comp_mb:.2f}MB ({ratio}%) [{method}]")
        return output_path

    @staticmethod
    def decompress(input_path: str, output_path: str = None) -> str:
        if input_path.endswith(".gz"):
            opener  = gzip.open
        elif input_path.endswith(".bz2"):
            opener  = bz2.open
        elif input_path.endswith(".xz"):
            import lzma
            opener  = lzma.open
        else:
            raise ValueError(f"Unknown compression format: {input_path}")

        output_path = output_path or input_path.rsplit(".", 1)[0]
        with opener(input_path, "rb") as f_in:
            with open(output_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        return output_path

    @staticmethod
    def get_compression_ratio(original: str, compressed: str) -> dict:
        orig_size = os.path.getsize(original)
        comp_size = os.path.getsize(compressed)
        return {
            "original_mb":    round(orig_size / 1024 / 1024, 3),
            "compressed_mb":  round(comp_size / 1024 / 1024, 3),
            "ratio_pct":      round(comp_size / max(orig_size, 1) * 100, 2),
            "saved_mb":       round((orig_size - comp_size) / 1024 / 1024, 3),
        }

    @staticmethod
    def best_compression(input_path: str) -> dict:
        """সব methods test করে best compression খুঁজো।"""
        results = []
        for method in ModelCompressor.METHODS:
            try:
                out = f"/tmp/test_compress_{method}"
                ModelCompressor.compress(input_path, method, out)
                size = os.path.getsize(out)
                results.append({"method": method, "size": size, "path": out})
                os.remove(out)
            except Exception as e:
                logger.warning(f"Compression test failed [{method}]: {e}")
        if results:
            best = min(results, key=lambda x: x["size"])
            return {"best_method": best["method"], "all_results": results}
        return {"best_method": "gzip"}
