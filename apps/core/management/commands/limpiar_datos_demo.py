from django.core.management.base import BaseCommand
from apps.core.services_demo import limpiar_datos_demo_q1_2026

class Command(BaseCommand):
    help = "Elimina de forma segura y completa todos los datos de prueba del 1° Trimestre de 2026 (Enero a Marzo)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Iniciando purga segura de datos de prueba Q1 2026..."))
        try:
            reporte = limpiar_datos_demo_q1_2026()
            self.stdout.write(self.style.SUCCESS("[OK] Registros eliminados:"))
            for k, v in reporte.items():
                if k not in ('estado', 'mensaje') and v > 0:
                    self.stdout.write(f"   * {k}: {v} registros")
            self.stdout.write(self.style.SUCCESS(f"[OK] {reporte.get('mensaje')}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"[ERROR] Error al limpiar datos: {e}"))
