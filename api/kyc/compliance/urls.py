# kyc/compliance/urls.py  ── WORLD #1
from django.urls import path
from . import views

urlpatterns = [
    # User-facing GDPR
    path('gdpr/erasure/',      views.request_gdpr_erasure, name='kyc-gdpr-erasure'),
    path('gdpr/export/',       views.request_data_export,  name='kyc-gdpr-export'),
    path('gdpr/consent/',      views.log_consent,          name='kyc-gdpr-consent'),
    path('gdpr/my-consents/',  views.my_consents,          name='kyc-gdpr-my-consents'),
    # Admin
    path('admin/gdpr/',                           views.gdpr_requests_list, name='kyc-gdpr-list'),
    path('admin/gdpr/<int:request_id>/process/',  views.process_erasure,    name='kyc-gdpr-process'),
    path('admin/cdd/',                            views.cdd_list,           name='kyc-cdd-list'),
]
