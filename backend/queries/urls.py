from django.urls import path
from . import views

urlpatterns = [
    # Query generation and listing
    path('', views.QueryListCreateView.as_view(), name='query-list-create'),
    
    # Query task management - using 'tasks' for clarity
    path('tasks/<uuid:task_id>/', views.QueryDetailView.as_view(), name='query-task-detail'),
    path('tasks/<uuid:task_id>/execute/', views.QueryExecuteView.as_view(), name='query-task-execute'),
    path('tasks/<uuid:task_id>/export/<str:format>/', views.QueryExportView.as_view(), name='query-task-export'),
    
    # Legacy support for existing API calls (backward compatibility)
    path('<str:task_id>/', views.QueryDetailView.as_view(), name='query-detail-legacy'),
    path('<str:task_id>/execute/', views.QueryExecuteView.as_view(), name='query-execute-legacy'),
    path('<str:task_id>/export/<str:format>/', views.QueryExportView.as_view(), name='query-export-legacy'),
]