# kyc/workflow/urls.py  ── WORLD #1
from django.urls import path
from . import views

urlpatterns = [
    path('',                      views.workflow_list,      name='kyc-workflows'),
    path('templates/',            views.workflow_templates,  name='kyc-workflow-templates'),
    path('<int:wf_id>/',          views.workflow_detail,    name='kyc-workflow-detail'),
    path('<int:wf_id>/activate/', views.workflow_activate,  name='kyc-workflow-activate'),
    path('<int:wf_id>/run/',      views.workflow_run,       name='kyc-workflow-run'),
    path('<int:wf_id>/runs/',     views.workflow_runs,      name='kyc-workflow-runs'),
]
