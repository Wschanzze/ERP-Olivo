from django.urls import path
from . import views

app_name = 'finanzas'

urlpatterns = [
    path('', views.FinanzasDashboardView.as_view(), name='dashboard'),
    path('caja/', views.CuentasListValoresView.as_view(), name='cuentas_list'),
    path('caja/arqueo/', views.ArqueoCajaView.as_view(), name='caja_arqueo'),
    path('cuentas/crear/', views.CuentaCreateView.as_view(), name='cuenta_create'),
    path('cuentas/<int:pk>/editar/', views.CuentaUpdateView.as_view(), name='cuenta_edit'),
    path('movimientos/crear/', views.MovimientoCreateView.as_view(), name='movimiento_create'),
    path('movimientos/<int:pk>/imprimir/', views.ComprobantePrintView.as_view(), name='comprobante_print'),
    path('transferencias/crear/', views.TransferenciaCreateView.as_view(), name='transferencia_create'),
    path('proveedores/', views.CuentasCorrientesProveedoresView.as_view(), name='proveedores_list'),
    path('proveedores/pagar/', views.PagoProveedorView.as_view(), name='proveedor_pagar'),
    path('clientes/', views.CuentasCorrientesClientesView.as_view(), name='clientes_list'),
    path('clientes/cobrar/', views.CobroClienteView.as_view(), name='cliente_cobrar'),
    path('cuenta-corriente/comprobante/', views.ComprobanteCuentaCorrienteView.as_view(), name='cuenta_corriente_comprobante'),
    path('cuenta-corriente/<int:pk>/movimientos/', views.CuentaCorrienteDetalleModalView.as_view(), name='cuenta_corriente_movimientos'),
    path('cuenta-corriente/crear/', views.CuentaCorrienteCreateView.as_view(), name='cuenta_corriente_crear'),
    path('cheques/', views.ChequesListView.as_view(), name='cheques_list'),
    path('cheques/crear/', views.ChequeCreateView.as_view(), name='cheque_create'),
    path('cheques/<int:pk>/cambiar-estado/', views.ChequeCambiarEstadoView.as_view(), name='cheque_cambiar_estado'),
    path('conciliaciones/', views.ConciliacionListView.as_view(), name='conciliaciones'),
    path('conciliaciones/crear/', views.ConciliacionCreateView.as_view(), name='conciliacion_create'),
    path('conciliaciones/<int:pk>/', views.ConciliacionDetailView.as_view(), name='conciliacion_detail'),
    # Plan de Cuentas
    path('plan-cuentas/', views.PlanCuentasView.as_view(), name='plan_cuentas'),
    path('plan-cuentas/<int:pk>/detalle/', views.CuentaContableDetailModalView.as_view(), name='cuenta_contable_detail'),
    path('plan-cuentas/<int:pk>/editar/', views.CuentaContableUpdateView.as_view(), name='cuenta_contable_edit'),
    path('plan-cuentas/vincular-rapido/', views.VincularEntidadRapidaView.as_view(), name='vincular_entidad_rapida'),
    path('plan-cuentas/sincronizar/', views.SincronizarPlanCuentasView.as_view(), name='sincronizar_plan_cuentas'),
    # Resultados del Período (Cuadro de Resultados / P&L)
    path('cuadros-resultado/crear/', views.CuadroResultadoCreateView.as_view(), name='cuadro_resultado_create'),
    path('cuadros-resultado/<int:pk>/imprimir/', views.CuadroResultadoPrintView.as_view(), name='cuadro_resultado_print'),
    path('cuadros-resultado/<int:pk>/notas/', views.CuadroResultadoNotasUpdateView.as_view(), name='cuadro_resultado_notas'),
    path('cuadros-resultado/linea/<int:pk>/editar/', views.LineaCuadroResultadoUpdateView.as_view(), name='linea_resultado_edit'),
    # Tipo de Cambio Mensual / Coeficiente
    path('tipo-cambio/guardar/', views.TipoCambioGuardarView.as_view(), name='tipo_cambio_guardar'),
    # Facturación, Libro de IVA & Arqueo de Caja
    path('comprobante/crear/', views.ComprobanteFiscalCreateView.as_view(), name='comprobante_create'),
    path('comprobante/pago/', views.ComprobantePagoCobroView.as_view(), name='comprobante_pago'),
    path('comprobante/<int:pk>/imprimir/', views.ComprobanteFiscalPrintView.as_view(), name='comprobante_fiscal_print'),
    path('comprobante/<int:pk>/autorizar-arca/', views.ComprobanteAutorizarArcaView.as_view(), name='comprobante_autorizar_arca'),
    path('comprobante/<int:pk>/pdf-oficial/', views.ComprobantePdfOficialView.as_view(), name='comprobante_pdf_oficial'),
    path('api/afip/padron/<str:cuit>/', views.AfipPadronLookupView.as_view(), name='afip_padron_lookup'),
    path('arqueo/crear/', views.ArqueoCajaCreateView.as_view(), name='arqueo_create'),
    path('orden-pago/<int:pk>/imprimir/', views.OrdenPagoReciboPrintView.as_view(), name='orden_pago_print'),
    path('libro-iva/exportar/', views.ExportarLibroIVAView.as_view(), name='exportar_libro_iva'),
    # Gestión de Datos de Prueba (Demo Q1 2026)
    path('demo/limpiar/', views.LimpiarDatosDemoView.as_view(), name='demo_limpiar'),
    path('demo/poblar/', views.PoblarDatosDemoView.as_view(), name='demo_poblar'),
]
