from django.urls import re_path
from queries.consumers import QueryProgressConsumer
from evaluation.consumers import EvaluationProgressConsumer
from security.consumers import SecurityTestProgressConsumer
from data_management.consumers import DataIngestionProgressConsumer

websocket_urlpatterns = [
    re_path(r'ws/queries/(?P<task_id>\w+)/$', QueryProgressConsumer.as_asgi()),
    re_path(r'ws/evaluation/(?P<run_id>\w+)/$', EvaluationProgressConsumer.as_asgi()),
    re_path(r'ws/security/(?P<test_id>\w+)/$', SecurityTestProgressConsumer.as_asgi()),
    re_path(r'ws/data/(?P<task_id>\w+)/$', DataIngestionProgressConsumer.as_asgi()),
]