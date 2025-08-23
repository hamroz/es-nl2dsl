from django.urls import path
from rest_framework_simplejwt.views import TokenVerifyView
from . import views, session_views, admin_views

urlpatterns = [
    # Authentication endpoints
    path('login/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', views.CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    
    # User management
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),
    path('change-password/', views.PasswordChangeView.as_view(), name='change_password'),
    path('permissions/', views.UserPermissionsView.as_view(), name='user_permissions'),
    
    # Admin user management
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/<uuid:pk>/', views.UserDetailView.as_view(), name='user_detail'),
    path('users/<str:user_id>/terminate-sessions/', session_views.UserSessionsTerminateView.as_view(), name='user_sessions_terminate'),
    
    # Enhanced session management
    path('sessions/', session_views.SessionListView.as_view(), name='session_list'),
    path('sessions/<str:session_id>/', session_views.SessionDetailView.as_view(), name='session_detail'),
    path('sessions/<str:session_id>/terminate/', session_views.SessionTerminateView.as_view(), name='session_terminate'),
    path('session-analytics/', session_views.SessionAnalyticsView.as_view(), name='session_analytics'),
    
    # Security policies
    path('security-policies/', session_views.SecurityPolicyListView.as_view(), name='security_policy_list'),
    path('security-policies/<str:policy_id>/', session_views.SecurityPolicyDetailView.as_view(), name='security_policy_detail'),
    path('policy-evaluation/', session_views.PolicyEvaluationView.as_view(), name='policy_evaluation'),
    path('initialize-policies/', session_views.InitializePoliciesView.as_view(), name='initialize_policies'),
    
    # Admin dashboard endpoints
    path('admin/system-health/', admin_views.SystemHealthView.as_view(), name='admin_system_health'),
    path('admin/system-stats/', admin_views.SystemStatsView.as_view(), name='admin_system_stats'),
    path('admin/metrics-history/', admin_views.MetricsHistoryView.as_view(), name='admin_metrics_history'),
    path('admin/performance-metrics/', admin_views.PerformanceMetricsView.as_view(), name='admin_performance_metrics'),
    path('admin/security-events/', admin_views.SecurityEventsView.as_view(), name='admin_security_events'),
    path('admin/threat-analysis/', admin_views.ThreatAnalysisView.as_view(), name='admin_threat_analysis'),
    path('admin/security-configuration/', admin_views.SecurityConfigurationView.as_view(), name='admin_security_config'),
    path('admin/maintenance/<str:action>/', admin_views.MaintenanceView.as_view(), name='admin_maintenance'),
    path('admin/security/block-ip/', admin_views.SecurityActionView.as_view(), name='admin_block_ip'),
    path('admin/security/unblock-ip/', admin_views.SecurityActionView.as_view(), name='admin_unblock_ip'),
    
    # Audit logs
    path('audit-logs/', views.AuditLogListView.as_view(), name='audit_logs'),
    path('audit-logs/export/', views.AuditLogExportView.as_view(), name='audit_logs_export'),
    
    # Tenant and Workspace management
    path('tenants/', views.TenantListView.as_view(), name='tenant_list'),
    path('workspaces/', views.WorkspaceListView.as_view(), name='workspace_list'),
    
    # Health check
    path('health/', views.health_check, name='health_check'),
]