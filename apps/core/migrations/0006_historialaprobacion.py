from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_populate_empresa_kek'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistorialAprobacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Última Modificación')),
                ('tipo_documento', models.CharField(choices=[('OC', 'Orden de Compra'), ('OP', 'Orden de Pago')], max_length=5, verbose_name='Tipo de Documento')),
                ('objeto_id', models.PositiveBigIntegerField(verbose_name='ID del Documento')),
                ('referencia', models.CharField(max_length=60, verbose_name='N° de Documento')),
                ('columna_origen', models.CharField(max_length=30, verbose_name='Columna Origen')),
                ('columna_destino', models.CharField(max_length=30, verbose_name='Columna Destino')),
                ('estado_anterior', models.CharField(max_length=30, verbose_name='Estado Anterior')),
                ('estado_nuevo', models.CharField(max_length=30, verbose_name='Estado Nuevo')),
                ('motivo', models.TextField(blank=True, verbose_name='Motivo / Comentario')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='aprobaciones_realizadas', to=settings.AUTH_USER_MODEL, verbose_name='Usuario')),
            ],
            options={
                'verbose_name': 'Historial de Aprobación',
                'verbose_name_plural': 'Historial de Aprobaciones',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['tipo_documento', 'objeto_id'], name='core_hist_aprob_doc_idx')],
            },
        ),
    ]
