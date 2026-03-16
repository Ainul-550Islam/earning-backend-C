# api/security/utils/__init__.py

# আপনার অন্যান্য ইউটিলিটি ইমপোর্ট
from .cache_manager import *
from .device import *

# views.py যে ক্লাসগুলো খুঁজছে সেগুলো এখানে ডিফাইন বা ইমপোর্ট করে দিন
import logging
from typing import Any, Dict

class NullSafe:
    @staticmethod
    def get_value(data: Any, key: str, default: Any = "") -> Any:
        try:
            if isinstance(data, dict):
                return data.get(key, default)
            return getattr(data, key, default)
        except Exception:
            return default

class TypeValidator:
    @staticmethod
    def is_valid(value: Any, expected_type: type) -> bool:
        return isinstance(value, expected_type)

class GracefulDegradation:
    @staticmethod
    def safe_execute(func, *args, **kwargs) -> Dict[str, Any]:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return {"error": str(e), "status": "degraded"}