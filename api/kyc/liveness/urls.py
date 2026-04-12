# kyc/liveness/urls.py  ── WORLD #1
from django.urls import path
from . import views

urlpatterns = [
    path('check/',         views.run_liveness_check,  name='kyc-liveness-check'),
    path('history/',       views.my_liveness_history, name='kyc-liveness-history'),
    path('admin/',         views.liveness_admin_list, name='kyc-liveness-admin'),
]
