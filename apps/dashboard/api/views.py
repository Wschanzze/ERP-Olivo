from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from apps.campos.models import Cuadro, LoteDeCosecha
from apps.personal.models import Empleado, RegistroAsistencia
from apps.inventario.models import Insumo, Maquina
from apps.finanzas.models import Cuenta, CuentaCorriente, MovimientoFinanciero
from apps.costos.models import CostoPorCentro

class DashboardKPIView(APIView):
    """Endpoint REST que agrega KPIs consolidados de todos los módulos del ERP."""
    permission_classes = [AllowAny]  # Permitir visualización en demo / dashboard island

    def get(self, request):
        finca_id = request.query_params.get('finca_id')

        # Filtros base según finca si viene especificada
        cuadros_qs = Cuadro.objects.filter(activo=True)
        cosechas_qs = LoteDeCosecha.objects.all()
        empleados_qs = Empleado.objects.filter(activo=True)
        asistencias_qs = RegistroAsistencia.objects.filter(fecha=timezone.now().date())
        costos_qs = CostoPorCentro.objects.all()
        
        if finca_id:
            cuadros_qs = cuadros_qs.filter(finca_id=finca_id)
            cosechas_qs = cosechas_qs.filter(cuadro__finca_id=finca_id)
            empleados_qs = empleados_qs.filter(finca_habitual_id=finca_id)
            asistencias_qs = asistencias_qs.filter(finca_id=finca_id)
            costos_qs = costos_qs.filter(finca_id=finca_id)

        # 1. KPIs Agronómicos
        total_hectareas = float(cuadros_qs.aggregate(total=Sum('hectareas_netas'))['total'] or 0.0)
        total_cuadros = cuadros_qs.count()
        total_cosecha_kg = float(cosechas_qs.aggregate(total=Sum('kg_cosechados'))['total'] or 0.0)

        # Variedades de olivo
        variedades = list(cuadros_qs.values('variedad_olivo').annotate(
            superficie=Sum('hectareas_netas'),
            cantidad_cuadros=Count('id')
        ).order_by('-superficie'))

        # 2. KPIs Financieros
        total_caja_bancos_ars = float(Cuenta.objects.filter(moneda='ARS', activa=True).aggregate(s=Sum('saldo_actual'))['s'] or 0.0)
        total_caja_bancos_usd = float(Cuenta.objects.filter(moneda='USD', activa=True).aggregate(s=Sum('saldo_actual'))['s'] or 0.0)

        # Cuentas corrientes:
        # Clientes con saldo positivo = nos deben dinero
        nos_deben_clientes_ars = float(CuentaCorriente.objects.filter(tipo_entidad='CLIENTE', saldo_actual__gt=0).aggregate(s=Sum('saldo_actual'))['s'] or 0.0)
        # Proveedores con saldo negativo = debemos dinero (convertir a positivo para display)
        debemos_proveedores_ars = abs(float(CuentaCorriente.objects.filter(tipo_entidad='PROVEEDOR', saldo_actual__lt=0).aggregate(s=Sum('saldo_actual'))['s'] or 0.0))

        # 3. KPIs de Inventario y Operaciones
        insumos = Insumo.objects.filter(activo=True)
        valor_stock_estimado_ars = float(sum(ins.stock_actual * ins.costo_unitario_ars for ins in insumos))
        insumos_bajo_stock = insumos.filter(stock_actual__lte=F('stock_minimo')).count()
        maquinaria_operativa = Maquina.objects.filter(estado='OPERATIVA').count()
        maquinaria_taller = Maquina.objects.filter(estado='EN_MANTENIMIENTO').count()

        # 4. KPIs de Personal
        personal_activo_total = empleados_qs.count()
        presentes_hoy = asistencias_qs.filter(estado='PRESENTE').count()

        # 5. Costos por categoría de origen
        costos_por_categoria = list(costos_qs.values('tipo_origen').annotate(
            total_ars=Sum('importe_ars')
        ).order_by('-total_ars'))

        # 6. Evolución de Cosecha mensual / últimos registros
        ultimas_cosechas = list(cosechas_qs.select_related('cuadro').values(
            'campana', 'cuadro__codigo', 'cuadro__variedad_olivo', 'kg_cosechados', 'destino', 'rendimiento_graso_porcentaje'
        )[:8])

        data = {
            'resumen': {
                'total_caja_bancos_ars': total_caja_bancos_ars,
                'total_caja_bancos_usd': total_caja_bancos_usd,
                'nos_deben_clientes_ars': nos_deben_clientes_ars,
                'debemos_proveedores_ars': debemos_proveedores_ars,
                'resultado_neto_estimado': total_caja_bancos_ars + nos_deben_clientes_ars - debemos_proveedores_ars,
                'total_hectareas': total_hectareas,
                'total_cuadros': total_cuadros,
                'total_cosecha_kg': total_cosecha_kg,
                'valor_stock_ars': valor_stock_estimado_ars,
                'insumos_alerta_stock': insumos_bajo_stock,
                'personal_activo': personal_activo_total,
                'presentes_hoy': presentes_hoy,
                'maquinaria_operativa': maquinaria_operativa,
                'maquinaria_taller': maquinaria_taller,
            },
            'variedades': variedades,
            'costos_por_categoria': costos_por_categoria,
            'ultimas_cosechas': ultimas_cosechas,
        }
        return Response(data)
