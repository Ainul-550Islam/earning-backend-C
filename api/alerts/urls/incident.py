# alerts/urls/incident.py  — FIXED: all missing viewset actions now exposed
from django.urls import path
from ..viewsets import incident as viewsets_incident

app_name = 'incident'

urlpatterns = [
    # ── Incidents ────────────────────────────────────────────────────────────
    path('', viewsets_incident.IncidentViewSet.as_view({'get': 'list', 'post': 'create'}), name='incident-list'),
    path('<int:pk>/', viewsets_incident.IncidentViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='incident-detail'),
    path('<int:pk>/acknowledge/', viewsets_incident.IncidentViewSet.as_view({'post': 'acknowledge'}), name='incident-acknowledge'),
    path('<int:pk>/identify/', viewsets_incident.IncidentViewSet.as_view({'post': 'identify'}), name='incident-identify'),
    path('<int:pk>/resolve/', viewsets_incident.IncidentViewSet.as_view({'post': 'resolve'}), name='incident-resolve'),
    path('<int:pk>/close/', viewsets_incident.IncidentViewSet.as_view({'post': 'close'}), name='incident-close'),
    path('<int:pk>/escalate/', viewsets_incident.IncidentViewSet.as_view({'post': 'escalate'}), name='incident-escalate'),
    path('<int:pk>/mark-false-positive/', viewsets_incident.IncidentViewSet.as_view({'post': 'mark_false_positive'}), name='incident-mark-false-positive'),   # ADDED
    path('<int:pk>/severity-score/', viewsets_incident.IncidentViewSet.as_view({'get': 'severity_score'}), name='incident-severity-score'),                   # ADDED
    path('<int:pk>/escalation-chain/', viewsets_incident.IncidentViewSet.as_view({'get': 'escalation_chain'}), name='incident-escalation-chain'),             # ADDED
    path('<int:pk>/timeline/', viewsets_incident.IncidentViewSet.as_view({'get': 'timeline'}), name='incident-timeline'),
    path('stats/', viewsets_incident.IncidentViewSet.as_view({'get': 'stats'}), name='incident-stats'),                                                        # ADDED
    path('by_severity/<str:severity>/', viewsets_incident.IncidentViewSet.as_view({'get': 'by_severity'}), name='incident-by-severity'),
    path('by_status/<str:status>/', viewsets_incident.IncidentViewSet.as_view({'get': 'by_status'}), name='incident-by-status'),
    path('active/', viewsets_incident.IncidentViewSet.as_view({'get': 'active'}), name='incident-active'),
    path('overdue/', viewsets_incident.IncidentViewSet.as_view({'get': 'overdue'}), name='incident-overdue'),

    # ── Incident Timeline ────────────────────────────────────────────────────
    path('timelines/', viewsets_incident.IncidentTimelineViewSet.as_view({'get': 'list', 'post': 'create'}), name='incident-timeline-list'),
    path('timelines/<int:pk>/', viewsets_incident.IncidentTimelineViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='incident-timeline-detail'),
    path('timelines/<int:pk>/add-event/', viewsets_incident.IncidentTimelineViewSet.as_view({'post': 'add_event'}), name='incident-timeline-add-event'),          # ADDED
    path('timelines/<int:pk>/add_participant/', viewsets_incident.IncidentTimelineViewSet.as_view({'post': 'add_participant'}), name='incident-timeline-add-participant'),
    path('timelines/by_incident/<int:incident_id>/', viewsets_incident.IncidentTimelineViewSet.as_view({'get': 'by_incident'}), name='incident-timeline-by-incident'),
    path('timelines/by_type/<str:type>/', viewsets_incident.IncidentTimelineViewSet.as_view({'get': 'by_type'}), name='incident-timeline-by-type'),

    # ── Incident Responders ──────────────────────────────────────────────────
    path('responders/', viewsets_incident.IncidentResponderViewSet.as_view({'get': 'list', 'post': 'create'}), name='incident-responder-list'),
    path('responders/<int:pk>/', viewsets_incident.IncidentResponderViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='incident-responder-detail'),
    path('responders/<int:pk>/activate/', viewsets_incident.IncidentResponderViewSet.as_view({'post': 'activate'}), name='incident-responder-activate'),
    path('responders/<int:pk>/deactivate/', viewsets_incident.IncidentResponderViewSet.as_view({'post': 'deactivate'}), name='incident-responder-deactivate'),
    path('responders/<int:pk>/complete/', viewsets_incident.IncidentResponderViewSet.as_view({'post': 'complete'}), name='incident-responder-complete'),
    path('responders/by_incident/<int:incident_id>/', viewsets_incident.IncidentResponderViewSet.as_view({'get': 'by_incident'}), name='incident-responder-by-incident'),
    path('responders/by_role/<str:role>/', viewsets_incident.IncidentResponderViewSet.as_view({'get': 'by_role'}), name='incident-responder-by-role'),

    # ── Post-Mortem ──────────────────────────────────────────────────────────
    path('postmortems/', viewsets_incident.IncidentPostMortemViewSet.as_view({'get': 'list', 'post': 'create'}), name='incident-postmortem-list'),
    path('postmortems/<int:pk>/', viewsets_incident.IncidentPostMortemViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='incident-postmortem-detail'),
    path('postmortems/<int:pk>/submit_for_review/', viewsets_incident.IncidentPostMortemViewSet.as_view({'post': 'submit_for_review'}), name='incident-postmortem-submit-for-review'),
    path('postmortems/<int:pk>/approve/', viewsets_incident.IncidentPostMortemViewSet.as_view({'post': 'approve'}), name='incident-postmortem-approve'),
    path('postmortems/<int:pk>/reject/', viewsets_incident.IncidentPostMortemViewSet.as_view({'post': 'reject'}), name='incident-postmortem-reject'),
    path('postmortems/<int:pk>/publish/', viewsets_incident.IncidentPostMortemViewSet.as_view({'post': 'publish'}), name='incident-postmortem-publish'),
    path('postmortems/<int:pk>/completion-score/', viewsets_incident.IncidentPostMortemViewSet.as_view({'get': 'completion_score'}), name='incident-postmortem-completion-score'),  # ADDED
    path('postmortems/by_status/<str:status>/', viewsets_incident.IncidentPostMortemViewSet.as_view({'get': 'by_status'}), name='incident-postmortem-by-status'),
    path('postmortems/by_incident/<int:incident_id>/', viewsets_incident.IncidentPostMortemViewSet.as_view({'get': 'by_incident'}), name='incident-postmortem-by-incident'),

    # ── On-Call Schedules ────────────────────────────────────────────────────
    path('oncall_schedules/', viewsets_incident.OnCallScheduleViewSet.as_view({'get': 'list', 'post': 'create'}), name='oncall-schedule-list'),
    path('oncall_schedules/<int:pk>/', viewsets_incident.OnCallScheduleViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='oncall-schedule-detail'),
    path('oncall_schedules/<int:pk>/rotate/', viewsets_incident.OnCallScheduleViewSet.as_view({'post': 'rotate'}), name='oncall-schedule-rotate'),
    path('oncall_schedules/<int:pk>/current_oncall/', viewsets_incident.OnCallScheduleViewSet.as_view({'get': 'current_oncall'}), name='oncall-schedule-current-oncall'),
    path('oncall_schedules/<int:pk>/current-on-call/', viewsets_incident.OnCallScheduleViewSet.as_view({'get': 'current_on_call'}), name='oncall-schedule-current-on-call'),          # ADDED
    path('oncall_schedules/<int:pk>/upcoming-schedule/', viewsets_incident.OnCallScheduleViewSet.as_view({'get': 'upcoming_schedule'}), name='oncall-schedule-upcoming'),              # ADDED
    path('oncall_schedules/<int:pk>/availability/', viewsets_incident.OnCallScheduleViewSet.as_view({'get': 'availability'}), name='oncall-schedule-availability'),                    # ADDED
    path('oncall_schedules/<int:pk>/next_rotation/', viewsets_incident.OnCallScheduleViewSet.as_view({'get': 'next_rotation'}), name='oncall-schedule-next-rotation'),
    path('oncall_schedules/<int:pk>/add_user/', viewsets_incident.OnCallScheduleViewSet.as_view({'post': 'add_user'}), name='oncall-schedule-add-user'),
    path('oncall_schedules/<int:pk>/remove_user/', viewsets_incident.OnCallScheduleViewSet.as_view({'post': 'remove_user'}), name='oncall-schedule-remove-user'),
    path('oncall_schedules/<int:pk>/is_oncall/<int:user_id>/', viewsets_incident.OnCallScheduleViewSet.as_view({'get': 'is_oncall'}), name='oncall-schedule-is-oncall'),
    path('oncall_schedules/<int:pk>/is-on-call/', viewsets_incident.OnCallScheduleViewSet.as_view({'get': 'is_on_call'}), name='oncall-schedule-is-on-call'),                         # ADDED
    path('oncall_schedules/all-current-on-call/', viewsets_incident.OnCallScheduleViewSet.as_view({'get': 'all_current_on_call'}), name='oncall-schedule-all-current'),               # ADDED
    path('oncall_schedules/by_type/<str:type>/', viewsets_incident.OnCallScheduleViewSet.as_view({'get': 'by_type'}), name='oncall-schedule-by-type'),
    path('oncall_schedules/active/', viewsets_incident.OnCallScheduleViewSet.as_view({'get': 'active'}), name='oncall-schedule-active'),
]
