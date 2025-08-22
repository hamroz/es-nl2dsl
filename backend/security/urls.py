from django.urls import path
from . import views

urlpatterns = [
    # Adversarial prompts
    path('prompts/', views.AdversarialPromptListView.as_view(), name='adversarial-prompts'),
    
    # Security tests
    path('tests/', views.SecurityTestListView.as_view(), name='security-tests'),
    path('tests/run/', views.run_security_test, name='run-security-test'),
    
    # Test results
    path('results/', views.SecurityTestResultListView.as_view(), name='security-test-results'),
    
    # Metrics
    path('metrics/', views.get_security_metrics, name='security-metrics'),
]