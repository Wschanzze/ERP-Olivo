from django.test import TestCase
from decimal import Decimal
from django.utils import timezone
from apps.core.models import Empresa
from apps.finanzas.models import Cuenta, CuentaCorriente, MovimientoFinanciero, TipoCambioMensual
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


class TipoCambioYCuadroSimplificadoTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            razon_social="Agro Olivarera Test S.A.",
            cuit="30-77889900-1",
            moneda_principal="ARS"
        )
        self.tc_ene = TipoCambioMensual.objects.create(
            empresa=self.empresa,
            ano=2026,
            mes=1,
            tc=Decimal("1050.00")
        )

    def test_tipo_cambio_mensual_lookup(self):
        # TC para Enero 2026 debe devolver 1050
        tc = TipoCambioMensual.get_tc(self.empresa, ano=2026, mes=1)
        self.assertEqual(tc, Decimal("1050.00"))

        # TC para mes no registrado debe retornar el último registrado (1050)
        tc_feb = TipoCambioMensual.get_tc(self.empresa, ano=2026, mes=2)
        self.assertEqual(tc_feb, Decimal("1050.00"))

    def test_tipo_cambio_guardar_view(self):
        from django.urls import reverse
        url = reverse('finanzas:tipo_cambio_guardar')
        response = self.client.post(url, {
            'ano': 2026,
            'mes': 4,
            'tc': '1120.50',
            'fuente': 'OFICIAL'
        })
        self.assertEqual(response.status_code, 302)
        tc_obj = TipoCambioMensual.objects.get(empresa=self.empresa, ano=2026, mes=4)
        self.assertEqual(tc_obj.tc, Decimal("1120.50"))

    def test_finanzas_dashboard_no_contiene_tabs_horizontales_y_tiene_tc(self):
        from django.urls import reverse
        url = reverse('finanzas:dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Contexto contiene tc_vigente y cuadro_simplificado si hay cuadro
        self.assertIn('tc_vigente', response.context)
        self.assertIn('total_consolidado_ars', response.context)
        self.assertIn('total_consolidado_usd', response.context)

        # Verificar que el modal de tipo de cambio y botón fijar TC están presentes en el HTML
        content = response.content.decode('utf-8')
        self.assertIn('modalTipoCambio', content)
        self.assertIn('Fijar TC', content)

    def test_cuadro_resultado_simplificado_en_ars(self):
        from apps.finanzas.models import CuadroResultado, CuentaContable, LineaCuadroResultado
        from apps.finanzas.views import build_cuadro_simplificado
        import datetime

        cuadro = CuadroResultado.objects.create(
            empresa=self.empresa,
            titulo="Cuadro Test ARS",
            tipo_periodo=CuadroResultado.TipoPeriodo.TRIMESTRAL,
            fecha_inicio=datetime.date(2026, 1, 1),
            fecha_fin=datetime.date(2026, 3, 31),
            moneda=CuadroResultado.Moneda.ARS,
            tipo_cambio=Decimal("1050.00"),
        )
        self.assertEqual(cuadro.moneda, 'ARS')

        cta_vtas = CuentaContable.objects.create(
            codigo="4.1.1.01",
            nombre="Ventas de Aceite Fraccionado",
            clase=CuentaContable.ClaseCuenta.RESULTADO_POSITIVO,
            nivel=4,
            es_imputable=True
        )
        LineaCuadroResultado.objects.create(
            cuadro=cuadro,
            cuenta_contable=cta_vtas,
            seccion=LineaCuadroResultado.SeccionResultado.INGRESOS_OPERATIVOS,
            monto_real=Decimal("10500000.00"),
            monto_presupuestado=Decimal("10000000.00")
        )
        cuadro.recalcular_totales(save=True)

        res = build_cuadro_simplificado(cuadro, Decimal("1050.00"))
        self.assertEqual(res['ventas_totales_ars'], Decimal("10500000.00"))
        self.assertEqual(res['ventas_totales_usd'], Decimal("10000.00"))
        self.assertTrue(len(res['bloques']) > 0)


class FinanzasOperacionesInteractivasTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(razon_social="Olivo Finca Test", cuit="30-33445566-7")
        self.cuenta = Cuenta.objects.create(
            empresa=self.empresa,
            nombre="Caja Central Finca",
            tipo="CAJA",
            saldo_actual=Decimal("50000.00")
        )
        self.cuenta_banco = Cuenta.objects.create(
            empresa=self.empresa,
            nombre="Banco Galicia Cta Cte",
            tipo="BANCO",
            saldo_actual=Decimal("150000.00")
        )
        self.proveedor = CuentaCorriente.objects.create(
            razon_social="Agronomía San Juan S.A.",
            cuit="30-44556677-8",
            tipo_entidad=CuentaCorriente.TipoEntidad.PROVEEDOR,
            saldo_actual=Decimal("-40000.00")
        )
        self.cliente = CuentaCorriente.objects.create(
            razon_social="Aceitera del Sol S.A.",
            cuit="30-88990011-2",
            tipo_entidad=CuentaCorriente.TipoEntidad.CLIENTE,
            saldo_actual=Decimal("90000.00")
        )
        self.cheque = Cheque.objects.create(
            tipo="RECIBIDO",
            banco_emisor="Banco Macro",
            numero="99887711",
            emisor_firmante="Aceitera del Sol S.A.",
            cuit_emisor="30-88990011-2",
            fecha_emision=timezone.now().date(),
            fecha_cobro=timezone.now().date(),
            importe=Decimal("35000.00"),
            estado="EN_CARTERA"
        )

    def test_pago_proveedor_view(self):
        from django.urls import reverse
        url = reverse('finanzas:proveedor_pagar')
        resp = self.client.post(url, {
            'proveedor_id': self.proveedor.id,
            'cuenta_id': self.cuenta.id,
            'importe': '15000.00',
            'concepto': 'Pago factura abonos',
            'comprobante_nro': 'OP-001'
        })
        self.assertEqual(resp.status_code, 302)
        self.cuenta.refresh_from_db()
        self.proveedor.refresh_from_db()
        self.assertEqual(self.cuenta.saldo_actual, Decimal("35000.00"))
        self.assertEqual(self.proveedor.saldo_actual, Decimal("-25000.00"))

    def test_cobro_cliente_view(self):
        from django.urls import reverse
        url = reverse('finanzas:cliente_cobrar')
        resp = self.client.post(url, {
            'cliente_id': self.cliente.id,
            'cuenta_id': self.cuenta_banco.id,
            'importe': '30000.00',
            'concepto': 'Cobro lote aceituna',
            'comprobante_nro': 'REC-001'
        })
        self.assertEqual(resp.status_code, 302)
        self.cuenta_banco.refresh_from_db()
        self.cliente.refresh_from_db()
        self.assertEqual(self.cuenta_banco.saldo_actual, Decimal("180000.00"))
        self.assertEqual(self.cliente.saldo_actual, Decimal("60000.00"))

    def test_arqueo_caja_con_ajuste(self):
        from django.urls import reverse
        url = reverse('finanzas:caja_arqueo')
        resp = self.client.post(url, {
            'cuenta_id': self.cuenta.id,
            'monto_fisico': '52000.00',  # Sobrante de 2.000
            'ajustar_saldo': 'true',
            'observaciones': 'Conteo físico fin de turno'
        })
        self.assertEqual(resp.status_code, 302)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.saldo_actual, Decimal("52000.00"))

    def test_cheque_depositar_y_acreditar(self):
        from django.urls import reverse
        # 1. Depositar
        url = reverse('finanzas:cheque_cambiar_estado', args=[self.cheque.id])
        resp = self.client.post(url, {
            'accion': 'depositar',
            'cuenta_bancaria_id': self.cuenta_banco.id
        })
        self.assertEqual(resp.status_code, 302)
        self.cheque.refresh_from_db()
        self.assertEqual(self.cheque.estado, 'DEPOSITADO')
        self.assertEqual(self.cheque.cuenta_bancaria_origen, self.cuenta_banco)

        # 2. Acreditar
        saldo_inicial = self.cuenta_banco.saldo_actual
        resp2 = self.client.post(url, {
            'accion': 'acreditar'
        })
        self.assertEqual(resp2.status_code, 302)
        self.cheque.refresh_from_db()
        self.cuenta_banco.refresh_from_db()
        self.assertEqual(self.cheque.estado, 'COBRADO')
        self.assertEqual(self.cuenta_banco.saldo_actual, saldo_inicial + Decimal("35000.00"))

    def test_cheque_endosar_a_proveedor(self):
        from django.urls import reverse
        url = reverse('finanzas:cheque_cambiar_estado', args=[self.cheque.id])
        resp = self.client.post(url, {
            'accion': 'endosar',
            'proveedor_id': self.proveedor.id
        })
        self.assertEqual(resp.status_code, 302)
        self.cheque.refresh_from_db()
        self.proveedor.refresh_from_db()
        self.assertEqual(self.cheque.estado, 'ENTREGADO_PROVEEDOR')
        self.assertEqual(self.cheque.cuenta_corriente, self.proveedor)
        # Deuda baja de -40000 a -5000 (+35000)
        self.assertEqual(self.proveedor.saldo_actual, Decimal("-5000.00"))


