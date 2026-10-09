from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


def _monto(nombre):
    return models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name=nombre)


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0010_alter_comprobantefiscal_tipo_comprobante'),
    ]

    operations = [
        # Moneda y cotización
        migrations.AddField(
            model_name='comprobantefiscal',
            name='moneda',
            field=models.CharField(choices=[('ARS', 'Pesos Argentinos (ARS)'), ('USD', 'Dólares Estadounidenses (USD)')], default='ARS', max_length=5, verbose_name='Moneda del Comprobante'),
        ),
        migrations.AddField(
            model_name='comprobantefiscal',
            name='tipo_cambio',
            field=models.DecimalField(decimal_places=6, default=Decimal('1.000000'), help_text='Cotización informada a ARCA. 1 para comprobantes en pesos.', max_digits=14, verbose_name='Tipo de Cambio (ARS por unidad)'),
        ),
        # Alícuotas de IVA faltantes
        migrations.AddField(model_name='comprobantefiscal', name='neto_gravado_0', field=_monto('Neto Gravado 0%')),
        migrations.AddField(model_name='comprobantefiscal', name='neto_gravado_2_5', field=_monto('Neto Gravado 2.5%')),
        migrations.AddField(model_name='comprobantefiscal', name='neto_gravado_5', field=_monto('Neto Gravado 5%')),
        migrations.AddField(model_name='comprobantefiscal', name='iva_2_5', field=_monto('IVA Liquidado 2.5%')),
        migrations.AddField(model_name='comprobantefiscal', name='iva_5', field=_monto('IVA Liquidado 5%')),
        # Otros tributos
        migrations.AddField(model_name='comprobantefiscal', name='percepcion_ganancias', field=_monto('Percepción de Ganancias')),
        migrations.AddField(model_name='comprobantefiscal', name='impuestos_municipales', field=_monto('Impuestos Municipales')),
        # Líneas del comprobante
        migrations.CreateModel(
            name='DetalleComprobanteFiscal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Última Modificación')),
                ('orden', models.PositiveSmallIntegerField(default=0, verbose_name='Orden')),
                ('codigo', models.CharField(blank=True, max_length=50, verbose_name='Código')),
                ('descripcion', models.CharField(max_length=500, verbose_name='Producto / Servicio')),
                ('cantidad', models.DecimalField(decimal_places=3, default=Decimal('1.000'), max_digits=14, verbose_name='Cantidad')),
                ('unidad_medida', models.CharField(default='unidades', max_length=20, verbose_name='Unidad de Medida')),
                ('precio_unitario', models.DecimalField(decimal_places=4, default=Decimal('0.0000'), max_digits=16, verbose_name='Precio Unitario')),
                ('bonificacion_porcentaje', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=5, verbose_name='% Bonificación')),
                ('alicuota_iva', models.CharField(choices=[('NG', 'No Gravado'), ('EX', 'Exento'), ('0', '0%'), ('2.5', '2,5%'), ('5', '5%'), ('10.5', '10,5%'), ('21', '21%'), ('27', '27%')], default='21', max_length=4, verbose_name='Alícuota IVA')),
                ('subtotal_neto', _monto('Subtotal Neto')),
                ('importe_iva', _monto('Importe IVA')),
                ('subtotal_con_iva', _monto('Subtotal c/IVA')),
                ('comprobante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles', to='finanzas.comprobantefiscal', verbose_name='Comprobante')),
            ],
            options={
                'verbose_name': 'Detalle de Comprobante',
                'verbose_name_plural': 'Detalles de Comprobantes',
                'ordering': ['comprobante', 'orden', 'id'],
            },
        ),
    ]
