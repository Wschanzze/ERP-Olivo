from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from datetime import date

from apps.core.models import Empresa, Finca, CentroDeCosto
from apps.campos.models import Cuadro
from apps.costos.models import CostoPorCentro


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
        self.centro_campo = CentroDeCosto.objects.create(
            empresa=self.empresa,
            codigo="CC-CAMPO",
            nombre="Campo Test",
            finca=self.finca,
            tipo="PRODUCTIVO_CAMPO",
            activo=True
        )
        self.cuadro = Cuadro.objects.create(
            finca=self.finca,
            codigo="CUA-01",
            nombre="Cuadro 1",
            hectareas_netas=Decimal("10.00"),
            variedad_olivo="ARBEQUINA",
            ano_plantacion=2018
        )
        self.costo1 = CostoPorCentro.objects.create(
            finca=self.finca,
            centro_de_costo=self.centro_campo,
            cuadro=self.cuadro,
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
        self.assertIn('resumen_por_cuadro', response.context)
        self.assertIn('resumen_por_categoria', response.context)

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
