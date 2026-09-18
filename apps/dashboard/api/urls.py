from django.urls import path
from .views import DashboardKPIView

urlpatterns = [
    path('dashboard/kpis/', DashboardKPIView.as_view(), name='dashboard-kpis'),
]
