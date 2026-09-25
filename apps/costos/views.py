import csv
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from apps.core.models import Empresa
import datetime
from decimal import Decimal
from django.views.generic import ListView, View
from django.db.models import Sum, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone

from .models import CostoPorCentro
from .services import (
    registrar_costo, 
    prorratear_costo_indirecto, 
    sincronizar_costos_con_cuadro_resultado
)
from apps.core.models import CentroDeCosto, Finca
from apps.campos.models import Cuadro, LoteDeCosecha
from apps.finanzas.models import (
    CuentaContable, 
    CuentaCorriente, 
    Cuenta, 
    CuadroResultado, 
    LineaCuadroResultado,
    TipoCambioMensual
)

CATEGORIA_META = {
    'MANO_DE_OBRA': {
        'label': 'Mano de Obra (Jornales)',
        'color': 'emerald',
        'badge_bg': 'bg-emerald-50 text-emerald-700 border-emerald-200',
        'dot_bg': 'bg-emerald-500',
        'icon': 'users',
        'cuenta_codigo': '4.2.1.01.000000',
        'cuenta_nombre': 'Sueldos y cargas sociales - producción agrícola',
    },
    'INSUMO': {
        'label': 'Insumos Agrícolas (Nutrición/Curas)',
        'color': 'amber',
        'badge_bg': 'bg-amber-50 text-amber-700 border-amber-200',
        'dot_bg': 'bg-amber-500',
        'icon': 'flask',
        'cuenta_codigo': '4.2.1.02.000000',
        'cuenta_nombre': 'Fertilizantes, agroquímicos y riego',
    },
    'COMBUSTIBLE': {
        'label': 'Combustibles y Maquinaria',
        'color': 'sky',
        'badge_bg': 'bg-sky-50 text-sky-700 border-sky-200',
        'dot_bg': 'bg-sky-500',
        'icon': 'truck',
        'cuenta_codigo': '4.2.1.06.000000',
        'cuenta_nombre': 'Fletes y acarreo de aceituna',
    },
    'CONTRATISTA': {
        'label': 'Servicios Contratistas / Fletes',
        'color': 'purple',
        'badge_bg': 'bg-purple-50 text-purple-700 border-purple-200',
        'dot_bg': 'bg-purple-500',
        'icon': 'briefcase',
        'cuenta_codigo': '4.2.1.05.000000',
        'cuenta_nombre': 'Cosecha - servicios de terceros / contratistas',
    },
    'ENERGIA_RIEGO': {
        'label': 'Energía Eléctrica y Riego',
        'color': 'cyan',
        'badge_bg': 'bg-cyan-50 text-cyan-700 border-cyan-200',
        'dot_bg': 'bg-cyan-500',
        'icon': 'zap',
        'cuenta_codigo': '4.2.1.02.000000',
        'cuenta_nombre': 'Fertilizantes, agroquímicos y riego',
    },
    'MANTENIMIENTO': {
        'label': 'Mantenimiento y Reparaciones',
        'color': 'orange',
        'badge_bg': 'bg-orange-50 text-orange-700 border-orange-200',
        'dot_bg': 'bg-orange-500',
        'icon': 'wrench',
        'cuenta_codigo': '4.2.1.07.000000',
        'cuenta_nombre': 'Amortizaciones y conservación agrícola',
    },
    'ESTRUCTURA_ADMIN': {
        'label': 'Estructura y Administración',
        'color': 'slate',
        'badge_bg': 'bg-slate-50 text-slate-700 border-slate-200',
        'dot_bg': 'bg-slate-500',
        'icon': 'building',
        'cuenta_codigo': '4.2.5.01.000000',
        'cuenta_nombre': 'Gastos de estructura y administración',
    },
}


