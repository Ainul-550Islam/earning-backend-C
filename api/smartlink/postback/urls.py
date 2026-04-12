from django.urls import path
from .views import PostbackView, PostbackPixelView

urlpatterns = [
    path('postback/', PostbackView.as_view(), name='postback'),
    path('pixel/', PostbackPixelView.as_view(), name='postback-pixel'),
]
