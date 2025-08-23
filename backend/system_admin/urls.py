from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.SystemHealthView.as_view(), name='system-health'),
    path('indices/', views.AvailableIndicesView.as_view(), name='available-indices'),
    path('models/', views.AvailableModelsView.as_view(), name='available-models'),
    path('status/', views.SystemStatusView.as_view(), name='system-status'),
    # CRITICAL: Add missing endpoints that frontend expects
    path('metrics/', views.SystemMetricsView.as_view(), name='system-metrics'),
    path('analytics/', views.SystemAnalyticsView.as_view(), name='system-analytics'),
    path('custom-metrics/', views.CustomMetricsView.as_view(), name='custom-metrics'),
    path('analytics/export/', views.AnalyticsExportView.as_view(), name='analytics-export'),
]