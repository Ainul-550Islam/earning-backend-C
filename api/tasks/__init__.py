"""
api/tasks/__init__.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"এক কাজের জন্য একটাই মালিক: api.tasks"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This is the SINGLE OWNER of all Celery tasks in the platform.

All other apps (wallet, notifications, gamification, etc.)
import their tasks FROM HERE. They do not define task logic.

Architecture:
    api/tasks/
    ├── *_tasks.py           ← All 71 task files (business logic here)
    ├── integration/         ← EventBus, DataBridge, SharedContext
    ├── models/              ← TaskMonitor, Workflow, DLQ, Analytics
    ├── services/            ← Business services
    ├── viewsets/            ← DRF API endpoints for task management
    └── management/commands/ ← Django management commands

Usage from other apps:
    from api.tasks.wallet_tasks import process_pending_withdrawals
    from api.tasks.notification_tasks import send_notification_task
    from api.tasks.integration import EventBus, DataBridge

DO NOT add @shared_task functions to other apps' tasks.py files.
"""

default_app_config = 'api.tasks.apps.TasksConfig'
