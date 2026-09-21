from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from datetime import date

from apps.core.models import Empresa, Finca, CentroDeCosto
from apps.campos.models import Cuadro
from apps.costos.models import CostoPorCentro
from apps.costos.services import registrar_costo, prorratear_costo_indirecto, sincronizar_costos_con_cuadro_resultado
from apps.finanzas.models import (
    CuentaContable, 
    CuentaCorriente, 
    Cuenta, 
    CuadroResultado, 
    LineaCuadroResultado,
    TipoCambioMensual
)


class CostosDashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.empresa = Empresa.objects.create(
            razon_social="Olivo Test S.A.",
            cuit="30-11223344-5"
        )
        self.finca = Finca.objects.create(
            empresa=self.empresa,
            nombre="Finca Test",
            codigo="F-TEST",
            superficie_total_ha=Decimal("150.00"),
            activa=True
        )
        self.cuenta_contable = CuentaContable.objects.create(
            codigo='4.2.1.01.000000',
            nombre='Sueldos y cargas sociales - producción agrícola',
            es_imputable=True,
            activa=True
        )
        self.cuenta_insumo = CuentaContable.objects.create(
            codigo='4.2.1.02.000000',
            nombre='Fertilizantes, agroquímicos y riego',
            es_imputable=True,
            activa=True
        )
        self.centro_campo = CentroDeCosto.objects.create(
            empresa=self.empresa,
            codigo="CC-CAMPO",
            nombre="Campo Test",
            finca=self.finca,
            tipo="PRODUCTIVO_CAMPO",
            cuenta_contable_defecto=self.cuenta_contable,
            activo=True
        )
        self.cuadro = Cuadro.objects.create(
            finca=self.finca,
            codigo="CUA-01",
            nombre="Cuadro 1",
            hectareas_netas=Decimal("10.00"),
            variedad_olivo="ARBEQUINA",
            ano_plantacion=2018,
            activo=True
        )
        self.cuadro2 = Cuadro.objects.create(
            finca=self.finca,
            codigo="CUA-02",
            nombre="Cuadro 2",
            hectareas_netas=Decimal("20.00"),
            variedad_olivo="PICUAL",
            ano_plantacion=2019,
            activo=True
        )
        self.proveedor = CuentaCorriente.objects.create(
            tipo_entidad=CuentaCorriente.TipoEntidad.PROVEEDOR,
            razon_social="Agroquímica Pomán SRL",
            cuit="30-77889900-1",
            saldo_actual=Decimal("-50000.00")
        )
        self.caja = Cuenta.objects.create(
            empresa=self.empresa,
            nombre="Caja Finca Test",
            tipo=Cuenta.TipoCuenta.CAJA_EFECTIVO,
            saldo_actual=Decimal("1000000.00")
        )
        self.costo1 = CostoPorCentro.objects.create(
            finca=self.finca,
            centro_de_costo=self.centro_campo,
            cuadro=self.cuadro,
            cuenta_contable=self.cuenta_contable,
            tipo_origen=CostoPorCentro.TipoOrigen.MANO_DE_OBRA,
            fecha=date(2026, 1, 15),
            importe_ars=Decimal("50000.00"),
            importe_usd=Decimal("50.00"),
            descripcion="Jornales de poda"
        )
        self.costo2 = CostoPorCentro.objects.create(
            finca=self.finca,
            centro_de_costo=self.centro_campo,
            cuadro=None,
            cuenta_contable=self.cuenta_insumo,
            tipo_origen=CostoPorCentro.TipoOrigen.ENERGIA_RIEGO,
            fecha=date(2026, 2, 20),
            importe_ars=Decimal("30000.00"),
            importe_usd=Decimal("30.00"),
            descripcion="Factura energía bomba pozo"
        )

    def test_dashboard_renders_successfully(self):
        response = self.client.get(reverse('costos:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'costos/costos_dashboard.html')
        self.assertIn('total_costos_ars', response.context)
        self.assertEqual(response.context['total_costos_ars'], Decimal("80000.00"))
        self.assertEqual(response.context['total_registros'], 2)
        self.assertIn('articulacion_plan_cuentas', response.context)

    def test_dashboard_filters(self):
        # Filter by finca
        response = self.client.get(reverse('costos:dashboard'), {'finca': self.finca.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_registros'], 2)

        # Filter by mes 1 (Enero)
        response_jan = self.client.get(reverse('costos:dashboard'), {'mes': '1'})
        self.assertEqual(response_jan.status_code, 200)
        self.assertEqual(response_jan.context['total_registros'], 1)
        self.assertEqual(response_jan.context['total_costos_ars'], Decimal("50000.00"))

        # Filter by search q
        response_q = self.client.get(reverse('costos:dashboard'), {'q': 'pozo'})
        self.assertEqual(response_q.status_code, 200)
        self.assertEqual(response_q.context['total_registros'], 1)

    def test_exportar_csv_view(self):
        response = self.client.get(reverse('costos:exportar_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/csv'))
        content = response.content.decode('utf-8-sig')
        self.assertIn('Jornales de poda', content)
        self.assertIn('Factura energía bomba pozo', content)
        self.assertIn('50000.00', content)

    def test_crear_costo_view(self):
        data = {
            'finca_id': self.finca.id,
            'cuadro_id': self.cuadro.id,
            'centro_id': self.centro_campo.id,
            'tipo_origen': CostoPorCentro.TipoOrigen.INSUMO,
            'cuenta_contable_id': self.cuenta_insumo.id,
            'fecha': '2026-03-01',
            'importe_ars': '125000.00',
            'descripcion': 'Fertilizante foliar olivo',
            'metodo_pago': 'SOLO_COSTO',
        }
        response = self.client.post(reverse('costos:crear'), data)
        self.assertEqual(response.status_code, 302)
        nuevo_costo = CostoPorCentro.objects.filter(descripcion='Fertilizante foliar olivo').first()
        self.assertIsNotNone(nuevo_costo)
        self.assertEqual(nuevo_costo.cuenta_contable, self.cuenta_insumo)
        self.assertEqual(nuevo_costo.cuadro, self.cuadro)

    def test_crear_costo_con_cuenta_corriente_proveedor(self):
        saldo_previo = self.proveedor.saldo_actual
        data = {
            'finca_id': self.finca.id,
            'cuadro_id': 'general',
            'centro_id': self.centro_campo.id,
            'tipo_origen': CostoPorCentro.TipoOrigen.CONTRATISTA,
            'cuenta_contable_id': self.cuenta_insumo.id,
            'fecha': '2026-03-05',
            'importe_ars': '70000.00',
            'descripcion': 'Servicio de poda mecanizada contratada',
            'proveedor_id': self.proveedor.id,
            'metodo_pago': 'CUENTA_CORRIENTE',
        }
        response = self.client.post(reverse('costos:crear'), data)
        self.assertEqual(response.status_code, 302)
        self.proveedor.refresh_from_db()
        self.assertEqual(self.proveedor.saldo_actual, saldo_previo - Decimal('70000.00'))

    def test_crear_costo_contado_con_caja(self):
        saldo_caja_previo = self.caja.saldo_actual
        data = {
            'finca_id': self.finca.id,
            'cuadro_id': self.cuadro.id,
            'centro_id': self.centro_campo.id,
            'tipo_origen': CostoPorCentro.TipoOrigen.MANO_DE_OBRA,
            'cuenta_contable_id': self.cuenta_contable.id,
            'fecha': '2026-03-10',
            'importe_ars': '45000.00',
            'descripcion': 'Pago jornal regador de guardia',
            'metodo_pago': 'CONTADO',
            'cuenta_financiera_id': self.caja.id,
        }
        response = self.client.post(reverse('costos:crear'), data)
        self.assertEqual(response.status_code, 302)
        self.caja.refresh_from_db()
        self.assertEqual(self.caja.saldo_actual, saldo_caja_previo - Decimal('45000.00'))

    def test_editar_costo_view(self):
        data = {
            'descripcion': 'Jornales de poda invernal reajustados',
            'importe_ars': '55000.00',
            'cuadro_id': self.cuadro.id,
            'cuenta_contable_id': self.cuenta_contable.id,
        }
        response = self.client.post(reverse('costos:editar', args=[self.costo1.id]), data)
        self.assertEqual(response.status_code, 302)
        self.costo1.refresh_from_db()
        self.assertEqual(self.costo1.descripcion, 'Jornales de poda invernal reajustados')
        self.assertEqual(self.costo1.importe_ars, Decimal('55000.00'))

    def test_prorratear_costo_indirecto(self):
        # Costo 2 es indirecto (cuadro=None) de 30.000 ARS.
        # Finca Test tiene Cuadro 1 (10 ha) y Cuadro 2 (20 ha), total 30 ha.
        # Cuadro 1 debe recibir 10.000 ARS y Cuadro 2 debe recibir 20.000 ARS.
        response = self.client.post(reverse('costos:prorratear', args=[self.costo2.id]))
        self.assertEqual(response.status_code, 302)
        self.costo2.refresh_from_db()
        self.assertTrue(self.costo2.prorrateo_realizado)

        hijos = CostoPorCentro.objects.filter(costo_origen_prorrateo=self.costo2)
        self.assertEqual(hijos.count(), 2)
        c1_item = hijos.filter(cuadro=self.cuadro).first()
        c2_item = hijos.filter(cuadro=self.cuadro2).first()
        self.assertEqual(c1_item.importe_ars, Decimal('10000.00'))
        self.assertEqual(c2_item.importe_ars, Decimal('20000.00'))

    def test_eliminar_costo_view(self):
        costo_id = self.costo1.id
        response = self.client.post(reverse('costos:eliminar', args=[costo_id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CostoPorCentro.objects.filter(id=costo_id).exists())

    def test_sincronizar_costos_con_pl(self):
        cuadro_pl = CuadroResultado.objects.create(
            empresa=self.empresa,
            titulo="P&L Q1 2026 Test",
            tipo_periodo=CuadroResultado.TipoPeriodo.TRIMESTRAL,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 3, 31),
            ventas_totales=Decimal('5000000.00')
        )
        response = self.client.post(reverse('costos:sincronizar_pl'))
        self.assertEqual(response.status_code, 302)
        linea_sueldos = LineaCuadroResultado.objects.filter(cuadro=cuadro_pl, cuenta_contable=self.cuenta_contable).first()
        self.assertIsNotNone(linea_sueldos)
        self.assertEqual(linea_sueldos.monto_real, Decimal('50000.00'))
