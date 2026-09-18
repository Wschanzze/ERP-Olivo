from django.urls import path
from . import views

app_name = 'costos'

urlpatterns = [
    path('', views.CostosDashboardView.as_view(), name='dashboard'),
]
