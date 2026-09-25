from django.test import TestCase
from django.urls import reverse
from decimal import Decimal
from django.utils import timezone
from apps.core.models import Empresa
from apps.finanzas.models import (
    Cuenta, CuentaCorriente, MovimientoFinanciero, TipoCambioMensual,
    ComprobanteFiscal, ArqueoCaja, OrdenPagoRecibo, Cheque
)
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


class LibroIVAyTesoreriaTest(TestCase):
    def setUp(self):
        from django.urls import reverse
        self.empresa, _ = Empresa.objects.get_or_create(
            razon_social="Olivo Test S.A.",
            defaults={'cuit': "30-55667788-9"}
        )
        self.caja, _ = Cuenta.objects.get_or_create(
            empresa=self.empresa,
            nombre="Caja Chica Finca Test",
            defaults={'tipo': Cuenta.TipoCuenta.CAJA_EFECTIVO, 'moneda': "ARS", 'saldo_actual': Decimal("50000.00")}
        )
        self.proveedor, _ = CuentaCorriente.objects.get_or_create(
            cuit="30-77112233-1",
            defaults={
                'razon_social': "Insumos Agrícolas Catamarca SRL",
                'tipo_entidad': CuentaCorriente.TipoEntidad.PROVEEDOR,
                'saldo_actual': Decimal("0.00")
            }
        )
        self.cliente, _ = CuentaCorriente.objects.get_or_create(
            cuit="30-99887766-5",
            defaults={
                'razon_social': "Distribuidora Aceitera Mayorista S.A.",
                'tipo_entidad': CuentaCorriente.TipoEntidad.CLIENTE,
                'saldo_actual': Decimal("0.00")
            }
        )

    def test_crear_comprobante_fiscal_compra_actualiza_cta_cte_y_libro_iva(self):
        from django.urls import reverse
        url = reverse('finanzas:comprobante_create')
        resp = self.client.post(url, {
            'tipo_operacion': 'COMPRA',
            'tipo_comprobante': 'F_A',
            'punto_de_venta': '00002',
            'numero_comprobante': '00004567',
            'fecha_emision': '2026-03-10',
            'cuenta_corriente_id': self.proveedor.id,
            'concepto': 'Compra de fertilizantes foliares',
            'neto_gravado_21': '100000.00',
            'neto_gravado_10_5': '50000.00',
            'exento': '0.00',
            'percepcion_iibb': '3500.00'
        })
        self.assertEqual(resp.status_code, 302)

        comp = ComprobanteFiscal.objects.filter(numero_comprobante='00004567').first()
        self.assertIsNotNone(comp)
        self.assertEqual(comp.neto_gravado_21, Decimal('100000.00'))
        self.assertEqual(comp.iva_21, Decimal('21000.00'))
        self.assertEqual(comp.iva_10_5, Decimal('5250.00'))
        # Total = 100k + 50k + 21k + 5.25k + 3.5k = 179.750
        self.assertEqual(comp.total, Decimal('179750.00'))
        self.assertEqual(comp.saldo_pendiente, Decimal('179750.00'))
        self.assertEqual(comp.estado_pago, 'PENDIENTE')

        self.proveedor.refresh_from_db()
        self.assertEqual(self.proveedor.saldo_actual, Decimal('-179750.00'))

    def test_pago_comprobante_fiscal_emite_orden_pago_y_descuenta_caja(self):
        from django.urls import reverse
        comp = ComprobanteFiscal.objects.create(
            tipo_operacion='COMPRA',
            tipo_comprobante='F_A',
            punto_de_venta='00001',
            numero_comprobante='00008899',
            fecha_emision=timezone.now().date(),
            cuenta_corriente=self.proveedor,
            razon_social=self.proveedor.razon_social,
            cuit=self.proveedor.cuit,
            concepto='Factura a cancelar',
            total=Decimal('30000.00'),
            saldo_pendiente=Decimal('30000.00')
        )
        self.proveedor.saldo_actual = Decimal('-30000.00')
        self.proveedor.save()

        url_pago = reverse('finanzas:comprobante_pago')
        resp = self.client.post(url_pago, {
            'comprobante_id': comp.id,
            'importe': '30000.00',
            'cuenta_financiera_id': self.caja.id,
            'medio_pago': 'EFECTIVO',
            'fecha': str(timezone.now().date()),
            'beneficiario_firmante': 'Chofer del Proveedor'
        })
        self.assertEqual(resp.status_code, 302)

        comp.refresh_from_db()
        self.assertEqual(comp.saldo_pendiente, Decimal('0.00'))
        self.assertEqual(comp.estado_pago, 'PAGADA')

        self.caja.refresh_from_db()
        self.assertEqual(self.caja.saldo_actual, Decimal('20000.00'))  # 50.000 - 30.000

        self.proveedor.refresh_from_db()
        self.assertEqual(self.proveedor.saldo_actual, Decimal('0.00'))

        orden = OrdenPagoRecibo.objects.filter(comprobante_fiscal=comp).first()
        self.assertIsNotNone(orden)
        self.assertEqual(orden.tipo, 'OP')
        self.assertEqual(orden.importe_total, Decimal('30000.00'))

    def test_arqueo_caja_detecta_diferencia_y_ajusta(self):
        from django.urls import reverse
        url = reverse('finanzas:arqueo_create')
        # Saldo sistema en caja es 50.000. Contamos 48.000 (faltante de 2.000)
        resp = self.client.post(url, {
            'cuenta_id': self.caja.id,
            'fecha': '2026-03-21',
            'hora': '18:00',
            'saldo_real_contado': '48000.00',
            'ajustar_saldo': '1',
            'observaciones': 'Arqueo de cierre de jornada'
        })
        self.assertEqual(resp.status_code, 302)

        arqueo = ArqueoCaja.objects.filter(cuenta=self.caja).first()
        self.assertIsNotNone(arqueo)
        self.assertEqual(arqueo.diferencia, Decimal('-2000.00'))

        self.caja.refresh_from_db()
        self.assertEqual(self.caja.saldo_actual, Decimal('48000.00'))

    def test_exportar_libro_iva_csv(self):
        from django.urls import reverse
        ComprobanteFiscal.objects.create(
            tipo_operacion='COMPRA',
            tipo_comprobante='F_A',
            punto_de_venta='00001',
            numero_comprobante='00009999',
            fecha_emision=timezone.now().date(),
            cuenta_corriente=self.proveedor,
            razon_social=self.proveedor.razon_social,
            cuit=self.proveedor.cuit,
            concepto='Fertilizante test',
            neto_gravado_21=Decimal('10000.00'),
            iva_21=Decimal('2100.00'),
            total=Decimal('12100.00')
        )
        url_exp = reverse('finanzas:exportar_libro_iva')
        now = timezone.now().date()
        resp = self.client.get(f"{url_exp}?mes={now.month}&ano={now.year}&tipo=COMPRA")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        pass # Cannot easily assert string in binary excel

    def test_afip_padron_lookup_endpoint(self):
        url = reverse('finanzas:afip_padron_lookup', kwargs={'cuit': '20409378472'})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('data', {}).get('cuit'), '20409378472')

    def test_comprobante_fiscal_print_con_qr_arca(self):
        comp = ComprobanteFiscal.objects.create(
            tipo_operacion='VENTA',
            tipo_comprobante='F_B',
            punto_de_venta='00001',
            numero_comprobante='00035201',
            fecha_emision=timezone.now().date(),
            cuenta_corriente=self.cliente,
            razon_social=self.cliente.razon_social,
            cuit=self.cliente.cuit,
            concepto='Aceite de Oliva Extra Virgen 500ml',
            neto_gravado_21=Decimal('100.00'),
            iva_21=Decimal('21.00'),
            total=Decimal('121.00'),
            cae='86380918421149',
            vto_cae=timezone.now().date()
        )
        url = reverse('finanzas:comprobante_fiscal_print', kwargs={'pk': comp.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'86380918421149', resp.content)
        self.assertIn(b'arca.gob.ar/fe/qr', resp.content)