class CostosDashboardView(ListView):
    model = CostoPorCentro
    template_name = 'costos/costos_dashboard.html'
    context_object_name = 'costos'
    paginate_by = 25

    def get_base_queryset(self):
        qs = CostoPorCentro.objects.select_related(
            'centro_de_costo', 'finca', 'cuadro', 'cuenta_contable', 'proveedor', 'movimiento_financiero'
        ).order_by('-fecha', '-id')

        finca_id = self.request.GET.get('finca')
        cuadro_id = self.request.GET.get('cuadro')
        centro_id = self.request.GET.get('centro')
        tipo = self.request.GET.get('tipo')
        mes = self.request.GET.get('mes')
        cuenta_id = self.request.GET.get('cuenta_id')
        fecha_desde = self.request.GET.get('fecha_desde')
        fecha_hasta = self.request.GET.get('fecha_hasta')
        q = self.request.GET.get('q')

        if finca_id:
            qs = qs.filter(finca_id=finca_id)
        if cuadro_id:
            if cuadro_id == 'general':
                qs = qs.filter(cuadro__isnull=True)
            else:
                qs = qs.filter(cuadro_id=cuadro_id)
        if centro_id:
            qs = qs.filter(centro_de_costo_id=centro_id)
        if tipo:
            qs = qs.filter(tipo_origen=tipo)
        if cuenta_id:
            qs = qs.filter(cuenta_contable_id=cuenta_id)
        if mes:
            try:
                m_int = int(mes)
                qs = qs.filter(fecha__year=2026, fecha__month=m_int)
            except (ValueError, TypeError):
                pass
        if fecha_desde:
            qs = qs.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha__lte=fecha_hasta)
        if q:
            q = q.strip()
            qs = qs.filter(
                Q(descripcion__icontains=q) |
                Q(documento_origen_tipo__icontains=q) |
                Q(centro_de_costo__nombre__icontains=q) |
                Q(cuadro__nombre__icontains=q) |
                Q(finca__nombre__icontains=q) |
                Q(proveedor__razon_social__icontains=q) |
                Q(cuenta_contable__nombre__icontains=q) |
                Q(cuenta_contable__codigo__icontains=q)
            )

        return qs

    def get_queryset(self):
        return self.get_base_queryset()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base_qs = self.get_base_queryset()

        # Para los agregados estadísticos y Pareto, excluimos los costos padres
        # cuyo prorrateo ya fue distribuido a los cuadros, para evitar duplicación
        base_agregados = base_qs.filter(prorrateo_realizado=False)

        # ── 1. Totales Generales y Distribución en 1 sola consulta SQL ────────
        totales_res = base_agregados.aggregate(
            total_ars=Sum('importe_ars'),
            total_usd=Sum('importe_usd'),
            costo_agricola=Sum('importe_ars', filter=Q(centro_de_costo__tipo='PRODUCTIVO_CAMPO')),
            costo_almazara=Sum('importe_ars', filter=Q(centro_de_costo__tipo='FABRICA_ALMAZARA')),
            costo_admin=Sum('importe_ars', filter=Q(centro_de_costo__tipo='ESTRUCTURA_ADMIN')),
            costos_generales_campo=Sum('importe_ars', filter=Q(cuadro__isnull=True, centro_de_costo__tipo='PRODUCTIVO_CAMPO')),
        )

        total_ars = totales_res['total_ars'] or Decimal('0.00')
        total_usd = totales_res['total_usd'] or Decimal('0.00')
        costo_agricola = totales_res['costo_agricola'] or Decimal('0.00')
        costo_almazara = totales_res['costo_almazara'] or Decimal('0.00')
        costo_admin = totales_res['costo_admin'] or Decimal('0.00')
        costos_generales_campo = totales_res['costos_generales_campo'] or Decimal('0.00')

        ctx['total_costos_ars'] = total_ars
        ctx['total_costos_usd'] = total_usd
        ctx['total_registros'] = base_qs.count()

        ctx['costo_agricola_ars'] = costo_agricola
        ctx['costo_almazara_ars'] = costo_almazara
        ctx['costo_admin_ars'] = costo_admin

        ctx['pct_agricola'] = round((costo_agricola / total_ars * 100) if total_ars > 0 else Decimal('0.0'), 1)
        ctx['pct_almazara'] = round((costo_almazara / total_ars * 100) if total_ars > 0 else Decimal('0.0'), 1)
        ctx['pct_admin'] = round((costo_admin / total_ars * 100) if total_ars > 0 else Decimal('0.0'), 1)

        # ── 3. Resumen por Categoría de Origen (Pareto) ───────────────────────
        resumen_cat_raw = base_agregados.values('tipo_origen').annotate(
            total_ars=Sum('importe_ars'),
            total_usd=Sum('importe_usd')
        ).order_by('-total_ars')

        resumen_categorias = []
        for r in resumen_cat_raw:
            code = r['tipo_origen']
            meta = CATEGORIA_META.get(code, {
                'label': code.replace('_', ' ').title(),
                'color': 'slate',
                'badge_bg': 'bg-slate-50 text-slate-700 border-slate-200',
                'dot_bg': 'bg-slate-400',
                'icon': 'tag',
                'cuenta_codigo': '4.2.1.00.000000',
                'cuenta_nombre': 'Costos generales',
            })
            val_ars = r['total_ars'] or Decimal('0.00')
            val_usd = r['total_usd'] or Decimal('0.00')
            pct = round((val_ars / total_ars * 100) if total_ars > 0 else Decimal('0.0'), 1)

            resumen_categorias.append({
                'codigo': code,
                'label': meta['label'],
                'color': meta['color'],
                'badge_bg': meta['badge_bg'],
                'dot_bg': meta['dot_bg'],
                'icon': meta['icon'],
                'cuenta_codigo': meta['cuenta_codigo'],
                'cuenta_nombre': meta['cuenta_nombre'],
                'total_ars': val_ars,
                'total_usd': val_usd,
                'porcentaje': pct,
            })
        ctx['resumen_por_categoria'] = resumen_categorias

        # ── 4. Análisis y Benchmarking Agronómico por Cuadro ($/ha y $/kg) ────
        finca_filter = self.request.GET.get('finca')
        cuadros_qs = Cuadro.objects.select_related('finca').filter(activo=True)
        if finca_filter:
            cuadros_qs = cuadros_qs.filter(finca_id=finca_filter)

        # Bulk Query 1: Costos totales por cuadro (0 queries dentro del loop)
        costos_cuadro_raw = base_agregados.filter(cuadro__isnull=False).values('cuadro_id').annotate(
            total_ars=Sum('importe_ars'),
            total_usd=Sum('importe_usd')
        )
        costos_cuadro_map = {
            r['cuadro_id']: (r['total_ars'] or Decimal('0.00'), r['total_usd'] or Decimal('0.00'))
            for r in costos_cuadro_raw
        }

        # Bulk Query 2: Kg de cosecha por cuadro
        cosecha_raw = LoteDeCosecha.objects.filter(cuadro__in=cuadros_qs).values('cuadro_id').annotate(
            total_kg=Sum('kg_cosechados')
        )
        cosecha_map = {r['cuadro_id']: (r['total_kg'] or Decimal('0.00')) for r in cosecha_raw}

        # Bulk Query 3: Desglose de labores por cuadro y origen
        desglose_raw = base_agregados.filter(cuadro__isnull=False).values('cuadro_id', 'tipo_origen').annotate(
            sub=Sum('importe_ars')
        ).order_by('cuadro_id', '-sub')
        desglose_map = {}
        for d in desglose_raw:
            desglose_map.setdefault(d['cuadro_id'], []).append({
                'tipo_origen': d['tipo_origen'],
                'sub': d['sub'] or Decimal('0.00')
            })

        resumen_cuadros = []
        total_ha_cuadros = Decimal('0.00')
        total_directo_cuadros = Decimal('0.00')
        max_costo_ha = Decimal('1.00')

        for cua in cuadros_qs:
            ha = cua.hectareas_netas or Decimal('0.00')
            total_ha_cuadros += ha

            c_ars, c_usd = costos_cuadro_map.get(cua.id, (Decimal('0.00'), Decimal('0.00')))
            total_directo_cuadros += c_ars

            costo_ha = round(c_ars / ha, 2) if ha > 0 else Decimal('0.00')
            if costo_ha > max_costo_ha:
                max_costo_ha = costo_ha

            kg_cosecha = cosecha_map.get(cua.id, Decimal('0.00'))
            costo_kg = round(c_ars / kg_cosecha, 2) if kg_cosecha > 0 else None

            desglose_labores = desglose_map.get(cua.id, [])

            resumen_cuadros.append({
                'cuadro': cua,
                'finca': cua.finca,
                'hectareas': ha,
                'costo_total_ars': c_ars,
                'costo_total_usd': c_usd,
                'costo_por_ha': costo_ha,
                'kg_cosechados': kg_cosecha,
                'costo_por_kg': costo_kg,
                'desglose': desglose_labores,
            })

        costo_general_ha = round(costos_generales_campo / total_ha_cuadros, 2) if total_ha_cuadros > 0 else Decimal('0.00')

        for it in resumen_cuadros:
            it['bar_pct'] = min(100, int((it['costo_por_ha'] / max_costo_ha) * 100)) if max_costo_ha > 0 else 0

        costo_promedio_ha = round(costo_agricola / total_ha_cuadros, 2) if total_ha_cuadros > 0 else Decimal('0.00')
        ctx['costo_promedio_ha'] = costo_promedio_ha
        ctx['total_ha_analizadas'] = total_ha_cuadros
        ctx['resumen_por_cuadro'] = resumen_cuadros
        ctx['costos_generales_campo'] = costos_generales_campo
        ctx['costo_general_ha'] = costo_general_ha

        # ── 5. Articulación Dinámica con el Plan de Cuentas (Tab 4) ───────────
        cuadro_resultado_activo = CuadroResultado.objects.order_by('-fecha_fin', '-id').first()
        ctx['cuadro_resultado_activo'] = cuadro_resultado_activo

        # Obtener todas las cuentas de egresos imputables (4.2.)
        cuentas_egreso = CuentaContable.objects.filter(
            codigo__startswith='4.2.',
            es_imputable=True,
            activa=True
        ).order_by('codigo')

        # Mapear montos de líneas de P&L existente
        lineas_pl_map = {}
        if cuadro_resultado_activo:
            for l in cuadro_resultado_activo.lineas.select_related('cuenta_contable'):
                lineas_pl_map[l.cuenta_contable_id] = l

        # Mapear sumas acumuladas de CostoPorCentro por cuenta
        sumas_costos_cuenta = dict(
            base_agregados.filter(cuenta_contable__isnull=False)
            .values_list('cuenta_contable_id')
            .annotate(t=Sum('importe_ars'))
        )

        articulacion_plan_cuentas = []
        for cta in cuentas_egreso:
            saldo_costos = sumas_costos_cuenta.get(cta.id, Decimal('0.00'))
            linea_pl = lineas_pl_map.get(cta.id)
            monto_pl_real = linea_pl.monto_real if linea_pl else Decimal('0.00')
            monto_pl_presup = linea_pl.monto_presupuestado if linea_pl else Decimal('0.00')
            diferencia = saldo_costos - monto_pl_real
            esta_conciliado = abs(diferencia) < Decimal('0.01')

            # Incluir solo si tiene saldo en costos o en el P&L, o si es de producción principal
            if saldo_costos > 0 or monto_pl_real > 0 or cta.codigo.startswith('4.2.1.'):
                articulacion_plan_cuentas.append({
                    'cuenta': cta,
                    'saldo_costos_ars': saldo_costos,
                    'monto_pl_real': monto_pl_real,
                    'monto_pl_presup': monto_pl_presup,
                    'diferencia': diferencia,
                    'esta_conciliado': esta_conciliado,
                    'seccion': linea_pl.get_seccion_display() if linea_pl else 'Costos Producción Agrícola',
                })

        ctx['articulacion_plan_cuentas'] = articulacion_plan_cuentas

        # ── 6. Opciones de Selección y Filtros ────────────────────────────────
        ctx['fincas'] = Finca.objects.filter(activa=True)
        ctx['cuadros'] = Cuadro.objects.select_related('finca').filter(activo=True)
        ctx['centros_costo'] = CentroDeCosto.objects.filter(activo=True)
        ctx['cuentas_contables'] = cuentas_egreso
        ctx['proveedores'] = CuentaCorriente.objects.filter(tipo_entidad=CuentaCorriente.TipoEntidad.PROVEEDOR, activo=True).order_by('razon_social')
        ctx['cuentas_financieras'] = Cuenta.objects.filter(activa=True).order_by('nombre')
        ctx['tipos_origen'] = CostoPorCentro.TipoOrigen.choices
        
        ctx['filtro_finca'] = self.request.GET.get('finca', '')
        ctx['filtro_cuadro'] = self.request.GET.get('cuadro', '')
        ctx['filtro_centro'] = self.request.GET.get('centro', '')
        ctx['filtro_tipo'] = self.request.GET.get('tipo', '')
        ctx['filtro_mes'] = self.request.GET.get('mes', '')
        ctx['filtro_cuenta_id'] = self.request.GET.get('cuenta_id', '')
        ctx['filtro_q'] = self.request.GET.get('q', '')
        ctx['tab_activa'] = self.request.GET.get('tab', 'imputaciones')

        # ── 7. Enriquecer los items de la página actual ───────────────────────
        for item in ctx['costos']:
            item.meta = CATEGORIA_META.get(item.tipo_origen, {
                'label': item.get_tipo_origen_display(),
                'badge_bg': 'bg-slate-100 text-slate-700',
                'dot_bg': 'bg-slate-400',
                'icon': 'tag',
            })
            if item.cuadro and item.cuadro.hectareas_netas:
                item.costo_por_ha = round(item.importe_ars / item.cuadro.hectareas_netas, 2)
            else:
                item.costo_por_ha = None

        return ctx


