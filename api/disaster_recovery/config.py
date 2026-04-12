"""
Configuration for Disaster Recovery System
"""
import os
from functools import lru_cache
from pydantic import BaseSettings, validator
from typing import List, Optional


class DatabaseSettings(BaseSettings):
    url: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/dr_db")
    pool_size: int = 20
    max_overflow: int = 10
    pool_timeout: int = 30
    echo: bool = False

    class Config:
        env_prefix = "DB_"


class RedisSettings(BaseSettings):
    url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    max_connections: int = 100
    decode_responses: bool = True

    class Config:
        env_prefix = "REDIS_"


class AWSSettings(BaseSettings):
    access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    region: str = os.getenv("AWS_REGION", "us-east-1")
    s3_bucket: str = os.getenv("AWS_S3_BACKUP_BUCKET", "dr-backups")
    glacier_vault: str = os.getenv("AWS_GLACIER_VAULT", "dr-archive")

    class Config:
        env_prefix = "AWS_"


class AzureSettings(BaseSettings):
    connection_string: str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    container_name: str = os.getenv("AZURE_CONTAINER_NAME", "dr-backups")
    account_name: str = os.getenv("AZURE_STORAGE_ACCOUNT", "")

    class Config:
        env_prefix = "AZURE_"


class GCPSettings(BaseSettings):
    project_id: str = os.getenv("GCP_PROJECT_ID", "")
    credentials_file: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    bucket_name: str = os.getenv("GCP_BUCKET_NAME", "dr-backups")

    class Config:
        env_prefix = "GCP_"


class EncryptionSettings(BaseSettings):
    master_key: str = os.getenv("ENCRYPTION_MASTER_KEY", "")
    algorithm: str = "AES-256-GCM"
    key_rotation_days: int = 90

    class Config:
        env_prefix = "ENCRYPTION_"


class NotificationSettings(BaseSettings):
    slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
    pagerduty_api_key: str = os.getenv("PAGERDUTY_API_KEY", "")
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = 587
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    alert_emails: List[str] = []

    class Config:
        env_prefix = "NOTIFICATION_"


class Settings(BaseSettings):
    # App
    app_name: str = "Disaster Recovery System"
    environment: str = os.getenv("ENVIRONMENT", "production")
    debug: bool = False
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    # Sub-settings
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    aws: AWSSettings = AWSSettings()
    azure: AzureSettings = AzureSettings()
    gcp: GCPSettings = GCPSettings()
    encryption: EncryptionSettings = EncryptionSettings()
    notifications: NotificationSettings = NotificationSettings()

    # DR specific
    default_rto_seconds: int = 3600
    default_rpo_seconds: int = 900
    health_check_interval: int = 30
    backup_storage_path: str = "/var/backups/dr"
    enable_auto_failover: bool = True
    enable_auto_backup: bool = True
    enable_encryption: bool = True

    # Celery
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

    class Config:
        env_file = ".env"
        case_sensitive = False

    @validator("environment")
    def validate_environment(cls, v):
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
