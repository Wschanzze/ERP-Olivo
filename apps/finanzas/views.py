from django.views.generic import TemplateView, ListView, CreateView, DetailView, UpdateView
from django.urls import reverse_lazy
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Sum, Q
from django.utils import timezone
from decimal import Decimal
import json
import datetime
from django.core.cache import cache

from django.core.management import call_command
from django.contrib import messages
from django.views import View

from collections import OrderedDict

from .models import (
    CuentaContable, Cuenta, CuentaCorriente, MovimientoFinanciero, Cheque, ConciliacionBancaria,
    CuadroResultado, LineaCuadroResultado, TipoCambioMensual,
    ComprobanteFiscal, ArqueoCaja, OrdenPagoRecibo
)
from apps.inventario.models import CategoriaInsumo
from apps.core.models import CentroDeCosto, Empresa
from .services import registrar_movimiento_financiero, poblar_lineas_cuadro, get_or_create_cuadro_default
from .afip_service import (
    consultar_padron_arca, autorizar_comprobante_arca,
    generar_qr_arca_base64, generar_qr_arca_url, generar_pdf_oficial_afipsdk
)


def get_plan_cuentas_payload():
    """Genera datos serializados y estadísticas para el visor reactivo del Plan de Cuentas, con caché en memoria."""
    cached_payload = cache.get('plan_cuentas_payload')
    if cached_payload is not None:
        return cached_payload

    qs = list(CuentaContable.objects.all().select_related('padre').prefetch_related(
        'cuentas_financieras', 'categorias_insumo_activo', 'categorias_insumo_gasto', 'centros_de_costo'
    ).order_by('codigo'))

    children_ids = set(c.padre_id for c in qs if c.padre_id)
    children_map = {}
    qs_dict = {c.id: c for c in qs}
    descendants_count = {}

    for c in qs:
        if c.padre_id:
            children_map.setdefault(c.padre_id, []).append(c)
        curr = c.padre_id
        visited = set()
        while curr and curr in qs_dict and curr not in visited:
            visited.add(curr)
            descendants_count[curr] = descendants_count.get(curr, 0) + 1
            parent_obj = qs_dict.get(curr)
            curr = parent_obj.padre_id if parent_obj else None

    data = []
    total_imputables = 0
    total_activos = 0
    total_pasivos = 0
    total_patrimonio = 0
    total_ingresos = 0
    total_egresos = 0
    total_vinculadas = 0
    total_biologicas = 0
    total_industriales = 0
    total_exportacion = 0

    for c in qs:
        c.es_padre = (c.id in children_ids)
        c.hijos_count = len(children_map.get(c.id, []))
        c.total_descendientes = descendants_count.get(c.id, 0)
        ancestors = []
        curr_p_id = c.padre_id
        visited_anc = set()
        while curr_p_id and curr_p_id in qs_dict and curr_p_id not in visited_anc:
            visited_anc.add(curr_p_id)
            p = qs_dict[curr_p_id]
            ancestors.append(p.codigo)
            curr_p_id = p.padre_id
        c.ancestros_codigos_str = ' '.join(ancestors)

        c_cajas = len(c.cuentas_financieras.all())
        c_act = len(c.categorias_insumo_activo.all())
        c_gas = len(c.categorias_insumo_gasto.all())
        c_cc = len(c.centros_de_costo.all())
        vinc = c_cajas + c_act + c_gas + c_cc
        c.vinculos_count = vinc
        c.c_cajas = c_cajas
        c.c_act = c_act
        c.c_gas = c_gas
        c.c_cc = c_cc

        if vinc > 0:
            total_vinculadas += 1

        if c.es_imputable:
            total_imputables += 1
        
        if c.clase in [CuentaContable.ClaseCuenta.ACTIVO, CuentaContable.ClaseCuenta.ACTIVO_REGULARIZADORA]:
            total_activos += 1
        elif c.clase == CuentaContable.ClaseCuenta.PASIVO:
            total_pasivos += 1
        elif c.clase == CuentaContable.ClaseCuenta.PATRIMONIO_NETO:
            total_patrimonio += 1
        elif c.clase == CuentaContable.ClaseCuenta.RESULTADO_POSITIVO:
            total_ingresos += 1
        elif c.clase == CuentaContable.ClaseCuenta.RESULTADO_NEGATIVO:
            total_egresos += 1

        text_search = f"{c.nombre} {c.nota}".lower()
        es_bio = any(w in text_search for w in ['biológ', 'biolog', 'olivar', 'aceituna', 'fruto', 'pie'])
        es_ind = any(w in text_search for w in ['aceite', 'molienda', 'almazara', 'fraccionado', 'extracción', 'extraccion', 'conserva', 'orujo', 'hueso'])
        es_exp = any(w in text_search for w in ['export', 'usd', 'exterior'])

        if es_bio:
            total_biologicas += 1
        if es_ind:
            total_industriales += 1
        if es_exp:
            total_exportacion += 1

        data.append({
            'id': c.id,
            'codigo': c.codigo,
            'nombre': c.nombre,
            'nivel': c.nivel,
            'padre_id': c.padre_id,
            'padre_codigo': c.padre.codigo if c.padre else None,
            'saldo': c.get_saldo_habitual_display() if c.saldo_habitual else '',
            'clase': c.get_clase_display() if c.clase else '',
            'clase_raw': c.clase,
            'es_imputable': c.es_imputable,
            'es_padre': c.es_padre,
            'ancestros': c.ancestros_codigos_str,
            'nota': c.nota,
            'es_biologico': es_bio,
            'es_industrial': es_ind,
            'es_exportacion': es_exp,
            'vinculos_count': vinc
        })

    stats = {
        'total': len(data),
        'imputables': total_imputables,
        'activos': total_activos,
        'pasivos': total_pasivos,
        'patrimonio': total_patrimonio,
        'ingresos': total_ingresos,
        'egresos': total_egresos,
        'vinculadas': total_vinculadas,
        'biologicas': total_biologicas,
        'industriales': total_industriales,
        'exportacion': total_exportacion,
    }

    payload = (stats, data, qs)
    cache.set('plan_cuentas_payload', payload, timeout=600)
    return payload


