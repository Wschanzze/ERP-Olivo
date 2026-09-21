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
    # Órdenes de Compra
    path('ordenes-compra/', views.OrdenesCompraListView.as_view(), name='ordenes_compra_list'),
    path('ordenes-compra/crear/', views.OrdenCompraCreateView.as_view(), name='oc_create'),
    path('recepciones/crear/', views.RecepcionCreateView.as_view(), name='recepcion_create'),
    path('recepciones/<int:pk>/confirmar/', views.ConfirmarRecepcionView.as_view(), name='recepcion_confirmar'),
]
