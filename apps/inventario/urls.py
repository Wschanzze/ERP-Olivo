from django.urls import path
from . import views

app_name = 'inventario'

urlpatterns = [
    path('', views.InsumosListView.as_view(), name='insumos_list'),
    path('insumos/crear/', views.InsumoCreateView.as_view(), name='insumo_create'),
    path('insumos/<int:pk>/kardex/', views.InsumoKardexView.as_view(), name='insumo_kardex'),
    path('transferencias/crear/', views.TransferenciaStockCreateView.as_view(), name='transferencia_create'),
    path('ajustes/crear/', views.AjusteStockCreateView.as_view(), name='ajuste_create'),
    path('movimientos/', views.MovimientosStockListView.as_view(), name='movimientos_list'),
    path('movimientos/crear/', views.MovimientoStockCreateView.as_view(), name='movimiento_create'),
    path('maquinas/', views.MaquinasListView.as_view(), name='maquinas_list'),
    path('maquinas/crear/', views.MaquinaCreateView.as_view(), name='maquina_create'),
    path('remitos/', views.RemitosListView.as_view(), name='remitos_list'),
    path('remitos/crear/', views.RemitoCreateView.as_view(), name='remito_create'),
    path('remitos/<int:pk>/', views.RemitoDetailView.as_view(), name='remito_detalle'),
    path('remitos/<int:pk>/firmar/', views.RemitoFirmarMobileView.as_view(), name='remito_firmar'),
    # Análisis y Control Estratégico (Fase 2)
    path('analisis/', views.AnalisisInventarioView.as_view(), name='analisis_stock'),
    path('ordenes-compra/generar-sugerida/', views.GenerarOCSugeridaView.as_view(), name='oc_generar_sugerida'),
    # Órdenes de Compra
    path('ordenes-compra/', views.OrdenesCompraListView.as_view(), name='ordenes_compra_list'),
    path('ordenes-compra/crear/', views.OrdenCompraCreateView.as_view(), name='oc_create'),
    path('ordenes-compra/<int:pk>/', views.OrdenCompraDetailView.as_view(), name='oc_detalle'),
    path('ordenes-compra/<int:pk>/imprimir/', views.OrdenCompraPrintView.as_view(), name='oc_imprimir'),
    path('ordenes-compra/<int:pk>/aprobar/', views.aprobar_oc_htmx, name='oc_aprobar'),
    path('recepciones/crear/', views.RecepcionCreateView.as_view(), name='recepcion_create'),
    path('recepciones/<int:pk>/confirmar/', views.ConfirmarRecepcionView.as_view(), name='recepcion_confirmar'),
    # Exportaciones Excel
    path('insumos/exportar/', views.ExportarInsumosExcelView.as_view(), name='exportar_insumos'),
    path('movimientos/exportar/', views.ExportarMovimientosExcelView.as_view(), name='exportar_movimientos'),
    path('remitos/exportar/', views.ExportarRemitosExcelView.as_view(), name='exportar_remitos'),
    path('ordenes-compra/exportar/', views.ExportarOrdenesExcelView.as_view(), name='exportar_ordenes_compra'),
]