def build_cuadro_simplificado(cuadro_activo, tc):
    """
    Construye la estructura gerencial de manejo interno del Cuadro de Resultados (P&L),
    agrupando los 56 códigos contables en bloques operativos comprensibles para la gerencia,
    con presentación simultánea en Pesos Argentinos (ARS) y Dólares (USD) con su coeficiente.
    """
    if not cuadro_activo:
        return None

    is_usd = (cuadro_activo.moneda == CuadroResultado.Moneda.USD)
    tc = tc or cuadro_activo.tipo_cambio or Decimal("1050.00")
    if tc <= 0:
        tc = Decimal("1050.00")

    def to_ars_usd(val):
        if is_usd:
            v_usd = val or Decimal('0')
            v_ars = v_usd * tc
        else:
            v_ars = val or Decimal('0')
            v_usd = round(v_ars / tc, 2) if tc > 0 else Decimal('0')
        return v_ars, v_usd

    vt_ars, vt_usd = to_ars_usd(cuadro_activo.ventas_totales)

    # Inicializar grupos ejecutivos
    grupos = {
        'ingresos': {
            'titulo': '1. INGRESOS OPERATIVOS / VENTAS NETAS',
            'tipo': 'seccion',
            'items': OrderedDict([
                ('aceite_granel', {'label': 'Venta Aceite Virgen Extra a Granel (Exportación)', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('aceite_fraccionado', {'label': 'Venta Aceite Fraccionado y Gourmet (Mercado Interno)', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('aceituna_mesa', {'label': 'Venta Aceituna de Mesa (Conserva en Fresco)', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('subproductos', {'label': 'Venta Subproductos (Orujo y Hueso para Biomasa)', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('otros_ingresos', {'label': 'Otros Ingresos Operativos Agronómicos', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
            ])
        },
        'costos_agro': {
            'titulo': '2. COSTOS DIRECTOS DE PRODUCCIÓN AGRÍCOLA (CAMPO)',
            'tipo': 'seccion',
            'items': OrderedDict([
                ('mano_obra_campo', {'label': 'Mano de Obra Agrícola y Jornales de Cosecha UATRE', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('riego_energia', {'label': 'Riego por Goteo y Energía Eléctrica de Pozos', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('fertilizantes', {'label': 'Fertilizantes, Enmiendas y Nutrición Foliar', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('fitosanitarios', {'label': 'Fitosanitarios, Curación Cúprica y Sanidad', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('maquinaria_combustibles', {'label': 'Combustibles, Tractores y Labores Mecanizadas', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('otros_agro', {'label': 'Otros Insumos y Servicios Agrícolas Directos', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
            ])
        },
        'costos_ind': {
            'titulo': '3. COSTOS INDUSTRIALES DE ALMAZARA & ENVASADO',
            'tipo': 'seccion',
            'items': OrderedDict([
                ('molienda_extraccion', {'label': 'Molienda y Operación de Almazara (Línea Continua)', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('envases_insumos', {'label': 'Botellas de Vidrio Dorica, Tapas, Etiquetas y Cajas', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('fletes_cosecha', {'label': 'Fletes de Cosecha y Logística de Tolva', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('mantenimiento_calidad', {'label': 'Mantenimiento de Planta y Análisis Panel Test', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
            ])
        },
        'gastos_admin': {
            'titulo': '4. GASTOS DE ADMINISTRACIÓN Y ESTRUCTURA',
            'tipo': 'seccion',
            'items': OrderedDict([
                ('sueldos_admin', {'label': 'Sueldos Administración, Dirección y Cargas Sociales', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('honorarios_profesionales', {'label': 'Honorarios Contables, Legales y Asesoría Agronómica', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('servicios_generales', {'label': 'Comunicaciones, Sistemas, Seguros y Servicios', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
            ])
        },
        'gastos_com': {
            'titulo': '5. GASTOS COMERCIALES, DISTRIBUCIÓN & EXPORTACIÓN',
            'tipo': 'seccion',
            'items': OrderedDict([
                ('fletes_puerto', {'label': 'Fletes Terrestres a Puerto y Despachos Aduana', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('comisiones_broker', {'label': 'Comisiones de Venta y Brokers Internacionales', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('certificaciones_mkt', {'label': 'Certificaciones de Calidad (Kosher/Orgánico) y Ferias', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
            ])
        },
        'amortizaciones': {
            'titulo': '6. AMORTIZACIONES Y DEPRECIACIONES',
            'tipo': 'seccion',
            'items': OrderedDict([
                ('depreciaciones', {'label': 'Depreciación Plantaciones, Pozos de Riego y Maquinaria', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
            ])
        },
        'financieros': {
            'titulo': '7. RESULTADOS FINANCIEROS Y DIFERENCIAS DE CAMBIO',
            'tipo': 'seccion',
            'items': OrderedDict([
                ('intereses_gastos', {'label': 'Intereses Prefinanciación BICE y Gastos Bancarios', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('dif_cambio', {'label': 'Diferencia de Cambio Neta (Liquidación Divisas / Proveedores)', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
            ])
        },
        'impuestos': {
            'titulo': '8. IMPUESTO A LAS GANANCIAS Y TASAS',
            'tipo': 'seccion',
            'items': OrderedDict([
                ('ganancias', {'label': 'Provisión Impuesto a las Ganancias Ejercicio', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
                ('tasas_ing_brutos', {'label': 'Ingresos Brutos, Canon Hídrico y Tasas Municipales', 'ars': Decimal('0'), 'presup_ars': Decimal('0'), 'obs': ''}),
            ])
        }
    }

    # Asignar cada línea al grupo e ítem correspondiente
    for l in cuadro_activo.lineas.select_related('cuenta_contable').all():
        n = (l.cuenta_contable.nombre or '').lower()
        sec = l.seccion
        m_ars, _ = to_ars_usd(l.monto_real)
        p_ars, _ = to_ars_usd(l.monto_presupuestado)
        
        target_group = None
        target_item = None

        if sec == LineaCuadroResultado.SeccionResultado.INGRESOS_OPERATIVOS:
            target_group = 'ingresos'
            if 'fraccionado' in n or 'gourmet' in n or 'botella' in n:
                target_item = 'aceite_fraccionado'
            elif 'granel' in n or 'export' in n:
                target_item = 'aceite_granel'
            elif 'mesa' in n or 'conserva' in n or 'fresco' in n:
                target_item = 'aceituna_mesa'
            elif 'subproducto' in n or 'orujo' in n or 'carozo' in n or 'hueso' in n:
                target_item = 'subproductos'
            else:
                target_item = 'otros_ingresos'

        elif sec == LineaCuadroResultado.SeccionResultado.COSTOS_PRODUCCION_AGRO:
            target_group = 'costos_agro'
            if 'mano de obra' in n or 'jornal' in n or 'cosecha' in n or 'poda' in n or 'asistencia' in n:
                target_item = 'mano_obra_campo'
            elif 'riego' in n or 'energ' in n or 'pozo' in n or 'electr' in n:
                target_item = 'riego_energia'
            elif 'fertiliz' in n or 'nutri' in n or 'abono' in n or 'enmienda' in n:
                target_item = 'fertilizantes'
            elif 'fitosanit' in n or 'curaci' in n or 'cobre' in n or 'defensiv' in n:
                target_item = 'fitosanitarios'
            elif 'maquin' in n or 'combust' in n or 'gasoil' in n or 'tractor' in n:
                target_item = 'maquinaria_combustibles'
            else:
                target_item = 'otros_agro'

        elif sec in [
            LineaCuadroResultado.SeccionResultado.COSTOS_PRODUCCION_IND,
            LineaCuadroResultado.SeccionResultado.COSTOS_ENVASADO,
            LineaCuadroResultado.SeccionResultado.COSTOS_VENTAS,
        ]:
            target_group = 'costos_ind'
            if 'botella' in n or 'tapa' in n or 'envase' in n or 'etiqueta' in n or 'caja' in n or sec == LineaCuadroResultado.SeccionResultado.COSTOS_ENVASADO:
                target_item = 'envases_insumos'
            elif 'flete' in n or 'transporte' in n or 'acopio' in n or 'logistica' in n or sec == LineaCuadroResultado.SeccionResultado.COSTOS_VENTAS:
                target_item = 'fletes_cosecha'
            elif 'mantenim' in n or 'calidad' in n or 'panel' in n or 'analisis' in n:
                target_item = 'mantenimiento_calidad'
            else:
                target_item = 'molienda_extraccion'

        elif sec == LineaCuadroResultado.SeccionResultado.GASTOS_ADMIN:
            target_group = 'gastos_admin'
            if 'sueldo' in n or 'cargas' in n or 'directorio' in n:
                target_item = 'sueldos_admin'
            elif 'honorario' in n or 'asesor' in n or 'legal' in n or 'contable' in n:
                target_item = 'honorarios_profesionales'
            else:
                target_item = 'servicios_generales'

        elif sec == LineaCuadroResultado.SeccionResultado.GASTOS_COMERCIALIZACION:
            target_group = 'gastos_com'
            if 'puerto' in n or 'aduana' in n or 'despacho' in n or 'flete' in n:
                target_item = 'fletes_puerto'
            elif 'comision' in n or 'broker' in n:
                target_item = 'comisiones_broker'
            else:
                target_item = 'certificaciones_mkt'

        elif sec == LineaCuadroResultado.SeccionResultado.AMORTIZACIONES:
            target_group = 'amortizaciones'
            target_item = 'depreciaciones'

        elif sec == LineaCuadroResultado.SeccionResultado.RESULTADOS_FINANCIEROS:
            target_group = 'financieros'
            if 'diferencia' in n or 'cambio' in n:
                target_item = 'dif_cambio'
            else:
                target_item = 'intereses_gastos'

        elif sec == LineaCuadroResultado.SeccionResultado.IMPUESTOS:
            target_group = 'impuestos'
            if 'ganancia' in n:
                target_item = 'ganancias'
            else:
                target_item = 'tasas_ing_brutos'

        if target_group and target_item:
            item_data = grupos[target_group]['items'][target_item]
            item_data['ars'] += m_ars
            item_data['presup_ars'] += p_ars
            if l.observaciones and not item_data['obs']:
                item_data['obs'] = l.observaciones

    def format_item(data):
        m_ars = data['ars']
        m_usd = round(m_ars / tc, 2)
        p_ars = data['presup_ars']
        p_usd = round(p_ars / tc, 2)
        desv_m = m_ars - p_ars
        desv_p = round((desv_m / p_ars) * 100, 1) if p_ars > 0 else 0.0
        pct_vt = round((m_ars / vt_ars) * 100, 1) if vt_ars > 0 else 0.0
        return {
            'label': data['label'],
            'monto_ars': m_ars,
            'monto_usd': m_usd,
            'presup_ars': p_ars,
            'presup_usd': p_usd,
            'desvio_monto_ars': desv_m,
            'desvio_pct': desv_p,
            'pct_ventas': pct_vt,
            'obs': data.get('obs', '')
        }

    resultado_bloques = []

    # 1. Ventas
    items_ventas = [format_item(d) for d in grupos['ingresos']['items'].values() if d['ars'] > 0 or d['presup_ars'] > 0]
    total_ventas_ars = sum((it['monto_ars'] for it in items_ventas), Decimal('0'))
    total_ventas_usd = round(total_ventas_ars / tc, 2)
    total_ventas_presup = sum((it['presup_ars'] for it in items_ventas), Decimal('0'))
    resultado_bloques.append({
        'tipo': 'seccion',
        'key': 'ingresos',
        'titulo': '1. INGRESOS OPERATIVOS / VENTAS NETAS',
        'items': items_ventas,
        'subtotal_ars': total_ventas_ars,
        'subtotal_usd': total_ventas_usd,
        'presup_ars': total_ventas_presup,
        'pct_ventas': 100.0,
        'bg_header': 'bg-oliva-50',
        'text_header': 'text-oliva-900',
    })

    # 2. Costos Agrícolas
    items_agro = [format_item(d) for d in grupos['costos_agro']['items'].values() if d['ars'] > 0 or d['presup_ars'] > 0]
    total_agro_ars = sum((it['monto_ars'] for it in items_agro), Decimal('0'))
    total_agro_usd = round(total_agro_ars / tc, 2)
    total_agro_presup = sum((it['presup_ars'] for it in items_agro), Decimal('0'))
    pct_agro = round((total_agro_ars / total_ventas_ars) * 100, 1) if total_ventas_ars > 0 else 0.0
    resultado_bloques.append({
        'tipo': 'seccion',
        'key': 'costos_agro',
        'titulo': '2. COSTOS DIRECTOS DE PRODUCCIÓN AGRÍCOLA (CAMPO)',
        'items': items_agro,
        'subtotal_ars': total_agro_ars,
        'subtotal_usd': total_agro_usd,
        'presup_ars': total_agro_presup,
        'pct_ventas': pct_agro,
        'bg_header': 'bg-amber-50/70',
        'text_header': 'text-amber-900',
    })

    # 👉 MARGEN AGRÍCOLA
    margen_agro_ars = total_ventas_ars - total_agro_ars
    margen_agro_usd = round(margen_agro_ars / tc, 2)
    pct_margen_agro = round((margen_agro_ars / total_ventas_ars) * 100, 1) if total_ventas_ars > 0 else 0.0
    resultado_bloques.append({
        'tipo': 'indicador_clave',
        'titulo': '(=) MARGEN DE CONTRIBUCIÓN AGRÍCOLA (CAMPO)',
        'descripcion': 'Facturación neta menos costos directos de mano de obra, fertirriego, químicos y laboreo.',
        'monto_ars': margen_agro_ars,
        'monto_usd': margen_agro_usd,
        'pct_ventas': pct_margen_agro,
        'badge_bg': 'bg-emerald-50 text-emerald-800 border border-emerald-200',
    })

    # 3. Costos Industriales y Envasado
    items_ind = [format_item(d) for d in grupos['costos_ind']['items'].values() if d['ars'] > 0 or d['presup_ars'] > 0]
    total_ind_ars = sum((it['monto_ars'] for it in items_ind), Decimal('0'))
    total_ind_usd = round(total_ind_ars / tc, 2)
    total_ind_presup = sum((it['presup_ars'] for it in items_ind), Decimal('0'))
    pct_ind = round((total_ind_ars / total_ventas_ars) * 100, 1) if total_ventas_ars > 0 else 0.0
    resultado_bloques.append({
        'tipo': 'seccion',
        'key': 'costos_ind',
        'titulo': '3. COSTOS INDUSTRIALES DE ALMAZARA & ENVASADO',
        'items': items_ind,
        'subtotal_ars': total_ind_ars,
        'subtotal_usd': total_ind_usd,
        'presup_ars': total_ind_presup,
        'pct_ventas': pct_ind,
        'bg_header': 'bg-amber-50/70',
        'text_header': 'text-amber-900',
    })

    # 👉 MARGEN BRUTO OPERATIVO
    margen_bruto_ars = margen_agro_ars - total_ind_ars
    margen_bruto_usd = round(margen_bruto_ars / tc, 2)
    pct_margen_bruto = round((margen_bruto_ars / total_ventas_ars) * 100, 1) if total_ventas_ars > 0 else 0.0
    resultado_bloques.append({
        'tipo': 'indicador_clave',
        'titulo': '(=) MARGEN BRUTO OPERATIVO (UTILIDAD BRUTA AGROINDUSTRIAL)',
        'descripcion': 'Margen después de absorber todos los costos directos de campo, molienda y envasado.',
        'monto_ars': margen_bruto_ars,
        'monto_usd': margen_bruto_usd,
        'pct_ventas': pct_margen_bruto,
        'badge_bg': 'bg-emerald-100 text-emerald-950 font-bold border border-emerald-300',
    })

    # 4. Gastos de Administración
    items_admin = [format_item(d) for d in grupos['gastos_admin']['items'].values() if d['ars'] > 0 or d['presup_ars'] > 0]
    total_admin_ars = sum((it['monto_ars'] for it in items_admin), Decimal('0'))
    total_admin_usd = round(total_admin_ars / tc, 2)
    total_admin_presup = sum((it['presup_ars'] for it in items_admin), Decimal('0'))
    pct_admin = round((total_admin_ars / total_ventas_ars) * 100, 1) if total_ventas_ars > 0 else 0.0
    resultado_bloques.append({
        'tipo': 'seccion',
        'key': 'gastos_admin',
        'titulo': '4. GASTOS DE ADMINISTRACIÓN Y ESTRUCTURA',
        'items': items_admin,
        'subtotal_ars': total_admin_ars,
        'subtotal_usd': total_admin_usd,
        'presup_ars': total_admin_presup,
        'pct_ventas': pct_admin,
        'bg_header': 'bg-slate-100',
        'text_header': 'text-slate-800',
    })

    # 5. Gastos Comerciales
    items_com = [format_item(d) for d in grupos['gastos_com']['items'].values() if d['ars'] > 0 or d['presup_ars'] > 0]
    total_com_ars = sum((it['monto_ars'] for it in items_com), Decimal('0'))
    total_com_usd = round(total_com_ars / tc, 2)
    total_com_presup = sum((it['presup_ars'] for it in items_com), Decimal('0'))
    pct_com = round((total_com_ars / total_ventas_ars) * 100, 1) if total_ventas_ars > 0 else 0.0
    resultado_bloques.append({
        'tipo': 'seccion',
        'key': 'gastos_com',
        'titulo': '5. GASTOS COMERCIALES, LOGÍSTICA & EXPORTACIÓN',
        'items': items_com,
        'subtotal_ars': total_com_ars,
        'subtotal_usd': total_com_usd,
        'presup_ars': total_com_presup,
        'pct_ventas': pct_com,
        'bg_header': 'bg-slate-100',
        'text_header': 'text-slate-800',
    })

    # 👉 EBITDA
    ebitda_ars = margen_bruto_ars - (total_admin_ars + total_com_ars)
    ebitda_usd = round(ebitda_ars / tc, 2)
    pct_ebitda = round((ebitda_ars / total_ventas_ars) * 100, 1) if total_ventas_ars > 0 else 0.0
    resultado_bloques.append({
        'tipo': 'indicador_clave',
        'titulo': '(=) EBITDA OPERATIVO (RESULTADO ANTES DE AMORTIZACIONES E IMPUESTOS)',
        'descripcion': 'Capacidad pura de generación operativa de fondos de la empresa olivícola.',
        'monto_ars': ebitda_ars,
        'monto_usd': ebitda_usd,
        'pct_ventas': pct_ebitda,
        'badge_bg': 'bg-oliva-100 text-oliva-950 font-bold border border-oliva-300',
    })

    # 6. Amortizaciones
    items_amort = [format_item(d) for d in grupos['amortizaciones']['items'].values() if d['ars'] > 0 or d['presup_ars'] > 0]
    total_amort_ars = sum((it['monto_ars'] for it in items_amort), Decimal('0'))
    total_amort_usd = round(total_amort_ars / tc, 2)
    total_amort_presup = sum((it['presup_ars'] for it in items_amort), Decimal('0'))
    pct_amort = round((total_amort_ars / total_ventas_ars) * 100, 1) if total_ventas_ars > 0 else 0.0
    resultado_bloques.append({
        'tipo': 'seccion',
        'key': 'amortizaciones',
        'titulo': '6. AMORTIZACIONES Y DEPRECIACIONES',
        'items': items_amort,
        'subtotal_ars': total_amort_ars,
        'subtotal_usd': total_amort_usd,
        'presup_ars': total_amort_presup,
        'pct_ventas': pct_amort,
        'bg_header': 'bg-slate-100',
        'text_header': 'text-slate-800',
    })

    # 👉 EBIT
    ebit_ars = ebitda_ars - total_amort_ars
    ebit_usd = round(ebit_ars / tc, 2)
    pct_ebit = round((ebit_ars / total_ventas_ars) * 100, 1) if total_ventas_ars > 0 else 0.0
    resultado_bloques.append({
        'tipo': 'indicador_clave',
        'titulo': '(=) EBIT OPERATIVO (RESULTADO OPERATIVO NETO)',
        'descripcion': 'Resultado operativo descontando el desgaste del capital invertido en plantación y maquinarias.',
        'monto_ars': ebit_ars,
        'monto_usd': ebit_usd,
        'pct_ventas': pct_ebit,
        'badge_bg': 'bg-oliva-100 text-oliva-950 font-bold border border-oliva-300',
    })

    # 7. Resultados Financieros
    items_fin = [format_item(d) for d in grupos['financieros']['items'].values() if d['ars'] != 0 or d['presup_ars'] != 0]
    total_fin_ars = sum((it['monto_ars'] for it in items_fin), Decimal('0'))
    total_fin_usd = round(total_fin_ars / tc, 2)
    total_fin_presup = sum((it['presup_ars'] for it in items_fin), Decimal('0'))
    pct_fin = round((total_fin_ars / total_ventas_ars) * 100, 1) if total_ventas_ars > 0 else 0.0
    resultado_bloques.append({
        'tipo': 'seccion',
        'key': 'financieros',
        'titulo': '7. RESULTADOS FINANCIEROS Y DIFERENCIAS DE CAMBIO',
        'items': items_fin,
        'subtotal_ars': total_fin_ars,
        'subtotal_usd': total_fin_usd,
        'presup_ars': total_fin_presup,
        'pct_ventas': pct_fin,
        'bg_header': 'bg-slate-100',
        'text_header': 'text-slate-800',
    })

    # 8. Impuestos
    items_imp = [format_item(d) for d in grupos['impuestos']['items'].values() if d['ars'] > 0 or d['presup_ars'] > 0]
    total_imp_ars = sum((it['monto_ars'] for it in items_imp), Decimal('0'))
    total_imp_usd = round(total_imp_ars / tc, 2)
    total_imp_presup = sum((it['presup_ars'] for it in items_imp), Decimal('0'))
    pct_imp = round((total_imp_ars / total_ventas_ars) * 100, 1) if total_ventas_ars > 0 else 0.0
    resultado_bloques.append({
        'tipo': 'seccion',
        'key': 'impuestos',
        'titulo': '8. IMPUESTO A LAS GANANCIAS Y TASAS',
        'items': items_imp,
        'subtotal_ars': total_imp_ars,
        'subtotal_usd': total_imp_usd,
        'presup_ars': total_imp_presup,
        'pct_ventas': pct_imp,
        'bg_header': 'bg-slate-100',
        'text_header': 'text-slate-800',
    })

    # 🏆 RESULTADO NETO FINAL
    resultado_neto_ars = ebit_ars + total_fin_ars - total_imp_ars
    resultado_neto_usd = round(resultado_neto_ars / tc, 2)
    pct_resultado_neto = round((resultado_neto_ars / total_ventas_ars) * 100, 1) if total_ventas_ars > 0 else 0.0
    resultado_bloques.append({
        'tipo': 'indicador_final',
        'titulo': '(=) RESULTADO NETO DEL EJERCICIO',
        'descripcion': 'Utilidad neta final distribuible de la campaña olivícola tras impuestos y financiamiento.',
        'monto_ars': resultado_neto_ars,
        'monto_usd': resultado_neto_usd,
        'pct_ventas': pct_resultado_neto,
        'badge_bg': 'bg-emerald-600 text-white font-black shadow-sm',
    })

    return {
        'bloques': resultado_bloques,
        'ventas_totales_ars': total_ventas_ars,
        'ventas_totales_usd': total_ventas_usd,
        'margen_bruto_ars': margen_bruto_ars,
        'margen_bruto_usd': margen_bruto_usd,
        'margen_bruto_pct': pct_margen_bruto,
        'ebitda_ars': ebitda_ars,
        'ebitda_usd': ebitda_usd,
        'ebitda_pct': pct_ebitda,
        'resultado_neto_ars': resultado_neto_ars,
        'resultado_neto_usd': resultado_neto_usd,
        'resultado_neto_pct': pct_resultado_neto,
        'tc_utilizado': tc
    }


class FinanzasDashboardView(TemplateView):
    template_name = 'finanzas/finanzas_tabs.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        empresa = Empresa.objects.first()
        ctx['empresa'] = empresa

        ctx['cuentas'] = Cuenta.objects.filter(activa=True)
        ctx['proveedores'] = CuentaCorriente.objects.filter(tipo_entidad='PROVEEDOR', activo=True)
        ctx['clientes'] = CuentaCorriente.objects.filter(tipo_entidad='CLIENTE', activo=True)
        ctx['cheques'] = Cheque.objects.all()[:15]
        ctx['movimientos_recientes'] = MovimientoFinanciero.objects.select_related('cuenta', 'cuenta_corriente')[:20]
        ctx['active_tab'] = self.request.GET.get('tab', 'flujo')

        # Coeficiente de Tipo de Cambio mensual fijado
        tc_vigente = TipoCambioMensual.get_tc(empresa=empresa, ano=2026, mes=3)
        tipos_cambio_recientes = TipoCambioMensual.objects.filter(empresa=empresa).order_by('-ano', '-mes')[:12] if empresa else []
        ctx['tc_vigente'] = tc_vigente
        ctx['tipos_cambio_recientes'] = tipos_cambio_recientes
        ctx['meses_choices'] = TipoCambioMensual.Mes.choices
        ctx['anos_choices'] = [2025, 2026, 2027]

        # Plan de Cuentas para vista integrada
        stats, cuentas_list, cuentas_qs = get_plan_cuentas_payload()
        ctx['plan_cuentas_stats'] = stats
        ctx['cuentas_plan'] = cuentas_qs
        ctx['cuentas_contables_json'] = json.dumps(cuentas_list)
        ctx['cajas_bancos'] = Cuenta.objects.all().select_related('cuenta_contable')
        ctx['categorias_insumo'] = CategoriaInsumo.objects.all().select_related('cuenta_contable_activo', 'cuenta_contable_gasto').prefetch_related('insumos')
        ctx['centros_costo'] = CentroDeCosto.objects.all().select_related('cuenta_contable_defecto')
        ctx['cuentas_imputables'] = CuentaContable.objects.filter(es_imputable=True, activa=True).order_by('codigo')

        # Totales consolidados de liquidez: Base uniforme en ARS con contravalor USD
        saldos_cuentas = Cuenta.objects.filter(activa=True).values('moneda').annotate(total=Sum('saldo_actual'))
        saldos_map = {row['moneda']: (row['total'] or Decimal('0')) for row in saldos_cuentas}
        total_ars = saldos_map.get('ARS', Decimal('0'))
        total_usd = saldos_map.get('USD', Decimal('0'))
        total_consolidado_ars = total_ars + (total_usd * tc_vigente)
        total_consolidado_usd = round(total_consolidado_ars / tc_vigente, 2) if tc_vigente > 0 else Decimal('0')
        
        ctx['total_consolidado_ars'] = total_consolidado_ars
        ctx['total_consolidado_usd'] = total_consolidado_usd

        # Datos para Módulo de Libro de IVA & Facturación (1 consulta unificada)
        try:
            mes_iva = int(self.request.GET.get('periodo_mes', 3))
        except (ValueError, TypeError):
            mes_iva = 3
        try:
            ano_iva = int(self.request.GET.get('periodo_ano', 2026))
        except (ValueError, TypeError):
            ano_iva = 2026

        ctx['periodo_mes'] = mes_iva
        ctx['periodo_ano'] = ano_iva

        facturas_mes = list(
            ComprobanteFiscal.objects.filter(
                fecha_emision__year=ano_iva, fecha_emision__month=mes_iva
            ).select_related('cuenta_corriente').order_by('-fecha_emision', '-id')
        )
        facturas_compras = [f for f in facturas_mes if f.tipo_operacion == 'COMPRA']
        facturas_ventas = [f for f in facturas_mes if f.tipo_operacion == 'VENTA']

        ctx['facturas_compras'] = facturas_compras
        ctx['facturas_ventas'] = facturas_ventas

        tot_credito = sum((f.total_iva for f in facturas_compras), Decimal('0.00'))
        tot_debito = sum((f.total_iva for f in facturas_ventas), Decimal('0.00'))
        tot_neto_compras = sum((f.neto_gravado_21 + f.neto_gravado_10_5 for f in facturas_compras), Decimal('0.00'))
        tot_neto_ventas = sum((f.neto_gravado_21 + f.neto_gravado_10_5 for f in facturas_ventas), Decimal('0.00'))
        tot_percep = sum((f.percepcion_iibb + f.percepcion_iva for f in facturas_compras), Decimal('0.00'))

        ctx['total_credito_fiscal'] = tot_credito
        ctx['total_debito_fiscal'] = tot_debito
        ctx['total_neto_compras'] = tot_neto_compras
        ctx['total_neto_ventas'] = tot_neto_ventas
        ctx['total_percepciones'] = tot_percep
        ctx['posicion_iva_neta'] = tot_debito - tot_credito

        # Pre-cargar tipos de cambio en memoria para evitar N+1 queries sobre TipoCambioMensual
        tcs_empresa = list(TipoCambioMensual.objects.filter(empresa=empresa)) if empresa else []
        tc_dict = {(tc.ano, tc.mes): tc.tc for tc in tcs_empresa}

        # Selector de Período para Flujo de Caja
        periodo_flujo = self.request.GET.get('periodo_flujo')
        if not periodo_flujo:
            if MovimientoFinanciero.objects.filter(fecha__year=2026).exists():
                periodo_flujo = 'q1_2026'
            else:
                periodo_flujo = 'ultimos_6'
        ctx['periodo_flujo'] = periodo_flujo

        if periodo_flujo == 'q1_2026':
            f_desde = datetime.date(2026, 1, 1)
            f_hasta = datetime.date(2026, 3, 31)
            ctx['periodo_flujo_label'] = "1° Trimestre 2026 (Ene - Mar)"
            meses_list = [
                ('Ene 26', datetime.date(2026, 1, 1), datetime.date(2026, 2, 1)),
                ('Feb 26', datetime.date(2026, 2, 1), datetime.date(2026, 3, 1)),
                ('Mar 26', datetime.date(2026, 3, 1), datetime.date(2026, 4, 1)),
            ]
        elif periodo_flujo == 'ano_2026':
            f_desde = datetime.date(2026, 1, 1)
            f_hasta = datetime.date(2026, 12, 31)
            ctx['periodo_flujo_label'] = "Año 2026 Completo"
            meses_list = []
            nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            for m in range(1, 13):
                d_ini = datetime.date(2026, m, 1)
                d_fin = datetime.date(2026, m + 1, 1) if m < 12 else datetime.date(2027, 1, 1)
                meses_list.append((nombres[m - 1], d_ini, d_fin))
        else: # ultimos_6
            hoy = timezone.now().date()
            f_hasta = hoy
            f_desde = (hoy.replace(day=1) - datetime.timedelta(days=5 * 28)).replace(day=1)
            ctx['periodo_flujo_label'] = "Últimos 6 Meses"
            meses_list = []
            for i in range(5, -1, -1):
                mes_ref = (hoy.replace(day=1) - datetime.timedelta(days=i * 28)).replace(day=1)
                siguiente = (mes_ref.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
                meses_list.append((mes_ref.strftime('%b %y'), mes_ref, siguiente))

        # Movimientos del período analizado (1 consulta precargada en memoria)
        movs_periodo = list(
            MovimientoFinanciero.objects.filter(
                fecha__gte=f_desde, fecha__lte=f_hasta
            ).select_related('cuenta', 'cuenta_corriente').order_by('-fecha', '-id')
        )
        
        # Desglose de ingresos y egresos
        ingresos_ars = Decimal('0')
        ingresos_usd = Decimal('0')
        egresos_ars = Decimal('0')
        egresos_usd = Decimal('0')

        for m in movs_periodo:
            tc_m = m.tipo_cambio if m.tipo_cambio > 0 else tc_dict.get((m.fecha.year, m.fecha.month), tc_vigente)
            if m.tipo == 'INGRESO':
                if m.moneda == 'USD':
                    ingresos_usd += m.importe
                    ingresos_ars += (m.importe * tc_m)
                else:
                    ingresos_ars += m.importe
                    ingresos_usd += round(m.importe / tc_m, 2) if tc_m > 0 else Decimal('0')
            elif m.tipo == 'EGRESO':
                if m.moneda == 'USD':
                    egresos_usd += m.importe
                    egresos_ars += (m.importe * tc_m)
                else:
                    egresos_ars += m.importe
                    egresos_usd += round(m.importe / tc_m, 2) if tc_m > 0 else Decimal('0')

        ctx['ingresos_periodo_total'] = ingresos_ars
        ctx['ingresos_usd_total'] = ingresos_usd
        ctx['egresos_periodo_total'] = egresos_ars
        ctx['egresos_usd_total'] = egresos_usd
        ctx['flujo_neto_periodo'] = ingresos_ars - egresos_ars
        ctx['flujo_neto_usd'] = ingresos_usd - egresos_usd
        ctx['ingresos_mes'] = ingresos_ars
        ctx['egresos_mes'] = egresos_ars

        # Gráfico dinámico por mes (Calculado 100% en memoria sobre movs_periodo, 0 queries extra)
        grafico_data = []
        for nombre_mes, d_ini, d_fin in meses_list:
            tc_mes = tc_dict.get((d_ini.year, d_ini.month), tc_vigente)
            ing_mes = Decimal('0')
            egr_mes = Decimal('0')
            for m in movs_periodo:
                if d_ini <= m.fecha < d_fin:
                    tc_m = m.tipo_cambio if m.tipo_cambio > 0 else tc_mes
                    if m.tipo == 'INGRESO':
                        ing_mes += (m.importe * tc_m if m.moneda == 'USD' else m.importe)
                    elif m.tipo == 'EGRESO':
                        egr_mes += (m.importe * tc_m if m.moneda == 'USD' else m.importe)
            
            grafico_data.append({
                'mes': nombre_mes,
                'ingresos': float(ing_mes),
                'egresos': float(egr_mes),
                'neto': float(ing_mes - egr_mes)
            })

        max_val_grafico = max([max(d['ingresos'], d['egresos']) for d in grafico_data] + [1000.0])
        for d in grafico_data:
            pct_ing = round((d['ingresos'] / max_val_grafico) * 100, 1) if max_val_grafico > 0 else 0
            pct_egr = round((d['egresos'] / max_val_grafico) * 100, 1) if max_val_grafico > 0 else 0
            d['pct_ingresos'] = pct_ing
            d['pct_egresos'] = pct_egr
            d['pct_ingresos_css'] = f"{pct_ing:.1f}"
            d['pct_egresos_css'] = f"{pct_egr:.1f}"
            d['ingresos_m'] = round(d['ingresos'] / 1_000_000, 1)
            d['egresos_m'] = round(d['egresos'] / 1_000_000, 1)
            d['neto_m'] = round(d['neto'] / 1_000_000, 1)

        ctx['grafico_data'] = grafico_data
        ctx['grafico_data_json'] = json.dumps(grafico_data)
        ctx['grafico_max_val'] = max_val_grafico
        ctx['grafico_max_m'] = round(max_val_grafico / 1_000_000, 1)
        ctx['grafico_ticks'] = [
            {'label': f"${round(max_val_grafico / 1_000_000, 1)}M", 'pct': 100},
            {'label': f"${round(max_val_grafico * 0.75 / 1_000_000, 1)}M", 'pct': 75},
            {'label': f"${round(max_val_grafico * 0.5 / 1_000_000, 1)}M", 'pct': 50},
            {'label': f"${round(max_val_grafico * 0.25 / 1_000_000, 1)}M", 'pct': 25},
            {'label': "$0", 'pct': 0},
        ]
        ctx['movimientos_flujo'] = movs_periodo[:25]

        # Conciliaciones recientes
        ctx['conciliaciones'] = ConciliacionBancaria.objects.select_related('cuenta').order_by('-fecha_extracto')[:10]

        # Cuadros de Resultados (Estado de Resultados / P&L)
        cuadros = CuadroResultado.objects.filter(empresa=empresa).order_by('-fecha_fin', '-created_at') if empresa else CuadroResultado.objects.none()
        
        # Obtener cuadro activo seleccionado o el default
        cuadro_id = self.request.GET.get('cuadro_id')
        cuadro_activo = None
        if cuadro_id and str(cuadro_id).isdigit():
            cuadro_activo = cuadros.filter(id=int(cuadro_id)).first()
        if not cuadro_activo:
            if cuadros.exists():
                cuadro_activo = cuadros.first()
            elif empresa:
                cuadro_activo = get_or_create_cuadro_default(empresa)
                cuadros = CuadroResultado.objects.filter(empresa=empresa).order_by('-fecha_fin', '-created_at')

        ctx['cuadros_resultado'] = cuadros
        ctx['cuadro_activo'] = cuadro_activo
        ctx['tipo_periodo_choices'] = CuadroResultado.TipoPeriodo.choices
        ctx['moneda_choices'] = CuadroResultado.Moneda.choices
        ctx['estado_cuadro_choices'] = CuadroResultado.EstadoCuadro.choices

        if cuadro_activo:
            tc_cuadro = cuadro_activo.tipo_cambio if cuadro_activo.tipo_cambio > 0 else tc_vigente
            ctx['tc_cuadro'] = tc_cuadro
            # Construir vista simplificada gerencial interna
            ctx['cuadro_simplificado'] = build_cuadro_simplificado(cuadro_activo, tc_cuadro)

            # Estructura detallada por Plan de Cuentas (56 cuentas)
            lineas_qs = cuadro_activo.lineas.select_related('cuenta_contable').order_by('seccion', 'cuenta_contable__codigo')
            secciones = OrderedDict()
            for key, label in LineaCuadroResultado.SeccionResultado.choices:
                secciones[key] = {
                    'key': key,
                    'label': label,
                    'lineas': [],
                    'total_real': Decimal('0'),
                    'total_presup': Decimal('0'),
                    'total_desvio': Decimal('0'),
                    'pct_ventas': Decimal('0'),
                }
            for linea in lineas_qs:
                sec = secciones.get(linea.seccion)
                if sec:
                    sec['lineas'].append(linea)
                    sec['total_real'] += (linea.monto_real or Decimal('0'))
                    sec['total_presup'] += (linea.monto_presupuestado or Decimal('0'))
                    sec['total_desvio'] += (linea.desvio_monto or Decimal('0'))
            
            vt = cuadro_activo.ventas_totales or Decimal('0')
            for sec in secciones.values():
                if vt > 0:
                    sec['pct_ventas'] = round((sec['total_real'] / vt) * 100, 2)

            ctx['secciones_resultado'] = [s for s in secciones.values() if s['lineas']]

        # Detección de datos de prueba (Q1 2026)
        ctx['hay_datos_demo'] = CuadroResultado.objects.filter(
            fecha_inicio__gte=datetime.date(2026, 1, 1), 
            fecha_fin__lte=datetime.date(2026, 3, 31)
        ).exists() or MovimientoFinanciero.objects.filter(concepto__startswith="[DEMO]").exists()

        return ctx


class CuentasListValoresView(ListView):
    model = Cuenta
    template_name = 'finanzas/partials/tab_caja.html'
    context_object_name = 'cuentas'

    def dispatch(self, request, *args, **kwargs):
        if not request.headers.get('HX-Request'):
            return redirect('/finanzas/?tab=caja')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['movimientos'] = MovimientoFinanciero.objects.select_related('cuenta')[:15]
        return ctx


class CuentaCreateView(CreateView):
    model = Cuenta
    fields = ['nombre', 'tipo', 'moneda', 'banco_nombre', 'numero_cuenta', 'cbu_cvu', 'saldo_actual', 'empresa']
    template_name = 'finanzas/partials/cuenta_form_modal.html'

    def get_success_url(self):
        return reverse('finanzas:dashboard') + '?tab=caja'

    def form_valid(self, form):
        cuenta = form.save()
        if self.request.headers.get('HX-Request'):
            return render(self.request, 'finanzas/partials/cuenta_card.html', {'c': cuenta})
        return super().form_valid(form)


class CuentaUpdateView(UpdateView):
    model = Cuenta
    fields = ['nombre', 'tipo', 'moneda', 'banco_nombre', 'numero_cuenta', 'cbu_cvu', 'activa', 'empresa']
    template_name = 'finanzas/cuenta_edit.html'
    success_url = reverse_lazy('finanzas:dashboard')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cuenta'] = self.get_object()
        return ctx


class MovimientoCreateView(CreateView):
    model = MovimientoFinanciero
    fields = ['cuenta', 'tipo', 'fecha', 'importe', 'moneda', 'concepto', 'comprobante_tipo', 'comprobante_nro', 'cuenta_corriente', 'centro_de_costo', 'finca']
    template_name = 'finanzas/partials/movimiento_form_modal.html'
    success_url = reverse_lazy('finanzas:dashboard')

    def form_valid(self, form):
        movimiento = registrar_movimiento_financiero(
            cuenta=form.cleaned_data['cuenta'],
            tipo=form.cleaned_data['tipo'],
            fecha=form.cleaned_data['fecha'],
            importe=form.cleaned_data['importe'],
            concepto=form.cleaned_data['concepto'],
            moneda=form.cleaned_data['moneda'],
            comprobante_tipo=form.cleaned_data.get('comprobante_tipo', ''),
            comprobante_nro=form.cleaned_data.get('comprobante_nro', ''),
            cuenta_corriente=form.cleaned_data.get('cuenta_corriente'),
            centro_de_costo=form.cleaned_data.get('centro_de_costo'),
            finca=form.cleaned_data.get('finca'),
            usuario=self.request.user if self.request.user.is_authenticated else None
        )
        if self.request.headers.get('HX-Request'):
            return render(self.request, 'finanzas/partials/movimiento_row.html', {'mov': movimiento})
        return super().form_valid(form)


class TransferenciaCreateView(CreateView):
    """Vista específica para registrar transferencias entre cuentas propias."""
    model = MovimientoFinanciero
    fields = ['cuenta', 'cuenta_destino', 'fecha', 'importe', 'moneda', 'concepto']
    template_name = 'finanzas/partials/transferencia_form_modal.html'
    success_url = reverse_lazy('finanzas:dashboard')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cuentas'] = Cuenta.objects.filter(activa=True)
        return ctx

    def form_valid(self, form):
        movimiento = registrar_movimiento_financiero(
            cuenta=form.cleaned_data['cuenta'],
            tipo=MovimientoFinanciero.TipoMovimiento.TRANSFERENCIA,
            fecha=form.cleaned_data['fecha'],
            importe=form.cleaned_data['importe'],
            concepto=form.cleaned_data['concepto'],
            moneda=form.cleaned_data['moneda'],
            cuenta_destino=form.cleaned_data.get('cuenta_destino'),
            usuario=self.request.user if self.request.user.is_authenticated else None
        )
        if self.request.headers.get('HX-Request'):
            return render(self.request, 'finanzas/partials/movimiento_row.html', {'mov': movimiento})
        return redirect(self.success_url)


class CuentasCorrientesProveedoresView(ListView):
    model = CuentaCorriente
    template_name = 'finanzas/partials/tab_proveedores.html'
    context_object_name = 'proveedores'

    def dispatch(self, request, *args, **kwargs):
        if not request.headers.get('HX-Request'):
            return redirect('/finanzas/?tab=proveedores')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return CuentaCorriente.objects.filter(tipo_entidad='PROVEEDOR', activo=True)


class CuentasCorrientesClientesView(ListView):
    model = CuentaCorriente
    template_name = 'finanzas/partials/tab_clientes.html'
    context_object_name = 'clientes'

    def dispatch(self, request, *args, **kwargs):
        if not request.headers.get('HX-Request'):
            return redirect('/finanzas/?tab=clientes')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return CuentaCorriente.objects.filter(tipo_entidad='CLIENTE', activo=True)


class ChequesListView(ListView):
    model = Cheque
    template_name = 'finanzas/partials/tab_cheques.html'
    context_object_name = 'cheques'

    def dispatch(self, request, *args, **kwargs):
        if not request.headers.get('HX-Request'):
            return redirect('/finanzas/?tab=cheques')
        return super().dispatch(request, *args, **kwargs)


class ChequeCreateView(CreateView):
    model = Cheque
    fields = ['tipo', 'banco_emisor', 'numero', 'emisor_firmante', 'cuit_emisor', 'fecha_emision', 'fecha_cobro', 'importe', 'cuenta_bancaria_origen', 'cuenta_corriente', 'estado', 'observaciones']
    template_name = 'finanzas/partials/cheque_form_modal.html'

    def get_success_url(self):
        return reverse('finanzas:dashboard') + '?tab=cheques'


class ConciliacionListView(ListView):
    model = ConciliacionBancaria
    template_name = 'finanzas/partials/tab_conciliacion.html'
    context_object_name = 'conciliaciones'

    def dispatch(self, request, *args, **kwargs):
        if not request.headers.get('HX-Request'):
            return redirect('/finanzas/?tab=conciliacion')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return ConciliacionBancaria.objects.select_related('cuenta', 'usuario').order_by('-fecha_extracto')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cuentas_bancarias'] = Cuenta.objects.filter(activa=True, tipo='BANCO')
        return ctx


class ConciliacionCreateView(CreateView):
    model = ConciliacionBancaria
    fields = ['cuenta', 'fecha_extracto', 'saldo_extracto', 'observaciones']
    template_name = 'finanzas/partials/conciliacion_form_modal.html'

    def get_success_url(self):
        return reverse('finanzas:dashboard') + '?tab=conciliacion'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cuentas'] = Cuenta.objects.filter(activa=True)
        return ctx

    def form_valid(self, form):
        conciliacion = form.save(commit=False)
        conciliacion.saldo_sistema = conciliacion.cuenta.saldo_actual
        conciliacion.diferencia = conciliacion.saldo_extracto - conciliacion.saldo_sistema
        if self.request.user.is_authenticated:
            conciliacion.usuario = self.request.user
        conciliacion.save()
        return redirect(self.success_url)


class ConciliacionDetailView(DetailView):
    model = ConciliacionBancaria
    template_name = 'finanzas/conciliacion_detail.html'
    context_object_name = 'conciliacion'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        c = self.get_object()
        # Movimientos del período de la cuenta
        ctx['movimientos'] = MovimientoFinanciero.objects.filter(
            cuenta=c.cuenta,
            fecha__lte=c.fecha_extracto
        ).order_by('-fecha')[:50]
        ctx['ids_conciliados'] = set(c.movimientos_conciliados.values_list('id', flat=True))
        return ctx

    def post(self, request, *args, **kwargs):
        """Marcar/desmarcar movimientos como conciliados."""
        conciliacion = self.get_object()
        mov_ids = request.POST.getlist('movimientos_conciliados')
        conciliacion.movimientos_conciliados.set(mov_ids)
        # Actualizar diferencia
        total_conciliado = conciliacion.movimientos_conciliados.filter(tipo='INGRESO').aggregate(t=Sum('importe'))['t'] or 0
        total_conciliado -= float(conciliacion.movimientos_conciliados.filter(tipo='EGRESO').aggregate(t=Sum('importe'))['t'] or 0)
        if 'cerrar' in request.POST:
            conciliacion.estado = ConciliacionBancaria.EstadoConciliacion.CERRADA
        conciliacion.save()
        return redirect('finanzas:conciliacion_detail', pk=conciliacion.pk)


# =============================================================================
# VISTAS: PLAN DE CUENTAS & ENLACES CONTABLES
# =============================================================================

class PlanCuentasView(TemplateView):
    """Visor interactivo Tree-View del Plan de Cuentas Agropecuario e Industrial."""
    template_name = 'finanzas/plan_cuentas.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        stats, cuentas_list, cuentas_qs = get_plan_cuentas_payload()
        ctx['stats'] = stats
        ctx['cuentas_plan'] = cuentas_qs
        ctx['cuentas_json'] = json.dumps(cuentas_list)
        ctx['cajas_bancos'] = Cuenta.objects.all().select_related('cuenta_contable')
        ctx['categorias_insumo'] = CategoriaInsumo.objects.all().select_related('cuenta_contable_activo', 'cuenta_contable_gasto')
        ctx['centros_costo'] = CentroDeCosto.objects.all().select_related('cuenta_contable_defecto')
        ctx['cuentas_imputables'] = CuentaContable.objects.filter(es_imputable=True, activa=True).order_by('codigo')
        return ctx


class CuentaContableDetailModalView(DetailView):
    """Modal HTMX / parcial con el detalle agronómico y las relaciones de una cuenta contable."""
    model = CuentaContable
    template_name = 'finanzas/partials/cuenta_contable_detail_modal.html'
    context_object_name = 'cuenta'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        c = self.get_object()
        ctx['cajas_vinculadas'] = c.cuentas_financieras.all()
        ctx['categorias_activo'] = c.categorias_insumo_activo.all()
        ctx['categorias_gasto'] = c.categorias_insumo_gasto.all()
        ctx['centros_costo'] = c.centros_de_costo.all()
        ctx['insumos_vinculados'] = c.insumos_vinculados.all()
        return ctx


class CuentaContableUpdateView(UpdateView):
    """Permite actualizar la nota técnica o estado de una cuenta contable."""
    model = CuentaContable
    fields = ['nombre', 'saldo_habitual', 'clase', 'es_imputable', 'nota', 'activa']
    template_name = 'finanzas/partials/cuenta_contable_edit_modal.html'
    success_url = reverse_lazy('finanzas:plan_cuentas')

    def form_valid(self, form):
        messages.success(self.request, f"Cuenta {form.instance.codigo} actualizada con éxito.")
        return super().form_valid(form)


class VincularEntidadRapidaView(View):
    """Enlace rápido desde la interfaz entre entidades operativas y cuentas del Plan de Cuentas."""

    def post(self, request, *args, **kwargs):
        entidad_tipo = request.POST.get('entidad_tipo')
        entidad_id = request.POST.get('entidad_id')
        cuenta_id = request.POST.get('cuenta_contable_id')
        campo = request.POST.get('campo', 'defecto')

        cuenta_contable = CuentaContable.objects.filter(id=cuenta_id).first() if cuenta_id else None

        if entidad_tipo == 'caja':
            caja = get_object_or_404(Cuenta, id=entidad_id)
            caja.cuenta_contable = cuenta_contable
            caja.save(update_fields=['cuenta_contable'])
            messages.success(request, f"Caja/Banco '{caja.nombre}' vinculado a cuenta contable.")

        elif entidad_tipo == 'categoria_insumo':
            cat = get_object_or_404(CategoriaInsumo, id=entidad_id)
            if campo == 'activo':
                cat.cuenta_contable_activo = cuenta_contable
                cat.save(update_fields=['cuenta_contable_activo'])
                messages.success(request, f"Cuenta de activo de categoría '{cat.nombre}' actualizada.")
            else:
                cat.cuenta_contable_gasto = cuenta_contable
                cat.save(update_fields=['cuenta_contable_gasto'])
                messages.success(request, f"Cuenta de consumo de categoría '{cat.nombre}' actualizada.")

        elif entidad_tipo == 'centro_costo':
            cc = get_object_or_404(CentroDeCosto, id=entidad_id)
            cc.cuenta_contable_defecto = cuenta_contable
            cc.save(update_fields=['cuenta_contable_defecto'])
            messages.success(request, f"Centro de Costo '{cc.nombre}' vinculado a cuenta contable.")

        next_url = request.POST.get('next', reverse_lazy('finanzas:plan_cuentas'))
        return redirect(next_url)


class SincronizarPlanCuentasView(View):
    """Ejecuta la sincronización / reimportación desde el archivo Excel del servidor."""

    def post(self, request, *args, **kwargs):
        try:
            call_command('importar_plan_cuentas')
            messages.success(request, "Plan de Cuentas sincronizado exitosamente desde el archivo Excel.")
        except Exception as e:
            messages.error(request, f"Error al sincronizar Plan de Cuentas: {e}")

        next_url = request.POST.get('next', reverse_lazy('finanzas:plan_cuentas'))
        return redirect(next_url)


class TipoCambioGuardarView(View):
    """Guarda o actualiza el coeficiente oficial de tipo de cambio para un año y mes."""

    def post(self, request, *args, **kwargs):
        empresa = Empresa.objects.first()
        ano = request.POST.get('ano')
        mes = request.POST.get('mes')
        tc_str = request.POST.get('tc', '').strip().replace(',', '.')
        fuente = request.POST.get('fuente', '').strip() or 'Banco Nación (BNA) / Oficial'

        try:
            ano_val = int(ano)
            mes_val = int(mes)
            tc_val = Decimal(tc_str)
            if tc_val <= 0:
                raise ValueError("El tipo de cambio debe ser mayor a 0.")

            obj, created = TipoCambioMensual.objects.update_or_create(
                empresa=empresa,
                ano=ano_val,
                mes=mes_val,
                defaults={
                    'tc': tc_val,
                    'fuente': fuente,
                }
            )

            # Sincronizar con cuadros de resultados que abarquen este mes
            if empresa:
                for c in CuadroResultado.objects.filter(empresa=empresa, fecha_inicio__year=ano_val):
                    if c.fecha_inicio.month <= mes_val <= c.fecha_fin.month:
                        c.tipo_cambio = tc_val
                        c.save(update_fields=['tipo_cambio'])

            action_text = "registrado" if created else "actualizado"
            messages.success(
                request,
                f"Coeficiente de Tipo de Cambio para {obj.get_mes_display()} {ano_val} {action_text}: $1 USD = ${tc_val:,.2f} ARS."
            )
        except Exception as e:
            messages.error(request, f"Error al guardar el tipo de cambio: {str(e)}")

        redirect_url = request.META.get('HTTP_REFERER') or '/finanzas/'
        return redirect(redirect_url)


class CuadroResultadoCreateView(View):
    """Crea un nuevo período para el Estado de Resultados."""

    def post(self, request, *args, **kwargs):
        empresa = Empresa.objects.first()
        titulo = request.POST.get('titulo', '').strip() or 'Nuevo Estado de Resultados'
        tipo_periodo = request.POST.get('tipo_periodo', CuadroResultado.TipoPeriodo.CAMPANA_ANUAL)
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        moneda = request.POST.get('moneda', CuadroResultado.Moneda.ARS)
        tc_default = TipoCambioMensual.get_tc(empresa=empresa)
        tipo_cambio = request.POST.get('tipo_cambio') or str(tc_default)
        vol_aceituna = request.POST.get('volumen_aceituna_kg', '0')
        vol_aceite = request.POST.get('volumen_aceite_litros', '0')
        clonar_de = request.POST.get('clonar_de')

        try:
            cuadro = CuadroResultado.objects.create(
                empresa=empresa,
                titulo=titulo,
                tipo_periodo=tipo_periodo,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                moneda=moneda,
                tipo_cambio=Decimal(tipo_cambio) if tipo_cambio else tc_default,
                volumen_aceituna_kg=Decimal(vol_aceituna) if vol_aceituna else Decimal('0'),
                volumen_aceite_litros=Decimal(vol_aceite) if vol_aceite else Decimal('0'),
                usuario=request.user if request.user.is_authenticated else None,
                estado=CuadroResultado.EstadoCuadro.BORRADOR
            )

            if clonar_de and str(clonar_de).isdigit():
                orig = CuadroResultado.objects.filter(id=int(clonar_de)).first()
                if orig:
                    for l in orig.lineas.all():
                        LineaCuadroResultado.objects.create(
                            cuadro=cuadro,
                            cuenta_contable=l.cuenta_contable,
                            seccion=l.seccion,
                            monto_real=l.monto_real,
                            monto_presupuestado=l.monto_presupuestado,
                            observaciones=l.observaciones
                        )
                    cuadro.recalcular_totales(save=True)
            else:
                poblar_lineas_cuadro(cuadro, inicializar_con_valores_demo=False)

            messages.success(request, f"Cuadro de resultados '{cuadro.titulo}' creado exitosamente.")
            return redirect(f"/finanzas/?tab=resultados&cuadro_id={cuadro.id}")
        except Exception as e:
            messages.error(request, f"Error al crear el cuadro: {str(e)}")
            return redirect("/finanzas/?tab=resultados")


class LineaCuadroResultadoUpdateView(View):
    """Actualiza una línea individual del cuadro (monto real, presupuesto u observaciones). Soporta AJAX."""

    def post(self, request, pk, *args, **kwargs):
        linea = get_object_or_404(LineaCuadroResultado, pk=pk)
        monto_real = request.POST.get('monto_real')
        monto_presup = request.POST.get('monto_presupuestado')
        obs = request.POST.get('observaciones')

        if monto_real is not None:
            try:
                linea.monto_real = Decimal(monto_real.replace(',', '.'))
            except Exception:
                pass
        if monto_presup is not None:
            try:
                linea.monto_presupuestado = Decimal(monto_presup.replace(',', '.'))
            except Exception:
                pass
        if obs is not None:
            linea.observaciones = obs.strip()

        linea.save()
        cuadro = linea.cuadro
        cuadro.recalcular_totales(save=True)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
            linea.refresh_from_db()
            return JsonResponse({
                'status': 'ok',
                'linea': {
                    'id': linea.id,
                    'monto_real': float(linea.monto_real),
                    'monto_presupuestado': float(linea.monto_presupuestado),
                    'desvio_monto': float(linea.desvio_monto),
                    'desvio_porcentaje': float(linea.desvio_porcentaje),
                    'porcentaje_ventas': float(linea.porcentaje_ventas),
                    'observaciones': linea.observaciones,
                },
                'cuadro': {
                    'ventas_totales': float(cuadro.ventas_totales),
                    'costo_produccion': float(cuadro.costo_produccion),
                    'margen_bruto': float(cuadro.margen_bruto),
                    'margen_bruto_pct': cuadro.margen_bruto_pct,
                    'ebitda': float(cuadro.ebitda),
                    'margen_ebitda_pct': cuadro.margen_ebitda_pct,
                    'resultado_neto': float(cuadro.resultado_neto),
                    'margen_neto_pct': cuadro.margen_neto_pct,
                }
            })

        messages.success(request, f"Línea '{linea.cuenta_contable.nombre}' actualizada.")
        return redirect(f"/finanzas/?tab=resultados&cuadro_id={cuadro.id}")


class CuadroResultadoNotasUpdateView(View):
    """Actualiza notas ejecutivas, estado y parámetros del período para el Directorio."""

    def post(self, request, pk, *args, **kwargs):
        cuadro = get_object_or_404(CuadroResultado, pk=pk)
        notas = request.POST.get('notas_gerencia')
        estado = request.POST.get('estado')
        vol_kg = request.POST.get('volumen_aceituna_kg')
        vol_lt = request.POST.get('volumen_aceite_litros')

        if notas is not None:
            cuadro.notas_gerencia = notas.strip()
        if estado in dict(CuadroResultado.EstadoCuadro.choices):
            cuadro.estado = estado
        if vol_kg:
            try:
                cuadro.volumen_aceituna_kg = Decimal(vol_kg.replace(',', '.'))
            except Exception:
                pass
        if vol_lt:
            try:
                cuadro.volumen_aceite_litros = Decimal(vol_lt.replace(',', '.'))
            except Exception:
                pass

        cuadro.save()
        messages.success(request, "Notas gerenciales y parámetros del período actualizados con éxito.")
        return redirect(f"/finanzas/?tab=resultados&cuadro_id={cuadro.id}")


class CuadroResultadoPrintView(DetailView):
    """Vista ejecutiva de presentación imprimible para Gerencia General y Directorio."""
    model = CuadroResultado
    template_name = 'finanzas/cuadro_resultado_print.html'
    context_object_name = 'cuadro'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cuadro = self.object
        lineas_qs = cuadro.lineas.select_related('cuenta_contable').order_by('seccion', 'cuenta_contable__codigo')
        secciones = OrderedDict()
        for key, label in LineaCuadroResultado.SeccionResultado.choices:
            secciones[key] = {
                'key': key,
                'label': label,
                'lineas': [],
                'total_real': Decimal('0'),
                'total_presup': Decimal('0'),
                'total_desvio': Decimal('0'),
                'pct_ventas': Decimal('0'),
            }
        for linea in lineas_qs:
            sec = secciones.get(linea.seccion)
            if sec:
                sec['lineas'].append(linea)
                sec['total_real'] += (linea.monto_real or Decimal('0'))
                sec['total_presup'] += (linea.monto_presupuestado or Decimal('0'))
                sec['total_desvio'] += (linea.desvio_monto or Decimal('0'))

        vt = cuadro.ventas_totales or Decimal('0')
        for sec in secciones.values():
            if vt > 0:
                sec['pct_ventas'] = round((sec['total_real'] / vt) * 100, 2)

        tc_cuadro = cuadro.tipo_cambio if cuadro.tipo_cambio > 0 else TipoCambioMensual.get_tc(empresa=cuadro.empresa)
        ctx['tc_cuadro'] = tc_cuadro
        ctx['cuadro_simplificado'] = build_cuadro_simplificado(cuadro, tc_cuadro)
        ctx['secciones_resultado'] = [s for s in secciones.values() if s['lineas']]
        ctx['empresa'] = cuadro.empresa
        return ctx


class LimpiarDatosDemoView(View):
    """Purga de forma segura todos los datos transaccionales de prueba Q1 2026."""
    def post(self, request, *args, **kwargs):
        from apps.core.services_demo import limpiar_datos_demo_q1_2026
        try:
            reporte = limpiar_datos_demo_q1_2026()
            total_eliminados = sum(v for k, v in reporte.items() if isinstance(v, int))
            messages.success(
                request,
                f"Datos de prueba Q1 2026 eliminados con éxito ({total_eliminados} registros purgados). El sistema quedó listo para operar con datos 100% reales."
            )
        except Exception as e:
            messages.error(request, f"Error al limpiar datos de prueba: {str(e)}")
        
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('finanzas:dashboard')


class PoblarDatosDemoView(View):
    """Siembra los datos de prueba coherentes para Q1 2026."""
    def post(self, request, *args, **kwargs):
        from apps.core.services_demo import poblar_datos_demo_q1_2026
        try:
            poblar_datos_demo_q1_2026()
            messages.success(request, "Datos de prueba del 1° Trimestre 2026 (Ene-Mar) generados con éxito.")
        except Exception as e:
            messages.error(request, f"Error al poblar datos de prueba: {str(e)}")
        
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('finanzas:dashboard')


class ComprobantePrintView(DetailView):
    """Vista imprimible oficial para Facturas, Recibos y Comprobantes Comerciales con logo corporativo."""
    model = MovimientoFinanciero
    template_name = 'finanzas/comprobante_print.html'
    context_object_name = 'mov'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        mov = self.object
        empresa = getattr(mov.cuenta, 'empresa', None) or Empresa.objects.first()
        ctx['empresa'] = empresa

        tipo_upper = (mov.comprobante_tipo or '').strip().upper()

        # Clasificación fiscal AFIP del comprobante
        if 'FACTURA A' in tipo_upper or 'FACTURA-A' in tipo_upper or tipo_upper == 'A':
            letra = 'A'
            cod_afip = '01'
            nombre_doc = 'FACTURA "A"'
            aplica_iva = True
        elif 'FACTURA B' in tipo_upper or 'FACTURA-B' in tipo_upper or tipo_upper == 'B':
            letra = 'B'
            cod_afip = '06'
            nombre_doc = 'FACTURA "B"'
            aplica_iva = True
        elif 'FACTURA E' in tipo_upper or 'FACTURA-E' in tipo_upper or tipo_upper == 'E':
            letra = 'E'
            cod_afip = '19'
            nombre_doc = 'FACTURA "E" DE EXPORTACIÓN'
            aplica_iva = False
        elif 'RECIBO' in tipo_upper:
            letra = 'R'
            cod_afip = '04'
            nombre_doc = 'RECIBO OFICIAL DE COBRANZA / PAGO'
            aplica_iva = False
        elif 'TICKET' in tipo_upper:
            letra = 'T'
            cod_afip = '83'
            nombre_doc = 'TICKET FISCAL'
            aplica_iva = True
        else:
            if mov.tipo == MovimientoFinanciero.TipoMovimiento.INGRESO:
                letra = 'A' if (mov.cuenta_corriente and mov.cuenta_corriente.tipo_entidad == CuentaCorriente.TipoEntidad.CLIENTE) else 'B'
                cod_afip = '01' if letra == 'A' else '06'
                nombre_doc = f'FACTURA COMERCIAL "{letra}"'
                aplica_iva = True
            else:
                letra = 'X'
                cod_afip = '99'
                nombre_doc = 'ORDEN DE PAGO / COMPROBANTE DE EGRESO'
                aplica_iva = False

        # Desglose de importes e IVA (21% estándar)
        if aplica_iva:
            tasa_iva = Decimal('21.00')
            neto_gravado = (mov.importe / Decimal('1.21')).quantize(Decimal('0.01'))
            iva_liquidado = (mov.importe - neto_gravado).quantize(Decimal('0.01'))
        else:
            tasa_iva = Decimal('0.00')
            neto_gravado = mov.importe
            iva_liquidado = Decimal('0.00')

        # Formato de punto de venta y número
        comp_nro = mov.comprobante_nro or f"{mov.pk:08d}"
        if '-' in comp_nro:
            partes = comp_nro.split('-', 1)
            pto_vta = partes[0].zfill(4)
            nro_formateado = partes[1].zfill(8)
        else:
            pto_vta = '0001'
            nro_formateado = comp_nro.zfill(8)

        # Conversión cambiaria
        tc = mov.tipo_cambio if (mov.tipo_cambio and mov.tipo_cambio > 1) else TipoCambioMensual.get_tc(empresa, mov.fecha.year, mov.fecha.month)
        if mov.moneda == 'ARS':
            importe_usd = (mov.importe / tc).quantize(Decimal('0.01')) if tc else None
            importe_ars = mov.importe
        else:
            importe_usd = mov.importe
            importe_ars = (mov.importe * tc).quantize(Decimal('0.01')) if tc else mov.importe

        from datetime import timedelta
        cae_num = f"74{mov.fecha.strftime('%y%m')}{mov.pk:08d}"[:14]
        vto_cae = mov.fecha + timedelta(days=10)

        # Generar QR para comprobante de tesorería
        try:
            import qrcode, io, base64
            qr = qrcode.QRCode(version=1, box_size=4, border=1)
            qr_content = f"https://www.arca.gob.ar/fe/qr/?p=mov-{mov.pk}-{cae_num}"
            qr.add_data(qr_content)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#1e293b", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            qr_arca_base64 = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
            qr_arca_url = qr_content
        except Exception:
            qr_arca_base64 = ""
            qr_arca_url = ""

        ctx.update({
            'letra': letra,
            'cod_afip': cod_afip,
            'nombre_doc': nombre_doc,
            'aplica_iva': aplica_iva,
            'tasa_iva': tasa_iva,
            'neto_gravado': neto_gravado,
            'iva_liquidado': iva_liquidado,
            'pto_vta': pto_vta,
            'nro_formateado': nro_formateado,
            'tc': tc,
            'importe_ars': importe_ars,
            'importe_usd': importe_usd,
            'cae_num': cae_num,
            'vto_cae': vto_cae,
            'qr_arca_base64': qr_arca_base64,
            'qr_arca_url': qr_arca_url,
        })
        return ctx


class PagoProveedorView(View):
    """Registra una Orden de Pago a Proveedor con impacto en caja y saldo de cuenta corriente."""
    def post(self, request):
        proveedor_id = request.POST.get('proveedor_id')
        cuenta_id = request.POST.get('cuenta_id')
        importe = Decimal(request.POST.get('importe', '0'))
        fecha_str = request.POST.get('fecha')
        concepto = request.POST.get('concepto', 'Pago a Proveedor')
        comprobante_nro = request.POST.get('comprobante_nro', '')
        
        proveedor = get_object_or_404(CuentaCorriente, id=proveedor_id, tipo_entidad=CuentaCorriente.TipoEntidad.PROVEEDOR)
        cuenta = get_object_or_404(Cuenta, id=cuenta_id)
        
        fecha = datetime.date.fromisoformat(fecha_str) if fecha_str else timezone.now().date()
        
        mov = registrar_movimiento_financiero(
            cuenta=cuenta,
            tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
            fecha=fecha,
            importe=importe,
            moneda=cuenta.moneda,
            concepto=concepto,
            comprobante_tipo="ORDEN_PAGO",
            comprobante_nro=comprobante_nro,
            cuenta_corriente=proveedor,
            usuario=request.user if request.user.is_authenticated else None
        )
        messages.success(request, f"Pago de ${importe:,.2f} registrado exitosamente a {proveedor.razon_social}.")
        return redirect(reverse_lazy('finanzas:dashboard') + '?tab=proveedores')


class CobroClienteView(View):
    """Registra un Recibo de Cobranza de Cliente con impacto en cuenta bancaria y saldo del cliente."""
    def post(self, request):
        cliente_id = request.POST.get('cliente_id')
        cuenta_id = request.POST.get('cuenta_id')
        importe = Decimal(request.POST.get('importe', '0'))
        fecha_str = request.POST.get('fecha')
        concepto = request.POST.get('concepto', 'Cobranza de Cliente')
        comprobante_nro = request.POST.get('comprobante_nro', '')
        
        cliente = get_object_or_404(CuentaCorriente, id=cliente_id, tipo_entidad=CuentaCorriente.TipoEntidad.CLIENTE)
        cuenta = get_object_or_404(Cuenta, id=cuenta_id)
        
        fecha = datetime.date.fromisoformat(fecha_str) if fecha_str else timezone.now().date()
        
        mov = registrar_movimiento_financiero(
            cuenta=cuenta,
            tipo=MovimientoFinanciero.TipoMovimiento.INGRESO,
            fecha=fecha,
            importe=importe,
            moneda=cuenta.moneda,
            concepto=concepto,
            comprobante_tipo="RECIBO_COBRO",
            comprobante_nro=comprobante_nro,
            cuenta_corriente=cliente,
            usuario=request.user if request.user.is_authenticated else None
        )
        messages.success(request, f"Cobranza de ${importe:,.2f} registrada exitosamente de {cliente.razon_social}.")
        return redirect(reverse_lazy('finanzas:dashboard') + '?tab=clientes')


class ComprobanteCuentaCorrienteView(View):
    """Registra una Factura de Compra (Proveedor) o Factura de Venta (Cliente) en Cuenta Corriente."""
    def post(self, request):
        entidad_id = request.POST.get('entidad_id')
        importe = Decimal(request.POST.get('importe', '0'))
        tipo_comprobante = request.POST.get('tipo_comprobante', 'FACTURA')
        comprobante_nro = request.POST.get('comprobante_nro', '')
        concepto = request.POST.get('concepto', '')
        fecha_str = request.POST.get('fecha')
        fecha = datetime.date.fromisoformat(fecha_str) if fecha_str else timezone.now().date()
        
        entidad = get_object_or_404(CuentaCorriente, id=entidad_id)
        if entidad.tipo_entidad == CuentaCorriente.TipoEntidad.PROVEEDOR:
            # Factura de compra: aumenta nuestra deuda (saldo más negativo)
            entidad.saldo_actual -= importe
            entidad.save(update_fields=['saldo_actual', 'updated_at'])
            messages.success(request, f"Comprobante {tipo_comprobante} N° {comprobante_nro} registrado por ${importe:,.2f} a {entidad.razon_social}.")
            return redirect(reverse_lazy('finanzas:dashboard') + '?tab=proveedores')
        else:
            # Factura de venta: aumenta saldo a cobrar (más positivo)
            entidad.saldo_actual += importe
            entidad.save(update_fields=['saldo_actual', 'updated_at'])
            messages.success(request, f"Factura de Venta N° {comprobante_nro} registrada por ${importe:,.2f} a {entidad.razon_social}.")
            return redirect(reverse_lazy('finanzas:dashboard') + '?tab=clientes')


class CuentaCorrienteDetalleModalView(View):
    """Devuelve el extracto / movimientos de una cuenta corriente específica para modal HTMX."""
    def get(self, request, pk):
        entidad = get_object_or_404(CuentaCorriente, pk=pk)
        movimientos = MovimientoFinanciero.objects.filter(cuenta_corriente=entidad).select_related('cuenta').order_by('-fecha', '-created_at')[:50]
        cheques = Cheque.objects.filter(cuenta_corriente=entidad).order_by('-fecha_cobro')[:20]
        return render(request, 'finanzas/partials/cuenta_corriente_movimientos_modal.html', {
            'entidad': entidad,
            'movimientos': movimientos,
            'cheques': cheques
        })


class ArqueoCajaView(View):
    """Procesa el arqueo de caja físico y genera ajuste automático si se solicita."""
    def post(self, request):
        cuenta_id = request.POST.get('cuenta_id')
        monto_fisico = Decimal(request.POST.get('monto_fisico', '0'))
        observaciones = request.POST.get('observaciones', '')
        ajustar = request.POST.get('ajustar_saldo') in ('true', 'on', '1', True)
        
        cuenta = get_object_or_404(Cuenta, id=cuenta_id)
        diferencia = monto_fisico - cuenta.saldo_actual
        
        if ajustar and diferencia != Decimal('0'):
            if diferencia > 0:
                tipo = MovimientoFinanciero.TipoMovimiento.INGRESO
                concepto = f"Ajuste Arqueo (Sobrante de Caja): {observaciones}".strip(' :')
                imp = diferencia
            else:
                tipo = MovimientoFinanciero.TipoMovimiento.EGRESO
                concepto = f"Ajuste Arqueo (Faltante de Caja): {observaciones}".strip(' :')
                imp = abs(diferencia)
                
            registrar_movimiento_financiero(
                cuenta=cuenta,
                tipo=tipo,
                fecha=timezone.now().date(),
                importe=imp,
                moneda=cuenta.moneda,
                concepto=concepto,
                comprobante_tipo="ARQUEO_CAJA",
                usuario=request.user if request.user.is_authenticated else None
            )
            messages.success(request, f"Arqueo realizado en {cuenta.nombre}. Saldo ajustado a ${monto_fisico:,.2f} con registro de diferencia.")
        else:
            messages.info(request, f"Arqueo registrado en {cuenta.nombre}. Conteo físico: ${monto_fisico:,.2f} | Sistema: ${cuenta.saldo_actual:,.2f} | Diferencia: ${diferencia:,.2f}.")
            
        return redirect(reverse_lazy('finanzas:dashboard') + '?tab=caja')


class ChequeCambiarEstadoView(View):
    """Gestiona el ciclo de vida del cheque: depositar, cobrar/acreditar, endosar o rechazar."""
    def post(self, request, pk):
        cheque = get_object_or_404(Cheque, pk=pk)
        accion = request.POST.get('accion')
        
        if accion == 'depositar':
            cuenta_id = request.POST.get('cuenta_bancaria_id')
            cuenta = get_object_or_404(Cuenta, id=cuenta_id)
            cheque.estado = Cheque.EstadoCheque.DEPOSITADO
            cheque.cuenta_bancaria_origen = cuenta
            cheque.save(update_fields=['estado', 'cuenta_bancaria_origen', 'updated_at'])
            messages.success(request, f"Cheque #{cheque.numero} depositado en {cuenta.nombre}.")
            
        elif accion == 'acreditar':
            cuenta = cheque.cuenta_bancaria_origen or Cuenta.objects.filter(tipo='BANCO', activa=True).first()
            if not cuenta:
                messages.error(request, "Debe especificar o contar con una cuenta bancaria activa.")
                return redirect(reverse_lazy('finanzas:dashboard') + '?tab=cheques')
                
            cheque.estado = Cheque.EstadoCheque.COBRADO
            cheque.save(update_fields=['estado', 'updated_at'])
            # Acreditar fondos en la cuenta bancaria
            registrar_movimiento_financiero(
                cuenta=cuenta,
                tipo=MovimientoFinanciero.TipoMovimiento.INGRESO,
                fecha=timezone.now().date(),
                importe=cheque.importe,
                moneda=cuenta.moneda,
                concepto=f"Acreditación Cheque {cheque.banco_emisor} #{cheque.numero} ({cheque.emisor_firmante})",
                comprobante_tipo="CHEQUE_COBRADO",
                comprobante_nro=cheque.numero,
                usuario=request.user if request.user.is_authenticated else None
            )
            messages.success(request, f"Cheque #{cheque.numero} acreditado en {cuenta.nombre} por ${cheque.importe:,.2f}.")
            
        elif accion == 'endosar':
            proveedor_id = request.POST.get('proveedor_id')
            proveedor = get_object_or_404(CuentaCorriente, id=proveedor_id, tipo_entidad=CuentaCorriente.TipoEntidad.PROVEEDOR)
            cheque.estado = Cheque.EstadoCheque.ENTREGADO_PROVEEDOR
            cheque.cuenta_corriente = proveedor
            cheque.save(update_fields=['estado', 'cuenta_corriente', 'updated_at'])
            # Reduce la deuda con el proveedor
            proveedor.saldo_actual += cheque.importe
            proveedor.save(update_fields=['saldo_actual', 'updated_at'])
            messages.success(request, f"Cheque #{cheque.numero} (${cheque.importe:,.2f}) endosado a {proveedor.razon_social}. Deuda cancelada.")
            
        elif accion == 'rechazar':
            motivo = request.POST.get('motivo', 'Rechazado por el banco (sin fondos o defecto formal)')
            cheque.estado = Cheque.EstadoCheque.RECHAZADO
            cheque.observaciones = f"{cheque.observaciones or ''} | Rechazo: {motivo}".strip(' |')
            cheque.save(update_fields=['estado', 'observaciones', 'updated_at'])
            messages.warning(request, f"Cheque #{cheque.numero} marcado como RECHAZADO: {motivo}.")
            
        return redirect(reverse_lazy('finanzas:dashboard') + '?tab=cheques')


class CuentaCorrienteCreateView(CreateView):
    """Crea un nuevo Cliente o Proveedor."""
    model = CuentaCorriente
    fields = ['tipo_entidad', 'razon_social', 'nombre_comercial', 'cuit', 'email', 'telefono', 'direccion', 'limite_credito']
    
    def form_valid(self, form):
        entidad = form.save()
        messages.success(self.request, f"{entidad.get_tipo_entidad_display()} '{entidad.razon_social}' creado con éxito.")
        tab = 'proveedores' if entidad.tipo_entidad == CuentaCorriente.TipoEntidad.PROVEEDOR else 'clientes'
        return redirect(reverse_lazy('finanzas:dashboard') + f'?tab={tab}')


# ──────────────────────────────────────────────────────────────────────────────
# VISTAS DE FACTURACIÓN, PAGOS/COBROS, LIBRO DE IVA Y ARQUEO DE CAJA
# ──────────────────────────────────────────────────────────────────────────────

class ComprobanteFiscalCreateView(View):
    """Alta de Comprobante Fiscal (Factura A, B, C) con impacto en cta cte y Libro de IVA."""
    def post(self, request):
        try:
            tipo_operacion = request.POST.get('tipo_operacion', 'COMPRA')
            tipo_comprobante = request.POST.get('tipo_comprobante', 'F_A')
            punto_de_venta = request.POST.get('punto_de_venta', '00001').zfill(5)
            numero_comprobante = request.POST.get('numero_comprobante', '00000001').zfill(8)
            fecha_emision = request.POST.get('fecha_emision') or timezone.now().date()
            fecha_vencimiento = request.POST.get('fecha_vencimiento') or None
            cuenta_corriente_id = request.POST.get('cuenta_corriente_id')
            concepto = request.POST.get('concepto', '').strip()

            neto_21 = Decimal(request.POST.get('neto_gravado_21') or '0.00')
            neto_105 = Decimal(request.POST.get('neto_gravado_10_5') or '0.00')
            exento = Decimal(request.POST.get('exento') or '0.00')
            percep_iibb = Decimal(request.POST.get('percepcion_iibb') or '0.00')

            iva_21 = round(neto_21 * Decimal('0.21'), 2)
            iva_105 = round(neto_105 * Decimal('0.105'), 2)
            total = neto_21 + neto_105 + iva_21 + iva_105 + exento + percep_iibb

            cuenta_corriente = get_object_or_404(CuentaCorriente, pk=cuenta_corriente_id)
            cuenta_contable_id = request.POST.get('cuenta_contable_id') or None

            condicion_iva = request.POST.get('condicion_iva') or ComprobanteFiscal.CondicionIVA.RESPONSABLE_INSCRIPTO
            comprobante = ComprobanteFiscal.objects.create(
                tipo_operacion=tipo_operacion,
                tipo_comprobante=tipo_comprobante,
                punto_de_venta=punto_de_venta,
                numero_comprobante=numero_comprobante,
                fecha_emision=fecha_emision,
                fecha_vencimiento=fecha_vencimiento,
                cuenta_corriente=cuenta_corriente,
                razon_social=cuenta_corriente.razon_social,
                cuit=cuenta_corriente.cuit,
                condicion_iva=condicion_iva,
                concepto=concepto,
                neto_gravado_21=neto_21,
                neto_gravado_10_5=neto_105,
                iva_21=iva_21,
                iva_10_5=iva_105,
                exento=exento,
                percepcion_iibb=percep_iibb,
                total=total,
                saldo_pendiente=total,
                cuenta_contable_id=cuenta_contable_id
            )

            # Impacto en la cuenta corriente
            if tipo_operacion == 'COMPRA':
                cuenta_corriente.saldo_actual -= total  # Aumenta deuda con proveedor
            else:
                cuenta_corriente.saldo_actual += total  # Aumenta crédito por cobrar a cliente
            cuenta_corriente.save(update_fields=['saldo_actual', 'updated_at'])

            # Autorización inmediata en ARCA si fue solicitada para una Venta
            autorizar_arca = request.POST.get('autorizar_arca') in ('1', 'true', 'on')
            if autorizar_arca and tipo_operacion == 'VENTA':
                try:
                    res_arca = autorizar_comprobante_arca(comprobante)
                    messages.success(
                        request,
                        f"¡Factura {comprobante.numero_completo} emitida y autorizada en ARCA! CAE: {res_arca['cae']} (Vto: {res_arca['vto_cae'].strftime('%d/%m/%Y')})."
                    )
                except Exception as e_arca:
                    messages.warning(
                        request,
                        f"Comprobante {comprobante.numero_completo} registrado en el ERP, pero no se pudo autorizar en ARCA: {str(e_arca)}. Puede autorizarlo desde el Libro de IVA."
                    )
            else:
                messages.success(request, f"Comprobante {comprobante.numero_completo} ({cuenta_corriente.razon_social}) registrado en Libro de IVA por ${total:,.2f}.")
        except Exception as e:
            messages.error(request, f"Error al registrar comprobante fiscal: {str(e)}")

        return redirect(reverse_lazy('finanzas:dashboard') + '?tab=libro_iva')


class ComprobantePagoCobroView(View):
    """Registra pago de compra o cobro de venta, emite Orden de Pago / Recibo y descuenta cta cte y caja/banco."""
    def post(self, request):
        try:
            comprobante_id = request.POST.get('comprobante_id')
            importe = Decimal(request.POST.get('importe') or '0.00')
            cuenta_financiera_id = request.POST.get('cuenta_financiera_id')
            medio_pago = request.POST.get('medio_pago', 'TRANSFERENCIA')
            fecha = request.POST.get('fecha') or timezone.now().date()
            beneficiario = request.POST.get('beneficiario_firmante', '').strip()
            es_cobro = request.POST.get('es_cobro') == '1'

            comprobante = get_object_or_404(ComprobanteFiscal, pk=comprobante_id)
            cuenta_financiera = get_object_or_404(Cuenta, pk=cuenta_financiera_id)
            cuenta_corriente = comprobante.cuenta_corriente

            tipo_doc = 'RC' if es_cobro else 'OP'
            count = OrdenPagoRecibo.objects.filter(tipo=tipo_doc).count() + 1
            numero = f"{tipo_doc}-2026-{count:04d}"

            concepto = f"{'Cobro' if es_cobro else 'Pago'} Factura {comprobante.numero_completo} ({comprobante.razon_social})"

            # Generar Movimiento Financiero
            tipo_mov = MovimientoFinanciero.TipoMovimiento.INGRESO if es_cobro else MovimientoFinanciero.TipoMovimiento.EGRESO
            mov_fin = MovimientoFinanciero.objects.create(
                cuenta=cuenta_financiera,
                tipo=tipo_mov,
                fecha=fecha,
                importe=importe,
                moneda=cuenta_financiera.moneda,
                concepto=concepto,
                comprobante_tipo=comprobante.get_tipo_comprobante_display(),
                comprobante_nro=comprobante.numero_completo,
                cuenta_corriente=cuenta_corriente,
                usuario=request.user if request.user.is_authenticated else None
            )

            # Actualizar saldos de caja/banco y cta cte
            if es_cobro:
                cuenta_financiera.saldo_actual += importe
                cuenta_corriente.saldo_actual -= importe
            else:
                cuenta_financiera.saldo_actual -= importe
                cuenta_corriente.saldo_actual += importe
            cuenta_financiera.save(update_fields=['saldo_actual', 'updated_at'])
            cuenta_corriente.save(update_fields=['saldo_actual', 'updated_at'])

            # Actualizar comprobante fiscal
            comprobante.saldo_pendiente = max(Decimal('0.00'), comprobante.saldo_pendiente - importe)
            if comprobante.saldo_pendiente == 0:
                comprobante.estado_pago = ComprobanteFiscal.EstadoPago.PAGADA
            else:
                comprobante.estado_pago = ComprobanteFiscal.EstadoPago.PAGO_PARCIAL
            comprobante.save(update_fields=['saldo_pendiente', 'estado_pago', 'updated_at'])

            # Crear Orden de Pago / Recibo
            orden = OrdenPagoRecibo.objects.create(
                tipo=tipo_doc,
                numero=numero,
                fecha=fecha,
                cuenta_corriente=cuenta_corriente,
                cuenta_financiera=cuenta_financiera,
                importe_total=importe,
                medio_pago=medio_pago,
                comprobante_fiscal=comprobante,
                movimiento_financiero=mov_fin,
                concepto=concepto,
                beneficiario_firmante=beneficiario,
                usuario=request.user if request.user.is_authenticated else None
            )

            messages.success(request, f"{orden.get_tipo_display()} {orden.numero} por ${importe:,.2f} registrada exitosamente.")
            return redirect('finanzas:orden_pago_print', pk=orden.id)
        except Exception as e:
            messages.error(request, f"Error al procesar pago/cobro: {str(e)}")
            return redirect(reverse_lazy('finanzas:dashboard') + '?tab=libro_iva')


class ArqueoCajaCreateView(View):
    """Cierre y arqueo físico de caja chica diaria."""
    def post(self, request):
        try:
            cuenta_id = request.POST.get('cuenta_id')
            fecha = request.POST.get('fecha') or timezone.now().date()
            hora = request.POST.get('hora') or '18:00'
            saldo_real_contado = Decimal(request.POST.get('saldo_real_contado') or '0.00')
            ajustar_saldo = request.POST.get('ajustar_saldo') == '1'
            observaciones = request.POST.get('observaciones', '').strip()

            cuenta = get_object_or_404(Cuenta, pk=cuenta_id)
            saldo_sistema = cuenta.saldo_actual
            diferencia = saldo_real_contado - saldo_sistema

            arqueo = ArqueoCaja.objects.create(
                cuenta=cuenta,
                fecha=fecha,
                hora=hora,
                saldo_sistema=saldo_sistema,
                saldo_real_contado=saldo_real_contado,
                diferencia=diferencia,
                estado=ArqueoCaja.Estado.CERRADO,
                observaciones=observaciones,
                usuario=request.user if request.user.is_authenticated else None
            )

            if ajustar_saldo and diferencia != 0:
                tipo_mov = MovimientoFinanciero.TipoMovimiento.INGRESO if diferencia > 0 else MovimientoFinanciero.TipoMovimiento.EGRESO
                MovimientoFinanciero.objects.create(
                    cuenta=cuenta,
                    tipo=tipo_mov,
                    fecha=fecha,
                    importe=abs(diferencia),
                    moneda=cuenta.moneda,
                    concepto=f"Ajuste por Arqueo Diario #{arqueo.id} ({'Sobrante' if diferencia > 0 else 'Faltante'})",
                    comprobante_tipo="ARQUEO",
                    comprobante_nro=f"ARQ-{arqueo.id}",
                    usuario=request.user if request.user.is_authenticated else None
                )
                cuenta.saldo_actual = saldo_real_contado
                cuenta.save(update_fields=['saldo_actual', 'updated_at'])

            dif_txt = f"+${diferencia:,.2f} (sobrante)" if diferencia > 0 else (f"-${abs(diferencia):,.2f} (faltante)" if diferencia < 0 else "cuadrada exacta")
            messages.success(request, f"Arqueo de {cuenta.nombre} cerrado con éxito al {fecha}. Diferencia: {dif_txt}.")
        except Exception as e:
            messages.error(request, f"Error al procesar el arqueo: {str(e)}")

        return redirect(reverse_lazy('finanzas:dashboard') + '?tab=caja')


class OrdenPagoReciboPrintView(DetailView):
    model = OrdenPagoRecibo
    template_name = 'finanzas/orden_pago_recibo_print.html'
    context_object_name = 'orden'


class ExportarLibroIVAView(View):
    """Exporta el Libro de IVA en formato Excel (.xlsx) con diseño corporativo."""
    def get(self, request):
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from django.http import HttpResponse
        from apps.core.models import Empresa

        try:
            mes = int(request.GET.get('mes', 3))
        except (ValueError, TypeError):
            mes = 3
        try:
            ano = int(request.GET.get('ano', 2026))
        except (ValueError, TypeError):
            ano = 2026
        tipo = request.GET.get('tipo', 'COMPRA')

        qs = ComprobanteFiscal.objects.filter(tipo_operacion=tipo, fecha_emision__year=ano, fecha_emision__month=mes).order_by('fecha_emision', 'numero_comprobante')

        empresa = Empresa.objects.first()
        razon_social = empresa.razon_social if empresa else "Empresa S.A."
        cuit = empresa.cuit if empresa else "-"
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Libro IVA {tipo.capitalize()}"

        title_font = Font(name='Arial', size=14, bold=True, color='003D4A2A')
        header_font = Font(name='Arial', size=10, bold=True, color='FFFFFFFF')
        header_fill = PatternFill(start_color='005A6E3F', end_color='005A6E3F', fill_type='solid')
        center_align = Alignment(horizontal='center', vertical='center')
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

        ws.merge_cells('A1:O1')
        ws['A1'] = f"{razon_social.upper()} - CUIT {cuit}"
        ws['A1'].font = title_font
        ws['A1'].alignment = Alignment(horizontal='center')
        
        ws.merge_cells('A2:O2')
        ws['A2'] = f"LIBRO DE IVA {tipo.upper()}S - PERÍODO {mes:02d}/{ano}"
        ws['A2'].font = Font(name='Arial', size=12, bold=True)
        ws['A2'].alignment = Alignment(horizontal='center')

        headers = ['Fecha', 'Tipo Comprobante', 'Pto. Venta', 'Número', 'CUIT', 'Razón Social', 'Cond. IVA', 
                   'Neto Grav 21%', 'IVA 21%', 'Neto Grav 10.5%', 'IVA 10.5%', 'Exento/No Gravado', 
                   'Perc. IIBB', 'Total Facturado', 'Estado AFIP']
        
        ws.append([]) # Fila 3 vacía
        ws.append(headers) # Fila 4
        
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border

        for c in qs:
            row_data = [
                c.fecha_emision.strftime('%d/%m/%Y'),
                c.get_tipo_comprobante_display(),
                f"{c.punto_venta:04d}",
                f"{c.numero_comprobante:08d}",
                c.cuenta_corriente.cuit if c.cuenta_corriente else 'Consumidor Final',
                c.cuenta_corriente.razon_social if c.cuenta_corriente else 'Varios',
                c.cuenta_corriente.get_tipo_entidad_display() if c.cuenta_corriente else '-',
                float(c.neto_gravado_21),
                float(c.iva_21),
                float(c.neto_gravado_105),
                float(c.iva_105),
                float(c.exento),
                float(c.percepciones_iibb),
                float(c.total),
                c.get_estado_afip_display()
            ]
            ws.append(row_data)

        # Anchos de columna dinámicos
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                if cell.row > 3:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
            ws.column_dimensions[column].width = min(max_length + 2, 35)

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        filename = f"Libro_IVA_{tipo}_{ano}_{mes:02d}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response


# ──────────────────────────────────────────────────────────────────────────────
# INTEGRACIÓN ARCA (EX AFIP) - AFIPSDK
# ──────────────────────────────────────────────────────────────────────────────

class AfipPadronLookupView(View):
    """Endpoint AJAX /finanzas/api/afip/padron/<cuit>/ para consultar datos fiscales en ARCA."""
    def get(self, request, cuit):
        try:
            datos = consultar_padron_arca(cuit)
            return JsonResponse({"success": True, "data": datos})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)


class ComprobanteAutorizarArcaView(View):
    """Acción para autorizar un ComprobanteFiscal de VENTA ante ARCA (WSFE) y obtener CAE."""
    def post(self, request, pk):
        comprobante = get_object_or_404(ComprobanteFiscal, pk=pk)
        try:
            res = autorizar_comprobante_arca(comprobante)
            messages.success(
                request,
                f"¡Factura autorizada exitosamente en ARCA! CAE: {res['cae']} (Vto: {res['vto_cae'].strftime('%d/%m/%Y')}). N° {res['numero_completo']}."
            )
        except Exception as e:
            messages.error(request, f"Error al autorizar en ARCA: {str(e)}")

        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect(reverse_lazy('finanzas:dashboard') + '?tab=libro_iva')


class ComprobantePdfOficialView(View):
    """Genera y redirige al PDF oficial emitido con AfipSDK."""
    def get(self, request, pk):
        comprobante = get_object_or_404(ComprobanteFiscal, pk=pk)
        if not comprobante.cae:
            messages.error(request, "El comprobante no posee CAE asignado. Debe autorizarlo primero en ARCA.")
            return redirect(reverse_lazy('finanzas:dashboard') + '?tab=libro_iva')
        try:
            res_pdf = generar_pdf_oficial_afipsdk(comprobante)
            file_url = res_pdf.get('file')
            if file_url:
                return redirect(file_url)
            messages.error(request, "No se pudo recuperar la URL del PDF oficial de AfipSDK.")
        except Exception as e:
            messages.error(request, f"Error al generar PDF oficial con AfipSDK: {str(e)}")

        return redirect(reverse_lazy('finanzas:dashboard') + '?tab=libro_iva')


class ComprobanteFiscalPrintView(DetailView):
    """Vista de impresión formal homologada para ComprobanteFiscal con QR oficial de ARCA."""
    model = ComprobanteFiscal
    template_name = 'finanzas/comprobante_print.html'
    context_object_name = 'comp'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        comp = self.object
        empresa = Empresa.objects.first()
        ctx['empresa'] = empresa
        ctx['es_comprobante_fiscal'] = True

        tipo = comp.tipo_comprobante
        if 'F_A' in tipo:
            ctx['letra'] = 'A'
            ctx['cod_afip'] = '01'
            ctx['nombre_doc'] = 'FACTURA "A"'
            ctx['aplica_iva'] = True
        elif 'F_B' in tipo:
            ctx['letra'] = 'B'
            ctx['cod_afip'] = '06'
            ctx['nombre_doc'] = 'FACTURA "B"'
            ctx['aplica_iva'] = True
        elif 'F_C' in tipo:
            ctx['letra'] = 'C'
            ctx['cod_afip'] = '11'
            ctx['nombre_doc'] = 'FACTURA "C"'
            ctx['aplica_iva'] = False
        elif 'NC_A' in tipo:
            ctx['letra'] = 'A'
            ctx['cod_afip'] = '03'
            ctx['nombre_doc'] = 'NOTA DE CRÉDITO "A"'
            ctx['aplica_iva'] = True
        elif 'NC_B' in tipo:
            ctx['letra'] = 'B'
            ctx['cod_afip'] = '08'
            ctx['nombre_doc'] = 'NOTA DE CRÉDITO "B"'
            ctx['aplica_iva'] = True
        else:
            ctx['letra'] = 'X'
            ctx['cod_afip'] = '99'
            ctx['nombre_doc'] = comp.get_tipo_comprobante_display()
            ctx['aplica_iva'] = True

        ctx['pto_vta'] = comp.punto_de_venta.zfill(4)
        ctx['nro_formateado'] = comp.numero_comprobante.zfill(8)
        ctx['neto_gravado'] = (comp.neto_gravado_21 or Decimal('0')) + (comp.neto_gravado_10_5 or Decimal('0'))
        ctx['iva_liquidado'] = comp.total_iva
        ctx['cae_num'] = comp.cae or 'PENDIENTE'
        ctx['vto_cae'] = comp.vto_cae
        ctx['mov'] = {
            'fecha': comp.fecha_emision,
            'concepto': comp.concepto,
            'comprobante_tipo': comp.get_tipo_comprobante_display(),
            'comprobante_nro': comp.numero_completo,
            'importe': comp.total,
            'moneda': 'ARS',
            'cuenta_corriente': comp.cuenta_corriente,
            'tipo': 'INGRESO' if comp.tipo_operacion == 'VENTA' else 'EGRESO',
            'pk': comp.pk
        }

        # Generación de QR oficial de ARCA
        ctx['qr_arca_url'] = generar_qr_arca_url(comp)
        ctx['qr_arca_base64'] = generar_qr_arca_base64(comp)

        return ctx