class CostoCreateView(View):
    """Registra una nueva imputación de costo por centro y lote agrícola."""
    def post(self, request):
        try:
            finca_id = request.POST.get('finca_id')
            cuadro_id = request.POST.get('cuadro_id')
            centro_id = request.POST.get('centro_id')
            tipo_origen = request.POST.get('tipo_origen')
            cuenta_contable_id = request.POST.get('cuenta_contable_id')
            importe_ars_str = request.POST.get('importe_ars', '0').replace(',', '.')
            importe_ars = Decimal(importe_ars_str)
            fecha_str = request.POST.get('fecha')
            fecha = datetime.date.fromisoformat(fecha_str) if fecha_str else timezone.now().date()
            descripcion = request.POST.get('descripcion', '').strip()
            proveedor_id = request.POST.get('proveedor_id')
            metodo_pago = request.POST.get('metodo_pago', 'SOLO_COSTO')
            cuenta_financiera_id = request.POST.get('cuenta_financiera_id')
            documento_origen_tipo = request.POST.get('documento_origen_tipo', '')
            documento_origen_id_str = request.POST.get('documento_origen_id', '')
            doc_id = int(documento_origen_id_str) if documento_origen_id_str.isdigit() else None

            finca = get_object_or_404(Finca, id=finca_id)
            centro = get_object_or_404(CentroDeCosto, id=centro_id)
            cuadro = Cuadro.objects.filter(id=cuadro_id).first() if cuadro_id and cuadro_id != 'general' else None
            cuenta_contable = CuentaContable.objects.filter(id=cuenta_contable_id).first() if cuenta_contable_id else None
            proveedor = CuentaCorriente.objects.filter(id=proveedor_id).first() if proveedor_id else None
            cuenta_financiera = Cuenta.objects.filter(id=cuenta_financiera_id).first() if cuenta_financiera_id else None

            costo = registrar_costo(
                centro_de_costo=centro,
                finca=finca,
                fecha=fecha,
                importe_ars=importe_ars,
                tipo_origen=tipo_origen,
                descripcion=descripcion,
                cuadro=cuadro,
                cuenta_contable=cuenta_contable,
                proveedor=proveedor,
                metodo_pago=metodo_pago,
                cuenta_financiera=cuenta_financiera,
                documento_origen_tipo=documento_origen_tipo,
                documento_origen_id=doc_id,
                usuario=request.user if request.user.is_authenticated else None
            )

            cuadro_nombre = f"Cuadro {cuadro.codigo}" if cuadro else "General Finca (Indirecto)"
            messages.success(
                request, 
                f"Costo registrado con éxito: ${importe_ars:,.2f} en {cuadro_nombre} "
                f"imputado a cuenta [{costo.cuenta_contable.codigo if costo.cuenta_contable else 'General'}]."
            )
        except Exception as e:
            messages.error(request, f"Error al registrar costo: {str(e)}")

        return redirect(reverse_lazy('costos:dashboard') + '?tab=imputaciones')


