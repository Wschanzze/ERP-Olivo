from django.db import migrations
from datetime import date

def populate_empresa(apps, schema_editor):
    Empresa = apps.get_model('core', 'Empresa')
    empresa = Empresa.objects.first()
    if not empresa:
        empresa = Empresa()

    empresa.razon_social = "KEK PRODUCERS ARGENTINA SRL"
    empresa.cuit = "30710172907"
    empresa.direccion = "Ruta 74 Km 829 0 - Vichigasta, La Rioja"
    empresa.condicion_iva = "Responsable Inscripto"
    empresa.ingresos_brutos = "007-007257-7"
    empresa.inicio_actividades = date(2017, 1, 1)
    
    empresa.save()

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_empresa_condicion_iva_empresa_ingresos_brutos_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_empresa),
    ]
