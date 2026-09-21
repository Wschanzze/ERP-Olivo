import io
from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from django.views import View
from django.template.loader import render_to_string
from django.db.models import Count, Sum
from .models import PeriodoLiquidacion, LiquidacionEmpleado
from .tasks import calcular_liquidacion_periodo_task

class PeriodosListView(ListView):
    model = PeriodoLiquidacion
    template_name = 'liquidacion/periodos_list.html'
    context_object_name = 'periodos'

    def get_queryset(self):
        return PeriodoLiquidacion.objects.prefetch_related('liquidaciones__empleado').annotate(
            total_liquidaciones=Count('liquidaciones', distinct=True),
            total_bruto_ars=Sum('liquidaciones__total_bruto_remunerativo_ars'),
            total_retenciones_ars=Sum('liquidaciones__total_retenciones_ars'),
            total_neto_ars=Sum('liquidaciones__neto_a_cobrar_ars'),
        ).order_by('-ano', '-mes', '-tipo')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['todas_liquidaciones'] = LiquidacionEmpleado.objects.select_related(
            'empleado', 'periodo', 'empleado__finca_habitual'
        ).prefetch_related('items').order_by('-periodo__ano', '-periodo__mes', 'empleado__legajo')
        ctx['total_recibos_count'] = ctx['todas_liquidaciones'].count()
        ctx['total_neto_historico'] = ctx['todas_liquidaciones'].aggregate(t=Sum('neto_a_cobrar_ars'))['t'] or 0
        ctx['tab_activa'] = self.request.GET.get('tab', 'periodos')
        return ctx


class PeriodoDetailView(DetailView):
    model = PeriodoLiquidacion
    template_name = 'liquidacion/periodo_detail.html'
    context_object_name = 'periodo'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['liquidaciones'] = self.object.liquidaciones.select_related('empleado').prefetch_related('items').all()
        return ctx


class PeriodoCreateView(CreateView):
    model = PeriodoLiquidacion
    fields = ['mes', 'ano', 'tipo', 'fecha_inicio', 'fecha_fin', 'observaciones']
    template_name = 'liquidacion/partials/periodo_form_modal.html'
    success_url = reverse_lazy('liquidacion:periodos_list')


def lanzar_calculo_liquidacion_htmx(request, pk):
    """Dispara el cálculo asíncrono en Celery (o síncrono de respaldo en local)."""
    if request.method == 'POST':
        periodo = get_object_or_404(PeriodoLiquidacion, pk=pk)
        try:
            # Ejecutar tarea asíncrona de Celery
            calcular_liquidacion_periodo_task.delay(pk)
            messages.info(request, f"Cálculo de liquidación iniciado en segundo plano con Celery para el período {periodo}.")
        except Exception:
            # Si Redis/Celery worker no está corriendo localmente, ejecutar sincrónicamente como fallback
            calcular_liquidacion_periodo_task(pk)
            messages.success(request, f"Liquidación calculada con éxito a partir de las asistencias.")

        if request.headers.get('HX-Request'):
            return render(request, 'liquidacion/partials/periodo_status_badge.html', {'periodo': get_object_or_404(PeriodoLiquidacion, pk=pk)})
        return redirect('liquidacion:periodo_detail', pk=pk)
    return HttpResponse(status=405)


# ──────────────────────────────────────────────────────────────────────────────
# GENERADOR DE RECIBOS PDF PROFESIONAL (ReportLab + WeasyPrint Fallback)
# ──────────────────────────────────────────────────────────────────────────────