class CostoUpdateView(View):
    """Edita una imputación de costo existente."""
    def post(self, request, pk):
        costo = get_object_or_404(CostoPorCentro, pk=pk)
        try:
            descripcion = request.POST.get('descripcion', '').strip()
            importe_ars_str = request.POST.get('importe_ars', '0').replace(',', '.')
            importe_ars = Decimal(importe_ars_str)
            cuenta_contable_id = request.POST.get('cuenta_contable_id')
            cuadro_id = request.POST.get('cuadro_id')
            proveedor_id = request.POST.get('proveedor_id')

            if importe_ars <= Decimal('0'):
                raise ValueError("El importe debe ser mayor a cero.")

            costo.descripcion = descripcion or costo.descripcion
            costo.importe_ars = importe_ars
            
            # Recalcular USD
            tc = TipoCambioMensual.get_tc(ano=costo.fecha.year, mes=costo.fecha.month)
            costo.importe_usd = round(importe_ars / tc, 2) if tc > 0 else Decimal('0.00')

            if cuenta_contable_id:
                costo.cuenta_contable = get_object_or_404(CuentaContable, id=cuenta_contable_id)
            
            if cuadro_id == 'general':
                costo.cuadro = None
            elif cuadro_id:
                costo.cuadro = Cuadro.objects.filter(id=cuadro_id).first()

            if proveedor_id:
                costo.proveedor = CuentaCorriente.objects.filter(id=proveedor_id).first()
            elif proveedor_id == '':
                costo.proveedor = None

            costo.save()
            try:
                sincronizar_costos_con_cuadro_resultado()
            except Exception:
                pass
            messages.success(request, f"Imputación #{costo.id} actualizada correctamente.")
        except Exception as e:
            messages.error(request, f"Error al actualizar imputación #{costo.id}: {str(e)}")

        return redirect(reverse_lazy('costos:dashboard') + '?tab=imputaciones')


