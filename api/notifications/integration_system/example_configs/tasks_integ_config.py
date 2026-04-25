# api/tasks/integ_config.py
"""
Tasks Module — Integration Configuration
"এক কাজের জন্য একটাই মালিক"

Tasks module owns: MasterTask, UserTaskCompletion, AdminLedger
Tasks PUBLISHES events → Notifications, Wallet, Gamification SUBSCRIBE.
"""
from api.notifications.integration_system.module_protocol import (
    ModuleConfig, SignalMap, EventMap, HealthCheck
)

class TasksIntegConfig(ModuleConfig):
    module_name = 'tasks_module'  # 'tasks' is reserved by Celery
    version = '1.0.0'
    description = 'Task/Offer Completion System'

    signal_maps = [
        SignalMap(
            model_path='tasks.UserTaskCompletion',
            field='status',
            value='approved',
            event_type='task.approved',
            user_field='user_id',
            data_fields=['task_id', 'task_title', 'reward_amount', 'currency'],
        ),
        SignalMap(
            model_path='tasks.UserTaskCompletion',
            field='status',
            value='rejected',
            event_type='task.rejected',
            user_field='user_id',
            data_fields=['task_id', 'task_title', 'rejection_reason'],
        ),
        SignalMap(
            model_path='tasks.UserTaskCompletion',
            field='status',
            value='completed',
            event_type='task.completed',
            user_field='user_id',
            data_fields=['task_id', 'task_title'],
            on_created=True,
            on_update=False,
        ),
        SignalMap(
            model_path='tasks.UserTaskCompletion',
            field='status',
            value='expired',
            event_type='task.expired',
            user_field='user_id',
            data_fields=['task_id', 'task_title'],
        ),
        SignalMap(
            model_path='tasks.MasterTask',
            field='is_active',
            value=True,
            event_type='task.new_available',
            user_field=None,
            data_fields=['task_id', 'task_title', 'reward_amount', 'category'],
            on_created=True,
            on_update=False,
        ),
    ]

    event_maps = [
        EventMap(
            event_type='task.approved',
            notification_type='task_approved',
            title_template='Task Approved! +৳{reward_amount} 🎉',
            message_template='"{task_title}" approved। ৳{reward_amount} আপনার wallet এ যোগ হয়েছে।',
            channel='in_app',
            priority='high',
            send_push=True,
        ),
        EventMap(
            event_type='task.rejected',
            notification_type='task_rejected',
            title_template='Task Rejected',
            message_template='"{task_title}" approved হয়নি। কারণ: {rejection_reason}',
            channel='in_app',
            priority='medium',
        ),
        EventMap(
            event_type='task.completed',
            notification_type='task_completed',
            title_template='Task Completed ✅',
            message_template='আপনি "{task_title}" সফলভাবে complete করেছেন।',
            channel='in_app',
            priority='medium',
        ),
    ]

    health_checks = [HealthCheck(name='tasks_db', model_path='tasks.MasterTask')]
    allowed_targets = ['notifications', 'wallet', 'gamification', 'analytics']