def _generar_recibo_reportlab(liq) -> bytes:
    """Genera un recibo de haberes A4 profesional usando ReportLab con el logo corporativo."""
    import os
    from django.conf import settings
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()

    c_oliva = colors.HexColor('#3D4A2A')
    c_oliva_light = colors.HexColor('#EAEFE3')
    c_gray = colors.HexColor('#4B5563')

    sub_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=c_gray
    )
    header_sub_right = ParagraphStyle(
        'HeaderSubRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        alignment=2,
        textColor=c_gray
    )

    # Logo Corporativo Oficial
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'icono.png')
    logo_img = None
    if os.path.exists(logo_path):
        try:
            logo_img = RLImage(logo_path, width=44, height=44)
        except Exception:
            logo_img = None

    empresa_p = Paragraph(
        "<b>Olivar del Valle Agroindustrial S.A.</b><br/>"
        "CUIT: 30-71458923-4 • Explotación Olivícola<br/>"
        "Ruta Nacional 60 Km 1140, Aimogasta, La Rioja",
        sub_style
    )
    recibo_p = Paragraph(
        f"<b>RECIBO DE HABERES</b><br/>"
        f"Período: {liq.periodo}<br/>"
        f"N° Recibo: #{liq.pk:06d}<br/>"
        f"Estado: {liq.get_estado_display()}",
        header_sub_right
    )

    if logo_img:
        header_table = Table([[logo_img, empresa_p, recibo_p]], colWidths=[52, 268, 200])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (0,-1), 0),
            ('LEFTPADDING', (1,0), (1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
    else:
        header_table = Table([[empresa_p, recibo_p]], colWidths=[300, 220])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=2, color=c_oliva, spaceBefore=4, spaceAfter=10))

    # Datos del empleado
    emp = liq.empleado
    finca_nom = emp.finca_habitual.nombre if emp.finca_habitual else "Central"
    datos_emp = [
        [
            Paragraph(f"<b>Empleado:</b> {emp.nombre_completo}", sub_style),
            Paragraph(f"<b>Legajo:</b> {emp.legajo}", sub_style),
            Paragraph(f"<b>CUIL:</b> {emp.dni_cuil}", sub_style)
        ],
        [
            Paragraph(f"<b>Puesto:</b> {emp.get_rol_laboral_display()}", sub_style),
            Paragraph(f"<b>Modalidad:</b> {emp.get_modalidad_display()}", sub_style),
            Paragraph(f"<b>Finca:</b> {finca_nom}", sub_style)
        ],
        [
            Paragraph(f"<b>Fecha Ingreso:</b> {emp.fecha_ingreso or '—'}", sub_style),
            Paragraph(f"<b>Jornales Computados:</b> {liq.dias_jornales_computados}", sub_style),
            Paragraph(f"<b>Horas Extras:</b> {liq.horas_extras}h", sub_style)
        ],
    ]
    t_emp = Table(datos_emp, colWidths=[200, 160, 160])
    t_emp.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_oliva_light),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#D5DFC9')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_emp)
    story.append(Spacer(1, 10))

    # Detalle de conceptos
    table_data = [
        ["CÓD.", "CONCEPTO", "TIPO", "CANT / %", "IMPORTE (ARS)"]
    ]
    for item in liq.items.all():
        tipo_lbl = "Remun." if item.tipo == 'REMUNERATIVO' else ("No Rem." if item.tipo == 'NO_REMUNERATIVO' else "Retención")
        importe_str = f"-${item.importe_ars:,.2f}" if item.tipo == 'RETENCION' else f"${item.importe_ars:,.2f}"
        table_data.append([
            item.codigo_concepto,
            item.descripcion,
            tipo_lbl,
            str(item.cantidad_o_porcentaje),
            importe_str
        ])

    if len(table_data) == 1:
        table_data.append(["HAB-01", "Haberes según jornales trabajados del período", "Remun.", str(liq.dias_jornales_computados), f"${liq.total_bruto_remunerativo_ars:,.2f}"])

    t_conceptos = Table(table_data, colWidths=[55, 235, 75, 65, 90])
    t_conceptos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_oliva),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 5),
        ('TOPPADDING', (0,0), (-1,0), 5),
        ('ALIGN', (3,0), (-1,-1), 'RIGHT'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('TOPPADDING', (0,1), (-1,-1), 4),
        ('BOTTOMPADDING', (0,1), (-1,-1), 4),
        ('LINEBELOW', (0,1), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
    ]))
    story.append(t_conceptos)
    story.append(Spacer(1, 10))

    # Totales
    totales_data = [
        ["Total Remunerativo Bruto:", f"${liq.total_bruto_remunerativo_ars:,.2f}"],
        ["Total No Remunerativo:", f"${liq.total_no_remunerativo_ars:,.2f}"],
        ["Total Retenciones / Descuentos:", f"-${liq.total_retenciones_ars:,.2f}"],
        ["SUELDO NETO A COBRAR:", f"${liq.neto_a_cobrar_ars:,.2f}"],
    ]
    t_totales = Table(totales_data, colWidths=[380, 140])
    t_totales.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,-1), 'RIGHT'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,-2), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-2), 8),
        ('BACKGROUND', (0,-1), (-1,-1), c_oliva),
        ('TEXTCOLOR', (0,-1), (-1,-1), colors.white),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,-1), (-1,-1), 10),
        ('TOPPADDING', (0,-1), (-1,-1), 6),
        ('BOTTOMPADDING', (0,-1), (-1,-1), 6),
        ('LINEBELOW', (0,0), (-1,-2), 0.5, colors.HexColor('#E5E7EB')),
    ]))
    story.append(t_totales)
    story.append(Spacer(1, 30))

    # Firmas
    firmas_data = [
        [
            Paragraph("___________________________________<br/><b>Firma del Empleado</b><br/>Recibí conforme el importe neto<br/>CUIL: " + str(emp.dni_cuil), sub_style),
            Paragraph("___________________________________<br/><b>Por Olivar del Valle S.A.</b><br/>Firma y Sello Empleador", sub_style)
        ]
    ]
    t_firmas = Table(firmas_data, colWidths=[260, 260])
    t_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(t_firmas)

    story.append(Spacer(1, 15))
    story.append(Paragraph("<font size=7 color='#9CA3AF'>Comprobante emitido conforme Ley de Régimen de Trabajo Agrario (UATRE/RENATRE). Generado por ERP Olivícola.</font>", sub_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


class ReciboPDFView(View):
    """Genera el recibo de haberes oficial en PDF con ReportLab (o HTML si se especifica ?format=html)."""
    def get(self, request, pk):
        liq = get_object_or_404(
            LiquidacionEmpleado.objects.select_related('empleado', 'periodo', 'empleado__finca_habitual').prefetch_related('items'),
            pk=pk
        )

        if request.GET.get('format') == 'html':
            return render(request, 'liquidacion/recibo_pdf.html', {'liq': liq})

        # Generador nativo de alta fidelidad con ReportLab
        pdf = _generar_recibo_reportlab(liq)

        filename = f"recibo_{liq.empleado.legajo}_{liq.periodo.mes:02d}_{liq.periodo.ano}.pdf"
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