class CostoDeleteView(View):
    """Elimina una imputación de costo y sus dependencias de prorrateo si existen."""
    def post(self, request, pk):
        costo = get_object_or_404(CostoPorCentro, pk=pk)
        try:
            # Si este costo generó prorrateos hijos, eliminarlos también
            hijos_count = costo.costos_hijos_prorrateados.count()
            if hijos_count > 0:
                costo.costos_hijos_prorrateados.all().delete()

            desc = costo.descripcion
            costo.delete()
            try:
                sincronizar_costos_con_cuadro_resultado()
            except Exception:
                pass
            extra = f" (y sus {hijos_count} imputaciones prorrateadas)" if hijos_count > 0 else ""
            messages.success(request, f"Costo '{desc}' eliminado correctamente{extra}.")
        except Exception as e:
            messages.error(request, f"Error al eliminar costo: {str(e)}")

        return redirect(reverse_lazy('costos:dashboard') + '?tab=imputaciones')


class CostoProrratearView(View):
    """Ejecuta la distribución de un costo indirecto general entre todos los cuadros de la finca."""
    def post(self, request, pk):
        costo = get_object_or_404(CostoPorCentro, pk=pk)
        try:
            num_hijos = prorratear_costo_indirecto(
                costo, 
                usuario=request.user if request.user.is_authenticated else None
            )
            messages.success(
                request, 
                f"Prorrateo completado: El gasto de ${costo.importe_ars:,.2f} se distribuyó "
                f"exitosamente entre los {num_hijos} cuadros productivos de la finca {costo.finca.nombre}."
            )
        except Exception as e:
            messages.error(request, f"No se pudo prorratear el costo #{costo.id}: {str(e)}")

        return redirect(reverse_lazy('costos:dashboard') + '?tab=cuadros')


