import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0007_asignacionherramienta_cuadro_destino_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='ordendecompra',
            name='requiere_represupuesto',
            field=models.BooleanField(default=False, verbose_name='Requiere Represupuesto'),
        ),
        migrations.AddField(
            model_name='ordendecompra',
            name='motivo_represupuesto',
            field=models.TextField(blank=True, verbose_name='Motivo del Represupuesto'),
        ),
        migrations.AddField(
            model_name='ordendecompra',
            name='motivo_anulacion',
            field=models.TextField(blank=True, verbose_name='Motivo de Anulación'),
        ),
        migrations.AddField(
            model_name='ordendecompra',
            name='aprobada_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ordenes_compra_aprobadas', to=settings.AUTH_USER_MODEL, verbose_name='Aprobada por'),
        ),
        migrations.AddField(
            model_name='ordendecompra',
            name='fecha_aprobacion',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Fecha de Aprobación'),
        ),
    ]
