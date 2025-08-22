from django.urls import path
from . import views

urlpatterns = [
    path('scenarios/', views.ScenarioListView.as_view(), name='scenario-list'),
    path('scenarios/<str:scenario_id>/run/', views.RunEvaluationView.as_view(), name='run-evaluation'),
    path('results/', views.EvaluationResultsView.as_view(), name='evaluation-results'),
]