class SincronizarCostosPLView(View):
    """Sincroniza todas las imputaciones de costos con las líneas del Cuadro de Resultados (P&L)."""
    def post(self, request):
        try:
            res = sincronizar_costos_con_cuadro_resultado()
            cuadro = res['cuadro']
            messages.success(
                request, 
                f"Sincronización P&L completada: Se actualizaron {res['cuentas_actualizadas']} cuentas contables "
                f"en '{cuadro.titulo}'. Costo de Producción: ${res['nuevo_costo_produccion']:,.2f} | EBITDA: ${res['nuevo_ebitda']:,.2f}."
            )
        except Exception as e:
            messages.error(request, f"Error al sincronizar con Cuadro de Resultados: {str(e)}")

        return redirect(reverse_lazy('costos:dashboard') + '?tab=contabilidad')


class ExportarCostosCSVView(View):
    """Exporta el listado filtrado de costos por centro a un archivo CSV."""
    def get(self, request, *args, **kwargs):
        qs = CostoPorCentro.objects.select_related(
            'centro_de_costo', 'finca', 'cuadro', 'cuenta_contable', 'proveedor'
        ).order_by('-fecha', '-id')

        finca_id = request.GET.get('finca')
        cuadro_id = request.GET.get('cuadro')
        centro_id = request.GET.get('centro')
        tipo = request.GET.get('tipo')
        mes = request.GET.get('mes')
        cuenta_id = request.GET.get('cuenta_id')
        q = request.GET.get('q')

        if finca_id:
            qs = qs.filter(finca_id=finca_id)
        if cuadro_id:
            if cuadro_id == 'general':
                qs = qs.filter(cuadro__isnull=True)
            else:
                qs = qs.filter(cuadro_id=cuadro_id)
        if centro_id:
            qs = qs.filter(centro_de_costo_id=centro_id)
        if tipo:
            qs = qs.filter(tipo_origen=tipo)
        if cuenta_id:
            qs = qs.filter(cuenta_contable_id=cuenta_id)
        if mes:
            try:
                m_int = int(mes)
                qs = qs.filter(fecha__year=2026, fecha__month=m_int)
            except (ValueError, TypeError):
                pass
        if q:
            qs = qs.filter(
                Q(descripcion__icontains=q) |
                Q(documento_origen_tipo__icontains=q) |
                Q(centro_de_costo__nombre__icontains=q) |
                Q(proveedor__razon_social__icontains=q)
            )

        empresa = Empresa.objects.first()
        razon_social = empresa.razon_social if empresa else "Empresa S.A."
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Costos Agrícolas"

        # Estilos
        title_font = Font(name='Arial', size=14, bold=True, color='003D4A2A')
        header_font = Font(name='Arial', size=10, bold=True, color='FFFFFFFF')
        header_fill = PatternFill(start_color='005A6E3F', end_color='005A6E3F', fill_type='solid')
        center_align = Alignment(horizontal='center', vertical='center')
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

        # Encabezado Empresa
        ws.merge_cells('A1:S1')
        ws['A1'] = razon_social.upper()
        ws['A1'].font = title_font
        ws['A1'].alignment = Alignment(horizontal='center')
        
        ws.merge_cells('A2:S2')
        ws['A2'] = "REPORTE DETALLADO DE COSTOS AGRÍCOLAS Y OPERATIVOS"
        ws['A2'].font = Font(name='Arial', size=12, bold=True)
        ws['A2'].alignment = Alignment(horizontal='center')

        ws.merge_cells('A3:S3')
        ws['A3'] = f"Fecha de Emisión: {timezone.now().strftime('%d/%m/%Y %H:%M')} | ERP Olivícola"
        ws['A3'].font = Font(name='Arial', size=9, italic=True)
        ws['A3'].alignment = Alignment(horizontal='center')

        # Cabeceras
        headers = [
            'ID', 'Fecha', 'Centro de Costo', 'Tipo Centro', 'Finca', 'Cuadro Código',
            'Cuadro Variedad', 'Hectáreas', 'Concepto / Origen', 'Cod. Cta', 
            'Cuenta Contable', 'Proveedor', 'Descripción / Detalle',
            'Comprobante', 'Ref ID', 'Prorrateado', 'Importe ARS', 'Importe USD', 'Costo/ha (ARS)'
        ]
        
        ws.append([]) # Fila 4 vacía
        ws.append(headers) # Fila 5
        
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=5, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border

        for c in qs:
            ha = float(c.cuadro.hectareas_netas) if (c.cuadro and c.cuadro.hectareas_netas) else None
            c_ha = round(float(c.importe_ars) / ha, 2) if ha else None
            cta_cod = c.cuenta_contable.codigo if c.cuenta_contable else ''
            cta_nom = c.cuenta_contable.nombre if c.cuenta_contable else ''
            prov_nom = c.proveedor.razon_social if c.proveedor else ''

            row_data = [
                c.id,
                c.fecha.strftime('%d/%m/%Y'),
                c.centro_de_costo.nombre,
                c.centro_de_costo.get_tipo_display(),
                c.finca.nombre if c.finca else '',
                c.cuadro.codigo if c.cuadro else '',
                c.cuadro.variedad if c.cuadro else '',
                ha,
                c.get_tipo_origen_display(),
                cta_cod,
                cta_nom,
                prov_nom,
                c.descripcion,
                c.documento_origen_tipo,
                c.documento_origen_id or '',
                'Sí' if c.es_prorrateo else 'No',
                float(c.importe_ars),
                float(c.importe_usd) if c.importe_usd else None,
                c_ha
            ]
            ws.append(row_data)

        # Ajuste de ancho de columnas
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                if cell.row > 4: # Omit headers
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
            adjusted_width = (max_length + 2)
            if adjusted_width > 30: adjusted_width = 30
            ws.column_dimensions[column].width = adjusted_width

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        fecha_str = timezone.now().strftime('%Y%m%d_%H%M')
        response['Content-Disposition'] = f'attachment; filename="Costos_Agricolas_{fecha_str}.xlsx"'
        wb.save(response)
        return response
