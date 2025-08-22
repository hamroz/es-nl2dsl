from django.urls import path
from . import views

urlpatterns = [
    # Scenario management
    path('scenarios/', views.EvaluationScenarioListView.as_view(), name='evaluation-scenarios'),
    
    # Evaluation runs
    path('runs/', views.EvaluationRunListView.as_view(), name='evaluation-runs'),
    path('runs/scenario/<str:scenario_id>/', views.run_scenario_evaluation, name='run-scenario-evaluation'),
    
    # Batch evaluations
    path('batches/', views.EvaluationBatchListView.as_view(), name='evaluation-batches'),
    path('batches/run/', views.run_batch_evaluation, name='run-batch-evaluation'),
    
    # Metrics
    path('metrics/', views.get_evaluation_metrics, name='evaluation-metrics'),
]