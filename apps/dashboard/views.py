import json
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.utils import timezone
from django.db.models import Sum, F, Count, Q
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



        # Catálogo de Accesos Directos y Carpetas del Hub Operativo
        accesos = [
            # 🌿 CAMPO & PRODUCCIÓN
            {
                'id': 'catastro_cuadros',
                'titulo': 'Catastro y Superficie de Cuadros',
                'categoria': 'campo',
                'categoria_nombre': 'Campo & Olivos',
                'url': '/campos/',
                'icono': 'tree',
                'color': 'oliva',
                'badge': 'Superficies y Plantación',
                'descripcion': 'Superficies netas, densidades, marcos de plantación y riego por goteo.',
                'tipo_archivo': 'Catastro Agrícola'
            },
            {
                'id': 'partes_labor',
                'titulo': 'Partes Diarios de Labor y Riego',
                'categoria': 'campo',
                'categoria_nombre': 'Campo & Olivos',
                'url': '/parte-diario/',
                'icono': 'clipboard',
                'color': 'oliva',
                'badge': 'Registro Diario',
                'descripcion': 'Descarga de labores de campo, aplicación fitosanitaria y riego.',
                'tipo_archivo': 'Operaciones Agrícolas'
            },
            {
                'id': 'costos_cuadro',
                'titulo': 'Estructura de Costos por Lote y Centro',
                'categoria': 'campo',
                'categoria_nombre': 'Campo & Olivos',
                'url': '/costos/',
                'icono': 'chart_pie',
                'color': 'emerald',
                'badge': 'Análisis de Costos',
                'descripcion': 'Imputación ABC de jornales, insumos fitosanitarios y labores por cuadro.',
                'tipo_archivo': 'Consulta de Costos'
            },
            {
                'id': 'rendimiento_variedad',
                'titulo': 'Rendimiento y Cosecha por Variedad',
                'categoria': 'campo',
                'categoria_nombre': 'Campo & Olivos',
                'url': '/campos/?variedad=ARAUCO',
                'icono': 'filter',
                'color': 'oliva',
                'badge': 'Productividad',
                'descripcion': 'Comportamiento productivo y fechas óptimas de cosecha por variedad.',
                'tipo_archivo': 'Análisis Varietal'
            },

            # 💵 FINANZAS & TESORERÍA
            {
                'id': 'resultado_periodo',
                'titulo': 'Resultado del Período (P&L Gerencial)',
                'categoria': 'finanzas',
                'categoria_nombre': 'Finanzas & Control',
                'url': '/finanzas/?tab=resultados',
                'icono': 'chart_bar',
                'color': 'emerald',
                'badge': 'P&L Trimestral',
                'descripcion': 'Cuadro de resultados en Pesos y Dólares con margen bruto y EBITDA.',
                'tipo_archivo': 'Estado de Resultados'
            },
            {
                'id': 'posicion_cajas',
                'titulo': 'Posición de Cajas, Bancos y Arqueo',
                'categoria': 'finanzas',
                'categoria_nombre': 'Finanzas & Control',
                'url': '/finanzas/?tab=caja',
                'icono': 'building_library',
                'color': 'emerald',
                'badge': 'Saldos Disponibles',
                'descripcion': 'Arqueo de tesorería diaria en efectivo, bancos y billeteras virtuales.',
                'tipo_archivo': 'Tesorería'
            },
            {
                'id': 'facturas_proveedores',
                'titulo': 'Cuentas por Pagar a Proveedores',
                'categoria': 'finanzas',
                'categoria_nombre': 'Finanzas & Control',
                'url': '/finanzas/?tab=proveedores',
                'icono': 'document_arrow_down',
                'color': 'amber',
                'badge': 'Cuentas a Pagar',
                'descripcion': 'Vencimientos de proveedores de insumos, servicios de cosecha y fletes.',
                'tipo_archivo': 'Cuentas por Pagar'
            },
            {
                'id': 'clientes_cobranzas',
                'titulo': 'Cuentas y Cobranzas de Clientes',
                'categoria': 'finanzas',
                'categoria_nombre': 'Finanzas & Control',
                'url': '/finanzas/?tab=clientes',
                'icono': 'document_arrow_up',
                'color': 'emerald',
                'badge': 'Cuentas a Cobrar',
                'descripcion': 'Cobranzas de venta de aceite de oliva a granel y aceitunas de mesa.',
                'tipo_archivo': 'Cuentas por Cobrar'
            },
            {
                'id': 'libro_iva',
                'titulo': 'Libro de IVA Compras & Ventas AFIP',
                'categoria': 'finanzas',
                'categoria_nombre': 'Finanzas & Control',
                'url': '/finanzas/?tab=libro_iva',
                'icono': 'document_text',
                'color': 'amber',
                'badge': 'Régimen AFIP / ARCA',
                'descripcion': 'Desglose impositivo de alícuotas 21%, 10.5%, percepciones y exportación.',
                'tipo_archivo': 'Libro Impositivo'
            },
            {
                'id': 'cartera_cheques',
                'titulo': 'Cartera y Vencimientos de Cheques',
                'categoria': 'finanzas',
                'categoria_nombre': 'Finanzas & Control',
                'url': '/finanzas/?tab=cheques',
                'icono': 'credit_card',
                'color': 'amber',
                'badge': 'Valores en Cartera',
                'descripcion': 'Control de cheques diferidos propios y de clientes listos para depositar o endosar.',
                'tipo_archivo': 'Valores a Depositar'
            },
            {
                'id': 'plan_cuentas',
                'titulo': 'Plan de Cuentas Contable (Árbol)',
                'categoria': 'finanzas',
                'categoria_nombre': 'Finanzas & Control',
                'url': '/finanzas/plan-cuentas/',
                'icono': 'folder_tree',
                'color': 'oliva',
                'badge': 'Árbol Jerárquico',
                'descripcion': 'Nomenclador contable con cuentas de activo biológico, almazara y egresos.',
                'tipo_archivo': 'Estructura Contable'
            },

            # 👥 PERSONAL & CUADRILLAS
            {
                'id': 'padron_personal',
                'titulo': 'Padrón de Personal Rural y Legajos',
                'categoria': 'personal',
                'categoria_nombre': 'Personal & Nómina',
                'url': '/personal/',
                'icono': 'users',
                'color': 'sky',
                'badge': 'Legajos Activos',
                'descripcion': 'Nómina, categorías laborales y jornales base homologados UATRE.',
                'tipo_archivo': 'Legajos y RRHH'
            },
            {
                'id': 'asistencia_cuadrillas',
                'titulo': 'Asistencia Diaria de Cuadrillas',
                'categoria': 'personal',
                'categoria_nombre': 'Personal & Nómina',
                'url': '/personal/asistencia/',
                'icono': 'user_check',
                'color': 'sky',
                'badge': 'Control de Presentismo',
                'descripcion': 'Marcación de presentismo, ausencias justificadas y suspensiones.',
                'tipo_archivo': 'Carga Operativa'
            },
            {
                'id': 'fichaje_qr',
                'titulo': 'Fichaje por QR Móvil en Cuadrillas',
                'categoria': 'personal',
                'categoria_nombre': 'Personal & Nómina',
                'url': '/personal/fichaje-qr/',
                'icono': 'qr_code',
                'color': 'sky',
                'badge': 'Escaneo QR Móvil',
                'descripcion': 'Fichaje instantáneo de asistencia escaneando el código QR del legajo desde el celular.',
                'tipo_archivo': 'Control de Asistencia'
            },
            {
                'id': 'liquidacion_uatre',
                'titulo': 'Liquidación Quincenal UATRE',
                'categoria': 'personal',
                'categoria_nombre': 'Personal & Nómina',
                'url': '/liquidacion/',
                'icono': 'banknotes',
                'color': 'emerald',
                'badge': 'Recibos PDF',
                'descripcion': 'Devengamiento de haberes y descarga de recibos PDF profesionales.',
                'tipo_archivo': 'Liquidación Salarial'
            },

            # 📦 ALMAZARA, DEPÓSITOS & LOGÍSTICA
            {
                'id': 'stock_insumos',
                'titulo': 'Control de Stock e Insumos Agrícolas',
                'categoria': 'almazara',
                'categoria_nombre': 'Almazara & Depósitos',
                'url': '/inventario/',
                'icono': 'cube',
                'color': 'amber',
                'badge': 'Gestión de Inventario',
                'descripcion': 'Fitosanitarios, fertilizantes y lubricantes con control de punto de reposición.',
                'tipo_archivo': 'Control de Inventario'
            },
            {
                'id': 'remitos_firma',
                'titulo': 'Remitos con Firma Digital Móvil',
                'categoria': 'almazara',
                'categoria_nombre': 'Almazara & Depósitos',
                'url': '/inventario/remitos/',
                'icono': 'document_check',
                'color': 'emerald',
                'badge': 'Firma Táctil Móvil',
                'descripcion': 'Comprobantes de recepción con firma táctil en pantalla desde el celular del receptor.',
                'tipo_archivo': 'Logística de Entrada'
            },
            {
                'id': 'ordenes_compra',
                'titulo': 'Órdenes de Compra y Recepciones',
                'categoria': 'almazara',
                'categoria_nombre': 'Almazara & Depósitos',
                'url': '/inventario/ordenes-compra/',
                'icono': 'document_arrow_down',
                'color': 'amber',
                'badge': 'Flujo de Compras',
                'descripcion': 'Solicitudes formales de insumos y control de mercadería recibida.',
                'tipo_archivo': 'Gestión de Compras'
            },
            {
                'id': 'parque_maquinaria',
                'titulo': 'Parque de Maquinarias y Servicios',
                'categoria': 'campo',
                'categoria_nombre': 'Campo & Olivos',
                'url': '/inventario/maquinas/',
                'icono': 'truck',
                'color': 'oliva',
                'badge': 'Mantenimiento Preventivo',
                'descripcion': 'Gestión de tractores, cosechadoras, y mantenimientos mecánicos.',
                'tipo_archivo': 'Parque Automotor'
            },
            {
                'id': 'analisis_abc',
                'titulo': 'Análisis y Matriz de Rotación ABC',
                'categoria': 'almazara',
                'categoria_nombre': 'Almazara & Depósitos',
                'url': '/inventario/analisis/',
                'icono': 'chart_bar',
                'color': 'slate',
                'badge': 'Pareto 80/20',
                'descripcion': 'Clasificación de stock por valor monetario y criticidad para la cosecha.',
                'tipo_archivo': 'Analítica de Inventario'
            },
            {
                'id': 'movimientos_stock',
                'titulo': 'Kardex y Movimientos de Stock',
                'categoria': 'almazara',
                'categoria_nombre': 'Almazara & Depósitos',
                'url': '/inventario/movimientos/',
                'icono': 'arrows_right_left',
                'color': 'amber',
                'badge': 'Trazabilidad',
                'descripcion': 'Registro histórico de entradas, salidas, transferencias y ajustes de inventario.',
                'tipo_archivo': 'Auditoría de Stock'
            },
        ]

        for acc in accesos:
            if acc['categoria'] in ('finanzas', 'personal'):
                acc['icono_carpeta'] = '/static/img/folder_2577349.png'
            else:
                acc['icono_carpeta'] = '/static/img/folder_2577158.png'

        context['accesos_directos'] = accesos
        context['accesos_directos_json'] = json.dumps(accesos)
        context['kpis_resumen'] = {}
        return context
