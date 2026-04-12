# kyc/kyb/urls.py  ── WORLD #1
from django.urls import path
from . import views

urlpatterns = [
    # User
    path('my/',          views.my_business,   name='kyb-my-business'),
    path('ubo/',         views.add_ubo,        name='kyb-add-ubo'),
    path('directors/',   views.add_director,   name='kyb-add-director'),
    # Admin
    path('admin/',                            views.kyb_admin_list,   name='kyb-admin-list'),
    path('admin/<int:kyb_id>/',              views.kyb_admin_review, name='kyb-admin-review'),
    path('admin/ubo/<int:ubo_id>/verify/',   views.kyb_verify_ubo,   name='kyb-verify-ubo'),
]
