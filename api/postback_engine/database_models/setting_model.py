"""
database_models/setting_model.py
──────────────────────────────────
Runtime settings stored in DB with Redis cache.
"""
from django.db import models

class PostbackEngineSetting(models.Model):
    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.TextField()
    value_type = models.CharField(
        max_length=10, default="str",
        choices=[
            ("str", "String"), ("int", "Integer"),
            ("float", "Float"), ("bool", "Boolean"), ("json", "JSON"),
        ],
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=100, blank=True)

    class Meta:
        app_label = "postback_engine"
        verbose_name = "setting"
        verbose_name_plural = "settings"
        ordering = ["key"]

    def __str__(self):
        return f"{self.key} = {self.value[:50]}"

    def get_value(self):
        import json as _json
        if self.value_type == "int":   return int(self.value)
        if self.value_type == "float": return float(self.value)
        if self.value_type == "bool":  return self.value.lower() in ("true", "1", "yes")
        if self.value_type == "json":  return _json.loads(self.value)
        return self.value

    @classmethod
    def get(cls, key: str, default=None):
        from django.core.cache import cache
        cache_key = f"pe:setting:{key}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            setting = cls.objects.get(key=key, is_active=True)
            value = setting.get_value()
            cache.set(cache_key, value, timeout=300)
            return value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set_value(cls, key: str, value, value_type: str = "str",
                  description: str = "", updated_by: str = "system"):
        import json as _json
        from django.core.cache import cache
        str_value = _json.dumps(value) if value_type == "json" else str(value)
        cls.objects.update_or_create(
            key=key,
            defaults={
                "value": str_value, "value_type": value_type,
                "description": description, "is_active": True, "updated_by": updated_by,
            },
        )
        cache.delete(f"pe:setting:{key}")
