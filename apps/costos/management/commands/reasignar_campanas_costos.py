from django.core.management.base import BaseCommand
from apps.costos.models import CostoPorCentro
from apps.costos.services import calcular_campana_desde_fecha

class Command(BaseCommand):
    help = 'Reasigna campanas a costos huerfanos (campana="") basandose en la fecha'

    def add_arguments(self, parser):
        parser.add_argument(
            '--aplicar',
            action='store_true',
            help='Aplica los cambios en la base de datos (por defecto solo hace dry-run)',
        )

    def handle(self, *args, **options):
        aplicar = options['aplicar']
        costos = list(CostoPorCentro.objects.filter(campana=''))
        
        if not costos:
            self.stdout.write(self.style.SUCCESS('No se encontraron costos sin campana asignada.'))
            return

        self.stdout.write(f'Se encontraron {len(costos)} costos sin campana.')
        
        resumen = {}
        for costo in costos:
            campana = calcular_campana_desde_fecha(costo.fecha)
            costo.campana = campana
            resumen[campana] = resumen.get(campana, 0) + 1

        if aplicar:
            CostoPorCentro.objects.bulk_update(costos, ['campana'], batch_size=500)
            self.stdout.write(self.style.SUCCESS('\n--- CAMBIOS APLICADOS ---'))
        else:
            self.stdout.write(self.style.WARNING('\n--- MODO DRY-RUN (no se guardaron cambios) ---'))

        self.stdout.write(f'Total registros procesados: {len(costos)}')
        for k, v in sorted(resumen.items()):
            self.stdout.write(f'Campana {k}: {v} costos')
        
        if not aplicar:
            self.stdout.write(self.style.WARNING('\nPara aplicar los cambios, ejecute el comando con --aplicar'))