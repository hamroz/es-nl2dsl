from django.urls import path
from system_admin import consumers

websocket_urlpatterns = [
    path('ws/progress/', consumers.ProgressConsumer.as_asgi()),
]