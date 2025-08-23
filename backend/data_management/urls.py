from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.DataUploadView.as_view(), name='data-upload'),
    path('indices/', views.IndicesView.as_view(), name='indices'),
    path('indices/<str:index_name>/', views.IndexDetailView.as_view(), name='index-detail'),
    path('cic-process/', views.CICProcessView.as_view(), name='cic-process'),
    # CRITICAL: Add missing endpoint that frontend expects
    path('tasks/', views.DataTasksView.as_view(), name='data-tasks'),
]