# kyc/aml/urls.py  ── WORLD #1
from django.urls import path
from . import views

urlpatterns = [
    path('admin/<int:kyc_id>/screen/',       views.run_aml_screening,       name='kyc-aml-screen'),
    path('admin/<int:kyc_id>/history/',      views.aml_screening_history,   name='kyc-aml-history'),
    path('admin/alerts/',                    views.aml_alerts_list,         name='kyc-aml-alerts'),
    path('admin/alerts/<int:alert_id>/resolve/', views.aml_resolve_alert,  name='kyc-aml-resolve'),
    path('admin/screening/<int:screening_id>/false-positive/', views.aml_false_positive, name='kyc-aml-fp'),
]
