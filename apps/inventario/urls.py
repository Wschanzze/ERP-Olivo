from django.urls import path
from . import views

app_name = 'inventario'

urlpatterns = [
    path('', views.InsumosListView.as_view(), name='insumos_list'),
    path('insumos/crear/', views.InsumoCreateView.as_view(), name='insumo_create'),
    path('insumos/<int:pk>/editar/', views.InsumoUpdateView.as_view(), name='insumo_update'),
    path('insumos/<int:pk>/eliminar/', views.InsumoDeleteView.as_view(), name='insumo_delete'),
    path('insumos/<int:pk>/kardex/', views.InsumoKardexView.as_view(), name='insumo_kardex'),
    path('transferencias/crear/', views.TransferenciaStockCreateView.as_view(), name='transferencia_create'),
    path('ajustes/crear/', views.AjusteStockCreateView.as_view(), name='ajuste_create'),
    path('movimientos/', views.MovimientosStockListView.as_view(), name='movimientos_list'),
    path('movimientos/crear/', views.MovimientoStockCreateView.as_view(), name='movimiento_create'),
    path('maquinas/', views.MaquinasListView.as_view(), name='maquinas_list'),
    path('maquinas/crear/', views.MaquinaCreateView.as_view(), name='maquina_create'),
    path('maquinas/<int:pk>/editar/', views.MaquinaUpdateView.as_view(), name='maquina_update'),
    path('maquinas/<int:pk>/eliminar/', views.MaquinaDeleteView.as_view(), name='maquina_delete'),
    
    # Nuevos dashboards integrales para activos
    path('herramientas/', views.StockHerramientasListView.as_view(), name='herramientas_list'),
    path('herramientas/crear/', views.HerramientaCreateView.as_view(), name='herramienta_create'),
    path('herramientas/<int:pk>/editar/', views.HerramientaUpdateView.as_view(), name='herramienta_update'),
    path('herramientas/<int:pk>/eliminar/', views.HerramientaDeleteView.as_view(), name='herramienta_delete'),
    path('herramientas/<int:pk>/asignar/', views.AsignarHerramientaView.as_view(), name='herramienta_asignar'),
    
    path('rodados/', views.StockRodadosListView.as_view(), name='rodados_list'),
    
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
