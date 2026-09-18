from django.urls import path
from . import views

app_name = 'inventario'

urlpatterns = [
    path('', views.InsumosListView.as_view(), name='insumos_list'),
    path('insumos/crear/', views.InsumoCreateView.as_view(), name='insumo_create'),
    path('movimientos/', views.MovimientosStockListView.as_view(), name='movimientos_list'),
    path('movimientos/crear/', views.MovimientoStockCreateView.as_view(), name='movimiento_create'),
    path('maquinas/', views.MaquinasListView.as_view(), name='maquinas_list'),
    path('maquinas/crear/', views.MaquinaCreateView.as_view(), name='maquina_create'),
    path('remitos/', views.RemitosListView.as_view(), name='remitos_list'),
    path('remitos/crear/', views.RemitoCreateView.as_view(), name='remito_create'),
]
