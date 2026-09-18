from django.test import TestCase
from decimal import Decimal
from django.utils import timezone
from apps.core.models import Empresa
from apps.finanzas.models import Cuenta, CuentaCorriente, MovimientoFinanciero
from apps.finanzas.services import registrar_movimiento_financiero

class FinanzasServiceTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            razon_social="Olivo Test S.A.",
            cuit="30-55667788-9"
        )
        self.cuenta_banco = Cuenta.objects.create(
            empresa=self.empresa,
            nombre="Banco Galicia Test",
            tipo=Cuenta.TipoCuenta.CUENTA_BANCARIA,
            moneda="ARS",
            saldo_actual=Decimal("100000.00")
        )
        self.proveedor = CuentaCorriente.objects.create(
            razon_social="Proveedor Fertilizantes S.A.",
            cuit="30-99887766-1",
            tipo_entidad=CuentaCorriente.TipoEntidad.PROVEEDOR,
            saldo_actual=Decimal("-50000.00")  # Debemos 50.000
        )
        self.cliente = CuentaCorriente.objects.create(
            razon_social="Cliente Aceite S.A.",
            cuit="30-11992288-4",
            tipo_entidad=CuentaCorriente.TipoEntidad.CLIENTE,
            saldo_actual=Decimal("75000.00")  # Nos debe 75.000
        )

    def test_pago_proveedor_disminuye_saldo_cuenta_y_amortiza_deuda(self):
        # Pago de $20.000 al proveedor
        mov = registrar_movimiento_financiero(
            cuenta=self.cuenta_banco,
            tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
            fecha=timezone.now().date(),
            importe=Decimal("20000.00"),
            concepto="Pago factura N° 1004",
            cuenta_corriente=self.proveedor
        )

        self.assertIsNotNone(mov)
        # Saldo bancario baja de 100.000 a 80.000
        self.cuenta_banco.refresh_from_db()
        self.assertEqual(self.cuenta_banco.saldo_actual, Decimal("80000.00"))

        # Saldo proveedor sube de -50.000 a -30.000 (deuda reducida)
        self.proveedor.refresh_from_db()
        self.assertEqual(self.proveedor.saldo_actual, Decimal("-30000.00"))

    def test_cobro_cliente_aumenta_saldo_cuenta_y_disminuye_credito(self):
        # Cobro de $25.000 al cliente
        mov = registrar_movimiento_financiero(
            cuenta=self.cuenta_banco,
            tipo=MovimientoFinanciero.TipoMovimiento.INGRESO,
            fecha=timezone.now().date(),
            importe=Decimal("25000.00"),
            concepto="Cobro factura de exportación",
            cuenta_corriente=self.cliente
        )

        self.assertIsNotNone(mov)
        # Saldo bancario sube de 100.000 a 125.000
        self.cuenta_banco.refresh_from_db()
        self.assertEqual(self.cuenta_banco.saldo_actual, Decimal("125000.00"))

        # Deuda del cliente hacia nosotros baja de 75.000 a 50.000
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.saldo_actual, Decimal("50000.00"))
