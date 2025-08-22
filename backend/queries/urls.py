from django.urls import path
from . import views

urlpatterns = [
    path('', views.QueryListCreateView.as_view(), name='query-list-create'),
    path('<str:task_id>/', views.QueryDetailView.as_view(), name='query-detail'),
    path('<str:task_id>/execute/', views.QueryExecuteView.as_view(), name='query-execute'),
    path('<str:task_id>/export/<str:format>/', views.QueryExportView.as_view(), name='query-export'),
]