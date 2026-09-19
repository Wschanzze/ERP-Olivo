"""
Management command para cargar datos de ejemplo en el módulo de finanzas.
Uso: python manage.py seed_finanzas
"""
import datetime
import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.core.models import Empresa
from apps.finanzas.models import Cuenta, CuentaCorriente, MovimientoFinanciero
from apps.finanzas.services import registrar_movimiento_financiero

User = get_user_model()


class Command(BaseCommand):
    help = 'Carga datos de ejemplo para el módulo de Finanzas'

    def add_arguments(self, parser):
        parser.add_argument('--limpiar', action='store_true', help='Elimina movimientos existentes antes de cargar')

    def handle(self, *args, **options):
        empresa = Empresa.objects.first()
        if not empresa:
            self.stderr.write('❌ No existe ninguna Empresa. Creá una desde el admin primero.')
            return

        usuario = User.objects.filter(is_superuser=True).first()

        if options['limpiar']:
            MovimientoFinanciero.objects.all().delete()
            self.stdout.write('🗑  Movimientos eliminados.')

        # -----------------------------------------------------------------
        # 1. Cuentas financieras
        # -----------------------------------------------------------------
        cuentas_data = [
            dict(nombre='Banco Galicia CC Operativa ARS', tipo='BANCO', moneda='ARS',
                 banco_nombre='Banco Galicia', numero_cuenta='009-000012345/6',
                 cbu_cvu='0070088520000001234567', saldo_actual=Decimal('18940000.00')),
            dict(nombre='Banco Santander CC Exportacion USD', tipo='BANCO', moneda='USD',
                 banco_nombre='Banco Santander', numero_cuenta='072-000098765/4',
                 cbu_cvu='0720099830000009876543', saldo_actual=Decimal('85400.00')),
            dict(nombre='Caja Chica Finca Aimogasta', tipo='CAJA_EFECTIVO', moneda='ARS',
                 banco_nombre='', numero_cuenta='',
                 cbu_cvu='', saldo_actual=Decimal('1450000.00')),
            dict(nombre='Mercado Pago Operaciones', tipo='VIRTUAL', moneda='ARS',
                 banco_nombre='Mercado Pago', numero_cuenta='',
                 cbu_cvu='olivafinca.mp', saldo_actual=Decimal('320000.00')),
        ]

        cuentas = {}
        for cd in cuentas_data:
            c, created = Cuenta.objects.get_or_create(
                nombre=cd['nombre'],
                empresa=empresa,
                defaults=cd
            )
            cuentas[cd['nombre']] = c
            estado = '✅ Creada' if created else '⏩ Ya existe'
            self.stdout.write(f'  {estado}: {c.nombre}')

        # -----------------------------------------------------------------
        # 2. Cuentas corrientes de proveedores y clientes
        # -----------------------------------------------------------------
        cc_data = [
            dict(tipo_entidad='PROVEEDOR', razon_social='Agroquímica Cuyo & Cía S.A.',
                 nombre_comercial='AgroQuím Cuyo', cuit='30-71234567-0',
                 saldo_actual=Decimal('-4250000.00')),
            dict(tipo_entidad='PROVEEDOR', razon_social='Transportes El Olivar SRL',
                 nombre_comercial='El Olivar', cuit='30-68901234-5',
                 saldo_actual=Decimal('-1800000.00')),
            dict(tipo_entidad='CLIENTE', razon_social='Mediterráneo Trading Imports LLC / Suc. Arg.',
                 nombre_comercial='Mediterráneo Trading', cuit='30-99876543-2',
                 saldo_actual=Decimal('12800000.00')),
            dict(tipo_entidad='CLIENTE', razon_social='Aceites del Sol S.A.',
                 nombre_comercial='Aceites del Sol', cuit='30-55443322-1',
                 saldo_actual=Decimal('3500000.00')),
        ]

        ccs = {}
        for ccd in cc_data:
            cc, created = CuentaCorriente.objects.get_or_create(
                cuit=ccd['cuit'], defaults=ccd
            )
            ccs[ccd['razon_social']] = cc
            estado = '✅ Creada' if created else '⏩ Ya existe'
            self.stdout.write(f'  {estado}: {cc.razon_social}')

        # -----------------------------------------------------------------
        # 3. Movimientos de ejemplo — últimos 6 meses
        # -----------------------------------------------------------------
        hoy = datetime.date.today()

        movimientos_ejemplo = [
            # Ingresos
            dict(cuenta=cuentas['Banco Galicia CC Operativa ARS'],
                 tipo='INGRESO', fecha=hoy - datetime.timedelta(days=170),
                 importe=Decimal('8500000'), concepto='Cobro exportación aceite - Factura E0001-0000051',
                 comprobante_tipo='Factura E', comprobante_nro='0001-0000051',
                 cuenta_corriente=ccs['Mediterráneo Trading Imports LLC / Suc. Arg.']),
            dict(cuenta=cuentas['Banco Galicia CC Operativa ARS'],
                 tipo='INGRESO', fecha=hoy - datetime.timedelta(days=140),
                 importe=Decimal('4300000'), concepto='Cobro parcial aceitunas en conserva - Aceites del Sol',
                 comprobante_tipo='Recibo', comprobante_nro='R-0045',
                 cuenta_corriente=ccs['Aceites del Sol S.A.']),
            dict(cuenta=cuentas['Banco Galicia CC Operativa ARS'],
                 tipo='INGRESO', fecha=hoy - datetime.timedelta(days=90),
                 importe=Decimal('6200000'), concepto='Cobro 2da cuota exportación aceite - Mediterráneo',
                 comprobante_tipo='Factura E', comprobante_nro='0001-0000062',
                 cuenta_corriente=ccs['Mediterráneo Trading Imports LLC / Suc. Arg.']),
            dict(cuenta=cuentas['Banco Galicia CC Operativa ARS'],
                 tipo='INGRESO', fecha=hoy - datetime.timedelta(days=45),
                 importe=Decimal('3100000'), concepto='Cobro anticipo cosecha 2026 - Aceites del Sol',
                 comprobante_tipo='Recibo', comprobante_nro='R-0058',
                 cuenta_corriente=ccs['Aceites del Sol S.A.']),
            dict(cuenta=cuentas['Banco Santander CC Exportacion USD'],
                 tipo='INGRESO', fecha=hoy - datetime.timedelta(days=60),
                 importe=Decimal('25000'), concepto='Liquidación divisas exportación aceite oliva virgen extra',
                 comprobante_tipo='SWIFT', comprobante_nro='BCOSW-2026-0041'),
            dict(cuenta=cuentas['Banco Santander CC Exportacion USD'],
                 tipo='INGRESO', fecha=hoy - datetime.timedelta(days=15),
                 importe=Decimal('18500'), concepto='Cobro 2do anticipo exportación granel USD',
                 comprobante_tipo='SWIFT', comprobante_nro='BCOSW-2026-0062'),
            dict(cuenta=cuentas['Caja Chica Finca Aimogasta'],
                 tipo='INGRESO', fecha=hoy - datetime.timedelta(days=120),
                 importe=Decimal('500000'), concepto='Apertura caja chica temporada cosecha',
                 comprobante_tipo='Recibo interno', comprobante_nro='CI-0001'),
            # Egresos
            dict(cuenta=cuentas['Banco Galicia CC Operativa ARS'],
                 tipo='EGRESO', fecha=hoy - datetime.timedelta(days=155),
                 importe=Decimal('2100000'), concepto='Pago agroquímicos campaña 2026 - AgroQuím Cuyo',
                 comprobante_tipo='Factura A', comprobante_nro='0001-0000234',
                 cuenta_corriente=ccs['Agroquímica Cuyo & Cía S.A.']),
            dict(cuenta=cuentas['Banco Galicia CC Operativa ARS'],
                 tipo='EGRESO', fecha=hoy - datetime.timedelta(days=110),
                 importe=Decimal('950000'), concepto='Pago flete transporte aceitunas - El Olivar SRL',
                 comprobante_tipo='Factura A', comprobante_nro='0002-0001123',
                 cuenta_corriente=ccs['Transportes El Olivar SRL']),
            dict(cuenta=cuentas['Banco Galicia CC Operativa ARS'],
                 tipo='EGRESO', fecha=hoy - datetime.timedelta(days=80),
                 importe=Decimal('1850000'), concepto='Pago cuota seguro integral finca y maquinaria',
                 comprobante_tipo='Recibo', comprobante_nro='SEG-2026-07'),
            dict(cuenta=cuentas['Banco Galicia CC Operativa ARS'],
                 tipo='EGRESO', fecha=hoy - datetime.timedelta(days=50),
                 importe=Decimal('780000'), concepto='Honorarios agrónomo asesor campaña olivos',
                 comprobante_tipo='Factura B', comprobante_nro='0001-0000012'),
            dict(cuenta=cuentas['Caja Chica Finca Aimogasta'],
                 tipo='EGRESO', fecha=hoy - datetime.timedelta(days=95),
                 importe=Decimal('85000'), concepto='Combustible vehículos de campo - semana 15',
                 comprobante_tipo='Ticket', comprobante_nro='YPF-09-2026'),
            dict(cuenta=cuentas['Caja Chica Finca Aimogasta'],
                 tipo='EGRESO', fecha=hoy - datetime.timedelta(days=70),
                 importe=Decimal('42000'), concepto='Materiales de mantenimiento menor - vivero',
                 comprobante_tipo='Ticket', comprobante_nro='FCO-2026-1821'),
            dict(cuenta=cuentas['Banco Galicia CC Operativa ARS'],
                 tipo='EGRESO', fecha=hoy - datetime.timedelta(days=20),
                 importe=Decimal('2150000'), concepto='Pago saldo agroquímicos 2da entrega - AgroQuím',
                 comprobante_tipo='Factura A', comprobante_nro='0001-0000298',
                 cuenta_corriente=ccs['Agroquímica Cuyo & Cía S.A.']),
            # Transferencias
            dict(cuenta=cuentas['Banco Galicia CC Operativa ARS'],
                 tipo='TRANSFERENCIA', fecha=hoy - datetime.timedelta(days=130),
                 importe=Decimal('800000'), concepto='Reposición caja chica finca - mensual',
                 cuenta_destino=cuentas['Caja Chica Finca Aimogasta']),
            dict(cuenta=cuentas['Banco Galicia CC Operativa ARS'],
                 tipo='TRANSFERENCIA', fecha=hoy - datetime.timedelta(days=30),
                 importe=Decimal('350000'), concepto='Fondos a Mercado Pago para pagos de servicios online',
                 cuenta_destino=cuentas['Mercado Pago Operaciones']),
        ]

        creados = 0
        for mv in movimientos_ejemplo:
            cuenta_destino = mv.pop('cuenta_destino', None)
            cc = mv.pop('cuenta_corriente', None)
            try:
                registrar_movimiento_financiero(
                    **mv,
                    cuenta_destino=cuenta_destino,
                    cuenta_corriente=cc,
                    usuario=usuario
                )
                creados += 1
            except Exception as e:
                self.stderr.write(f'  ⚠ Error en movimiento: {e}')

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Datos de ejemplo cargados: {creados} movimientos financieros creados.'
        ))
