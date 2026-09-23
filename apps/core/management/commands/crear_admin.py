from django.core.management.base import BaseCommand
from apps.core.models import Usuario
from apps.core.supabase_service import SupabaseAuthService


class Command(BaseCommand):
    help = "Crea o actualiza la cuenta de Administrador General en Supabase Auth y en Django."

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, default='josuugonzalezz@gmail.com', help='Correo del administrador')
        parser.add_argument('--password', type=str, default='olivos123', help='Contraseña del administrador')
        parser.add_argument('--first-name', type=str, default='Joshua', help='Nombre del administrador')
        parser.add_argument('--last-name', type=str, default='Gonzalez', help='Apellido del administrador')

    def handle(self, *args, **options):
        email = options['email'].strip().lower()
        password = options['password'].strip()
        first_name = options['first_name'].strip()
        last_name = options['last_name'].strip()

        self.stdout.write(f"Configurando cuenta de administrador para {email}...")

        # 1. Supabase Auth
        supabase_uid = None
        if SupabaseAuthService.is_configured():
            self.stdout.write("Conectando con Supabase Auth API...")
            success, sb_data, err = SupabaseAuthService.admin_create_user(
                email=email,
                password=password,
                rol='ADMIN_GENERAL',
                first_name=first_name,
                last_name=last_name
            )
            if success and sb_data:
                supabase_uid = sb_data.get('supabase_uid')
                self.stdout.write(self.style.SUCCESS(f"Usuario registrado en Supabase Auth con UID: {supabase_uid}"))
            else:
                self.stdout.write(self.style.WARNING(f"Aviso Supabase: {err} (quizás el usuario ya existía en Supabase)."))
                # Intentar login en Supabase para obtener el UID existente
                ok_login, udata, _ = SupabaseAuthService.sign_in(email, password)
                if ok_login and udata:
                    supabase_uid = udata.get('supabase_uid')
                    self.stdout.write(self.style.SUCCESS(f"UID recuperado de Supabase: {supabase_uid}"))
        else:
            self.stdout.write(self.style.WARNING("Supabase no está configurado en el entorno; creando solo en Django local."))

        # 2. Django Local Usuario
        user = Usuario.objects.filter(email__iexact=email).first()
        if not user:
            username = email.split('@')[0]
            base_u = username
            c = 1
            while Usuario.objects.filter(username=username).exists():
                username = f"{base_u}{c}"
                c += 1
            user = Usuario.objects.create(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                rol=Usuario.Rol.ADMIN_GENERAL,
                is_staff=True,
                is_superuser=True,
                is_active=True,
            )
            self.stdout.write(self.style.SUCCESS(f"Usuario creado en Django: {user.username}"))
        else:
            user.rol = Usuario.Rol.ADMIN_GENERAL
            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            self.stdout.write(self.style.SUCCESS(f"Usuario existente actualizado en Django: {user.username}"))

        if supabase_uid:
            user.supabase_uid = supabase_uid

        user.set_password(password)
        user.save()

        self.stdout.write(self.style.SUCCESS(f"[OK] Cuenta de Administrador configurada exitosamente ({email})."))
