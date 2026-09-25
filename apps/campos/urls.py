from django.urls import path
from . import views

app_name = 'campos'

urlpatterns = [
    path('', views.CuadrosListView.as_view(), name='cuadros_list'),
    path('cuadros/crear/', views.CuadroCreateView.as_view(), name='cuadro_create'),
    path('cosechas/', views.CosechasListView.as_view(), name='cosechas_list'),
    path('cosechas/crear/', views.CosechaCreateView.as_view(), name='cosecha_create'),
    path('fenologia/crear/', views.RegistroFenologicoCreateView.as_view(), name='fenologia_create'),
    path('eventos/crear/', views.EventoCuadroCreateView.as_view(), name='evento_create'),
    
    # Órdenes de Trabajo
    path('orden-trabajo/', views.OrdenTrabajoView.as_view(), name='orden_trabajo'),
    path('orden-trabajo/guardar/', views.OrdenTrabajoGuardarView.as_view(), name='orden_trabajo_guardar'),
    path('orden-trabajo/estado/', views.OrdenTrabajoCambiarEstadoView.as_view(), name='orden_trabajo_estado'),

    # Excel Exports
    path('cuadros/exportar/', views.ExportarCuadrosExcelView.as_view(), name='exportar_cuadros'),
    path('orden-trabajo/exportar/', views.ExportarOrdenTrabajoExcelView.as_view(), name='exportar_ordenes_trabajo'),

]
