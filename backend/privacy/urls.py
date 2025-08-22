from django.urls import path
from . import views

urlpatterns = [
    path('dp-config/', views.DPConfigView.as_view(), name='dp-config'),
    path('analysis/', views.PrivacyAnalysisView.as_view(), name='privacy-analysis'),
]