from datetime import timedelta
from django.utils import timezone
from decimal import Decimal
from apps.finanzas.models import ComprobanteFiscal, Cheque, CuentaCorriente, Cuenta
from apps.inventario.models import OrdenDeCompra, Finca

def poblar_datos_dinamicos_proyeccion():
    """Genera datos de prueba para la Proyección de Pagos relativos a la fecha actual."""
    today = timezone.now().date()
    
    # 1. Obtener o crear proveedor genérico
    proveedor, _ = CuentaCorriente.objects.get_or_create(
        cuit="30-11111111-5",
        defaults={
            'razon_social': "Proveedor Demo Proyección S.A.",
            'tipo_entidad': 'PROVEEDOR',
        }
    )
    # 2. Finca para Orden de Compra
    finca = Finca.objects.first()
    
    # 3. Cuenta bancaria para cheques propios
    cuenta_banco = Cuenta.objects.filter(tipo_cuenta='BANCO_CC').first()

    # --- DATOS PARA LA SEMANA ACTUAL ---
    # Factura pendiente esta semana
    ComprobanteFiscal.objects.get_or_create(
        numero_comprobante="A-0001-0001",
        defaults={
            'tipo_operacion': 'COMPRA',
            'tipo_comprobante': 'F_A',
            'estado_pago': 'PENDIENTE',
            'fecha_emision': today - timedelta(days=15),
            'fecha_vencimiento': today + timedelta(days=1),
            'cuenta_corriente': proveedor,
            'razon_social': proveedor.razon_social,
            'cuit': proveedor.cuit,
            'concepto': "Insumos Agrícolas Semana Actual",
            'total': Decimal('250000.00'),
            'saldo_pendiente': Decimal('250000.00'),
        }
    )
    # Cheque emitido para cobrar esta semana
    Cheque.objects.get_or_create(
        numero="CHK-ACTUAL-01",
        defaults={
            'tipo': 'EMITIDO',
            'estado': 'ENTREGADO_PROVEEDOR',
            'banco_emisor': "Banco Demo",
            'emisor_firmante': "Empresa Demo",
            'fecha_emision': today - timedelta(days=20),
            'fecha_cobro': today + timedelta(days=2),
            'importe': Decimal('150000.00'),
            'cuenta_corriente': proveedor,
            'cuenta_bancaria_origen': cuenta_banco,
        }
    )
    
    # --- DATOS PARA LA PRÓXIMA SEMANA ---
    next_week = today + timedelta(days=8)
    ComprobanteFiscal.objects.get_or_create(
        numero_comprobante="A-0001-0002",
        defaults={
            'tipo_operacion': 'COMPRA',
            'tipo_comprobante': 'F_A',
            'estado_pago': 'PENDIENTE',
            'fecha_emision': today - timedelta(days=5),
            'fecha_vencimiento': next_week,
            'cuenta_corriente': proveedor,
            'razon_social': proveedor.razon_social,
            'cuit': proveedor.cuit,
            'concepto': "Servicios Mantenimiento Próxima Semana",
            'total': Decimal('420000.00'),
            'saldo_pendiente': Decimal('420000.00'),
        }
    )
    if finca:
        OrdenDeCompra.objects.get_or_create(
            numero="OC-PROX-01",
            defaults={
                'proveedor': proveedor,
                'finca_destino': finca,
                'fecha_emision': today,
                'fecha_entrega_estimada': next_week + timedelta(days=1),
                'estado': 'APROBADA',
                'total_estimado_ars': Decimal('850000.00'),
            }
        )

    # --- DATOS PARA SEMANAS FUTURAS ---
    future_week = today + timedelta(days=20)
    Cheque.objects.get_or_create(
        numero="CHK-FUTURO-01",
        defaults={
            'tipo': 'EMITIDO',
            'estado': 'ENTREGADO_PROVEEDOR',
            'banco_emisor': "Banco Demo",
            'emisor_firmante': "Empresa Demo",
            'fecha_emision': today,
            'fecha_cobro': future_week,
            'importe': Decimal('600000.00'),
            'cuenta_corriente': proveedor,
            'cuenta_bancaria_origen': cuenta_banco,
        }
    )
