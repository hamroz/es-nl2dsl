"""
URL configuration for es_nl2dsl_api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # Authentication endpoints
    path("api/v1/auth/", include("authentication.urls")),
    # Analytics endpoints
    path("api/v1/analytics/", include("analytics.urls")),
    # Application endpoints (now require authentication)
    path("api/v1/queries/", include("queries.urls")),
    path("api/v1/evaluation/", include("evaluation.urls")),
    path("api/v1/security/", include("security.urls")),
    path("api/v1/privacy/", include("privacy.urls")),
    path("api/v1/data/", include("data_management.urls")),
    path("api/v1/system/", include("system_admin.urls")),
]
