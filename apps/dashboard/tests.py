from django.test import TestCase, Client
from django.urls import reverse
from apps.core.models import Empresa, Finca, Usuario

class ERPViewsIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.empresa = Empresa.objects.create(
            razon_social="Olivo Test S.A.",
            cuit="30-88887777-1"
        )
        self.finca = Finca.objects.create(
            empresa=self.empresa,
            nombre="Finca Test",
            codigo="F-01",
            superficie_total_ha=50
        )
        self.user = Usuario.objects.create_user(
            username="testuser",
            password="password123",
            finca_predeterminada=self.finca,
            rol=Usuario.Rol.ADMIN_GENERAL
        )
        self.client.login(username="testuser", password="password123")

    def test_dashboard_page_mounts_react_island(self):
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="react-dashboard-island"')
        self.assertContains(response, '/api/v1/dashboard/kpis/')

    def test_drf_kpi_endpoint_returns_valid_json(self):
        response = self.client.get(reverse('dashboard-kpis'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('resumen', data)
        self.assertIn('variedades', data)
        self.assertIn('costos_por_categoria', data)

    def test_finanzas_tabs_view_loads(self):
        response = self.client.get(reverse('finanzas:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cajas y Bancos')
        self.assertContains(response, 'Proveedores')

    def test_personal_asistencia_view_loads(self):
        response = self.client.get(reverse('personal:asistencia_diaria'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Control de Asistencia')

    def test_campos_cuadros_view_loads(self):
        response = self.client.get(reverse('campos:cuadros_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Catastro de Cuadros')
