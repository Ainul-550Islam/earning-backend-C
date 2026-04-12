# alerts/urls/__init__.py
from django.urls import include, path
from . import core, channel, incident, intelligence, reporting, threshold

app_name = 'alerts'

urlpatterns = [
    path('', include(core)),
    path('channel/', include(channel)),
    path('incident/', include(incident)),
    path('intelligence/', include(intelligence)),
    path('reporting/', include(reporting)),
    path('threshold/', include(threshold)),
]
