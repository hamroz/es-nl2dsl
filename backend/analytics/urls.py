from django.urls import path
from . import views

urlpatterns = [
    # Main analytics endpoints
    path('', views.AnalyticsAPIView.as_view(), name='analytics_data'),
    path('export/', views.AnalyticsExportView.as_view(), name='analytics_export'),
    path('summary/', views.analytics_summary, name='analytics_summary'),
    
    # Custom metrics
    path('custom-metrics/', views.CustomMetricsView.as_view(), name='custom_metrics'),
    path('custom-metrics/<uuid:pk>/', views.CustomMetricDetailView.as_view(), name='custom_metric_detail'),
    path('custom-metrics/<uuid:pk>/execute/', views.ExecuteCustomMetricView.as_view(), name='execute_custom_metric'),
    
    # Alert rules
    path('alert-rules/', views.AlertRulesView.as_view(), name='alert_rules'),
    path('alert-rules/<uuid:pk>/', views.AlertRulesView.as_view(), name='alert_rule_detail'),
    
    # Alerts
    path('alerts/', views.AlertsView.as_view(), name='alerts'),
    path('alerts/<uuid:pk>/', views.AlertDetailView.as_view(), name='alert_detail'),
    path('alerts/<uuid:pk>/acknowledge/', views.acknowledge_alert, name='acknowledge_alert'),
    path('alerts/<uuid:pk>/resolve/', views.resolve_alert, name='resolve_alert'),
]