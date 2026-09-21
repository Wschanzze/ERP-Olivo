import csv
from decimal import Decimal
from django.views.generic import ListView, View
from django.db.models import Sum, Q
from django.http import HttpResponse
from django.utils import timezone

from .models import CostoPorCentro
from apps.core.models import CentroDeCosto, Finca
from apps.campos.models import Cuadro, LoteDeCosecha

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
        'cuenta_codigo': '4.2.1.00.000000',
        'cuenta_nombre': 'Costo de la producción agrícola',
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
            'centro_de_costo', 'finca', 'cuadro'
        ).order_by('-fecha', '-id')

        finca_id = self.request.GET.get('finca')
        cuadro_id = self.request.GET.get('cuadro')
        centro_id = self.request.GET.get('centro')
        tipo = self.request.GET.get('tipo')
        mes = self.request.GET.get('mes')
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
                Q(finca__nombre__icontains=q)
            )

        return qs

    def get_queryset(self):
        return self.get_base_queryset()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base_qs = self.get_base_queryset()

        # ── 1. Totales Generales ──────────────────────────────────────────────
        total_ars = base_qs.aggregate(t=Sum('importe_ars'))['t'] or Decimal('0.00')
        total_usd = base_qs.aggregate(t=Sum('importe_usd'))['t'] or Decimal('0.00')
        ctx['total_costos_ars'] = total_ars
        ctx['total_costos_usd'] = total_usd
        ctx['total_registros'] = base_qs.count()

        # ── 2. Distribución por Destino / Centro de Costo ──────────────────────
        costo_agricola = base_qs.filter(centro_de_costo__tipo='PRODUCTIVO_CAMPO').aggregate(t=Sum('importe_ars'))['t'] or Decimal('0.00')
        costo_almazara = base_qs.filter(centro_de_costo__tipo='FABRICA_ALMAZARA').aggregate(t=Sum('importe_ars'))['t'] or Decimal('0.00')
        costo_admin = base_qs.filter(centro_de_costo__tipo='ESTRUCTURA_ADMIN').aggregate(t=Sum('importe_ars'))['t'] or Decimal('0.00')

        ctx['costo_agricola_ars'] = costo_agricola
        ctx['costo_almazara_ars'] = costo_almazara
        ctx['costo_admin_ars'] = costo_admin

        ctx['pct_agricola'] = round((costo_agricola / total_ars * 100) if total_ars > 0 else Decimal('0.0'), 1)
        ctx['pct_almazara'] = round((costo_almazara / total_ars * 100) if total_ars > 0 else Decimal('0.0'), 1)
        ctx['pct_admin'] = round((costo_admin / total_ars * 100) if total_ars > 0 else Decimal('0.0'), 1)

        # ── 3. Resumen por Categoría de Origen (con labels e iconos) ──────────
        resumen_cat_raw = base_qs.values('tipo_origen').annotate(
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
        cuadros_qs = Cuadro.objects.select_related('finca').all()
        if finca_filter:
            cuadros_qs = cuadros_qs.filter(finca_id=finca_filter)

        resumen_cuadros = []
        total_ha_cuadros = Decimal('0.00')
        total_directo_cuadros = Decimal('0.00')

        # Determinar el costo directo máximo por ha para las barras de progreso
        max_costo_ha = Decimal('1.00')

        for cua in cuadros_qs:
            ha = cua.hectareas_netas or Decimal('0.00')
            total_ha_cuadros += ha

            costos_cua = base_qs.filter(cuadro=cua)
            c_ars = costos_cua.aggregate(t=Sum('importe_ars'))['t'] or Decimal('0.00')
            c_usd = costos_cua.aggregate(t=Sum('importe_usd'))['t'] or Decimal('0.00')
            total_directo_cuadros += c_ars

            costo_ha = round(c_ars / ha, 2) if ha > 0 else Decimal('0.00')
            if costo_ha > max_costo_ha:
                max_costo_ha = costo_ha

            # Kilos cosechados en el período
            kg_cosecha = LoteDeCosecha.objects.filter(cuadro=cua).aggregate(t=Sum('kg_cosechados'))['t'] or Decimal('0.00')
            costo_kg = round(c_ars / kg_cosecha, 2) if kg_cosecha > 0 else None

            # Desglose de labores del cuadro
            desglose_labores = costos_cua.values('tipo_origen').annotate(sub=Sum('importe_ars')).order_by('-sub')

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

        # Costos generales de campo no imputados a cuadro específico
        costos_generales_campo = base_qs.filter(
            cuadro__isnull=True,
            centro_de_costo__tipo='PRODUCTIVO_CAMPO'
        ).aggregate(t=Sum('importe_ars'))['t'] or Decimal('0.00')
        costo_general_ha = round(costos_generales_campo / total_ha_cuadros, 2) if total_ha_cuadros > 0 else Decimal('0.00')

        # Normalizar barras de progreso relativas
        for it in resumen_cuadros:
            it['bar_pct'] = min(100, int((it['costo_por_ha'] / max_costo_ha) * 100)) if max_costo_ha > 0 else 0

        # Costo promedio ponderado por hectárea
        costo_promedio_ha = round(costo_agricola / total_ha_cuadros, 2) if total_ha_cuadros > 0 else Decimal('0.00')
        ctx['costo_promedio_ha'] = costo_promedio_ha
        ctx['total_ha_analizadas'] = total_ha_cuadros
        ctx['resumen_por_cuadro'] = resumen_cuadros
        ctx['costos_generales_campo'] = costos_generales_campo
        ctx['costo_general_ha'] = costo_general_ha

        # ── 5. Filtros disponibles ───────────────────────────────────────────
        ctx['fincas'] = Finca.objects.filter(activa=True)
        ctx['cuadros'] = Cuadro.objects.select_related('finca').all()
        ctx['centros_costo'] = CentroDeCosto.objects.filter(activo=True)
        ctx['tipos_origen'] = CostoPorCentro.TipoOrigen.choices
        ctx['filtro_finca'] = self.request.GET.get('finca', '')
        ctx['filtro_cuadro'] = self.request.GET.get('cuadro', '')
        ctx['filtro_centro'] = self.request.GET.get('centro', '')
        ctx['filtro_tipo'] = self.request.GET.get('tipo', '')
        ctx['filtro_mes'] = self.request.GET.get('mes', '')
        ctx['filtro_q'] = self.request.GET.get('q', '')
        ctx['tab_activa'] = self.request.GET.get('tab', 'imputaciones')

        # ── 6. Enriquecer los items de la página actual ───────────────────────
        page_items = ctx['costos']
        for item in page_items:
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


class ExportarCostosCSVView(View):
    """Exporta el listado filtrado de costos por centro a un archivo CSV."""

    def get(self, request, *args, **kwargs):
        qs = CostoPorCentro.objects.select_related('centro_de_costo', 'finca', 'cuadro').order_by('-fecha', '-id')

        finca_id = request.GET.get('finca')
        cuadro_id = request.GET.get('cuadro')
        centro_id = request.GET.get('centro')
        tipo = request.GET.get('tipo')
        mes = request.GET.get('mes')
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
                Q(centro_de_costo__nombre__icontains=q)
            )

        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        fecha_str = timezone.now().strftime('%Y%m%d_%H%M')
        response['Content-Disposition'] = f'attachment; filename="control_costos_agricolas_{fecha_str}.csv"'

        writer = csv.writer(response, delimiter=';')
        writer.writerow([
            'Fecha', 'Centro de Costo', 'Tipo Centro', 'Finca', 'Cuadro Código',
            'Cuadro Variedad', 'Hectáreas', 'Tipo Origen / Concepto', 'Descripción / Detalle',
            'Comprobante Origen', 'ID Origen', 'Importe ARS', 'Importe USD', 'Costo por Hectárea (ARS/ha)'
        ])

        for c in qs:
            ha = c.cuadro.hectareas_netas if (c.cuadro and c.cuadro.hectareas_netas) else ''
            c_ha = round(c.importe_ars / c.cuadro.hectareas_netas, 2) if (c.cuadro and c.cuadro.hectareas_netas) else ''
            writer.writerow([
                c.fecha.strftime('%d/%m/%Y'),
                c.centro_de_costo.nombre,
                c.centro_de_costo.get_tipo_display(),
                c.finca.nombre,
                c.cuadro.codigo if c.cuadro else 'GENERAL',
                c.cuadro.get_variedad_olivo_display() if c.cuadro else '',
                ha,
                c.get_tipo_origen_display(),
                c.descripcion,
                c.documento_origen_tipo or '',
                c.documento_origen_id or '',
                f"{c.importe_ars:.2f}",
                f"{c.importe_usd:.2f}",
                f"{c_ha}" if c_ha != '' else '',
            ])

        return response
