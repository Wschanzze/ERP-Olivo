from django import forms
from decimal import Decimal
from .models import Insumo, Deposito, MovimientoStock, CategoriaInsumo

class BaseStyledForm(forms.Form):
    """Estilizado homogéneo con Tailwind CSS para campos de formulario."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            current_classes = field.widget.attrs.get('class', '')
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = f"{current_classes} rounded text-[#3D4A2A] focus:ring-[#3D4A2A] border-slate-300"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = f"{current_classes} w-full rounded-xl border border-slate-300 bg-white py-2 px-3 text-xs focus:border-[#3D4A2A] focus:outline-none focus:ring-1 focus:ring-[#3D4A2A]"
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = f"{current_classes} w-full rounded-xl border border-slate-300 bg-white py-2 px-3 text-xs focus:border-[#3D4A2A] focus:outline-none focus:ring-1 focus:ring-[#3D4A2A]"
                field.widget.attrs.setdefault('rows', 3)
            else:
                field.widget.attrs['class'] = f"{current_classes} w-full rounded-xl border border-slate-300 bg-white py-2 px-3 text-xs focus:border-[#3D4A2A] focus:outline-none focus:ring-1 focus:ring-[#3D4A2A]"


class TransferenciaStockForm(BaseStyledForm):
    insumo = forms.ModelChoiceField(
        queryset=Insumo.objects.filter(activo=True).order_by('nombre'),
        label="Insumo a transferir",
        empty_label="Seleccione un insumo..."
    )
    deposito_origen = forms.ModelChoiceField(
        queryset=Deposito.objects.filter(activo=True).order_by('finca__nombre', 'nombre'),
        label="Depósito Origen (Sale)",
        empty_label="Seleccione depósito origen..."
    )
    deposito_destino = forms.ModelChoiceField(
        queryset=Deposito.objects.filter(activo=True).order_by('finca__nombre', 'nombre'),
        label="Depósito Destino (Ingresa)",
        empty_label="Seleccione depósito destino..."
    )
    cantidad = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
        label="Cantidad a Trasladar",
        widget=forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'})
    )
    motivo = forms.CharField(
        max_length=200,
        required=False,
        label="Motivo o Justificación",
        widget=forms.TextInput(attrs={'placeholder': 'Ej. Reabastecimiento para cura de fin de semana'})
    )

    def clean(self):
        cleaned_data = super().clean()
        origen = cleaned_data.get('deposito_origen')
        destino = cleaned_data.get('deposito_destino')

        if origen and destino and origen == destino:
            raise forms.ValidationError("El depósito origen y destino no pueden ser el mismo.")

        return cleaned_data


class AjusteStockForm(BaseStyledForm):
    TIPO_CHOICES = [
        (MovimientoStock.TipoMovimiento.AJUSTE_POSITIVO, 'Ajuste Positivo (+ Ingreso por Sobrante)'),
        (MovimientoStock.TipoMovimiento.AJUSTE_NEGATIVO, 'Ajuste Negativo (- Salida por Faltante de Recuento)'),
        (MovimientoStock.TipoMovimiento.SALIDA_MERMA, 'Salida por Merma / Rotura / Vencimiento'),
    ]

    insumo = forms.ModelChoiceField(
        queryset=Insumo.objects.filter(activo=True).order_by('nombre'),
        label="Insumo",
        empty_label="Seleccione un insumo..."
    )
    deposito = forms.ModelChoiceField(
        queryset=Deposito.objects.filter(activo=True).order_by('finca__nombre', 'nombre'),
        label="Depósito Físico",
        empty_label="Seleccione depósito..."
    )
    tipo_ajuste = forms.ChoiceField(
        choices=TIPO_CHOICES,
        label="Tipo de Operación / Ajuste"
    )
    cantidad = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
        label="Cantidad a Ajustar",
        widget=forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'})
    )
    costo_unitario = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        label="Costo Unitario (ARS) - Opcional para revaluar PPP",
        widget=forms.NumberInput(attrs={'step': '0.01', 'placeholder': 'Dejar en blanco para usar costo PPP actual'})
    )
    motivo = forms.CharField(
        max_length=200,
        required=True,
        label="Justificación Obligatoria",
        widget=forms.TextInput(attrs={'placeholder': 'Ej. Rotura en estiba galpón norte, recuento físico trimestral'})
    )


class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = [
            'codigo', 'nombre', 'categoria', 'unidad_medida',
            'principio_activo', 'stock_minimo', 'costo_unitario_ars', 'costo_unitario_usd'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={'placeholder': 'Ej. AGRO-001'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre comercial o técnico'}),
            'principio_activo': forms.TextInput(attrs={'placeholder': 'Ej. Oxicloruro de Cobre 50%'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = "w-full rounded-xl border border-slate-300 bg-white py-2 px-3 text-xs focus:border-[#3D4A2A] focus:outline-none focus:ring-1 focus:ring-[#3D4A2A]"
            else:
                field.widget.attrs['class'] = "w-full rounded-xl border border-slate-300 bg-white py-2 px-3 text-xs focus:border-[#3D4A2A] focus:outline-none focus:ring-1 focus:ring-[#3D4A2A]"


class GenerarOCSugeridaForm(BaseStyledForm):
    """Formulario para confirmar la creación de una OC a partir de sugerencia de reorden."""
    from apps.finanzas.models import CuentaCorriente
    from apps.core.models import Finca

    proveedor = forms.ModelChoiceField(
        queryset=CuentaCorriente.objects.filter(tipo_entidad='PROVEEDOR', activo=True).order_by('razon_social'),
        label="Proveedor Habitual *",
        empty_label="Seleccione un proveedor..."
    )
    finca_destino = forms.ModelChoiceField(
        queryset=Finca.objects.filter(activa=True).order_by('nombre'),
        label="Finca de Entrega *",
        empty_label="Seleccione finca de destino..."
    )
    insumo_id = forms.IntegerField(widget=forms.HiddenInput())
    cantidad = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
        label="Cantidad a Comprar",
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )

