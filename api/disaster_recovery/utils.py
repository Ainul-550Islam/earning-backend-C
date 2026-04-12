"""Utility Functions for Disaster Recovery System."""
import hashlib, os, uuid, logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
logger = logging.getLogger(__name__)

def generate_id() -> str:
    return str(uuid.uuid4())

def compute_sha256(file_path: str) -> str:
    """Compute SHA-256 checksum synchronously (use in Celery tasks)."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

async def compute_sha256_async(file_path: str) -> str:
    """
    Non-blocking SHA-256 checksum for use in async Django views.
    Delegates the blocking file I/O to a thread executor.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, compute_sha256, file_path)

def format_bytes(size_bytes: int) -> str:
    for unit in ["B","KB","MB","GB","TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

def seconds_to_human(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds/60:.1f}m"
    return f"{seconds/3600:.1f}h"

def safe_json(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    raise TypeError(f"Not serializable: {type(obj)}")

def build_storage_path(backup_type: str, database: str, job_id: str, ext: str = ".dump") -> str:
    date = datetime.utcnow().strftime("%Y/%m/%d")
    return f"backups/{backup_type}/{database}/{date}/{job_id}{ext}"

def retry(max_attempts: int = 3, delay: float = 1.0, exceptions=(Exception,)):
    import time, functools
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        raise
                    logger.warning(
                        "dr.retry",
                        extra={"fn": fn.__name__, "attempt": attempt, "error": str(e)},
                    )
                    time.sleep(delay * attempt)
        return wrapper
    return decorator
