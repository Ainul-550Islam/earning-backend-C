"""
urls/system.py — NEWLY CREATED
Routes for system admin viewsets: Backup, Escalation, Scheduler,
MetricsCollector, Events (all were floating in root-level .py files).
"""
from django.urls import path
from api.alerts.viewsets.system import (
    BackupViewSet, EscalationViewSet, SchedulerViewSet,
    MetricsCollectorViewSet, EventViewSet,
)

app_name = 'system'

urlpatterns = [
    # ── Backup ─────────────────────────────────────────────────────────
    path('backup/',                BackupViewSet.as_view({'get': 'list'}),                   name='backup-list'),
    path('backup/create/',         BackupViewSet.as_view({'post': 'create_backup'}),          name='backup-create'),
    path('backup/restore/',        BackupViewSet.as_view({'post': 'restore'}),                name='backup-restore'),
    path('backup/status/',         BackupViewSet.as_view({'get': 'backup_status'}),           name='backup-status'),
    path('backup/cleanup/',        BackupViewSet.as_view({'post': 'cleanup'}),                name='backup-cleanup'),
    path('backup/stats/',          BackupViewSet.as_view({'get': 'stats'}),                   name='backup-stats'),
    path('backup/verify/',         BackupViewSet.as_view({'post': 'verify'}),                 name='backup-verify'),

    # ── Escalation ─────────────────────────────────────────────────────
    path('escalation/',            EscalationViewSet.as_view({'get': 'list'}),                name='escalation-list'),
    path('escalation/create/',     EscalationViewSet.as_view({'post': 'create_rule'}),        name='escalation-create'),
    path('escalation/trigger/',    EscalationViewSet.as_view({'post': 'trigger'}),            name='escalation-trigger'),
    path('escalation/history/',    EscalationViewSet.as_view({'get': 'history'}),             name='escalation-history'),
    path('escalation/stats/',      EscalationViewSet.as_view({'get': 'escalation_stats'}),    name='escalation-stats'),
    path('escalation/active/',     EscalationViewSet.as_view({'get': 'active_escalations'}),  name='escalation-active'),

    # ── Scheduler ──────────────────────────────────────────────────────
    path('scheduler/',             SchedulerViewSet.as_view({'get': 'list'}),                 name='scheduler-list'),
    path('scheduler/create/',      SchedulerViewSet.as_view({'post': 'create_task'}),         name='scheduler-create'),
    path('scheduler/run/',         SchedulerViewSet.as_view({'post': 'run_now'}),             name='scheduler-run'),
    path('scheduler/pause/',       SchedulerViewSet.as_view({'post': 'pause_task'}),          name='scheduler-pause'),
    path('scheduler/resume/',      SchedulerViewSet.as_view({'post': 'resume_task'}),         name='scheduler-resume'),
    path('scheduler/stats/',       SchedulerViewSet.as_view({'get': 'scheduler_stats'}),      name='scheduler-stats'),
    path('scheduler/due/',         SchedulerViewSet.as_view({'get': 'due_tasks'}),            name='scheduler-due'),
    path('scheduler/delete/',      SchedulerViewSet.as_view({'delete': 'delete_task'}),       name='scheduler-delete'),

    # ── Metrics Collector ──────────────────────────────────────────────
    path('metrics/',               MetricsCollectorViewSet.as_view({'get': 'list'}),          name='metrics-list'),
    path('metrics/collect/',       MetricsCollectorViewSet.as_view({'post': 'collect'}),      name='metrics-collect'),
    path('metrics/system/',        MetricsCollectorViewSet.as_view({'get': 'system_metrics'}), name='metrics-system'),
    path('metrics/alerts/',        MetricsCollectorViewSet.as_view({'get': 'alert_metrics'}), name='metrics-alerts'),
    path('metrics/export/',        MetricsCollectorViewSet.as_view({'get': 'export_metrics'}), name='metrics-export'),

    # ── Events ─────────────────────────────────────────────────────────
    path('events/',                EventViewSet.as_view({'get': 'list'}),                     name='event-list'),
    path('events/trigger/',        EventViewSet.as_view({'post': 'trigger'}),                 name='event-trigger'),
    path('events/history/',        EventViewSet.as_view({'get': 'event_history'}),            name='event-history'),
    path('events/stats/',          EventViewSet.as_view({'get': 'event_stats'}),              name='event-stats'),
    path('events/aggregated/',     EventViewSet.as_view({'get': 'aggregated'}),               name='event-aggregated'),
    path('events/emit/',           EventViewSet.as_view({'post': 'emit'}),                    name='event-emit'),
]
