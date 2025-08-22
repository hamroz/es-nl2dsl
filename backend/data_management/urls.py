from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.DataUploadView.as_view(), name='data-upload'),
    path('indices/', views.IndicesView.as_view(), name='indices'),
    path('cic-process/', views.CICProcessView.as_view(), name='cic-process'),
]