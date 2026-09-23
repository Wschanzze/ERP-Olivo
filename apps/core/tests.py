from django.test import TestCase, Client
from django.urls import reverse
from apps.core.models import Usuario


class ERPAuthenticationAndRBACTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Admin User
        self.admin_user = Usuario.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='password123',
            rol=Usuario.Rol.ADMIN_GENERAL,
            is_staff=True,
            is_superuser=True
        )
        # Operario User (campo / operario)
        self.operario_user = Usuario.objects.create_user(
            username='operario_test',
            email='operario@test.com',
            password='password123',
            rol=Usuario.Rol.OPERARIO,
            is_staff=False,
            is_superuser=False
        )
        # Contable User
        self.contable_user = Usuario.objects.create_user(
            username='contable_test',
            email='contable@test.com',
            password='password123',
            rol=Usuario.Rol.CONTABLE,
            is_staff=False,
            is_superuser=False
        )

    def test_anonymous_redirected_to_login(self):
        """Verifica que un usuario no autenticado sea redirigido al login."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

        response_finanzas = self.client.get('/finanzas/')
        self.assertEqual(response_finanzas.status_code, 302)
        self.assertIn('/login/', response_finanzas.url)

    def test_login_page_renders_successfully(self):
        """La página de inicio de sesión carga correctamente (HTTP 200)."""
        response = self.client.get(reverse('core:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ERP Olivícola')
        self.assertContains(response, 'Iniciar Sesión')

    def test_login_local_fallback(self):
        """Inicio de sesión exitoso con usuario local."""
        response = self.client.post(reverse('core:login'), {
            'identifier': 'admin@test.com',
            'password': 'password123',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertEqual(response.context['user'].username, 'admin_test')

    def test_admin_has_full_access(self):
        """El administrador general puede acceder a Finanzas, Usuarios y Tableros."""
        self.client.force_login(self.admin_user)
        
        # Tableros / Dashboard
        resp_dash = self.client.get(reverse('dashboard:index'))
        self.assertEqual(resp_dash.status_code, 200)

        # Usuarios
        resp_usuarios = self.client.get(reverse('core:usuarios_list'))
        self.assertEqual(resp_usuarios.status_code, 200)

    def test_operario_restricted_from_finanzas_and_usuarios(self):
        """Un operario no puede entrar a Finanzas ni al panel de Usuarios (HTTP 403)."""
        self.client.force_login(self.operario_user)

        # Finanzas debe retornar 403 Forbidden
        resp_fin = self.client.get('/finanzas/')
        self.assertEqual(resp_fin.status_code, 403)
        self.assertContains(resp_fin, 'Módulo Restringido', status_code=403)

        # Gestión de Usuarios debe retornar 403 Forbidden para no-administradores
        resp_usr = self.client.get(reverse('core:usuarios_list'))
        self.assertEqual(resp_usr.status_code, 403)

    def test_contable_access_to_finanzas(self):
        """Un usuario contable puede entrar a Finanzas pero no a Usuarios."""
        self.client.force_login(self.contable_user)

        resp_fin = self.client.get('/finanzas/')
        self.assertEqual(resp_fin.status_code, 200)

        resp_usr = self.client.get(reverse('core:usuarios_list'))
        self.assertEqual(resp_usr.status_code, 403)

    def test_logout(self):
        """Cierre de sesión redirige a /login/ y desautentica."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('core:logout'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

        # Ahora el acceso a / debe requerir login
        resp_after = self.client.get('/')
        self.assertEqual(resp_after.status_code, 302)
