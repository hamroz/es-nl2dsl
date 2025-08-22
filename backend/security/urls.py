from django.urls import path
from . import views

urlpatterns = [
    path('test/', views.SecurityTestView.as_view(), name='security-test'),
    path('test/<str:test_id>/', views.SecurityTestResultView.as_view(), name='security-test-result'),
]