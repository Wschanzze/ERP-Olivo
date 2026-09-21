from django.core.management.base import BaseCommand
from apps.core.services_demo import poblar_datos_demo_q1_2026

class Command(BaseCommand):
    help = "Siembra datos de prueba coherentes para el 1° Trimestre de 2026 (Enero a Marzo) en todos los módulos del ERP."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Sembrando datos de prueba para Q1 2026 (Enero a Marzo)..."))
        try:
            res = poblar_datos_demo_q1_2026()
            self.stdout.write(self.style.SUCCESS(f"[OK] {res.get('mensaje', 'Datos cargados exitosamente.')}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"[ERROR] Error al poblar datos: {e}"))
