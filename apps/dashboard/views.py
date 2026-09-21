import json
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.utils import timezone
from django.db.models import Sum, F, Count
from apps.campos.models import Cuadro, LoteDeCosecha
from apps.inventario.models import Insumo
from apps.personal.models import Empleado, RegistroAsistencia
from apps.finanzas.models import Cuenta, CuentaCorriente, Cheque
from apps.costos.models import CostoPorCentro
from apps.parte_diario.models import ParteDiario

class DashboardView(TemplateView):
    template_name = 'dashboard/index.html'

    def get(self, request, *args, **kwargs):
        tab = request.GET.get('tab')
        if tab:
            return redirect(f'/finanzas/?tab={tab}')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Inicio y Accesos Directos | ERP Olivícola'

        # ── Campaña activa y disponibles ──────────────────────────────────────
        ano_actual = timezone.now().year
        campana_default = f"{ano_actual}/{ano_actual + 1}"
        campana_activa = self.request.GET.get('campana', campana_default)
        context['campana_activa'] = campana_activa

        try:
            campanas_disponibles = list(
                LoteDeCosecha.objects.values_list('campana', flat=True).distinct().order_by('-campana')
            )
            if campana_activa not in campanas_disponibles:
                campanas_disponibles.insert(0, campana_activa)
            context['campanas_disponibles'] = campanas_disponibles
        except Exception:
            context['campanas_disponibles'] = [campana_activa]

        # Métricas en tiempo real para insignias
        try:
            cuadros_count = Cuadro.objects.filter(activo=True).count()
            ha_totales = Cuadro.objects.filter(activo=True).aggregate(Sum('hectareas_netas'))['hectareas_netas__sum'] or 0
        except Exception:
            cuadros_count, ha_totales = 0, 0

        try:
            insumos_count = Insumo.objects.filter(activo=True).count()
            insumos_criticos = Insumo.objects.filter(activo=True, stock_actual__lte=F('stock_minimo')).count()
        except Exception:
            insumos_count, insumos_criticos = 0, 0

        try:
            empleados_count = Empleado.objects.filter(activo=True).count()
            asistencia_hoy_count = RegistroAsistencia.objects.filter(fecha=timezone.now().date()).count()
        except Exception:
            empleados_count, asistencia_hoy_count = 0, 0

        try:
            partes_count = ParteDiario.objects.count()
        except Exception:
            partes_count = 0

        try:
            costos_total = CostoPorCentro.objects.aggregate(Sum('importe_ars'))['importe_ars__sum'] or 0
        except Exception:
            costos_total = 0

        # Cosecha y Costo por Kg de la campaña activa
        try:
            lotes_campana = LoteDeCosecha.objects.filter(campana=campana_activa)
            kg_cosechados_campana = lotes_campana.aggregate(Sum('kg_cosechados'))['kg_cosechados__sum'] or 0
            if kg_cosechados_campana and kg_cosechados_campana > 0 and costos_total > 0:
                costo_por_kg = round(float(costos_total) / float(kg_cosechados_campana), 2)
            else:
                costo_por_kg = None
        except Exception:
            kg_cosechados_campana, costo_por_kg = 0, None

        try:
            cajas_total = Cuenta.objects.filter(activa=True, moneda='ARS').aggregate(Sum('saldo_actual'))['saldo_actual__sum'] or 0
            cheques_count = Cheque.objects.filter(estado='EN_CARTERA').count()
            proveedores_count = CuentaCorriente.objects.filter(tipo_entidad='PROVEEDOR').count()
            clientes_count = CuentaCorriente.objects.filter(tipo_entidad='CLIENTE').count()
        except Exception:
            cajas_total, cheques_count, proveedores_count, clientes_count = 0, 0, 0, 0

        # Catálogo de Accesos Directos y Carpetas de Consulta estilo ERP CloudSuite
        accesos = [
            {
                'id': 'costos_cuadro',
                'titulo': 'Consulta de Estructura de Costos por Cuadro',
                'categoria': 'finanzas',
                'categoria_nombre': 'Costos & Finanzas',
                'url': '/costos/',
                'icono': 'chart_pie',
                'color': 'emerald',
                'badge': f"${costos_total:,.0f}",
                'descripcion': 'Imputación ABC de mano de obra, insumos fitosanitarios y riego por lote.',
                'tipo_archivo': 'Consulta Analítica'
            },
            {
                'id': 'catastro_cuadros',
                'titulo': 'Catastro y Superficie de Cuadros',
                'categoria': 'campo',
                'categoria_nombre': 'Campo & Olivos',
                'url': '/campos/',
                'icono': 'tree',
                'color': 'oliva',
                'badge': f"{cuadros_count} cuadros ({ha_totales:.0f} ha)",
                'descripcion': 'Superficies netas, densidades y marcos de riego por goteo.',
                'tipo_archivo': 'Catastro Agrícola'
            },
            {
                'id': 'rendimiento_variedad',
                'titulo': 'Consulta de Rendimiento por Variedad',
                'categoria': 'campo',
                'categoria_nombre': 'Campo & Olivos',
                'url': '/campos/?variedad=ARAUCO',
                'icono': 'filter',
                'color': 'oliva',
                'badge': 'Arauco / Arbequina / Picual',
                'descripcion': 'Comportamiento productivo y fechas óptimas de cosecha por variedad.',
                'tipo_archivo': 'Análisis Varietal'
            },
            {
                'id': 'stock_insumos',
                'titulo': 'Consulta de Stock Crítico de Insumos',
                'categoria': 'almazara',
                'categoria_nombre': 'Almazara & Depósitos',
                'url': '/inventario/',
                'icono': 'cube',
                'color': 'amber',
                'badge': f"{insumos_criticos} bajo mínimo" if insumos_criticos > 0 else f"{insumos_count} en orden",
                'descripcion': 'Fitosanitarios, fertilizantes y lubricantes en punto de reposición.',
                'tipo_archivo': 'Control de Inventario'
            },
            {
                'id': 'ordenes_compra',
                'titulo': 'Órdenes de Compra y Recepciones',
                'categoria': 'almazara',
                'categoria_nombre': 'Almazara & Depósitos',
                'url': '/inventario/ordenes-compra/',
                'icono': 'document_arrow_down',
                'color': 'amber',
                'badge': 'Gestión de Compras',
                'descripcion': 'Flujo formal de compras con control de recepciones y deuda proveedor.',
                'tipo_archivo': 'Compras de Insumos'
            },
            {
                'id': 'valorizacion_ppp',
                'titulo': 'Valorización de Depósitos al Costo PPP',
                'categoria': 'almazara',
                'categoria_nombre': 'Almazara & Depósitos',
                'url': '/inventario/',
                'icono': 'calculator',
                'color': 'slate',
                'badge': 'PPP en ARS',
                'descripcion': 'Valuación monetaria contable de insumos y consumibles de almazara.',
                'tipo_archivo': 'Consulta Valorizada'
            },
            {
                'id': 'partes_labor',
                'titulo': 'Partes Diarios de Labor, Riego y Cosecha',
                'categoria': 'almazara',
                'categoria_nombre': 'Almazara & Depósitos',
                'url': '/parte-diario/',
                'icono': 'clipboard',
                'color': 'oliva',
                'badge': f"{partes_count} partes emitidos",
                'descripcion': 'Descarga automática de stock, datos de riego y jornales.',
                'tipo_archivo': 'Operaciones de Campo'
            },
            {
                'id': 'asistencia_cuadrillas',
                'titulo': 'Carga Rápida de Asistencia de Cuadrillas',
                'categoria': 'personal',
                'categoria_nombre': 'Personal & Nómina',
                'url': '/personal/asistencia/',
                'icono': 'user_check',
                'color': 'sky',
                'badge': f"{asistencia_hoy_count}/{empleados_count} registrados hoy",
                'descripcion': 'Marcación de presentismo, ausencias y suspensiones climáticas.',
                'tipo_archivo': 'Carga Operativa'
            },
            {
                'id': 'fichaje_qr',
                'titulo': 'Fichaje por QR en Cuadrillas',
                'categoria': 'personal',
                'categoria_nombre': 'Personal & Nómina',
                'url': '/personal/fichaje-qr/',
                'icono': 'qr_code',
                'color': 'sky',
                'badge': 'Escaneo QR Móvil',
                'descripcion': 'Fichaje instantáneo de asistencia escaneando el código QR del legajo.',
                'tipo_archivo': 'Control de Asistencia'
            },
            {
                'id': 'padron_personal',
                'titulo': 'Padrón de Personal Rural y Legajos',
                'categoria': 'personal',
                'categoria_nombre': 'Personal & Nómina',
                'url': '/personal/',
                'icono': 'users',
                'color': 'sky',
                'badge': f"{empleados_count} legajos activos",
                'descripcion': 'Nómina, categorías laborales y jornales base homologados UATRE.',
                'tipo_archivo': 'Legajos y RRHH'
            },
            {
                'id': 'liquidacion_uatre',
                'titulo': 'Liquidación Quincenal de Sueldos UATRE',
                'categoria': 'personal',
                'categoria_nombre': 'Personal & Nómina',
                'url': '/liquidacion/',
                'icono': 'banknotes',
                'color': 'emerald',
                'badge': 'Recibos PDF',
                'descripcion': 'Devengamiento de haberes y descarga de recibos PDF profesionales.',
                'tipo_archivo': 'Liquidación Salarial'
            },
            {
                'id': 'posicion_cajas',
                'titulo': 'Posición Consolidada de Caja y Bancos',
                'categoria': 'finanzas',
                'categoria_nombre': 'Costos & Finanzas',
                'url': '/finanzas/',
                'icono': 'building_library',
                'color': 'emerald',
                'badge': f"${cajas_total:,.0f} ARS",
                'descripcion': 'Arqueo de tesorería en efectivo y cuentas bancarias.',
                'tipo_archivo': 'Tesorería'
            },
            {
                'id': 'facturas_proveedores',
                'titulo': 'Cuentas Corrientes y Facturas a Pagar',
                'categoria': 'finanzas',
                'categoria_nombre': 'Costos & Finanzas',
                'url': '/finanzas/',
                'icono': 'document_arrow_down',
                'color': 'amber',
                'badge': f"{proveedores_count} proveedores",
                'descripcion': 'Vencimientos de proveedores de insumos, servicios y fletes.',
                'tipo_archivo': 'Cuentas por Pagar'
            },
            {
                'id': 'clientes_cobranzas',
                'titulo': 'Cuentas y Cobranzas de Clientes de Aceite',
                'categoria': 'finanzas',
                'categoria_nombre': 'Costos & Finanzas',
                'url': '/finanzas/',
                'icono': 'document_arrow_up',
                'color': 'emerald',
                'badge': f"{clientes_count} clientes",
                'descripcion': 'Cobranzas de venta de aceite a granel y aceitunas de mesa.',
                'tipo_archivo': 'Cuentas por Cobrar'
            },
            {
                'id': 'cartera_cheques',
                'titulo': 'Cartera y Vencimientos de Cheques',
                'categoria': 'finanzas',
                'categoria_nombre': 'Costos & Finanzas',
                'url': '/finanzas/',
                'icono': 'credit_card',
                'color': 'amber',
                'badge': f"{cheques_count} en cartera",
                'descripcion': 'Control de cheques diferidos propios y recibidos de terceros.',
                'tipo_archivo': 'Valores a Depositar'
            },
        ]

        for acc in accesos:
            if acc['categoria'] in ('finanzas', 'personal'):
                acc['icono_carpeta'] = '/static/img/folder_2577349.png'
            else:
                acc['icono_carpeta'] = '/static/img/folder_2577158.png'

        context['accesos_directos'] = accesos
        context['accesos_directos_json'] = json.dumps(accesos)
        context['kpis_resumen'] = {
            'cuadros_count': cuadros_count,
            'ha_totales': ha_totales,
            'insumos_count': insumos_count,
            'insumos_criticos': insumos_criticos,
            'empleados_count': empleados_count,
            'asistencia_hoy_count': asistencia_hoy_count,
            'costos_total': costos_total,
            'cajas_total': cajas_total,
            'kg_cosechados_campana': kg_cosechados_campana,
            'costo_por_kg': costo_por_kg,
        }
        return context
