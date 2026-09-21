from django.urls import path
from . import views

app_name = 'costos'

urlpatterns = [
    path('', views.CostosDashboardView.as_view(), name='dashboard'),
    path('exportar/', views.ExportarCostosCSVView.as_view(), name='exportar_csv'),
    path('crear/', views.CostoCreateView.as_view(), name='crear'),
    path('<int:pk>/editar/', views.CostoUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.CostoDeleteView.as_view(), name='eliminar'),
    path('<int:pk>/prorratear/', views.CostoProrratearView.as_view(), name='prorratear'),
    path('sincronizar-pl/', views.SincronizarCostosPLView.as_view(), name='sincronizar_pl'),
]
