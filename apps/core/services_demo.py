"""
Servicio integral para la siembra y limpieza controlada de datos de demostración
del 1° Trimestre de 2026 (Enero a Marzo 2026) en todos los módulos del ERP Olivícola.
"""

import datetime
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.core.models import Empresa, Finca, CentroDeCosto
from apps.campos.models import Cuadro, RegistroFenologico, EventoCuadro, LoteDeCosecha
from apps.inventario.models import (
    CategoriaInsumo, Insumo, Deposito, StockPorDeposito, MovimientoStock,
    Maquina, MantenimientoMaquina, OrdenDeCompra, ItemOrdenDeCompra,
    RecepcionMercaderia, ItemRecepcion
)
from apps.personal.models import Empleado, RegistroAsistencia
from apps.parte_diario.models import (
    OrdenDeTrabajo, ParteDiario, ParteDiarioPersonal, ParteDiarioInsumo, ParteDiarioRiego
)
from apps.liquidacion.models import PeriodoLiquidacion, LiquidacionEmpleado, ItemLiquidacion
from apps.finanzas.models import (
    CuentaContable, Cuenta, CuentaCorriente, MovimientoFinanciero, Cheque,
    ConciliacionBancaria, CuadroResultado, LineaCuadroResultado, TipoCambioMensual,
    ComprobanteFiscal, ArqueoCaja, OrdenPagoRecibo
)
from apps.finanzas.services import poblar_lineas_cuadro
from apps.costos.models import CostoPorCentro
from django.db import models
from apps.costos.services import resolver_cuenta_contable_defecto, calcular_campana_desde_fecha

User = get_user_model()


@transaction.atomic
def poblar_datos_demo_q1_2026():
    """
    Siembra datos coherentes e interconectados de Enero a Marzo de 2026
    basados en el Plan de Cuentas para todos los módulos del ERP.
    """
    # Limpieza idempotente previa para evitar colisiones
    limpiar_datos_demo_q1_2026()

    stats = {}

    # 1. Empresa base
    empresa = Empresa.objects.first()
    if not empresa:
        empresa = Empresa.objects.create(
            razon_social="Olivar del Valle Agroindustrial S.A.",
            nombre_fantasia="Olivares del Valle",
            cuit="30-71458923-4",
            direccion="Ruta Nacional 60 Km 1140, Aimogasta, La Rioja",
            telefono="+54 3827 421000",
            email="administracion@olivaresdelvalle.com.ar",
            moneda_principal="ARS",
            moneda_secundaria="USD"
        )
    usuario = User.objects.filter(is_superuser=True).first() or User.objects.first()

    # 2. Fincas y Cuadros
    finca_norte, _ = Finca.objects.get_or_create(
        codigo="FINCA-01",
        defaults={
            'empresa': empresa,
            'nombre': "Finca Aimogasta Norte",
            'superficie_total_ha': Decimal("145.50"),
            'ubicacion': "Aimogasta, Dpto. Arauco, La Rioja",
            'tipo_riego_principal': 'GOTEO',
            'activa': True
        }
    )
    finca_sur, _ = Finca.objects.get_or_create(
        codigo="FINCA-02",
        defaults={
            'empresa': empresa,
            'nombre': "Finca Valle Vicioso",
            'superficie_total_ha': Decimal("92.00"),
            'ubicacion': "Valle Central, Pomán, Catamarca",
            'tipo_riego_principal': 'GOTEO',
            'activa': True
        }
    )

    cuadro_a1, _ = Cuadro.objects.get_or_create(
        finca=finca_norte,
        codigo="C-ARAUCO-01",
        defaults={
            'nombre': "Cuadro 1 - Arauco Tradicional",
            'hectareas_netas': Decimal("35.00"),
            'variedad_olivo': Cuadro.VariedadOlivo.ARAUCO,
            'ano_plantacion': 1998,
            'densidad_plantas_ha': 280,
            'marco_plantacion': "6x6 m",
            'sistema_riego': 'GOTEO',
            'estado_fitosanitario': 'Excelente vigor',
            'observaciones': '[DEMO] Aceituna de mesa verde y aceite monovarietal.'
        }
    )
    cuadro_b2, _ = Cuadro.objects.get_or_create(
        finca=finca_norte,
        codigo="C-ARBEQ-02",
        defaults={
            'nombre': "Cuadro 2 - Arbequina Intensiva",
            'hectareas_netas': Decimal("48.50"),
            'variedad_olivo': Cuadro.VariedadOlivo.ARBEQUINA,
            'ano_plantacion': 2015,
            'densidad_plantas_ha': 1200,
            'marco_plantacion': "4x2 m",
            'sistema_riego': 'GOTEO',
            'estado_fitosanitario': 'Óptimo estado vegetativo',
            'observaciones': '[DEMO] Cuadro intensivo para molienda en almazara.'
        }
    )
    cuadro_c3, _ = Cuadro.objects.get_or_create(
        finca=finca_sur,
        codigo="C-PICUAL-01",
        defaults={
            'nombre': "Cuadro Sur - Picual Almazara",
            'hectareas_netas': Decimal("30.00"),
            'variedad_olivo': Cuadro.VariedadOlivo.PICUAL,
            'ano_plantacion': 2018,
            'densidad_plantas_ha': 600,
            'marco_plantacion': "5x3.3 m",
            'sistema_riego': 'GOTEO',
            'estado_fitosanitario': 'Muy bueno',
            'observaciones': '[DEMO] Variedad de alto polifenol y conservación.'
        }
    )

    finca_chi = Finca.objects.filter(models.Q(codigo__icontains="CHILECITO") | models.Q(nombre__icontains="Chilecito")).first()
    if not finca_chi:
        finca_chi, _ = Finca.objects.get_or_create(
            codigo="CHILECITO",
            defaults={
                'empresa': empresa,
                'nombre': "Finca Chilecito",
                'superficie_total_ha': Decimal("65.00"),
                'ubicacion': "Chilecito, La Rioja",
                'tipo_riego_principal': 'GOTEO',
                'activa': True
            }
        )

    cuadro_d4, _ = Cuadro.objects.get_or_create(
        finca=finca_chi,
        codigo="C-MANZ-01",
        defaults={
            'nombre': "Cuadro Chilecito - Manzanilla",
            'hectareas_netas': Decimal("28.00"),
            'variedad_olivo': Cuadro.VariedadOlivo.MANZANILLA,
            'ano_plantacion': 2014,
            'densidad_plantas_ha': 400,
            'marco_plantacion': "6x4 m",
            'sistema_riego': 'GOTEO',
            'estado_fitosanitario': 'Excelente',
            'observaciones': '[DEMO] Aceituna de doble propósito en valle de Chilecito.'
        }
    )

    # 3. Cuentas Contables y Centros de Costo
    cta_fert = CuentaContable.objects.filter(codigo='4.2.1.02.000000').first()
    cta_jornal = CuentaContable.objects.filter(codigo='4.2.1.01.000000').first()
    cta_almazara = CuentaContable.objects.filter(codigo='4.2.2.01.000000').first()
    cta_admin = CuentaContable.objects.filter(codigo='4.2.5.01.000000').first()

    cc_prod_norte, _ = CentroDeCosto.objects.get_or_create(
        codigo="CC-PROD-FNORTE",
        defaults={
            'empresa': empresa,
            'nombre': "Producción Agrícola Finca Norte",
            'tipo': 'PRODUCTIVO_CAMPO',
            'finca': finca_norte,
            'cuenta_contable_defecto': cta_jornal
        }
    )
    cc_prod_sur, _ = CentroDeCosto.objects.get_or_create(
        codigo="CC-PROD-FSUR",
        defaults={
            'empresa': empresa,
            'nombre': "Producción Agrícola Finca Valle Vicioso",
            'tipo': 'PRODUCTIVO_CAMPO',
            'finca': finca_sur,
            'cuenta_contable_defecto': cta_jornal
        }
    )
    cc_prod_chi, _ = CentroDeCosto.objects.get_or_create(
        codigo="CC-PROD-FCHILECITO",
        defaults={
            'empresa': empresa,
            'nombre': "Producción Agrícola Finca Chilecito",
            'tipo': 'PRODUCTIVO_CAMPO',
            'finca': finca_chi,
            'cuenta_contable_defecto': cta_jornal
        }
    )
    cc_almazara, _ = CentroDeCosto.objects.get_or_create(
        codigo="CC-FABRICA-ALMAZARA",
        defaults={
            'empresa': empresa,
            'nombre': "Almazara y Planta de Extracción",
            'tipo': 'FABRICA_ALMAZARA',
            'finca': finca_norte,
            'cuenta_contable_defecto': cta_almazara
        }
    )
    cc_admin, _ = CentroDeCosto.objects.get_or_create(
        codigo="CC-ADM-CENTRAL",
        defaults={
            'empresa': empresa,
            'nombre': "Administración y Comercialización",
            'tipo': 'ESTRUCTURA_ADMIN',
            'cuenta_contable_defecto': cta_admin
        }
    )

    # 4. Insumos y Depósitos (Multidepósito & Plan de Cuentas)
    def _registrar_movimiento(insumo_obj, dep_orig, tipo_mov, cant, costo_u, fecha_dt, motivo_txt, dep_dest=None, ref=""):
        cant = Decimal(str(cant))
        costo_u = Decimal(str(costo_u))
        aware_dt = timezone.make_aware(fecha_dt) if timezone.is_naive(fecha_dt) else fecha_dt
        mov = MovimientoStock.objects.create(
            insumo=insumo_obj,
            deposito=dep_orig,
            deposito_destino=dep_dest,
            tipo=tipo_mov,
            cantidad=cant,
            costo_unitario=costo_u,
            fecha=aware_dt,
            motivo=motivo_txt,
            referencia_origen=ref or "",
            usuario=usuario
        )
        if tipo_mov in [MovimientoStock.TipoMovimiento.ENTRADA_COMPRA, MovimientoStock.TipoMovimiento.AJUSTE_POSITIVO]:
            sp, _ = StockPorDeposito.objects.get_or_create(deposito=dep_orig, insumo=insumo_obj, defaults={'cantidad': Decimal('0.00')})
            sp.cantidad += cant
            sp.save(update_fields=['cantidad'])
        elif tipo_mov in [MovimientoStock.TipoMovimiento.SALIDA_PARTE_DIARIO, MovimientoStock.TipoMovimiento.SALIDA_MERMA, MovimientoStock.TipoMovimiento.AJUSTE_NEGATIVO]:
            sp, _ = StockPorDeposito.objects.get_or_create(deposito=dep_orig, insumo=insumo_obj, defaults={'cantidad': Decimal('0.00')})
            sp.cantidad -= cant
            sp.save(update_fields=['cantidad'])
        elif tipo_mov == MovimientoStock.TipoMovimiento.TRANSFERENCIA and dep_dest:
            sp_orig, _ = StockPorDeposito.objects.get_or_create(deposito=dep_orig, insumo=insumo_obj, defaults={'cantidad': Decimal('0.00')})
            sp_orig.cantidad -= cant
            sp_orig.save(update_fields=['cantidad'])
            sp_dest, _ = StockPorDeposito.objects.get_or_create(deposito=dep_dest, insumo=insumo_obj, defaults={'cantidad': Decimal('0.00')})
            sp_dest.cantidad += cant
            sp_dest.save(update_fields=['cantidad'])
        return mov

    dep_central, _ = Deposito.objects.get_or_create(
        codigo="DEP-FNORTE-01",
        defaults={
            'finca': finca_norte,
            'nombre': "Depósito Central Insumos y Fertilizantes",
            'es_deposito_central': True
        }
    )
    dep_sur, _ = Deposito.objects.get_or_create(
        codigo="DEP-FSUR-01",
        defaults={
            'finca': finca_sur,
            'nombre': "Galpón Tinglado Sur",
            'es_deposito_central': False
        }
    )

    # Cuentas Contables del Rubro 1.1.5 (Bienes de Cambio) y 4.2.1 (Costos Agrícolas)
    cta_fert_act = CuentaContable.objects.filter(codigo='1.1.5.01.000001').first()
    cta_herb_act = CuentaContable.objects.filter(codigo='1.1.5.01.000002').first()
    cta_fung_act = CuentaContable.objects.filter(codigo='1.1.5.01.000003').first()
    cta_riego_act = CuentaContable.objects.filter(codigo='1.1.5.01.000004').first()
    cta_agro_act = CuentaContable.objects.filter(codigo='1.1.5.01.000000').first()
    cta_bot_act = CuentaContable.objects.filter(codigo='1.1.5.05.000001').first()
    cta_tap_act = CuentaContable.objects.filter(codigo='1.1.5.05.000003').first()
    cta_emb_act = CuentaContable.objects.filter(codigo='1.1.5.05.000005').first()
    cta_gasto_agro = CuentaContable.objects.filter(codigo='4.2.1.02.000000').first()
    cta_gasto_gral = CuentaContable.objects.filter(codigo='4.2.1.00.000000').first()

    cat_fert, _ = CategoriaInsumo.objects.get_or_create(
        nombre="Fertilizantes y Nutrición",
        defaults={'cuenta_contable_activo': cta_fert_act, 'cuenta_contable_gasto': cta_gasto_agro, 'descripcion': "Fertilizantes hidrosolubles y granulados para fertirriego y suelo"}
    )
    cat_quim, _ = CategoriaInsumo.objects.get_or_create(
        nombre="Fitosanitarios y Curas",
        defaults={'cuenta_contable_activo': cta_fung_act, 'cuenta_contable_gasto': cta_gasto_agro, 'descripcion': "Fungicidas, bactericidas e insecticidas para control fitosanitario"}
    )
    cat_herb, _ = CategoriaInsumo.objects.get_or_create(
        nombre="Herbicidas y Manejo de Suelo",
        defaults={'cuenta_contable_activo': cta_herb_act, 'cuenta_contable_gasto': cta_gasto_agro, 'descripcion': "Herbicidas sistémicos y residuales"}
    )
    cat_comb, _ = CategoriaInsumo.objects.get_or_create(
        nombre="Combustibles y Lubricantes",
        defaults={'cuenta_contable_activo': cta_agro_act, 'cuenta_contable_gasto': cta_gasto_gral, 'descripcion': "Gasoil agro y aceites para tractores y bombas"}
    )
    cat_env, _ = CategoriaInsumo.objects.get_or_create(
        nombre="Envases y Botellas de Vidrio",
        defaults={'cuenta_contable_activo': cta_bot_act, 'cuenta_contable_gasto': cta_gasto_gral, 'descripcion': "Botellas cónicas para fraccionado"}
    )
    cat_cierres, _ = CategoriaInsumo.objects.get_or_create(
        nombre="Tapas y Cierres D.O.P.",
        defaults={'cuenta_contable_activo': cta_tap_act, 'cuenta_contable_gasto': cta_gasto_gral, 'descripcion': "Tapas irrellenables con pico vertedor"}
    )
    cat_embalaje, _ = CategoriaInsumo.objects.get_or_create(
        nombre="Cajas y Bins de Cosecha",
        defaults={'cuenta_contable_activo': cta_emb_act, 'cuenta_contable_gasto': cta_gasto_gral, 'descripcion': "Cajas de cartón corrugado y bins de cosecha"}
    )
    cat_riego, _ = CategoriaInsumo.objects.get_or_create(
        nombre="Insumos y Repuestos de Riego",
        defaults={'cuenta_contable_activo': cta_riego_act, 'cuenta_contable_gasto': cta_gasto_agro, 'descripcion': "Goteros autocompensantes y repuestos de riego"}
    )

    insumos_data = [
        ('INS-UREA-01', "Urea Granulada 46% N Soluble", cat_fert, cta_fert_act, Insumo.UnidadMedida.KILOS, Decimal("2000.00"), Decimal("850.00"), Decimal("0.81")),
        ('INS-NITRATO-01', "Nitrato de Potasio Fertirriego 13-0-45", cat_fert, cta_fert_act, Insumo.UnidadMedida.KILOS, Decimal("1500.00"), Decimal("1650.00"), Decimal("1.57")),
        ('INS-COBRE-01', "Oxicloruro de Cobre 50% WP (Repilo)", cat_quim, cta_fung_act, Insumo.UnidadMedida.KILOS, Decimal("150.00"), Decimal("14500.00"), Decimal("13.80")),
        ('INS-GLIFO-01', "Glifosato 48% SL Control Malezas", cat_herb, cta_herb_act, Insumo.UnidadMedida.LITROS, Decimal("100.00"), Decimal("9200.00"), Decimal("8.76")),
        ('INS-GASOIL-01', "Gasoil Grado 2 Agro (Tractores)", cat_comb, cta_agro_act, Insumo.UnidadMedida.LITROS, Decimal("1500.00"), Decimal("1120.00"), Decimal("1.07")),
        ('INS-BOT-500', "Botella Vidrio UVAG 500ml Cónica", cat_env, cta_bot_act, Insumo.UnidadMedida.UNIDADES, Decimal("5000.00"), Decimal("580.00"), Decimal("0.55")),
        ('INS-TAPAS-01', "Tapa Irrellenable D.O.P. Verde Olivo", cat_cierres, cta_tap_act, Insumo.UnidadMedida.UNIDADES, Decimal("5000.00"), Decimal("190.00"), Decimal("0.18")),
        ('INS-CAJAS-12', "Cajas Cartón Corrugado x 12 Botellas", cat_embalaje, cta_emb_act, Insumo.UnidadMedida.UNIDADES, Decimal("500.00"), Decimal("1250.00"), Decimal("1.19")),
        ('INS-BINS-01', "Bins Plásticos Ventilados 400kg Cosecha", cat_embalaje, cta_emb_act, Insumo.UnidadMedida.UNIDADES, Decimal("50.00"), Decimal("95000.00"), Decimal("90.47")),
        ('INS-GOTERO-01', "Goteros Autocompensantes 2.2 L/h Netafim", cat_riego, cta_riego_act, Insumo.UnidadMedida.UNIDADES, Decimal("1000.00"), Decimal("120.00"), Decimal("0.11")),
    ]
    insumos = {}
    for cod, nom, cat, cta, um, st_min, c_ars, c_usd in insumos_data:
        ins, _ = Insumo.objects.update_or_create(
            codigo=cod,
            defaults={
                'nombre': nom,
                'categoria': cat,
                'cuenta_contable': cta,
                'unidad_medida': um,
                'stock_actual': Decimal('0.00'),
                'stock_minimo': st_min,
                'costo_unitario_ars': c_ars,
                'costo_unitario_usd': c_usd,
                'activo': True
            }
        )
        insumos[cod] = ins

    # Stock Inicial de Apertura de Campaña (02/01/2026) en ambos depósitos
    stock_inicial_central = [
        ('INS-UREA-01', Decimal("10000.00"), Decimal("850.00")),
        ('INS-NITRATO-01', Decimal("7000.00"), Decimal("1650.00")),
        ('INS-COBRE-01', Decimal("700.00"), Decimal("14500.00")),
        ('INS-GLIFO-01', Decimal("400.00"), Decimal("9200.00")),
        ('INS-GASOIL-01', Decimal("3000.00"), Decimal("1120.00")),
        ('INS-BOT-500', Decimal("15000.00"), Decimal("580.00")),
        ('INS-TAPAS-01', Decimal("22000.00"), Decimal("190.00")),
        ('INS-CAJAS-12', Decimal("1500.00"), Decimal("1250.00")),
        ('INS-BINS-01', Decimal("350.00"), Decimal("95000.00")),
        ('INS-GOTERO-01', Decimal("5000.00"), Decimal("120.00")),
    ]
    for cod, cant, c_u in stock_inicial_central:
        _registrar_movimiento(
            insumos[cod], dep_central, MovimientoStock.TipoMovimiento.AJUSTE_POSITIVO,
            cant, c_u, datetime.datetime(2026, 1, 2, 8, 0),
            "[DEMO] Inventario inicial apertura campaña 2026 - Depósito Central", ref="INI-20260102-1"
        )

    stock_inicial_sur = [
        ('INS-GASOIL-01', Decimal("1000.00"), Decimal("1120.00")),
        ('INS-BINS-01', Decimal("50.00"), Decimal("95000.00")),
    ]
    for cod, cant, c_u in stock_inicial_sur:
        _registrar_movimiento(
            insumos[cod], dep_sur, MovimientoStock.TipoMovimiento.AJUSTE_POSITIVO,
            cant, c_u, datetime.datetime(2026, 1, 2, 8, 30),
            "[DEMO] Inventario inicial apertura campaña 2026 - Galpón Tinglado Sur", ref="INI-20260102-2"
        )

    # 5. Maquinaria
    maq_tractor, _ = Maquina.objects.get_or_create(
        codigo="MAQ-TRAC-01",
        defaults={
            'nombre': "Tractor John Deere 5075E 4WD",
            'tipo': Maquina.TipoMaquina.TRACTOR,
            'marca': "John Deere",
            'modelo': "5075E",
            'ano_fabricacion': 2021,
            'horas_o_km_acumulados': Decimal("1840.5"),
            'finca_asignada': finca_norte,
            'estado': Maquina.EstadoMaquina.OPERATIVA,
            'fecha_ultimo_service': datetime.date(2026, 2, 10)
        }
    )
    maq_atomizadora, _ = Maquina.objects.get_or_create(
        codigo="MAQ-ATOM-01",
        defaults={
            'nombre': "Atomizadora Pulverizadora Caiman 2000L",
            'tipo': Maquina.TipoMaquina.ATOMIZADORA,
            'marca': "Caiman",
            'modelo': "Trail 2000",
            'ano_fabricacion': 2022,
            'horas_o_km_acumulados': Decimal("720.0"),
            'finca_asignada': finca_norte,
            'estado': Maquina.EstadoMaquina.OPERATIVA,
            'fecha_ultimo_service': datetime.date(2026, 2, 14)
        }
    )

    # 6. Personal y Empleados
    personal_data = [
        ('LEG-001', "Carlos Alberto", "Gómez", "20-28345912-4", Empleado.RolLaboral.CAPATAZ_FINCA, Decimal("42000.00"), Decimal("7875.00")),
        ('LEG-002', "Juan Ramón", "Pérez", "20-31845120-7", Empleado.RolLaboral.TRACTORISTA, Decimal("35000.00"), Decimal("6562.50")),
        ('LEG-003', "Miguel Ángel", "Vega", "20-33984125-9", Empleado.RolLaboral.REGADOR, Decimal("32000.00"), Decimal("6000.00")),
        ('LEG-004', "Roberto", "Carrizo", "20-29456781-3", Empleado.RolLaboral.PODADOR, Decimal("34000.00"), Decimal("6375.00")),
        ('LEG-005', "Eduardo", "Quinteros", "20-35678912-1", Empleado.RolLaboral.OPERARIO_ALMAZARA, Decimal("36000.00"), Decimal("6750.00")),
        ('LEG-006', "Luciano", "Bazán", "20-36789014-5", Empleado.RolLaboral.PEON_GENERAL, Decimal("29500.00"), Decimal("5531.25")),
        ('LEG-007', "Santos", "Luna", "20-38901234-8", Empleado.RolLaboral.COSECHERO, Decimal("31000.00"), Decimal("5812.50")),
        ('LEG-008', "Ramiro", "Nievas", "20-39456123-0", Empleado.RolLaboral.COSECHERO, Decimal("31000.00"), Decimal("5812.50")),
    ]
    empleados = {}
    for leg, nom, ape, dni, rol, val_j, val_he in personal_data:
        emp_obj, _ = Empleado.objects.get_or_create(
            legajo=leg,
            defaults={
                'nombre': nom,
                'apellido': ape,
                'dni_cuil': dni,
                'rol_laboral': rol,
                'modalidad': Empleado.ModalidadContratacion.JORNAL_RURAL,
                'finca_habitual': finca_norte,
                'valor_jornal_base_ars': val_j,
                'valor_hora_extra_ars': val_he,
                'fecha_ingreso': datetime.date(2023, 3, 1),
                'telefono': "+54 3827 491234",
                'activo': True
            }
        )
        empleados[leg] = emp_obj

    # 7. Cuentas Financieras y Cuentas Corrientes
    cta_banco_ars, _ = Cuenta.objects.get_or_create(
        nombre="Banco Galicia CC Operativa ARS",
        defaults={
            'empresa': empresa,
            'tipo': Cuenta.TipoCuenta.CUENTA_BANCARIA,
            'moneda': Cuenta.Moneda.ARS,
            'banco_nombre': "Banco Galicia",
            'numero_cuenta': "009-000012345/6",
            'cbu_cvu': "0070009220000012345601",
            'saldo_actual': Decimal("70814400.00")
        }
    )
    cta_banco_ars.saldo_actual = Decimal("70814400.00")
    cta_banco_ars.save(update_fields=['saldo_actual'])

    cta_banco_usd, _ = Cuenta.objects.get_or_create(
        nombre="Banco Santander CC Exportacion USD",
        defaults={
            'empresa': empresa,
            'tipo': Cuenta.TipoCuenta.CUENTA_BANCARIA,
            'moneda': Cuenta.Moneda.USD,
            'banco_nombre': "Banco Santander",
            'numero_cuenta': "072-000098765/4",
            'cbu_cvu': "0720072120000009876542",
            'saldo_actual': Decimal("142500.00")
        }
    )
    cta_banco_usd.saldo_actual = Decimal("142500.00")
    cta_banco_usd.save(update_fields=['saldo_actual'])

    caja_finca, _ = Cuenta.objects.get_or_create(
        nombre="Caja Chica Finca Aimogasta",
        defaults={
            'empresa': empresa,
            'tipo': Cuenta.TipoCuenta.CAJA_EFECTIVO,
            'moneda': Cuenta.Moneda.ARS,
            'saldo_actual': Decimal("1850000.00")
        }
    )
    caja_finca.saldo_actual = Decimal("1850000.00")
    caja_finca.save(update_fields=['saldo_actual'])

    caja_admin, _ = Cuenta.objects.get_or_create(
        nombre="Caja Administración Central",
        defaults={
            'empresa': empresa,
            'tipo': Cuenta.TipoCuenta.CAJA_EFECTIVO,
            'moneda': Cuenta.Moneda.ARS,
            'saldo_actual': Decimal("650000.00")
        }
    )
    caja_admin.saldo_actual = Decimal("650000.00")
    caja_admin.save(update_fields=['saldo_actual'])

    # Proveedores de Insumos y Servicios Agrícolas
    prov_agroquimica, _ = CuentaCorriente.objects.update_or_create(
        cuit="30-71234567-0",
        defaults={
            'tipo_entidad': CuentaCorriente.TipoEntidad.PROVEEDOR,
            'razon_social': "Agroquímica Cuyo & Cía S.A.",
            'nombre_comercial': "AgroQuím Cuyo",
            'email': "ventas@agroquimicacuyo.com.ar",
            'telefono': "+54 261 4981200",
            'direccion': "Acceso Sur Km 14, Luján de Cuyo, Mendoza",
            'saldo_actual': Decimal("-9957800.00"),
            'activo': True
        }
    )
    prov_ypf, _ = CuentaCorriente.objects.update_or_create(
        cuit="30-54668997-1",
        defaults={
            'tipo_entidad': CuentaCorriente.TipoEntidad.PROVEEDOR,
            'razon_social': "YPF Directo Agro La Rioja S.A.",
            'nombre_comercial': "YPF Directo",
            'email': "agro.larioja@redypf.com.ar",
            'telefono': "+54 380 4429900",
            'direccion': "Ruta 38 Km 432, Parque Industrial La Rioja",
            'saldo_actual': Decimal("-5132000.00"),
            'activo': True
        }
    )
    prov_edelar, _ = CuentaCorriente.objects.update_or_create(
        cuit="30-67891234-9",
        defaults={
            'tipo_entidad': CuentaCorriente.TipoEntidad.PROVEEDOR,
            'razon_social': "EDELAR S.A.",
            'nombre_comercial': "EDELAR Distribuidora Eléctrica",
            'email': "grandesclientes@edelar.com.ar",
            'telefono': "+54 380 4468000",
            'direccion': "San Nicolás de Bari 520, La Rioja",
            'saldo_actual': Decimal("-1244600.00"),
            'activo': True
        }
    )
    prov_edecat, _ = CuentaCorriente.objects.update_or_create(
        cuit="30-69123456-7",
        defaults={
            'tipo_entidad': CuentaCorriente.TipoEntidad.PROVEEDOR,
            'razon_social': "Energía Catamarca SAPEM",
            'nombre_comercial': "EC SAPEM Catamarca",
            'email': "facturacion@ecsapem.com.ar",
            'telefono': "+54 383 4458000",
            'direccion': "Av. Ocampo 890, San Fernando del Valle de Catamarca",
            'saldo_actual': Decimal("0.00"),
            'activo': True
        }
    )
    prov_taller, _ = CuentaCorriente.objects.update_or_create(
        cuit="30-65432198-7",
        defaults={
            'tipo_entidad': CuentaCorriente.TipoEntidad.PROVEEDOR,
            'razon_social': "Taller Metalúrgico e Hidráulica Aimogasta",
            'nombre_comercial': "Taller Aimogasta",
            'email': "taller.aimogasta@gmail.com",
            'telefono': "+54 3827 421500",
            'direccion': "Av. San Francisco 120, Aimogasta, La Rioja",
            'saldo_actual': Decimal("0.00"),
            'activo': True
        }
    )
    prov_envases, _ = CuentaCorriente.objects.update_or_create(
        cuit="30-68901234-5",
        defaults={
            'tipo_entidad': CuentaCorriente.TipoEntidad.PROVEEDOR,
            'razon_social': "Envases y Cristales Cuyanos S.A.",
            'nombre_comercial': "Envases Cuyanos",
            'email': "contacto@envasescuyanos.com.ar",
            'telefono': "+54 264 4238000",
            'direccion': "Parque Industrial San Juan",
            'saldo_actual': Decimal("-6495000.00"),
            'activo': True
        }
    )
    prov_contratista, _ = CuentaCorriente.objects.update_or_create(
        cuit="30-71987654-3",
        defaults={
            'tipo_entidad': CuentaCorriente.TipoEntidad.PROVEEDOR,
            'razon_social': "Servicios Agro-Mecánicos del Valle S.R.L.",
            'nombre_comercial': "Agro-Mecánicos Valle",
            'email': "servicios@agromecanicosvalle.com.ar",
            'telefono': "+54 3827 493000",
            'direccion': "Ruta 60 Km 1135, Aimogasta",
            'saldo_actual': Decimal("0.00"),
            'activo': True
        }
    )

    # Clientes Mayoristas y de Exportación
    cli_gourmet, _ = CuentaCorriente.objects.update_or_create(
        cuit="30-70891234-5",
        defaults={
            'tipo_entidad': CuentaCorriente.TipoEntidad.CLIENTE,
            'razon_social': "Aceitunas Riojanas Gourmet S.A.",
            'nombre_comercial': "Riojanas Gourmet",
            'email': "compras@riojanasgourmet.com.ar",
            'telefono': "+54 380 4431200",
            'direccion': "Ruta 38 Km 440, Parque Industrial La Rioja",
            'saldo_actual': Decimal("16300000.00"),
            'activo': True
        }
    )
    cli_local, _ = CuentaCorriente.objects.update_or_create(
        cuit="30-55443322-1",
        defaults={
            'tipo_entidad': CuentaCorriente.TipoEntidad.CLIENTE,
            'razon_social': "Aceites del Sol Mayorista S.A.",
            'nombre_comercial': "Aceites del Sol",
            'email': "adquisiciones@aceitesdelsol.com.ar",
            'telefono': "+54 11 48903300",
            'direccion': "Av. Belgrano 1450, CABA",
            'saldo_actual': Decimal("29093600.00"),
            'activo': True
        }
    )
    cli_exterior, _ = CuentaCorriente.objects.update_or_create(
        cuit="30-99876543-2",
        defaults={
            'tipo_entidad': CuentaCorriente.TipoEntidad.CLIENTE,
            'razon_social': "Mediterráneo Trading Imports LLC / Suc. Arg.",
            'nombre_comercial': "Mediterráneo Trading",
            'email': "imports@mediterraneantrading.com",
            'telefono': "+1 305 8901234",
            'direccion': "Brickell Ave 1200, Miami, FL, USA",
            'saldo_actual': Decimal("117700000.00"),
            'activo': True
        }
    )

    # ═════════════════════════════════════════════════════════════════════════
    # ENERO 2026: DEMANDA HÍDRICA, FERTIRRIEGO Y COMPRAS DE CAMPAÑA
    # ═════════════════════════════════════════════════════════════════════════

    # Fenología Enero
    for c in [cuadro_a1, cuadro_b2, cuadro_c3]:
        RegistroFenologico.objects.get_or_create(
            cuadro=c,
            campana="2025/2026",
            fecha=datetime.date(2026, 1, 15),
            defaults={
                'fase_vegetativa': RegistroFenologico.FaseVegetativa.CRECIMIENTO,
                'grados_dia_acumulados': Decimal("1420.5"),
                'temperatura_min': Decimal("18.5"),
                'temperatura_max': Decimal("37.2"),
                'riesgo_fitosanitario': RegistroFenologico.RiesgoFitosanitario.BAJO,
                'observaciones': '[DEMO] Fruto en crecimiento activo y endurecimiento de carozo. Buena respuesta a fertirriego.',
                'responsable': usuario
            }
        )

    # Eventos de Cuadro Enero
    EventoCuadro.objects.get_or_create(
        cuadro=cuadro_b2,
        campana="2025/2026",
        fecha=datetime.date(2026, 1, 10),
        tipo_evento=EventoCuadro.TipoEvento.FERTILIZACION,
        defaults={
            'descripcion': '[DEMO] Inyección de Urea y Nitrato de Potasio en sector de riego 1 y 2.',
            'responsable': usuario
        }
    )

    # Órdenes de Compra y Recepciones Enero
    oc_fert = OrdenDeCompra.objects.create(
        proveedor=prov_agroquimica,
        finca_destino=finca_norte,
        numero="OC-2026-001",
        fecha_emision=datetime.date(2026, 1, 8),
        fecha_entrega_estimada=datetime.date(2026, 1, 12),
        estado=OrdenDeCompra.Estado.RECIBIDA,
        observaciones="[DEMO] Adquisición de fertilizantes solubles para campaña estival de fertirriego."
    )
    ItemOrdenDeCompra.objects.create(orden=oc_fert, insumo=insumos['INS-UREA-01'], cantidad_solicitada=Decimal("3000.00"), precio_unitario_estimado_ars=Decimal("850.00"))
    ItemOrdenDeCompra.objects.create(orden=oc_fert, insumo=insumos['INS-NITRATO-01'], cantidad_solicitada=Decimal("1500.00"), precio_unitario_estimado_ars=Decimal("1650.00"))
    oc_fert.recalcular_total()

    rec_fert = RecepcionMercaderia.objects.create(
        orden=oc_fert,
        deposito_destino=dep_central,
        fecha_recepcion=datetime.date(2026, 1, 12),
        numero_remito_proveedor="R-0004-00129841",
        numero_factura_proveedor="FC-A-0004-00054129",
        estado=RecepcionMercaderia.Estado.CONFIRMADA,
        total_real_ars=oc_fert.total_estimado_ars,
        observaciones="[DEMO] Recepción conforme de fertilizantes en nave central."
    )
    mov_u_ene = _registrar_movimiento(insumos['INS-UREA-01'], dep_central, MovimientoStock.TipoMovimiento.ENTRADA_COMPRA, Decimal("3000.00"), Decimal("850.00"), datetime.datetime(2026, 1, 12, 10, 0), "[DEMO] Recepción OC OC-2026-001 remito R-0004-00129841", ref="OC-2026-001")
    mov_n_ene = _registrar_movimiento(insumos['INS-NITRATO-01'], dep_central, MovimientoStock.TipoMovimiento.ENTRADA_COMPRA, Decimal("1500.00"), Decimal("1650.00"), datetime.datetime(2026, 1, 12, 10, 0), "[DEMO] Recepción OC OC-2026-001 remito R-0004-00129841", ref="OC-2026-001")
    ItemRecepcion.objects.create(recepcion=rec_fert, insumo=insumos['INS-UREA-01'], cantidad_en_oc=Decimal("3000.00"), cantidad_recibida=Decimal("3000.00"), precio_unitario_real_ars=Decimal("850.00"), movimiento_stock=mov_u_ene)
    ItemRecepcion.objects.create(recepcion=rec_fert, insumo=insumos['INS-NITRATO-01'], cantidad_en_oc=Decimal("1500.00"), cantidad_recibida=Decimal("1500.00"), precio_unitario_real_ars=Decimal("1650.00"), movimiento_stock=mov_n_ene)

    # OC Combustible Enero y Recepción
    oc_comb = OrdenDeCompra.objects.create(
        proveedor=prov_ypf,
        finca_destino=finca_norte,
        numero="OC-2026-002",
        fecha_emision=datetime.date(2026, 1, 14),
        fecha_entrega_estimada=datetime.date(2026, 1, 16),
        estado=OrdenDeCompra.Estado.RECIBIDA,
        observaciones="[DEMO] Gasoil Grado 2 para tractores y grupos electrógenos de bombeo."
    )
    ItemOrdenDeCompra.objects.create(orden=oc_comb, insumo=insumos['INS-GASOIL-01'], cantidad_solicitada=Decimal("5000.00"), precio_unitario_estimado_ars=Decimal("1120.00"))
    oc_comb.recalcular_total()

    rec_comb = RecepcionMercaderia.objects.create(
        orden=oc_comb,
        deposito_destino=dep_central,
        fecha_recepcion=datetime.date(2026, 1, 16),
        numero_remito_proveedor="R-0001-00094120",
        numero_factura_proveedor="FC-A-0001-00031890",
        estado=RecepcionMercaderia.Estado.CONFIRMADA,
        total_real_ars=oc_comb.total_estimado_ars,
        observaciones="[DEMO] Descarga de combustible cisterna YPF en tanques nave central."
    )
    mov_g_ene = _registrar_movimiento(insumos['INS-GASOIL-01'], dep_central, MovimientoStock.TipoMovimiento.ENTRADA_COMPRA, Decimal("5000.00"), Decimal("1120.00"), datetime.datetime(2026, 1, 16, 11, 30), "[DEMO] Recepción cisterna YPF remito R-0001-00094120", ref="OC-2026-002")
    ItemRecepcion.objects.create(recepcion=rec_comb, insumo=insumos['INS-GASOIL-01'], cantidad_en_oc=Decimal("5000.00"), cantidad_recibida=Decimal("5000.00"), precio_unitario_real_ars=Decimal("1120.00"), movimiento_stock=mov_g_ene)

    # Transferencia Inter-depósito Enero (14/01/2026)
    _registrar_movimiento(insumos['INS-GASOIL-01'], dep_central, MovimientoStock.TipoMovimiento.TRANSFERENCIA, Decimal("1000.00"), Decimal("1120.00"), datetime.datetime(2026, 1, 14, 15, 0), "[DEMO] Traslado de gasoil para bombas de riego Finca Sur", dep_dest=dep_sur, ref="TRF-20260114")

    # Partes Diarios Enero (Riego por goteo & Fertirriego)
    ot_riego_ene = OrdenDeTrabajo.objects.create(
        cuadro=cuadro_b2,
        tipo_labor=OrdenDeTrabajo.TipoLabor.FERTIRRIEGO,
        fecha_programada=datetime.date(2026, 1, 18),
        responsable=usuario,
        estado=OrdenDeTrabajo.Estado.FINALIZADA,
        instrucciones_tecnicas="[DEMO] Inyección de 150 kg de nitrato de potasio durante 8 horas de riego nocturno."
    )
    pd_riego_ene = ParteDiario.objects.create(
        finca=finca_norte,
        cuadro=cuadro_b2,
        fecha=datetime.date(2026, 1, 18),
        supervisor=usuario,
        estado=ParteDiario.Estado.CONFIRMADO_CERRADO,
        observaciones="[DEMO] Turno de fertirriego completado sin anomalías de presión."
    )
    ParteDiarioRiego.objects.create(
        parte_diario=pd_riego_ene,
        tipo_agua=ParteDiarioRiego.TipoAgua.POZO,
        horas_bomba=Decimal("8.0"),
        caudal_m3_hora=Decimal("120.00"),
        conductividad_electrica=Decimal("850.00"),
        temperatura_agua=Decimal("21.5"),
        observaciones_riego="[DEMO] Pozo N° 2 trabajando con presión de cabezal 3.2 bar."
    )
    ParteDiarioPersonal.objects.create(
        parte_diario=pd_riego_ene,
        empleado=empleados['LEG-003'],
        horas_normales=Decimal("8.0"),
        costo_jornal_calculado_ars=Decimal("32000.00"),
        tarea_especifica="Operación cabezal y monitoreo goteros"
    )
    mov_fert = _registrar_movimiento(insumos['INS-NITRATO-01'], dep_central, MovimientoStock.TipoMovimiento.SALIDA_PARTE_DIARIO, Decimal("150.00"), Decimal("1650.00"), datetime.datetime(2026, 1, 18, 10, 0), "[DEMO] Fertirriego en Cuadro 2 Arbequina")
    ParteDiarioInsumo.objects.create(
        parte_diario=pd_riego_ene,
        insumo=insumos['INS-NITRATO-01'],
        deposito_origen=dep_central,
        cantidad_utilizada=Decimal("150.00"),
        dosis_por_hectarea="3.1 kg/ha",
        costo_unitario_aplicado_ars=Decimal("1650.00"),
        costo_total_ars=Decimal("247500.00"),
        movimiento_stock_generado=mov_fert
    )

    # Parte Diario Laboreo de Suelo Enero (22/01/2026)
    ot_laboreo = OrdenDeTrabajo.objects.create(
        cuadro=cuadro_a1,
        tipo_labor=OrdenDeTrabajo.TipoLabor.LABOR_SUELO,
        fecha_programada=datetime.date(2026, 1, 22),
        responsable=usuario,
        estado=OrdenDeTrabajo.Estado.FINALIZADA,
        instrucciones_tecnicas="[DEMO] Desmalezado mecánico y pasada de rastra de discos entre hileras."
    )
    pd_laboreo = ParteDiario.objects.create(
        finca=finca_norte,
        cuadro=cuadro_a1,
        fecha=datetime.date(2026, 1, 22),
        supervisor=usuario,
        estado=ParteDiario.Estado.CONFIRMADO_CERRADO,
        observaciones="[DEMO] Pasada de rastra en 35 ha completada con Tractor John Deere."
    )
    ParteDiarioPersonal.objects.create(
        parte_diario=pd_laboreo,
        empleado=empleados['LEG-002'],
        horas_normales=Decimal("8.0"),
        costo_jornal_calculado_ars=Decimal("35000.00"),
        tarea_especifica="Tractorista con rastra de discos"
    )
    mov_gasoil_ene = _registrar_movimiento(insumos['INS-GASOIL-01'], dep_central, MovimientoStock.TipoMovimiento.SALIDA_PARTE_DIARIO, Decimal("350.00"), Decimal("1120.00"), datetime.datetime(2026, 1, 22, 16, 0), "[DEMO] Consumo gasoil laboreo y rastra Cuadro Arauco")
    ParteDiarioInsumo.objects.create(
        parte_diario=pd_laboreo,
        insumo=insumos['INS-GASOIL-01'],
        deposito_origen=dep_central,
        cantidad_utilizada=Decimal("350.00"),
        dosis_por_hectarea="10.0 L/ha",
        costo_unitario_aplicado_ars=Decimal("1120.00"),
        costo_total_ars=Decimal("392000.00"),
        movimiento_stock_generado=mov_gasoil_ene
    )

    # Ajuste Físico de Fin de Mes Enero (30/01/2026)
    _registrar_movimiento(insumos['INS-UREA-01'], dep_central, MovimientoStock.TipoMovimiento.AJUSTE_POSITIVO, Decimal("20.00"), Decimal("850.00"), datetime.datetime(2026, 1, 30, 17, 0), "[DEMO] Ajuste de inventario físico mensual - sobrante balanza", ref="AJU-20260130")

    # Asistencia Diaria Enero (muestra representativa de días clave)
    dias_ene = [datetime.date(2026, 1, d) for d in range(5, 31, 2) if datetime.date(2026, 1, d).weekday() < 6]
    for d in dias_ene:
        for leg, emp in list(empleados.items())[:6]:
            RegistroAsistencia.objects.get_or_create(
                empleado=emp,
                fecha=d,
                defaults={
                    'finca': finca_norte,
                    'estado': RegistroAsistencia.Estado.PRESENTE,
                    'horas_normales': Decimal("8.0"),
                    'horas_extras': Decimal("0.0"),
                    'jornal_computado': Decimal("1.00"),
                    'observaciones': '[DEMO] Jornada normal de campo'
                }
            )

    # Liquidación Enero 2026
    periodo_ene, _ = PeriodoLiquidacion.objects.get_or_create(
        mes=1,
        ano=2026,
        tipo=PeriodoLiquidacion.TipoPeriodo.MENSUAL,
        defaults={
            'fecha_inicio': datetime.date(2026, 1, 1),
            'fecha_fin': datetime.date(2026, 1, 31),
            'estado': PeriodoLiquidacion.Estado.CERRADO,
            'observaciones': '[DEMO] Haberes mensuales UATRE Enero 2026'
        }
    )
    for leg, emp in list(empleados.items())[:6]:
        bruto = emp.valor_jornal_base_ars * Decimal("24")
        ret = bruto * Decimal("0.185")  # 18.5% descuentos
        neto = bruto - ret
        liq, _ = LiquidacionEmpleado.objects.get_or_create(
            periodo=periodo_ene,
            empleado=emp,
            defaults={
                'dias_jornales_computados': Decimal("24.00"),
                'horas_normales': Decimal("192.0"),
                'total_bruto_remunerativo_ars': bruto,
                'total_retenciones_ars': ret,
                'neto_a_cobrar_ars': neto,
                'estado': LiquidacionEmpleado.Estado.PAGADO
            }
        )
        ItemLiquidacion.objects.get_or_create(liquidacion=liq, codigo_concepto="101", defaults={'descripcion': "Básico Mensual Jornal Rural", 'tipo': ItemLiquidacion.TipoConcepto.REMUNERATIVO, 'importe_ars': bruto})
        ItemLiquidacion.objects.get_or_create(liquidacion=liq, codigo_concepto="501", defaults={'descripcion': "Aportes Jubilación y Ley 19032 (14%)", 'tipo': ItemLiquidacion.TipoConcepto.RETENCION, 'importe_ars': bruto * Decimal("0.14")})
        ItemLiquidacion.objects.get_or_create(liquidacion=liq, codigo_concepto="502", defaults={'descripcion': "Obra Social OSPRERA (3%)", 'tipo': ItemLiquidacion.TipoConcepto.RETENCION, 'importe_ars': bruto * Decimal("0.03")})

    # Comprobantes Fiscales Enero 2026 (Facturas de Compra)
    fact_agroquimica_ene, _ = ComprobanteFiscal.objects.update_or_create(
        tipo_operacion=ComprobanteFiscal.TipoOperacion.COMPRA,
        tipo_comprobante=ComprobanteFiscal.TipoComprobante.FACTURA_A,
        punto_de_venta="00004",
        numero_comprobante="00054129",
        cuit="30-71234567-0",
        defaults={
            'cuenta_corriente': prov_agroquimica,
            'razon_social': "Agroquímica Cuyo & Cía S.A.",
            'condicion_iva': ComprobanteFiscal.CondicionIVA.RESPONSABLE_INSCRIPTO,
            'fecha_emision': datetime.date(2026, 1, 12),
            'fecha_vencimiento': datetime.date(2026, 2, 12),
            'concepto': "[DEMO] Factura A Fertilizantes Solubles (Urea 46% y Nitrato de Potasio 13-0-45)",
            'neto_gravado_21': Decimal("5025000.00"),
            'iva_21': Decimal("1055250.00"),
            'percepcion_iibb': Decimal("150750.00"),
            'total': Decimal("6231000.00"),
            'estado_pago': ComprobanteFiscal.EstadoPago.PAGADA,
            'saldo_pendiente': Decimal("0.00"),
            'cae': "74011294821034",
            'vto_cae': datetime.date(2026, 1, 22),
            'es_oficial': True,
            'cuenta_contable': cta_fert_act,
            'centro_de_costo': cc_prod_norte
        }
    )

    fact_ypf_ene, _ = ComprobanteFiscal.objects.update_or_create(
        tipo_operacion=ComprobanteFiscal.TipoOperacion.COMPRA,
        tipo_comprobante=ComprobanteFiscal.TipoComprobante.FACTURA_A,
        punto_de_venta="00001",
        numero_comprobante="00031890",
        cuit="30-54668997-1",
        defaults={
            'cuenta_corriente': prov_ypf,
            'razon_social': "YPF Directo Agro La Rioja S.A.",
            'condicion_iva': ComprobanteFiscal.CondicionIVA.RESPONSABLE_INSCRIPTO,
            'fecha_emision': datetime.date(2026, 1, 16),
            'fecha_vencimiento': datetime.date(2026, 1, 26),
            'concepto': "[DEMO] Factura A 5.000 L Gasoil Grado 2 Agro para tractores y grupos electrógenos",
            'neto_gravado_21': Decimal("5600000.00"),
            'iva_21': Decimal("1176000.00"),
            'total': Decimal("6776000.00"),
            'estado_pago': ComprobanteFiscal.EstadoPago.PAGADA,
            'saldo_pendiente': Decimal("0.00"),
            'cae': "74011690123456",
            'vto_cae': datetime.date(2026, 1, 26),
            'es_oficial': True,
            'cuenta_contable': cta_agro_act,
            'centro_de_costo': cc_prod_norte
        }
    )

    fact_edelar_ene, _ = ComprobanteFiscal.objects.update_or_create(
        tipo_operacion=ComprobanteFiscal.TipoOperacion.COMPRA,
        tipo_comprobante=ComprobanteFiscal.TipoComprobante.FACTURA_A,
        punto_de_venta="00012",
        numero_comprobante="00451020",
        cuit="30-67891234-9",
        defaults={
            'cuenta_corriente': prov_edelar,
            'razon_social': "EDELAR S.A.",
            'condicion_iva': ComprobanteFiscal.CondicionIVA.RESPONSABLE_INSCRIPTO,
            'fecha_emision': datetime.date(2026, 1, 25),
            'fecha_vencimiento': datetime.date(2026, 2, 5),
            'concepto': "[DEMO] Suministro de Energía Eléctrica Riego Pozo 1 Finca Norte - Enero 2026",
            'neto_gravado_27': Decimal("520000.00"),
            'iva_27': Decimal("140400.00"),
            'total': Decimal("660400.00"),
            'estado_pago': ComprobanteFiscal.EstadoPago.PAGADA,
            'saldo_pendiente': Decimal("0.00"),
            'cae': "74012589012345",
            'vto_cae': datetime.date(2026, 2, 4),
            'es_oficial': True,
            'centro_de_costo': cc_prod_norte
        }
    )

    fact_edecat_ene, _ = ComprobanteFiscal.objects.update_or_create(
        tipo_operacion=ComprobanteFiscal.TipoOperacion.COMPRA,
        tipo_comprobante=ComprobanteFiscal.TipoComprobante.FACTURA_A,
        punto_de_venta="00005",
        numero_comprobante="00129040",
        cuit="30-69123456-7",
        defaults={
            'cuenta_corriente': prov_edecat,
            'razon_social': "Energía Catamarca SAPEM",
            'condicion_iva': ComprobanteFiscal.CondicionIVA.RESPONSABLE_INSCRIPTO,
            'fecha_emision': datetime.date(2026, 1, 26),
            'fecha_vencimiento': datetime.date(2026, 2, 10),
            'concepto': "[DEMO] Energía Eléctrica Riego Pozo Pomán Finca Sur - Enero 2026",
            'neto_gravado_27': Decimal("380000.00"),
            'iva_27': Decimal("102600.00"),
            'total': Decimal("482600.00"),
            'estado_pago': ComprobanteFiscal.EstadoPago.PAGADA,
            'saldo_pendiente': Decimal("0.00"),
            'cae': "74012698712345",
            'vto_cae': datetime.date(2026, 2, 5),
            'es_oficial': True,
            'centro_de_costo': cc_prod_sur
        }
    )

    # Movimientos Financieros Enero 2026
    mov_pago_ypf_ene = MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 1, 25),
        importe=Decimal("6776000.00"),
        moneda="ARS",
        concepto="[DEMO] Transferencia Pago Factura A 0001-00031890 Gasoil Grado 2 - YPF Directo",
        cuenta_corriente=prov_ypf,
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        comprobante_tipo="Transferencia",
        comprobante_nro="TRF-889102",
        usuario=usuario
    )
    mov_pago_agro_ene = MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 1, 28),
        importe=Decimal("4000000.00"),
        moneda="ARS",
        concepto="[DEMO] Pago a Cuenta Factura A 0004-00054129 Fertilizantes - Agroquímica Cuyo",
        cuenta_corriente=prov_agroquimica,
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        comprobante_tipo="Transferencia",
        comprobante_nro="TRF-889340",
        usuario=usuario
    )
    mov_pago_sueldos_ene = MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 1, 31),
        importe=Decimal("5850000.00"),
        moneda="ARS",
        concepto="[DEMO] Pago Haberes y Jornales Rurales UATRE Finca Norte - Diciembre 2025",
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        comprobante_tipo="Acreditación Haberes",
        comprobante_nro="HAB-202601",
        usuario=usuario
    )
    mov_caja_repuestos_ene = MovimientoFinanciero.objects.create(
        cuenta=caja_finca,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 1, 20),
        importe=Decimal("120000.00"),
        moneda="ARS",
        concepto="[DEMO] Compra repuestos menores y accesorios de riego en efectivo",
        cuenta_corriente=prov_taller,
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        comprobante_tipo="Ticket",
        comprobante_nro="TK-00912",
        usuario=usuario
    )

    # Orden de Pago Enero
    OrdenPagoRecibo.objects.create(
        tipo=OrdenPagoRecibo.TipoDocumento.ORDEN_PAGO,
        numero="OP-2026-0001",
        fecha=datetime.date(2026, 1, 25),
        cuenta_corriente=prov_ypf,
        cuenta_financiera=cta_banco_ars,
        importe_total=Decimal("6776000.00"),
        medio_pago=OrdenPagoRecibo.MedioPago.TRANSFERENCIA,
        comprobante_fiscal=fact_ypf_ene,
        movimiento_financiero=mov_pago_ypf_ene,
        concepto="[DEMO] Cancelación total Factura A 0001-00031890 Gasoil 5.000 L",
        beneficiario_firmante="YPF Directo Agro La Rioja S.A.",
        usuario=usuario
    )

    # Conciliación Bancaria Enero 2026 (Cerrada)
    ConciliacionBancaria.objects.get_or_create(
        cuenta=cta_banco_ars,
        fecha_extracto=datetime.date(2026, 1, 31),
        defaults={
            'saldo_extracto': Decimal("24800000.00"),
            'saldo_sistema': Decimal("24800000.00"),
            'diferencia': Decimal("0.00"),
            'estado': 'CERRADA',
            'observaciones': "[DEMO] Conciliación Enero 2026 cerrada y verificada con extracto Banco Galicia.",
            'usuario': usuario
        }
    )

    # ═════════════════════════════════════════════════════════════════════════
    # FEBRERO 2026: ENVERO, CURAS PREVENTIVAS Y MANTENIMIENTO
    # ═════════════════════════════════════════════════════════════════════════

    for c in [cuadro_a1, cuadro_b2]:
        RegistroFenologico.objects.get_or_create(
            cuadro=c,
            campana="2025/2026",
            fecha=datetime.date(2026, 2, 14),
            defaults={
                'fase_vegetativa': RegistroFenologico.FaseVegetativa.ENVERO,
                'grados_dia_acumulados': Decimal("1850.0"),
                'temperatura_min': Decimal("17.0"),
                'temperatura_max': Decimal("34.5"),
                'riesgo_fitosanitario': RegistroFenologico.RiesgoFitosanitario.BAJO,
                'observaciones': '[DEMO] Inicio de envero en Arauco. Cambio de color de verde claro a pajizo.',
                'responsable': usuario
            }
        )

    EventoCuadro.objects.get_or_create(
        cuadro=cuadro_a1,
        campana="2025/2026",
        fecha=datetime.date(2026, 2, 8),
        tipo_evento=EventoCuadro.TipoEvento.APLICACION_FITOSANITARIA,
        defaults={
            'descripcion': '[DEMO] Aplicación foliar preventiva con oxicloruro de cobre 50% para repilo.',
            'responsable': usuario
        }
    )

    # Mantenimiento de Maquinaria Febrero
    MantenimientoMaquina.objects.get_or_create(
        maquina=maq_tractor,
        fecha=datetime.date(2026, 2, 10),
        defaults={
            'tipo': 'PREVENTIVO',
            'horas_maquina': Decimal("1840.5"),
            'descripcion': '[DEMO] Cambio de aceite motor 15W40, filtros de gasoil y aire, engrase general.',
            'costo_total_ars': Decimal("480000.00"),
            'taller_o_proveedor': "Taller Mecánico Central Finca"
        }
    )

    # OC Envases Febrero y Recepción Confirmada
    oc_env = OrdenDeCompra.objects.create(
        proveedor=prov_envases,
        finca_destino=finca_norte,
        numero="OC-2026-003",
        fecha_emision=datetime.date(2026, 2, 10),
        fecha_entrega_estimada=datetime.date(2026, 2, 15),
        estado=OrdenDeCompra.Estado.RECIBIDA,
        observaciones="[DEMO] Envases de vidrio, tapas irrellenables y cajas para la línea de fraccionado."
    )
    ItemOrdenDeCompra.objects.create(orden=oc_env, insumo=insumos['INS-BOT-500'], cantidad_solicitada=Decimal("10000.00"), precio_unitario_estimado_ars=Decimal("580.00"))
    ItemOrdenDeCompra.objects.create(orden=oc_env, insumo=insumos['INS-TAPAS-01'], cantidad_solicitada=Decimal("10000.00"), precio_unitario_estimado_ars=Decimal("190.00"))
    ItemOrdenDeCompra.objects.create(orden=oc_env, insumo=insumos['INS-CAJAS-12'], cantidad_solicitada=Decimal("800.00"), precio_unitario_estimado_ars=Decimal("1250.00"))
    oc_env.recalcular_total()

    rec_env = RecepcionMercaderia.objects.create(
        orden=oc_env,
        deposito_destino=dep_central,
        fecha_recepcion=datetime.date(2026, 2, 15),
        numero_remito_proveedor="R-0008-00034190",
        numero_factura_proveedor="FC-A-0008-00012480",
        estado=RecepcionMercaderia.Estado.CONFIRMADA,
        total_real_ars=oc_env.total_estimado_ars,
        observaciones="[DEMO] Recepción paletizada de botellas, tapas y cajas en depósito central."
    )
    mov_b_feb = _registrar_movimiento(insumos['INS-BOT-500'], dep_central, MovimientoStock.TipoMovimiento.ENTRADA_COMPRA, Decimal("10000.00"), Decimal("580.00"), datetime.datetime(2026, 2, 15, 10, 0), "[DEMO] Ingreso botellas UVAG 500ml OC-2026-003", ref="OC-2026-003")
    mov_t_feb = _registrar_movimiento(insumos['INS-TAPAS-01'], dep_central, MovimientoStock.TipoMovimiento.ENTRADA_COMPRA, Decimal("10000.00"), Decimal("190.00"), datetime.datetime(2026, 2, 15, 10, 0), "[DEMO] Ingreso tapas irrellenables D.O.P. OC-2026-003", ref="OC-2026-003")
    mov_c_feb = _registrar_movimiento(insumos['INS-CAJAS-12'], dep_central, MovimientoStock.TipoMovimiento.ENTRADA_COMPRA, Decimal("800.00"), Decimal("1250.00"), datetime.datetime(2026, 2, 15, 10, 0), "[DEMO] Ingreso cajas corrugadas x 12 OC-2026-003", ref="OC-2026-003")
    ItemRecepcion.objects.create(recepcion=rec_env, insumo=insumos['INS-BOT-500'], cantidad_en_oc=Decimal("10000.00"), cantidad_recibida=Decimal("10000.00"), precio_unitario_real_ars=Decimal("580.00"), movimiento_stock=mov_b_feb)
    ItemRecepcion.objects.create(recepcion=rec_env, insumo=insumos['INS-TAPAS-01'], cantidad_en_oc=Decimal("10000.00"), cantidad_recibida=Decimal("10000.00"), precio_unitario_real_ars=Decimal("190.00"), movimiento_stock=mov_t_feb)
    ItemRecepcion.objects.create(recepcion=rec_env, insumo=insumos['INS-CAJAS-12'], cantidad_en_oc=Decimal("800.00"), cantidad_recibida=Decimal("800.00"), precio_unitario_real_ars=Decimal("1250.00"), movimiento_stock=mov_c_feb)

    # OC Fitosanitarios y Herbicidas Febrero
    oc_quim = OrdenDeCompra.objects.create(
        proveedor=prov_agroquimica,
        finca_destino=finca_norte,
        numero="OC-2026-004",
        fecha_emision=datetime.date(2026, 2, 12),
        fecha_entrega_estimada=datetime.date(2026, 2, 15),
        estado=OrdenDeCompra.Estado.RECIBIDA,
        observaciones="[DEMO] Fitosanitarios para cura preventiva de repilo y control de malezas."
    )
    ItemOrdenDeCompra.objects.create(orden=oc_quim, insumo=insumos['INS-COBRE-01'], cantidad_solicitada=Decimal("300.00"), precio_unitario_estimado_ars=Decimal("14500.00"))
    ItemOrdenDeCompra.objects.create(orden=oc_quim, insumo=insumos['INS-GLIFO-01'], cantidad_solicitada=Decimal("200.00"), precio_unitario_estimado_ars=Decimal("9200.00"))
    oc_quim.recalcular_total()

    rec_quim = RecepcionMercaderia.objects.create(
        orden=oc_quim,
        deposito_destino=dep_central,
        fecha_recepcion=datetime.date(2026, 2, 15),
        numero_remito_proveedor="R-0004-00130982",
        numero_factura_proveedor="FC-A-0004-00055810",
        estado=RecepcionMercaderia.Estado.CONFIRMADA,
        total_real_ars=oc_quim.total_estimado_ars,
        observaciones="[DEMO] Recepción fitosanitarios y herbicida en nave central."
    )
    mov_cu_feb = _registrar_movimiento(insumos['INS-COBRE-01'], dep_central, MovimientoStock.TipoMovimiento.ENTRADA_COMPRA, Decimal("300.00"), Decimal("14500.00"), datetime.datetime(2026, 2, 15, 14, 0), "[DEMO] Ingreso cobre repilo OC-2026-004", ref="OC-2026-004")
    mov_gl_feb = _registrar_movimiento(insumos['INS-GLIFO-01'], dep_central, MovimientoStock.TipoMovimiento.ENTRADA_COMPRA, Decimal("200.00"), Decimal("9200.00"), datetime.datetime(2026, 2, 15, 14, 0), "[DEMO] Ingreso glifosato herbicida OC-2026-004", ref="OC-2026-004")
    ItemRecepcion.objects.create(recepcion=rec_quim, insumo=insumos['INS-COBRE-01'], cantidad_en_oc=Decimal("300.00"), cantidad_recibida=Decimal("300.00"), precio_unitario_real_ars=Decimal("14500.00"), movimiento_stock=mov_cu_feb)
    ItemRecepcion.objects.create(recepcion=rec_quim, insumo=insumos['INS-GLIFO-01'], cantidad_en_oc=Decimal("200.00"), cantidad_recibida=Decimal("200.00"), precio_unitario_real_ars=Decimal("9200.00"), movimiento_stock=mov_gl_feb)

    # Transferencia Inter-depósito Febrero (17/02/2026)
    _registrar_movimiento(insumos['INS-COBRE-01'], dep_central, MovimientoStock.TipoMovimiento.TRANSFERENCIA, Decimal("50.00"), Decimal("14500.00"), datetime.datetime(2026, 2, 17, 14, 0), "[DEMO] Traslado de cobre preventivo a Galpón Tinglado Sur", dep_dest=dep_sur, ref="TRF-20260217")
    _registrar_movimiento(insumos['INS-GLIFO-01'], dep_central, MovimientoStock.TipoMovimiento.TRANSFERENCIA, Decimal("50.00"), Decimal("9200.00"), datetime.datetime(2026, 2, 17, 14, 0), "[DEMO] Traslado de glifosato a Galpón Tinglado Sur", dep_dest=dep_sur, ref="TRF-20260217")

    # Partes Diarios Febrero
    ot_cura_feb = OrdenDeTrabajo.objects.create(
        cuadro=cuadro_a1,
        tipo_labor=OrdenDeTrabajo.TipoLabor.CURA_FITOSANITARIA,
        fecha_programada=datetime.date(2026, 2, 16),
        responsable=usuario,
        estado=OrdenDeTrabajo.Estado.FINALIZADA,
        instrucciones_tecnicas="[DEMO] Aplicación con atomizadora a 400 L/ha de caldo."
    )
    pd_cura_feb = ParteDiario.objects.create(
        finca=finca_norte,
        cuadro=cuadro_a1,
        fecha=datetime.date(2026, 2, 16),
        supervisor=usuario,
        estado=ParteDiario.Estado.CONFIRMADO_CERRADO,
        observaciones="[DEMO] Tratamiento preventivo completado en todo el cuartel 1."
    )
    ParteDiarioPersonal.objects.create(
        parte_diario=pd_cura_feb,
        empleado=empleados['LEG-002'],
        horas_normales=Decimal("8.0"),
        horas_extras=Decimal("2.0"),
        costo_jornal_calculado_ars=Decimal("48125.00"),
        tarea_especifica="Tractorista con atomizadora"
    )
    mov_cobre = _registrar_movimiento(insumos['INS-COBRE-01'], dep_central, MovimientoStock.TipoMovimiento.SALIDA_PARTE_DIARIO, Decimal("70.00"), Decimal("14500.00"), datetime.datetime(2026, 2, 16, 9, 30), "[DEMO] Cura sanitaria repilo Cuadro Arauco")
    ParteDiarioInsumo.objects.create(
        parte_diario=pd_cura_feb,
        insumo=insumos['INS-COBRE-01'],
        deposito_origen=dep_central,
        cantidad_utilizada=Decimal("70.00"),
        dosis_por_hectarea="2.0 kg/ha",
        costo_unitario_aplicado_ars=Decimal("14500.00"),
        costo_total_ars=Decimal("1015000.00"),
        movimiento_stock_generado=mov_cobre
    )

    # Parte Diario Control de Malezas Febrero (20/02/2026)
    ot_desm = OrdenDeTrabajo.objects.create(
        cuadro=cuadro_b2,
        tipo_labor=OrdenDeTrabajo.TipoLabor.DESMALEZADO,
        fecha_programada=datetime.date(2026, 2, 20),
        responsable=usuario,
        estado=OrdenDeTrabajo.Estado.FINALIZADA,
        instrucciones_tecnicas="[DEMO] Aplicación dirigida de herbicida en ruedo y borduras con pulverizadora."
    )
    pd_desm = ParteDiario.objects.create(
        finca=finca_norte,
        cuadro=cuadro_b2,
        fecha=datetime.date(2026, 2, 20),
        supervisor=usuario,
        estado=ParteDiario.Estado.CONFIRMADO_CERRADO,
        observaciones="[DEMO] Tratamiento de malezas completado en Cuadro Arbequina."
    )
    ParteDiarioPersonal.objects.create(
        parte_diario=pd_desm,
        empleado=empleados['LEG-002'],
        horas_normales=Decimal("8.0"),
        costo_jornal_calculado_ars=Decimal("35000.00"),
        tarea_especifica="Tractorista aplicación herbicida"
    )
    mov_glifo_feb = _registrar_movimiento(insumos['INS-GLIFO-01'], dep_central, MovimientoStock.TipoMovimiento.SALIDA_PARTE_DIARIO, Decimal("40.00"), Decimal("9200.00"), datetime.datetime(2026, 2, 20, 11, 0), "[DEMO] Herbicida glifosato Cuadro Arbequina")
    ParteDiarioInsumo.objects.create(
        parte_diario=pd_desm,
        insumo=insumos['INS-GLIFO-01'],
        deposito_origen=dep_central,
        cantidad_utilizada=Decimal("40.00"),
        dosis_por_hectarea="0.8 L/ha",
        costo_unitario_aplicado_ars=Decimal("9200.00"),
        costo_total_ars=Decimal("368000.00"),
        movimiento_stock_generado=mov_glifo_feb
    )
    mov_gasoil_feb = _registrar_movimiento(insumos['INS-GASOIL-01'], dep_central, MovimientoStock.TipoMovimiento.SALIDA_PARTE_DIARIO, Decimal("250.00"), Decimal("1120.00"), datetime.datetime(2026, 2, 20, 16, 0), "[DEMO] Gasoil tractor aplicación herbicida")
    ParteDiarioInsumo.objects.create(
        parte_diario=pd_desm,
        insumo=insumos['INS-GASOIL-01'],
        deposito_origen=dep_central,
        cantidad_utilizada=Decimal("250.00"),
        dosis_por_hectarea="5.1 L/ha",
        costo_unitario_aplicado_ars=Decimal("1120.00"),
        costo_total_ars=Decimal("280000.00"),
        movimiento_stock_generado=mov_gasoil_feb
    )

    # Merma de Envases Febrero (27/02/2026)
    _registrar_movimiento(insumos['INS-BOT-500'], dep_central, MovimientoStock.TipoMovimiento.SALIDA_MERMA, Decimal("35.00"), Decimal("580.00"), datetime.datetime(2026, 2, 27, 16, 30), "[DEMO] Merma por rotura de pallet durante descarga en depósito", ref="MER-20260227")

    # Asistencia Febrero
    dias_feb = [datetime.date(2026, 2, d) for d in range(2, 28, 2) if datetime.date(2026, 2, d).weekday() < 6]
    for d in dias_feb:
        for leg, emp in list(empleados.items())[:6]:
            RegistroAsistencia.objects.get_or_create(
                empleado=emp,
                fecha=d,
                defaults={
                    'finca': finca_norte,
                    'estado': RegistroAsistencia.Estado.PRESENTE,
                    'horas_normales': Decimal("8.0"),
                    'jornal_computado': Decimal("1.00"),
                    'observaciones': '[DEMO] Tareas de precampaña'
                }
            )

    # Liquidación Febrero
    periodo_feb, _ = PeriodoLiquidacion.objects.get_or_create(
        mes=2,
        ano=2026,
        tipo=PeriodoLiquidacion.TipoPeriodo.MENSUAL,
        defaults={
            'fecha_inicio': datetime.date(2026, 2, 1),
            'fecha_fin': datetime.date(2026, 2, 28),
            'estado': PeriodoLiquidacion.Estado.CERRADO,
            'observaciones': '[DEMO] Haberes mensuales UATRE Febrero 2026'
        }
    )
    for leg, emp in list(empleados.items())[:6]:
        bruto = emp.valor_jornal_base_ars * Decimal("22")
        ret = bruto * Decimal("0.185")
        neto = bruto - ret
        liq_feb, _ = LiquidacionEmpleado.objects.get_or_create(
            periodo=periodo_feb,
            empleado=emp,
            defaults={
                'dias_jornales_computados': Decimal("22.00"),
                'horas_normales': Decimal("176.0"),
                'total_bruto_remunerativo_ars': bruto,
                'total_retenciones_ars': ret,
                'neto_a_cobrar_ars': neto,
                'estado': LiquidacionEmpleado.Estado.PAGADO
            }
        )
        ItemLiquidacion.objects.get_or_create(liquidacion=liq_feb, codigo_concepto="101", defaults={'descripcion': "Básico Mensual Jornal Rural", 'tipo': ItemLiquidacion.TipoConcepto.REMUNERATIVO, 'importe_ars': bruto})
        ItemLiquidacion.objects.get_or_create(liquidacion=liq_feb, codigo_concepto="501", defaults={'descripcion': "Aportes Jubilación y Ley 19032 (14%)", 'tipo': ItemLiquidacion.TipoConcepto.RETENCION, 'importe_ars': bruto * Decimal("0.14")})
        ItemLiquidacion.objects.get_or_create(liquidacion=liq_feb, codigo_concepto="502", defaults={'descripcion': "Obra Social OSPRERA (3%)", 'tipo': ItemLiquidacion.TipoConcepto.RETENCION, 'importe_ars': bruto * Decimal("0.03")})

    # Comprobantes Fiscales Febrero 2026 (Facturas de Compra)
    fact_taller_feb, _ = ComprobanteFiscal.objects.update_or_create(
        tipo_operacion=ComprobanteFiscal.TipoOperacion.COMPRA,
        tipo_comprobante=ComprobanteFiscal.TipoComprobante.FACTURA_A,
        punto_de_venta="00002",
        numero_comprobante="00004520",
        cuit="30-65432198-7",
        defaults={
            'cuenta_corriente': prov_taller,
            'razon_social': "Taller Metalúrgico e Hidráulica Aimogasta",
            'condicion_iva': ComprobanteFiscal.CondicionIVA.RESPONSABLE_INSCRIPTO,
            'fecha_emision': datetime.date(2026, 2, 10),
            'fecha_vencimiento': datetime.date(2026, 2, 15),
            'concepto': "[DEMO] Service preventivo 1.800 hs, lubricantes, filtros y puesta a punto John Deere 5075E",
            'neto_gravado_21': Decimal("480000.00"),
            'iva_21': Decimal("100800.00"),
            'total': Decimal("580800.00"),
            'estado_pago': ComprobanteFiscal.EstadoPago.PAGADA,
            'saldo_pendiente': Decimal("0.00"),
            'cae': "74021098123456",
            'vto_cae': datetime.date(2026, 2, 20),
            'es_oficial': True,
            'centro_de_costo': cc_prod_norte
        }
    )

    fact_agroquimica_feb, _ = ComprobanteFiscal.objects.update_or_create(
        tipo_operacion=ComprobanteFiscal.TipoOperacion.COMPRA,
        tipo_comprobante=ComprobanteFiscal.TipoComprobante.FACTURA_A,
        punto_de_venta="00004",
        numero_comprobante="00055012",
        cuit="30-71234567-0",
        defaults={
            'cuenta_corriente': prov_agroquimica,
            'razon_social': "Agroquímica Cuyo & Cía S.A.",
            'condicion_iva': ComprobanteFiscal.CondicionIVA.RESPONSABLE_INSCRIPTO,
            'fecha_emision': datetime.date(2026, 2, 14),
            'fecha_vencimiento': datetime.date(2026, 3, 14),
            'concepto': "[DEMO] Factura A Curas Repilo y Herbicidas (Oxicloruro de Cobre y Glifosato)",
            'neto_gravado_21': Decimal("11070000.00"),
            'iva_21': Decimal("2324700.00"),
            'percepcion_iibb': Decimal("332100.00"),
            'total': Decimal("13726800.00"),
            'estado_pago': ComprobanteFiscal.EstadoPago.PAGO_PARCIAL,
            'saldo_pendiente': Decimal("7726800.00"),
            'cae': "74021482910382",
            'vto_cae': datetime.date(2026, 2, 24),
            'es_oficial': True,
            'cuenta_contable': cta_fung_act,
            'centro_de_costo': cc_prod_norte
        }
    )

    fact_edelar_feb, _ = ComprobanteFiscal.objects.update_or_create(
        tipo_operacion=ComprobanteFiscal.TipoOperacion.COMPRA,
        tipo_comprobante=ComprobanteFiscal.TipoComprobante.FACTURA_A,
        punto_de_venta="00012",
        numero_comprobante="00458900",
        cuit="30-67891234-9",
        defaults={
            'cuenta_corriente': prov_edelar,
            'razon_social': "EDELAR S.A.",
            'condicion_iva': ComprobanteFiscal.CondicionIVA.RESPONSABLE_INSCRIPTO,
            'fecha_emision': datetime.date(2026, 2, 22),
            'fecha_vencimiento': datetime.date(2026, 3, 8),
            'concepto': "[DEMO] Suministro Trifásico Riego Pozo 1 Finca Norte - Febrero 2026",
            'neto_gravado_27': Decimal("1250000.00"),
            'iva_27': Decimal("337500.00"),
            'total': Decimal("1587500.00"),
            'estado_pago': ComprobanteFiscal.EstadoPago.PAGADA,
            'saldo_pendiente': Decimal("0.00"),
            'cae': "74022290128374",
            'vto_cae': datetime.date(2026, 3, 4),
            'es_oficial': True,
            'centro_de_costo': cc_prod_norte
        }
    )

    # Movimientos Financieros Febrero 2026
    mov_pago_edelar_feb = MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 2, 5),
        importe=Decimal("660400.00"),
        moneda="ARS",
        concepto="[DEMO] Débito Directo Factura EDELAR Suministro Pozo 1 Enero",
        cuenta_corriente=prov_edelar,
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        comprobante_tipo="Débito Automático",
        comprobante_nro="DEB-EDELAR-01",
        usuario=usuario
    )
    mov_pago_edecat_feb = MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 2, 10),
        importe=Decimal("482600.00"),
        moneda="ARS",
        concepto="[DEMO] Pago Factura Energía Catamarca SAPEM Riego Pomán Enero",
        cuenta_corriente=prov_edecat,
        centro_de_costo=cc_prod_sur,
        finca=finca_sur,
        comprobante_tipo="Transferencia",
        comprobante_nro="TRF-901412",
        usuario=usuario
    )
    mov_pago_taller_feb = MovimientoFinanciero.objects.create(
        cuenta=caja_finca,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 2, 12),
        importe=Decimal("580800.00"),
        moneda="ARS",
        concepto="[DEMO] Pago contado efectivo Service preventivo Tractor John Deere Factura A 0002-00004520",
        cuenta_corriente=prov_taller,
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        comprobante_tipo="Factura A",
        comprobante_nro="0002-00004520",
        usuario=usuario
    )
    mov_cobro_aceite_feb = MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.INGRESO,
        fecha=datetime.date(2026, 2, 15),
        importe=Decimal("7500000.00"),
        moneda="ARS",
        concepto="[DEMO] Cobranza Cheque #77124098 BBVA Venta Aceite Virgen Extra Fraccionado",
        cuenta_corriente=cli_local,
        centro_de_costo=cc_almazara,
        finca=finca_norte,
        comprobante_tipo="Acreditación Cheque",
        comprobante_nro="CHQ-77124098",
        usuario=usuario
    )
    mov_pago_sueldos_feb = MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 2, 20),
        importe=Decimal("5980000.00"),
        moneda="ARS",
        concepto="[DEMO] Pago Liquidación Haberes UATRE Enero 2026",
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        comprobante_tipo="Acreditación Haberes",
        comprobante_nro="HAB-202602",
        usuario=usuario
    )

    # Cheques Febrero 2026
    cheque_cobrado_feb, _ = Cheque.objects.update_or_create(
        numero="77124098",
        banco_emisor="Banco BBVA Argentina",
        defaults={
            'cuenta_bancaria_origen': cta_banco_ars,
            'emisor_firmante': "Distribuidora Los Olivos S.R.L.",
            'cuit_emisor': "30-66442211-8",
            'tipo': Cheque.TipoCheque.RECIBIDO_TERCERO,
            'cuenta_corriente': cli_local,
            'importe': Decimal("7500000.00"),
            'fecha_emision': datetime.date(2026, 2, 15),
            'fecha_cobro': datetime.date(2026, 2, 15),
            'estado': Cheque.EstadoCheque.COBRADO,
            'observaciones': "[DEMO] Cobro anticipado aceite fraccionado en botella UVAG 500ml"
        }
    )
    cheque_propio_feb, _ = Cheque.objects.update_or_create(
        numero="88341201",
        banco_emisor="Banco Galicia",
        defaults={
            'cuenta_bancaria_origen': cta_banco_ars,
            'emisor_firmante': "Olivar del Valle Agroindustrial S.A.",
            'cuit_emisor': "30-71458923-4",
            'tipo': Cheque.TipoCheque.EMITIDO_PROPIO,
            'cuenta_corriente': prov_agroquimica,
            'importe': Decimal("6000000.00"),
            'fecha_emision': datetime.date(2026, 2, 26),
            'fecha_cobro': datetime.date(2026, 3, 25),
            'estado': Cheque.EstadoCheque.COBRADO,
            'observaciones': "[DEMO] Cheque de pago diferido 30 días a Agroquímica Cuyo por fertilizantes y fitosanitarios"
        }
    )

    # Conciliación Bancaria Febrero 2026 (Cerrada)
    ConciliacionBancaria.objects.get_or_create(
        cuenta=cta_banco_ars,
        fecha_extracto=datetime.date(2026, 2, 28),
        defaults={
            'saldo_extracto': Decimal("28450000.00"),
            'saldo_sistema': Decimal("28450000.00"),
            'diferencia': Decimal("0.00"),
            'estado': 'CERRADA',
            'observaciones': "[DEMO] Conciliación Febrero 2026 cerrada y verificada.",
            'usuario': usuario
        }
    )

    # ═════════════════════════════════════════════════════════════════════════
    # MARZO 2026: COSECHA TEMPRANA, INGRESO A ALMAZARA Y CIERRE TRIMESTRAL
    # ═════════════════════════════════════════════════════════════════════════

    for c in [cuadro_a1, cuadro_b2, cuadro_c3]:
        RegistroFenologico.objects.get_or_create(
            cuadro=c,
            campana="2025/2026",
            fecha=datetime.date(2026, 3, 10),
            defaults={
                'fase_vegetativa': RegistroFenologico.FaseVegetativa.MADUREZ,
                'grados_dia_acumulados': Decimal("2240.0"),
                'temperatura_min': Decimal("14.8"),
                'temperatura_max': Decimal("31.0"),
                'riesgo_fitosanitario': RegistroFenologico.RiesgoFitosanitario.BAJO,
                'observaciones': '[DEMO] Madurez óptima alcanzada. Índice de madurez 3.2 ideal para virgen extra temprano.',
                'responsable': usuario
            }
        )

    # Lotes de Cosecha Campaña 2024/2025 (Histórica comparativa)
    LoteDeCosecha.objects.update_or_create(
        cuadro=cuadro_a1,
        campana="2024/2025",
        defaults={
            'fecha_inicio': datetime.date(2025, 3, 5),
            'fecha_fin': datetime.date(2025, 3, 20),
            'kg_cosechados': Decimal("42000.00"),
            'destino': LoteDeCosecha.Destino.ACEITUNA_MESA_VERDE,
            'rendimiento_graso_porcentaje': Decimal("16.00"),
            'estado': LoteDeCosecha.Estado.FINALIZADO,
            'precio_venta_estimado_por_kg': Decimal("1050.00"),
            'calidad_observaciones': '[DEMO] Cosecha manual Arauco 2024/2025.'
        }
    )
    LoteDeCosecha.objects.update_or_create(
        cuadro=cuadro_b2,
        campana="2024/2025",
        defaults={
            'fecha_inicio': datetime.date(2025, 3, 15),
            'fecha_fin': datetime.date(2025, 3, 30),
            'kg_cosechados': Decimal("85000.00"),
            'destino': LoteDeCosecha.Destino.ACEITE_ALMAZARA,
            'rendimiento_graso_porcentaje': Decimal("17.20"),
            'estado': LoteDeCosecha.Estado.FINALIZADO,
            'precio_venta_estimado_por_kg': Decimal("820.00"),
            'calidad_observaciones': '[DEMO] Cosecha mecánica Arbequina 2024/2025.'
        }
    )
    LoteDeCosecha.objects.update_or_create(
        cuadro=cuadro_c3,
        campana="2024/2025",
        defaults={
            'fecha_inicio': datetime.date(2025, 3, 20),
            'fecha_fin': datetime.date(2025, 3, 31),
            'kg_cosechados': Decimal("45000.00"),
            'destino': LoteDeCosecha.Destino.ACEITE_ALMAZARA,
            'rendimiento_graso_porcentaje': Decimal("18.50"),
            'estado': LoteDeCosecha.Estado.FINALIZADO,
            'precio_venta_estimado_por_kg': Decimal("890.00"),
            'calidad_observaciones': '[DEMO] Cosecha Picual Finca Sur 2024/2025.'
        }
    )
    LoteDeCosecha.objects.update_or_create(
        cuadro=cuadro_d4,
        campana="2024/2025",
        defaults={
            'fecha_inicio': datetime.date(2025, 3, 10),
            'fecha_fin': datetime.date(2025, 3, 25),
            'kg_cosechados': Decimal("38000.00"),
            'destino': LoteDeCosecha.Destino.ACEITUNA_MESA_VERDE,
            'rendimiento_graso_porcentaje': Decimal("15.50"),
            'estado': LoteDeCosecha.Estado.FINALIZADO,
            'precio_venta_estimado_por_kg': Decimal("950.00"),
            'calidad_observaciones': '[DEMO] Cosecha Manzanilla Chilecito 2024/2025.'
        }
    )

    # Lotes de Cosecha Campaña 2025/2026 (Actual)
    lote_arauco, _ = LoteDeCosecha.objects.update_or_create(
        cuadro=cuadro_a1,
        campana="2025/2026",
        defaults={
            'fecha_inicio': datetime.date(2026, 3, 5),
            'fecha_fin': datetime.date(2026, 3, 20),
            'kg_cosechados': Decimal("48000.00"),
            'destino': LoteDeCosecha.Destino.ACEITUNA_MESA_VERDE,
            'rendimiento_graso_porcentaje': Decimal("16.80"),
            'estado': LoteDeCosecha.Estado.FINALIZADO,
            'precio_venta_estimado_por_kg': Decimal("1250.00"),
            'calidad_observaciones': '[DEMO] Cosecha manual en fresco variedad Arauco, calibre comercial 140-160.'
        }
    )
    lote_arbequina, _ = LoteDeCosecha.objects.update_or_create(
        cuadro=cuadro_b2,
        campana="2025/2026",
        defaults={
            'fecha_inicio': datetime.date(2026, 3, 15),
            'fecha_fin': datetime.date(2026, 3, 30),
            'kg_cosechados': Decimal("92000.00"),
            'destino': LoteDeCosecha.Destino.ACEITE_ALMAZARA,
            'rendimiento_graso_porcentaje': Decimal("17.80"),
            'estado': LoteDeCosecha.Estado.FINALIZADO,
            'precio_venta_estimado_por_kg': Decimal("980.00"),
            'calidad_observaciones': '[DEMO] Cosecha mecánica cabalgante con traslado inmediato a molienda almazara.'
        }
    )
    lote_picual, _ = LoteDeCosecha.objects.update_or_create(
        cuadro=cuadro_c3,
        campana="2025/2026",
        defaults={
            'fecha_inicio': datetime.date(2026, 3, 20),
            'fecha_fin': datetime.date(2026, 3, 31),
            'kg_cosechados': Decimal("52000.00"),
            'destino': LoteDeCosecha.Destino.ACEITE_ALMAZARA,
            'rendimiento_graso_porcentaje': Decimal("19.20"),
            'estado': LoteDeCosecha.Estado.FINALIZADO,
            'precio_venta_estimado_por_kg': Decimal("1100.00"),
            'calidad_observaciones': '[DEMO] Cosecha Picual Pomán, alta concentración polifenólica.'
        }
    )
    lote_manzanilla, _ = LoteDeCosecha.objects.update_or_create(
        cuadro=cuadro_d4,
        campana="2025/2026",
        defaults={
            'fecha_inicio': datetime.date(2026, 3, 12),
            'fecha_fin': datetime.date(2026, 3, 26),
            'kg_cosechados': Decimal("44000.00"),
            'destino': LoteDeCosecha.Destino.ACEITUNA_MESA_VERDE,
            'rendimiento_graso_porcentaje': Decimal("16.20"),
            'estado': LoteDeCosecha.Estado.FINALIZADO,
            'precio_venta_estimado_por_kg': Decimal("1180.00"),
            'calidad_observaciones': '[DEMO] Cosecha Manzanilla Finca Chilecito mesa y conserva.'
        }
    )

    # Órdenes de Compra y Recepciones Marzo
    oc_gasoil_mar = OrdenDeCompra.objects.create(
        proveedor=prov_ypf,
        finca_destino=finca_norte,
        numero="OC-2026-005",
        fecha_emision=datetime.date(2026, 3, 2),
        fecha_entrega_estimada=datetime.date(2026, 3, 4),
        estado=OrdenDeCompra.Estado.RECIBIDA,
        observaciones="[DEMO] Gasoil para campaña de cosecha mecánica y fletes de campo a almazara."
    )
    ItemOrdenDeCompra.objects.create(orden=oc_gasoil_mar, insumo=insumos['INS-GASOIL-01'], cantidad_solicitada=Decimal("8000.00"), precio_unitario_estimado_ars=Decimal("1150.00"))
    oc_gasoil_mar.recalcular_total()

    rec_gasoil_mar = RecepcionMercaderia.objects.create(
        orden=oc_gasoil_mar,
        deposito_destino=dep_central,
        fecha_recepcion=datetime.date(2026, 3, 4),
        numero_remito_proveedor="R-0001-00095810",
        numero_factura_proveedor="FC-A-0001-00032990",
        estado=RecepcionMercaderia.Estado.CONFIRMADA,
        total_real_ars=oc_gasoil_mar.total_estimado_ars,
        observaciones="[DEMO] Descarga cisterna YPF 8.000 L para campaña de cosecha."
    )
    mov_g_mar = _registrar_movimiento(insumos['INS-GASOIL-01'], dep_central, MovimientoStock.TipoMovimiento.ENTRADA_COMPRA, Decimal("8000.00"), Decimal("1150.00"), datetime.datetime(2026, 3, 4, 11, 0), "[DEMO] Ingreso gasoil cisterna cosecha OC-2026-005", ref="OC-2026-005")
    ItemRecepcion.objects.create(recepcion=rec_gasoil_mar, insumo=insumos['INS-GASOIL-01'], cantidad_en_oc=Decimal("8000.00"), cantidad_recibida=Decimal("8000.00"), precio_unitario_real_ars=Decimal("1150.00"), movimiento_stock=mov_g_mar)

    oc_bins_mar = OrdenDeCompra.objects.create(
        proveedor=prov_envases,
        finca_destino=finca_norte,
        numero="OC-2026-006",
        fecha_emision=datetime.date(2026, 3, 3),
        fecha_entrega_estimada=datetime.date(2026, 3, 5),
        estado=OrdenDeCompra.Estado.RECIBIDA,
        observaciones="[DEMO] 100 Bins plásticos ventilados 400kg para recolección y logística de cosecha."
    )
    ItemOrdenDeCompra.objects.create(orden=oc_bins_mar, insumo=insumos['INS-BINS-01'], cantidad_solicitada=Decimal("100.00"), precio_unitario_estimado_ars=Decimal("95000.00"))
    oc_bins_mar.recalcular_total()

    rec_bins_mar = RecepcionMercaderia.objects.create(
        orden=oc_bins_mar,
        deposito_destino=dep_central,
        fecha_recepcion=datetime.date(2026, 3, 5),
        numero_remito_proveedor="R-0008-00035120",
        numero_factura_proveedor="FC-A-0008-00013210",
        estado=RecepcionMercaderia.Estado.CONFIRMADA,
        total_real_ars=oc_bins_mar.total_estimado_ars,
        observaciones="[DEMO] Recepción 100 bins plásticos nuevos en nave central."
    )
    mov_b_mar = _registrar_movimiento(insumos['INS-BINS-01'], dep_central, MovimientoStock.TipoMovimiento.ENTRADA_COMPRA, Decimal("100.00"), Decimal("95000.00"), datetime.datetime(2026, 3, 5, 15, 0), "[DEMO] Ingreso 100 bins cosecha OC-2026-006", ref="OC-2026-006")
    ItemRecepcion.objects.create(recepcion=rec_bins_mar, insumo=insumos['INS-BINS-01'], cantidad_en_oc=Decimal("100.00"), cantidad_recibida=Decimal("100.00"), precio_unitario_real_ars=Decimal("95000.00"), movimiento_stock=mov_b_mar)

    # Transferencia Logística Cosecha Sur (06/03/2026)
    _registrar_movimiento(insumos['INS-BINS-01'], dep_central, MovimientoStock.TipoMovimiento.TRANSFERENCIA, Decimal("50.00"), Decimal("95000.00"), datetime.datetime(2026, 3, 6, 9, 0), "[DEMO] Traslado de 50 bins al Galpón Tinglado Sur para cosecha", dep_dest=dep_sur, ref="TRF-20260306")
    _registrar_movimiento(insumos['INS-GASOIL-01'], dep_central, MovimientoStock.TipoMovimiento.TRANSFERENCIA, Decimal("2500.00"), Decimal("1150.00"), datetime.datetime(2026, 3, 6, 9, 0), "[DEMO] Traslado de 2500 L gasoil para cosecha en Finca Sur", dep_dest=dep_sur, ref="TRF-20260306")

    # Partes Diarios de Cosecha Marzo
    ot_cosecha = OrdenDeTrabajo.objects.create(
        cuadro=cuadro_a1,
        tipo_labor=OrdenDeTrabajo.TipoLabor.COSECHA_MANUAL,
        fecha_programada=datetime.date(2026, 3, 8),
        responsable=usuario,
        estado=OrdenDeTrabajo.Estado.FINALIZADA,
        instrucciones_tecnicas="[DEMO] Cuadrilla de cosecha manual con canastos de tela y vaciado en bins de 400kg."
    )
    pd_cosecha = ParteDiario.objects.create(
        finca=finca_norte,
        cuadro=cuadro_a1,
        fecha=datetime.date(2026, 3, 8),
        supervisor=usuario,
        estado=ParteDiario.Estado.CONFIRMADO_CERRADO,
        observaciones="[DEMO] Cosecha de 32 bins de aceituna Arauco verde transportados al playón de clasificación."
    )
    for leg in ['LEG-006', 'LEG-007', 'LEG-008']:
        ParteDiarioPersonal.objects.create(
            parte_diario=pd_cosecha,
            empleado=empleados[leg],
            horas_normales=Decimal("8.0"),
            horas_extras=Decimal("1.5"),
            costo_jornal_calculado_ars=Decimal("38000.00"),
            tarea_especifica="Cosechero manual y acopio en bines"
        )
    mov_gasoil_cos1 = _registrar_movimiento(insumos['INS-GASOIL-01'], dep_central, MovimientoStock.TipoMovimiento.SALIDA_PARTE_DIARIO, Decimal("450.00"), Decimal("1150.00"), datetime.datetime(2026, 3, 8, 18, 0), "[DEMO] Gasoil acarreo de bines cosecha Arauco")
    ParteDiarioInsumo.objects.create(
        parte_diario=pd_cosecha,
        insumo=insumos['INS-GASOIL-01'],
        deposito_origen=dep_central,
        cantidad_utilizada=Decimal("450.00"),
        dosis_por_hectarea="12.8 L/ha",
        costo_unitario_aplicado_ars=Decimal("1150.00"),
        costo_total_ars=Decimal("517500.00"),
        movimiento_stock_generado=mov_gasoil_cos1
    )

    # Parte Diario Cosecha Mecánica Arbequina (18/03/2026)
    ot_cos_mec = OrdenDeTrabajo.objects.create(
        cuadro=cuadro_b2,
        tipo_labor=OrdenDeTrabajo.TipoLabor.COSECHA_MECANICA,
        fecha_programada=datetime.date(2026, 3, 18),
        responsable=usuario,
        estado=OrdenDeTrabajo.Estado.FINALIZADA,
        instrucciones_tecnicas="[DEMO] Cosecha intensiva con cosechadora cabalgante vibradora y acarreo a tolva."
    )
    pd_cos_mec = ParteDiario.objects.create(
        finca=finca_norte,
        cuadro=cuadro_b2,
        fecha=datetime.date(2026, 3, 18),
        supervisor=usuario,
        estado=ParteDiario.Estado.CONFIRMADO_CERRADO,
        observaciones="[DEMO] Jornada de cosecha mecánica en Cuadro 2 Arbequina completada."
    )
    ParteDiarioPersonal.objects.create(
        parte_diario=pd_cos_mec,
        empleado=empleados['LEG-002'],
        horas_normales=Decimal("8.0"),
        horas_extras=Decimal("2.0"),
        costo_jornal_calculado_ars=Decimal("48125.00"),
        tarea_especifica="Operador cosechadora cabalgante"
    )
    mov_gasoil_cos2 = _registrar_movimiento(insumos['INS-GASOIL-01'], dep_central, MovimientoStock.TipoMovimiento.SALIDA_PARTE_DIARIO, Decimal("900.00"), Decimal("1150.00"), datetime.datetime(2026, 3, 18, 19, 0), "[DEMO] Gasoil cosechadora vibradora y tractores acarreadores")
    ParteDiarioInsumo.objects.create(
        parte_diario=pd_cos_mec,
        insumo=insumos['INS-GASOIL-01'],
        deposito_origen=dep_central,
        cantidad_utilizada=Decimal("900.00"),
        dosis_por_hectarea="18.5 L/ha",
        costo_unitario_aplicado_ars=Decimal("1150.00"),
        costo_total_ars=Decimal("1035000.00"),
        movimiento_stock_generado=mov_gasoil_cos2
    )

    # Parte Diario Fertirriego Post-Cosecha (22/03/2026)
    ot_riego_post = OrdenDeTrabajo.objects.create(
        cuadro=cuadro_a1,
        tipo_labor=OrdenDeTrabajo.TipoLabor.FERTIRRIEGO,
        fecha_programada=datetime.date(2026, 3, 22),
        responsable=usuario,
        estado=OrdenDeTrabajo.Estado.FINALIZADA,
        instrucciones_tecnicas="[DEMO] Riego de recuperación post-cosecha con urea soluble."
    )
    pd_riego_post = ParteDiario.objects.create(
        finca=finca_norte,
        cuadro=cuadro_a1,
        fecha=datetime.date(2026, 3, 22),
        supervisor=usuario,
        estado=ParteDiario.Estado.CONFIRMADO_CERRADO,
        observaciones="[DEMO] Turno de fertirriego post-cosecha completado."
    )
    ParteDiarioPersonal.objects.create(
        parte_diario=pd_riego_post,
        empleado=empleados['LEG-003'],
        horas_normales=Decimal("8.0"),
        costo_jornal_calculado_ars=Decimal("32000.00"),
        tarea_especifica="Regador monitoreo cabezal de riego"
    )
    mov_urea_mar = _registrar_movimiento(insumos['INS-UREA-01'], dep_central, MovimientoStock.TipoMovimiento.SALIDA_PARTE_DIARIO, Decimal("200.00"), Decimal("850.00"), datetime.datetime(2026, 3, 22, 10, 0), "[DEMO] Fertirriego post-cosecha Cuadro 1")
    ParteDiarioInsumo.objects.create(
        parte_diario=pd_riego_post,
        insumo=insumos['INS-UREA-01'],
        deposito_origen=dep_central,
        cantidad_utilizada=Decimal("200.00"),
        dosis_por_hectarea="5.7 kg/ha",
        costo_unitario_aplicado_ars=Decimal("850.00"),
        costo_total_ars=Decimal("170000.00"),
        movimiento_stock_generado=mov_urea_mar
    )

    # Ajuste Físico de Fin de Trimestre Marzo (30/03/2026)
    _registrar_movimiento(insumos['INS-GASOIL-01'], dep_central, MovimientoStock.TipoMovimiento.AJUSTE_NEGATIVO, Decimal("50.00"), Decimal("1150.00"), datetime.datetime(2026, 3, 30, 17, 0), "[DEMO] Ajuste trimestral por diferencia de aforo y evaporación en cisterna", ref="AJU-20260330")

    # Asistencias Marzo
    dias_mar = [datetime.date(2026, 3, d) for d in range(2, 31, 2) if datetime.date(2026, 3, d).weekday() < 6]
    for d in dias_mar:
        for leg, emp in empleados.items():
            RegistroAsistencia.objects.get_or_create(
                empleado=emp,
                fecha=d,
                defaults={
                    'finca': finca_norte,
                    'estado': RegistroAsistencia.Estado.PRESENTE,
                    'horas_normales': Decimal("8.0"),
                    'jornal_computado': Decimal("1.00"),
                    'observaciones': '[DEMO] Jornada de cosecha y molienda'
                }
            )

    # Liquidación Marzo
    periodo_mar, _ = PeriodoLiquidacion.objects.get_or_create(
        mes=3,
        ano=2026,
        tipo=PeriodoLiquidacion.TipoPeriodo.MENSUAL,
        defaults={
            'fecha_inicio': datetime.date(2026, 3, 1),
            'fecha_fin': datetime.date(2026, 3, 31),
            'estado': PeriodoLiquidacion.Estado.CALCULADO,
            'observaciones': '[DEMO] Haberes mensuales UATRE Marzo 2026 con jornales de cosecha'
        }
    )
    for leg, emp in empleados.items():
        bruto = emp.valor_jornal_base_ars * Decimal("25")
        ret = bruto * Decimal("0.185")
        neto = bruto - ret
        liq_mar, _ = LiquidacionEmpleado.objects.get_or_create(
            periodo=periodo_mar,
            empleado=emp,
            defaults={
                'dias_jornales_computados': Decimal("25.00"),
                'horas_normales': Decimal("200.0"),
                'total_bruto_remunerativo_ars': bruto,
                'total_retenciones_ars': ret,
                'neto_a_cobrar_ars': neto,
                'estado': LiquidacionEmpleado.Estado.APROBADO
            }
        )
        ItemLiquidacion.objects.get_or_create(liquidacion=liq_mar, codigo_concepto="101", defaults={'descripcion': "Básico Mensual Jornal Rural", 'tipo': ItemLiquidacion.TipoConcepto.REMUNERATIVO, 'importe_ars': bruto})
        ItemLiquidacion.objects.get_or_create(liquidacion=liq_mar, codigo_concepto="501", defaults={'descripcion': "Aportes Jubilación y Ley 19032 (14%)", 'tipo': ItemLiquidacion.TipoConcepto.RETENCION, 'importe_ars': bruto * Decimal("0.14")})
        ItemLiquidacion.objects.get_or_create(liquidacion=liq_mar, codigo_concepto="502", defaults={'descripcion': "Obra Social OSPRERA (3%)", 'tipo': ItemLiquidacion.TipoConcepto.RETENCION, 'importe_ars': bruto * Decimal("0.03")})

    # Comprobantes Fiscales Marzo 2026 (Compras)
    fact_ypf_mar, _ = ComprobanteFiscal.objects.update_or_create(
        tipo_operacion=ComprobanteFiscal.TipoOperacion.COMPRA,
        tipo_comprobante=ComprobanteFiscal.TipoComprobante.FACTURA_A,
        punto_de_venta="00001",
        numero_comprobante="00034100",
        cuit="30-54668997-1",
        defaults={
            'cuenta_corriente': prov_ypf,
            'razon_social': "YPF Directo Agro La Rioja S.A.",
            'condicion_iva': ComprobanteFiscal.CondicionIVA.RESPONSABLE_INSCRIPTO,
            'fecha_emision': datetime.date(2026, 3, 5),
            'fecha_vencimiento': datetime.date(2026, 3, 20),
            'concepto': "[DEMO] Factura A Gasoil Grado 2 Cosecha (5.000 L a $1.150)",
            'neto_gravado_21': Decimal("5750000.00"),
            'iva_21': Decimal("1207500.00"),
            'total': Decimal("6957500.00"),
            'estado_pago': ComprobanteFiscal.EstadoPago.PAGO_PARCIAL,
            'saldo_pendiente': Decimal("5132000.00"),
            'cae': "74030511223344",
            'vto_cae': datetime.date(2026, 3, 15),
            'es_oficial': True,
            'cuenta_contable': cta_agro_act,
            'centro_de_costo': cc_prod_norte
        }
    )

    fact_envases_mar, _ = ComprobanteFiscal.objects.update_or_create(
        tipo_operacion=ComprobanteFiscal.TipoOperacion.COMPRA,
        tipo_comprobante=ComprobanteFiscal.TipoComprobante.FACTURA_A,
        punto_de_venta="00003",
        numero_comprobante="00018940",
        cuit="30-68901234-5",
        defaults={
            'cuenta_corriente': prov_envases,
            'razon_social': "Envases y Cristales Cuyanos S.A.",
            'condicion_iva': ComprobanteFiscal.CondicionIVA.RESPONSABLE_INSCRIPTO,
            'fecha_emision': datetime.date(2026, 3, 12),
            'fecha_vencimiento': datetime.date(2026, 4, 12),
            'concepto': "[DEMO] Compra 350 Bines plásticos apilables 500kg cosecha y bidones",
            'neto_gravado_21': Decimal("5367768.60"),
            'iva_21': Decimal("1127231.40"),
            'total': Decimal("6495000.00"),
            'estado_pago': ComprobanteFiscal.EstadoPago.PENDIENTE,
            'saldo_pendiente': Decimal("6495000.00"),
            'cae': "74031299887766",
            'vto_cae': datetime.date(2026, 3, 22),
            'es_oficial': True,
            'centro_de_costo': cc_prod_norte
        }
    )

    fact_contratista_mar, _ = ComprobanteFiscal.objects.update_or_create(
        tipo_operacion=ComprobanteFiscal.TipoOperacion.COMPRA,
        tipo_comprobante=ComprobanteFiscal.TipoComprobante.FACTURA_A,
        punto_de_venta="00001",
        numero_comprobante="00000840",
        cuit="30-71987654-3",
        defaults={
            'cuenta_corriente': prov_contratista,
            'razon_social': "Servicios Agro-Mecánicos del Valle S.R.L.",
            'condicion_iva': ComprobanteFiscal.CondicionIVA.RESPONSABLE_INSCRIPTO,
            'fecha_emision': datetime.date(2026, 3, 24),
            'fecha_vencimiento': datetime.date(2026, 3, 25),
            'concepto': "[DEMO] Servicio Cosecha Mecánica Vibradora y Flete a Tolva",
            'neto_gravado_21': Decimal("1980000.00"),
            'iva_21': Decimal("415800.00"),
            'total': Decimal("2395800.00"),
            'estado_pago': ComprobanteFiscal.EstadoPago.PAGADA,
            'saldo_pendiente': Decimal("0.00"),
            'cae': "74032412345678",
            'vto_cae': datetime.date(2026, 4, 3),
            'es_oficial': True,
            'centro_de_costo': cc_prod_norte
        }
    )

    fact_edelar_mar, _ = ComprobanteFiscal.objects.update_or_create(
        tipo_operacion=ComprobanteFiscal.TipoOperacion.COMPRA,
        tipo_comprobante=ComprobanteFiscal.TipoComprobante.FACTURA_A,
        punto_de_venta="00012",
        numero_comprobante="00465100",
        cuit="30-67891234-9",
        defaults={
            'cuenta_corriente': prov_edelar,
            'razon_social': "EDELAR S.A.",
            'condicion_iva': ComprobanteFiscal.CondicionIVA.RESPONSABLE_INSCRIPTO,
            'fecha_emision': datetime.date(2026, 3, 22),
            'fecha_vencimiento': datetime.date(2026, 4, 8),
            'concepto': "[DEMO] Suministro Energía Eléctrica Riego y Almazara - Marzo 2026",
            'neto_gravado_27': Decimal("980000.00"),
            'iva_27': Decimal("264600.00"),
            'total': Decimal("1244600.00"),
            'estado_pago': ComprobanteFiscal.EstadoPago.PENDIENTE,
            'saldo_pendiente': Decimal("1244600.00"),
            'cae': "74032288990011",
            'vto_cae': datetime.date(2026, 4, 1),
            'es_oficial': True,
            'centro_de_costo': cc_prod_norte
        }
    )

    # Ventas Marzo (Libro IVA Ventas y Cuentas por Cobrar)
    cta_vtas_fresco = CuentaContable.objects.filter(codigo='4.1.1.01.000000').first()
    cta_vtas_aceite = CuentaContable.objects.filter(codigo='4.1.2.01.000000').first()
    cta_vtas_export = CuentaContable.objects.filter(codigo='4.1.2.03.000000').first()

    fact_venta_gourmet_mar, _ = ComprobanteFiscal.objects.update_or_create(
        tipo_operacion=ComprobanteFiscal.TipoOperacion.VENTA,
        tipo_comprobante=ComprobanteFiscal.TipoComprobante.FACTURA_A,
        punto_de_venta="00001",
        numero_comprobante="00000127",
        cuit="30-70891234-5",
        defaults={
            'cuenta_corriente': cli_gourmet,
            'razon_social': "Aceitunas Riojanas Gourmet S.A.",
            'condicion_iva': ComprobanteFiscal.CondicionIVA.RESPONSABLE_INSCRIPTO,
            'fecha_emision': datetime.date(2026, 3, 15),
            'fecha_vencimiento': datetime.date(2026, 4, 15),
            'concepto': "[DEMO] Venta 15.000 kg Aceituna Arauco Verde Mesa Calibre 120/140",
            'neto_gravado_21': Decimal("20000000.00"),
            'iva_21': Decimal("4200000.00"),
            'total': Decimal("24200000.00"),
            'estado_pago': ComprobanteFiscal.EstadoPago.PAGO_PARCIAL,
            'saldo_pendiente': Decimal("16300000.00"),
            'cae': "74031544556677",
            'vto_cae': datetime.date(2026, 3, 25),
            'es_oficial': True,
            'cuenta_contable': cta_vtas_fresco,
            'centro_de_costo': cc_prod_norte
        }
    )

    fact_venta_aceites_mar, _ = ComprobanteFiscal.objects.update_or_create(
        tipo_operacion=ComprobanteFiscal.TipoOperacion.VENTA,
        tipo_comprobante=ComprobanteFiscal.TipoComprobante.FACTURA_A,
        punto_de_venta="00001",
        numero_comprobante="00000128",
        cuit="30-55443322-1",
        defaults={
            'cuenta_corriente': cli_local,
            'razon_social': "Aceites del Sol Mayorista S.A.",
            'condicion_iva': ComprobanteFiscal.CondicionIVA.RESPONSABLE_INSCRIPTO,
            'fecha_emision': datetime.date(2026, 3, 20),
            'fecha_vencimiento': datetime.date(2026, 4, 20),
            'concepto': "[DEMO] Venta 40.000 L Aceite de Oliva Virgen Extra Granel en Cisterna",
            'neto_gravado_21': Decimal("38000000.00"),
            'iva_21': Decimal("7980000.00"),
            'percepcion_iibb': Decimal("1140000.00"),
            'percepcion_iva': Decimal("473600.00"),
            'total': Decimal("47593600.00"),
            'estado_pago': ComprobanteFiscal.EstadoPago.PAGO_PARCIAL,
            'saldo_pendiente': Decimal("29093600.00"),
            'cae': "74032011223344",
            'vto_cae': datetime.date(2026, 3, 30),
            'es_oficial': True,
            'cuenta_contable': cta_vtas_aceite,
            'centro_de_costo': cc_almazara
        }
    )

    fact_venta_export_mar, _ = ComprobanteFiscal.objects.update_or_create(
        tipo_operacion=ComprobanteFiscal.TipoOperacion.VENTA,
        tipo_comprobante=ComprobanteFiscal.TipoComprobante.FACTURA_A,
        punto_de_venta="00001",
        numero_comprobante="00000015",
        cuit="30-99876543-2",
        defaults={
            'cuenta_corriente': cli_exterior,
            'razon_social': "Mediterráneo Trading Imports LLC / Suc. Arg.",
            'condicion_iva': ComprobanteFiscal.CondicionIVA.EXENTO,
            'fecha_emision': datetime.date(2026, 3, 24),
            'fecha_vencimiento': datetime.date(2026, 4, 24),
            'concepto': "[DEMO] Factura E 00001-00000015 Exportación Aceite Virgen Extra a Granel",
            'exento': Decimal("176000000.00"),
            'total': Decimal("176000000.00"),
            'estado_pago': ComprobanteFiscal.EstadoPago.PAGO_PARCIAL,
            'saldo_pendiente': Decimal("117700000.00"),
            'cae': "74032499112233",
            'vto_cae': datetime.date(2026, 4, 3),
            'es_oficial': True,
            'cuenta_contable': cta_vtas_export,
            'centro_de_costo': cc_admin
        }
    )

    # Movimientos Financieros Marzo 2026
    mov_pago_ypf_mar = MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 3, 8),
        importe=Decimal("1825500.00"),
        moneda="ARS",
        concepto="[DEMO] Pago anticipo suministro Gasoil Cosecha Factura A 0001-00034100",
        cuenta_corriente=prov_ypf,
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        comprobante_tipo="Transferencia",
        comprobante_nro="TRF-912845",
        usuario=usuario
    )
    mov_caja_flete_mar = MovimientoFinanciero.objects.create(
        cuenta=caja_finca,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 3, 14),
        importe=Decimal("350000.00"),
        moneda="ARS",
        concepto="[DEMO] Anticipo viáticos y combustible camionetas cuadrilla cosecha",
        cuenta_corriente=prov_contratista,
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        comprobante_tipo="Recibo",
        comprobante_nro="RC-0012",
        usuario=usuario
    )
    mov_pago_sueldos_mar = MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 3, 20),
        importe=Decimal("6140000.00"),
        moneda="ARS",
        concepto="[DEMO] Pago Liquidación Haberes UATRE Febrero 2026",
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        comprobante_tipo="Acreditación Haberes",
        comprobante_nro="HAB-202603",
        usuario=usuario
    )
    mov_cobro_local_mar = MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.INGRESO,
        fecha=datetime.date(2026, 3, 22),
        importe=Decimal("18500000.00"),
        moneda="ARS",
        concepto="[DEMO] Cobranza Venta Aceite de Oliva Virgen Extra - Factura A 0001-00000128",
        cuenta_corriente=cli_local,
        centro_de_costo=cc_almazara,
        finca=finca_norte,
        comprobante_tipo="Transferencia",
        comprobante_nro="TRF-889012",
        usuario=usuario
    )
    mov_pago_contratista_mar = MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 3, 25),
        importe=Decimal("2395800.00"),
        moneda="ARS",
        concepto="[DEMO] Transferencia CBU Pago Factura A 0001-00000840 Cosecha Mecánica y Flete",
        cuenta_corriente=prov_contratista,
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        comprobante_tipo="Transferencia",
        comprobante_nro="TRF-931084",
        usuario=usuario
    )
    mov_pago_flete_mar = MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 3, 26),
        importe=Decimal("1980000.00"),
        moneda="ARS",
        concepto="[DEMO] Pago Flete y Servicio de Cosecha Mecánica Vibradora",
        cuenta_corriente=prov_contratista,
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        comprobante_tipo="Transferencia",
        comprobante_nro="TRF-934500",
        usuario=usuario
    )
    mov_cobro_export_mar = MovimientoFinanciero.objects.create(
        cuenta=cta_banco_usd,
        tipo=MovimientoFinanciero.TipoMovimiento.INGRESO,
        fecha=datetime.date(2026, 3, 27),
        importe=Decimal("68000.00"),
        moneda="USD",
        tipo_cambio=Decimal("1100.00"),
        concepto="[DEMO] Liquidación Divisas Cobranza Exportación Aceite Virgen Extra Permiso 26001",
        cuenta_corriente=cli_exterior,
        centro_de_costo=cc_admin,
        comprobante_tipo="Transferencia SWIFT",
        comprobante_nro="SWIFT-689102",
        usuario=usuario
    )
    mov_caja_admin_mar = MovimientoFinanciero.objects.create(
        cuenta=caja_admin,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 3, 28),
        importe=Decimal("180000.00"),
        moneda="ARS",
        concepto="[DEMO] Gastos de courier internacional y certificaciones de origen para exportación",
        centro_de_costo=cc_admin,
        comprobante_tipo="Ticket",
        comprobante_nro="TK-00452",
        usuario=usuario
    )

    # Cheques Marzo 2026 (Cartera y Emitidos)
    cheque_gourmet_mar, _ = Cheque.objects.update_or_create(
        numero="33445566",
        banco_emisor="Banco Santander Río",
        defaults={
            'cuenta_bancaria_origen': cta_banco_ars,
            'emisor_firmante': "Aceitunas Riojanas Gourmet S.A.",
            'cuit_emisor': "30-70891234-5",
            'tipo': Cheque.TipoCheque.RECIBIDO_TERCERO,
            'cuenta_corriente': cli_gourmet,
            'importe': Decimal("7900000.00"),
            'fecha_emision': datetime.date(2026, 3, 15),
            'fecha_cobro': datetime.date(2026, 4, 15),
            'estado': Cheque.EstadoCheque.EN_CARTERA,
            'observaciones': "[DEMO] Cheque de pago diferido 30 días recibido por venta de aceituna Arauco verde mesa"
        }
    )

    cheque_aceites_mar, _ = Cheque.objects.update_or_create(
        numero="44556677",
        banco_emisor="Banco Macro",
        defaults={
            'cuenta_bancaria_origen': cta_banco_ars,
            'emisor_firmante': "Aceites del Sol Mayorista S.A.",
            'cuit_emisor': "30-55443322-1",
            'tipo': Cheque.TipoCheque.RECIBIDO_TERCERO,
            'cuenta_corriente': cli_local,
            'importe': Decimal("10000000.00"),
            'fecha_emision': datetime.date(2026, 3, 20),
            'fecha_cobro': datetime.date(2026, 4, 20),
            'estado': Cheque.EstadoCheque.EN_CARTERA,
            'observaciones': "[DEMO] Cheque diferido recibido a cuenta Factura A 0001-00000128"
        }
    )

    cheque_envases_mar, _ = Cheque.objects.update_or_create(
        numero="88341202",
        banco_emisor="Banco Galicia",
        defaults={
            'cuenta_bancaria_origen': cta_banco_ars,
            'emisor_firmante': "Olivar del Valle Agroindustrial S.A.",
            'cuit_emisor': "30-71458923-4",
            'tipo': Cheque.TipoCheque.EMITIDO_PROPIO,
            'cuenta_corriente': prov_envases,
            'importe': Decimal("3500000.00"),
            'fecha_emision': datetime.date(2026, 3, 25),
            'fecha_cobro': datetime.date(2026, 4, 25),
            'estado': Cheque.EstadoCheque.ENTREGADO_PROVEEDOR,
            'observaciones': "[DEMO] Cheque de pago diferido emitido a Envases Cuyanos S.A. a 30 días"
        }
    )

    # Orden de Pago y Recibo Marzo 2026
    OrdenPagoRecibo.objects.create(
        tipo=OrdenPagoRecibo.TipoDocumento.ORDEN_PAGO,
        numero="OP-2026-0002",
        fecha=datetime.date(2026, 3, 25),
        cuenta_corriente=prov_contratista,
        cuenta_financiera=cta_banco_ars,
        importe_total=Decimal("2395800.00"),
        medio_pago=OrdenPagoRecibo.MedioPago.TRANSFERENCIA,
        comprobante_fiscal=fact_contratista_mar,
        movimiento_financiero=mov_pago_contratista_mar,
        concepto="[DEMO] Pago total Servicio Cosecha Mecánica Factura A 0001-00000840",
        beneficiario_firmante="Servicios Agro-Mecánicos del Valle S.R.L.",
        usuario=usuario
    )

    OrdenPagoRecibo.objects.create(
        tipo=OrdenPagoRecibo.TipoDocumento.RECIBO_COBRANZA,
        numero="RC-2026-0001",
        fecha=datetime.date(2026, 3, 15),
        cuenta_corriente=cli_gourmet,
        cuenta_financiera=cta_banco_ars,
        importe_total=Decimal("7900000.00"),
        medio_pago=OrdenPagoRecibo.MedioPago.CHEQUE_TERCERO,
        cheque=cheque_gourmet_mar,
        comprobante_fiscal=fact_venta_gourmet_mar,
        concepto="[DEMO] Cobro parcial Factura A 0001-00000127 mediante Cheque Santander #33445566",
        beneficiario_firmante="Aceitunas Riojanas Gourmet S.A.",
        usuario=usuario
    )

    # Conciliación Bancaria Marzo 2026 (En Proceso / Borrador con $5M de diferencia)
    ConciliacionBancaria.objects.get_or_create(
        cuenta=cta_banco_ars,
        fecha_extracto=datetime.date(2026, 3, 31),
        defaults={
            'saldo_extracto': Decimal("75814400.00"),
            'saldo_sistema': Decimal("70814400.00"),
            'diferencia': Decimal("5000000.00"),
            'estado': 'EN_PROCESO',
            'observaciones': "[DEMO] Conciliación Marzo 2026 en proceso. Diferencia de $5.000.000 por depósito pendiente de acreditación en 48hs.",
            'usuario': usuario
        }
    )

    # Arqueo de Caja Finca Marzo 2026 (Cerrado)
    ArqueoCaja.objects.get_or_create(
        cuenta=caja_finca,
        fecha=datetime.date(2026, 3, 31),
        defaults={
            'hora': datetime.time(18, 0),
            'saldo_sistema': Decimal("1850000.00"),
            'saldo_real_contado': Decimal("1850000.00"),
            'diferencia': Decimal("0.00"),
            'estado': ArqueoCaja.Estado.CERRADO,
            'observaciones': "[DEMO] Arqueo fin de mes Marzo 2026 verificado sin faltantes ni sobrantes.",
            'usuario': usuario
        }
    )

    # 7.1 Imputación de Costos por Centro (Q1 2026) - Calidad y Trazabilidad Completa
    costos_q1_data = [
        # ── ENERO 2026 ────────────────────────────────────────────────────────
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2026, 1, 18), Decimal("320000.00"), Decimal("1050.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Jornales fertirriego nocturno Cuadro Arbequina", "ParteDiario", pd_riego_ene.id, None, None),
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2026, 1, 18), Decimal("247500.00"), Decimal("1050.00"), CostoPorCentro.TipoOrigen.INSUMO, "[DEMO] Nitrato de potasio soluble aplicado en fertirriego", "ParteDiario", pd_riego_ene.id, prov_agroquimica, None),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 1, 22), Decimal("35000.00"), Decimal("1050.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Jornal tractorista pasada de rastra Cuadro Arauco", "ParteDiario", pd_laboreo.id, None, None),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 1, 22), Decimal("392000.00"), Decimal("1050.00"), CostoPorCentro.TipoOrigen.COMBUSTIBLE_MAQUINARIA, "[DEMO] Gasoil tractor John Deere laboreo y desmalezado", "ParteDiario", pd_laboreo.id, prov_ypf, mov_pago_ypf_ene),
        (cc_prod_norte, finca_norte, None, datetime.date(2026, 1, 25), Decimal("520000.00"), Decimal("1050.00"), CostoPorCentro.TipoOrigen.ENERGIA_RIEGO, "[DEMO] Factura EDELAR bombeo Pozo 1 - Enero 2026", "FacturaServicio", 101, prov_edelar, mov_pago_edelar_feb),
        (cc_prod_sur, finca_sur, cuadro_c3, datetime.date(2026, 1, 20), Decimal("280000.00"), Decimal("1050.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Jornales de riego y mantenimiento de goteros Finca Sur", "ParteDiario", None, None, None),
        (cc_prod_sur, finca_sur, None, datetime.date(2026, 1, 26), Decimal("380000.00"), Decimal("1050.00"), CostoPorCentro.TipoOrigen.ENERGIA_RIEGO, "[DEMO] Energía eléctrica trifásica bombeo de pozo Finca Sur", "FacturaServicio", 102, prov_edecat, mov_pago_edecat_feb),

        # ── FEBRERO 2026 ──────────────────────────────────────────────────────
        (cc_prod_norte, finca_norte, None, datetime.date(2026, 2, 10), Decimal("480000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.MANTENIMIENTO, "[DEMO] Service preventivo, lubricantes y filtros Tractor John Deere", "FacturaTaller", 201, prov_taller, mov_pago_taller_feb),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 2, 16), Decimal("48125.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Jornal tractorista atomizadora cura repilo", "ParteDiario", pd_cura_feb.id, None, None),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 2, 16), Decimal("1015000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.INSUMO, "[DEMO] Oxicloruro de cobre 50% cura sanitaria repilo", "ParteDiario", pd_cura_feb.id, prov_agroquimica, None),
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2026, 2, 20), Decimal("35000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Jornal tractorista aplicación herbicida", "ParteDiario", pd_desm.id, None, None),
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2026, 2, 20), Decimal("368000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.INSUMO, "[DEMO] Glifosato 48% control de malezas en ruedo", "ParteDiario", pd_desm.id, prov_agroquimica, None),
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2026, 2, 20), Decimal("280000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.COMBUSTIBLE_MAQUINARIA, "[DEMO] Gasoil tractor pulverizador malezas", "ParteDiario", pd_desm.id, prov_ypf, None),
        (cc_prod_norte, finca_norte, None, datetime.date(2026, 2, 22), Decimal("1250000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.ENERGIA_RIEGO, "[DEMO] Factura EDELAR energía eléctrica bombeo Pozo 1 - Febrero 2026", "FacturaServicio", 202, prov_edelar, None),
        (cc_prod_sur, finca_sur, cuadro_c3, datetime.date(2026, 2, 18), Decimal("310000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Tratamiento preventivo repilo en Cuadro Picual Pomán", "ParteDiario", None, None, None),
        (cc_prod_sur, finca_sur, cuadro_c3, datetime.date(2026, 2, 18), Decimal("725000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.INSUMO, "[DEMO] Oxicloruro de cobre aplicado en Finca Sur", "ParteDiario", None, prov_agroquimica, None),

        # ── MARZO 2026 ────────────────────────────────────────────────────────
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 3, 8), Decimal("114000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Jornales cuadrilla cosecha manual aceituna Arauco", "ParteDiario", pd_cosecha.id, None, None),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 3, 8), Decimal("517500.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.COMBUSTIBLE_MAQUINARIA, "[DEMO] Gasoil tractores acarreo de bines de cosecha a playón", "ParteDiario", pd_cosecha.id, prov_ypf, mov_pago_ypf_mar),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 3, 12), Decimal("1336000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Continuación cuadrilla cosecha manual aceituna verde mesa", "ParteDiario", None, None, None),
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2026, 3, 18), Decimal("48125.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Operador cosechadora cabalgante vibradora", "ParteDiario", pd_cos_mec.id, None, None),
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2026, 3, 18), Decimal("1035000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.COMBUSTIBLE_MAQUINARIA, "[DEMO] Gasoil cosechadora vibradora y tractores acarreadores", "ParteDiario", pd_cos_mec.id, prov_ypf, None),
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2026, 3, 20), Decimal("1841875.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Operadores y choferes cierre de cosecha mecánica", "ParteDiario", None, None, None),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 3, 22), Decimal("32000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Regador turno fertirriego post-cosecha", "ParteDiario", pd_riego_post.id, None, None),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 3, 22), Decimal("170000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.INSUMO, "[DEMO] Urea soluble fertirriego recuperador post-cosecha", "ParteDiario", pd_riego_post.id, prov_agroquimica, None),
        (cc_prod_norte, finca_norte, None, datetime.date(2026, 3, 25), Decimal("1980000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.SERVICIO_CONTRATISTA, "[DEMO] Servicio contratado de cosecha mecánica cabalgante y flete", "FacturaProveedor", 301, prov_contratista, mov_pago_contratista_mar),
        (cc_prod_sur, finca_sur, cuadro_c3, datetime.date(2026, 3, 24), Decimal("950000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Cuadrilla de cosecha manual variedad Picual Pomán", "ParteDiario", None, None, None),
        (cc_almazara, finca_norte, None, datetime.date(2026, 3, 25), Decimal("980000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.ENERGIA_RIEGO, "[DEMO] Energía eléctrica molienda, batido y centrífuga almazara", "FacturaServicio", 302, prov_edelar, None),
        (cc_admin, finca_norte, None, datetime.date(2026, 3, 28), Decimal("750000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.ESTRUCTURA_ADMIN, "[DEMO] Gastos operativos de estructura, logística y aduana exportación", "LiquidacionGasto", 303, None, mov_caja_admin_mar),
        (cc_prod_chi, finca_chi, cuadro_d4, datetime.date(2026, 1, 24), Decimal("310000.00"), Decimal("1050.00"), CostoPorCentro.TipoOrigen.INSUMO, "[DEMO] Fertilizante soluble NPK Finca Chilecito", "ParteDiario", None, prov_agroquimica, None),
        (cc_prod_chi, finca_chi, cuadro_d4, datetime.date(2026, 2, 22), Decimal("295000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Jornales poda y desbrote Cuadro Manzanilla Chilecito", "ParteDiario", None, None, None),
        (cc_prod_chi, finca_chi, cuadro_d4, datetime.date(2026, 3, 14), Decimal("980000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Cuadrilla cosecha manual Manzanilla Chilecito", "ParteDiario", None, None, None),
        # ── CAMPAÑA ANTERIOR 2024/2025 (Histórico para comparativas) ─────────
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2024, 11, 20), Decimal("450000.00"), Decimal("920.00"), CostoPorCentro.TipoOrigen.INSUMO, "[DEMO] Fertilizante foliar Cuadro Arauco 2024/2025", "ParteDiario", None, prov_agroquimica, None),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2025, 3, 10), Decimal("1850000.00"), Decimal("950.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Cosecha manual Arauco 2024/2025", "ParteDiario", None, None, None),
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2024, 12, 15), Decimal("520000.00"), Decimal("930.00"), CostoPorCentro.TipoOrigen.COMBUSTIBLE_MAQUINARIA, "[DEMO] Gasoil labores mecanizadas Arbequina 2024/2025", "ParteDiario", None, prov_ypf, None),
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2025, 3, 18), Decimal("2150000.00"), Decimal("950.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Cosecha mecánica cabalgante Arbequina 2024/2025", "ParteDiario", None, None, None),
        (cc_prod_sur, finca_sur, cuadro_c3, datetime.date(2025, 3, 22), Decimal("1320000.00"), Decimal("950.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Cosecha Picual Pomán 2024/2025", "ParteDiario", None, None, None),
        (cc_prod_chi, finca_chi, cuadro_d4, datetime.date(2025, 3, 15), Decimal("1100000.00"), Decimal("950.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Cosecha Manzanilla Chilecito 2024/2025", "ParteDiario", None, None, None),
    ]
    for cc, fin, cua, fec, imp, tc_mes, torig, desc, d_tipo, d_id, prov_obj, mov_obj in costos_q1_data:
        costo_existente = CostoPorCentro.objects.filter(
            centro_de_costo=cc,
            finca=fin,
            cuadro=cua,
            fecha=fec,
            tipo_origen=torig,
            descripcion=desc
        ).first()
        if not costo_existente:
            CostoPorCentro.objects.create(
                centro_de_costo=cc,
                finca=fin,
                cuadro=cua,
                fecha=fec,
                tipo_origen=torig,
                importe_ars=imp,
                importe_usd=round(imp / tc_mes, 2),
                cuenta_contable=resolver_cuenta_contable_defecto(torig, cc),
                proveedor=prov_obj,
                movimiento_financiero=mov_obj,
                descripcion=desc,
                documento_origen_tipo=d_tipo,
                documento_origen_id=d_id,
                campana=calcular_campana_desde_fecha(fec),
            )
        else:
            costo_existente.proveedor = prov_obj
            costo_existente.movimiento_financiero = mov_obj
            costo_existente.importe_ars = imp
            costo_existente.importe_usd = round(imp / tc_mes, 2)
            costo_existente.campana = calcular_campana_desde_fecha(fec)
            costo_existente.save()

    # 7.1 Tipos de Cambio Mensuales Oficiales Q1 2026
    tcs_demo = [
        (2026, 1, Decimal("1050.00"), "Banco Nación (BNA) / Cierre Enero 2026"),
        (2026, 2, Decimal("1080.00"), "Banco Nación (BNA) / Cierre Febrero 2026"),
        (2026, 3, Decimal("1100.00"), "Banco Nación (BNA) / Cierre Marzo 2026"),
    ]
    for ano, mes, tc, fuente in tcs_demo:
        TipoCambioMensual.objects.update_or_create(
            empresa=empresa,
            ano=ano,
            mes=mes,
            defaults={'tc': tc, 'fuente': fuente}
        )

    # 8. Estado de Resultados (Cuadro de Resultados) del 1° Trimestre 2026 (P&L Q1) en ARS
    cuadro_q1, _ = CuadroResultado.objects.get_or_create(
        empresa=empresa,
        titulo="Estado de Resultados 1° Trimestre 2026 (Q1: Ene - Mar)",
        defaults={
            'tipo_periodo': CuadroResultado.TipoPeriodo.TRIMESTRAL,
            'fecha_inicio': datetime.date(2026, 1, 1),
            'fecha_fin': datetime.date(2026, 3, 31),
            'moneda': CuadroResultado.Moneda.ARS,
            'tipo_cambio': Decimal("1050.00"),
            'volumen_aceituna_kg': Decimal("140000.00"),
            'volumen_aceite_litros': Decimal("25000.00"),
            'estado': CuadroResultado.EstadoCuadro.APROBADO_DIRECTORIO,
            'notas_gerencia': (
                "Informe Consolidado del 1° Trimestre 2026 (Enero a Marzo 2026):\n\n"
                "• Se completó la etapa crítica de fertirriego estival con óptimo desarrollo del fruto.\n"
                "• En marzo se cosecharon 48.000 kg de Arauco para aceituna de mesa verde y 92.000 kg de Arbequina para almazara (17.8% rinde graso).\n"
                "• Facturación neta consolidada en Pesos Argentinos ($510.384.000 ARS) equivalente a u$s 486.080 USD al tipo de cambio oficial promedio ($1.050 ARS/USD).\n"
                "• Los costos agrícolas e industriales se encuentran en línea con las metas presupuestarias de campaña."
            )
        }
    )
    # Si ya existía, asegurarse que la moneda sea ARS
    if cuadro_q1.moneda != CuadroResultado.Moneda.ARS:
        cuadro_q1.moneda = CuadroResultado.Moneda.ARS
        cuadro_q1.save(update_fields=['moneda'])

    poblar_lineas_cuadro(cuadro_q1, inicializar_con_valores_demo=True)
    cuadro_q1.recalcular_totales(save=True)

    # 9. Consolidación Final y Verificación Matemática de Stock
    for ins_obj in insumos.values():
        total_dep = StockPorDeposito.objects.filter(insumo=ins_obj).aggregate(t=Sum('cantidad'))['t'] or Decimal('0.00')
        ins_obj.stock_actual = total_dep
        ins_obj.save(update_fields=['stock_actual'])

    stats['estado'] = 'OK'
    stats['mensaje'] = "Datos de prueba del 1° Trimestre 2026 (Ene-Mar) generados con éxito en Pesos Argentinos (ARS)."
    return stats


@transaction.atomic
def limpiar_datos_demo_q1_2026():
    """
    Elimina con total seguridad todos los registros transaccionales de prueba
    comprendidos entre 2026-01-01 y 2026-03-31 o identificados con [DEMO],
    dejando intacta la estructura base de Empresa, Fincas, Cuadros, Plan de Cuentas y Usuarios.
    """
    desde = datetime.date(2026, 1, 1)
    hasta = datetime.date(2026, 3, 31)
    desde_dt = timezone.make_aware(datetime.datetime(2026, 1, 1, 0, 0, 0))
    hasta_dt = timezone.make_aware(datetime.datetime(2026, 3, 31, 23, 59, 59))

    reporte = {}

    # 1. Cuadros de Resultados Q1 y Tipos de Cambio
    q_cuadros = CuadroResultado.objects.filter(fecha_inicio__gte=desde, fecha_fin__lte=hasta)
    reporte['cuadros_resultado'] = q_cuadros.count()
    q_cuadros.delete()

    q_tc = TipoCambioMensual.objects.filter(ano=2026, mes__in=[1, 2, 3])
    reporte['tipos_cambio'] = q_tc.count()
    q_tc.delete()

    # 2. Conciliaciones Bancarias
    q_concil = ConciliacionBancaria.objects.filter(
        models.Q(observaciones__startswith='[DEMO]') |
        models.Q(fecha_extracto__gte=desde, fecha_extracto__lte=hasta)
    )
    reporte['conciliaciones'] = q_concil.count()
    q_concil.delete()

    # 3. Cheques
    q_cheques = Cheque.objects.filter(
        models.Q(observaciones__startswith='[DEMO]') |
        models.Q(fecha_emision__gte=desde, fecha_emision__lte=hasta)
    )
    reporte['cheques'] = q_cheques.count()
    q_cheques.delete()

    # 3.1 Comprobantes Fiscales (Libro de IVA Compras y Ventas)
    q_facturas = ComprobanteFiscal.objects.filter(
        models.Q(concepto__startswith='[DEMO]') |
        models.Q(fecha_emision__gte=desde, fecha_emision__lte=hasta)
    )
    reporte['comprobantes_fiscales'] = q_facturas.count()
    q_facturas.delete()

    # 3.2 Órdenes de Pago y Recibos
    q_ops = OrdenPagoRecibo.objects.filter(
        models.Q(concepto__startswith='[DEMO]') |
        models.Q(fecha__gte=desde, fecha__lte=hasta)
    )
    reporte['ordenes_pago_recibos'] = q_ops.count()
    q_ops.delete()

    # 3.3 Arqueos de Caja
    q_arq = ArqueoCaja.objects.filter(
        models.Q(observaciones__startswith='[DEMO]') |
        models.Q(fecha__gte=desde, fecha__lte=hasta)
    )
    reporte['arqueos_caja'] = q_arq.count()
    q_arq.delete()

    # 4. Movimientos Financieros
    q_movs = MovimientoFinanciero.objects.filter(
        models.Q(concepto__startswith='[DEMO]') |
        models.Q(fecha__gte=desde, fecha__lte=hasta)
    )
    reporte['movimientos_financieros'] = q_movs.count()
    q_movs.delete()

    # 5. Liquidaciones y Períodos
    q_periodos = PeriodoLiquidacion.objects.filter(ano=2026, mes__in=[1, 2, 3])
    reporte['periodos_liquidacion'] = q_periodos.count()
    q_periodos.delete()

    # 6. Partes Diarios (Riego, Personal, Insumos) y OTs
    q_partes = ParteDiario.objects.filter(fecha__gte=desde, fecha__lte=hasta)
    reporte['partes_diarios'] = q_partes.count()
    q_partes.delete()

    q_ots = OrdenDeTrabajo.objects.filter(fecha_programada__gte=desde, fecha_programada__lte=hasta)
    reporte['ordenes_trabajo'] = q_ots.count()
    q_ots.delete()

    # 7. Asistencias
    q_asist = RegistroAsistencia.objects.filter(fecha__gte=desde, fecha__lte=hasta)
    reporte['asistencias'] = q_asist.count()
    q_asist.delete()

    # 8. Recepciones y Órdenes de Compra
    q_recep = RecepcionMercaderia.objects.filter(fecha_recepcion__gte=desde, fecha_recepcion__lte=hasta)
    reporte['recepciones_mercaderia'] = q_recep.count()
    q_recep.delete()

    q_ocs = OrdenDeCompra.objects.filter(fecha_emision__gte=desde, fecha_emision__lte=hasta)
    reporte['ordenes_compra'] = q_ocs.count()
    q_ocs.delete()

    # 9. Movimientos de Stock y Existencias
    q_stock = MovimientoStock.objects.filter(fecha__gte=desde_dt, fecha__lte=hasta_dt)
    reporte['movimientos_stock'] = q_stock.count()
    q_stock.delete()

    q_stock_dep = StockPorDeposito.objects.all()
    reporte['stock_por_deposito'] = q_stock_dep.count()
    q_stock_dep.delete()
    Insumo.objects.all().update(stock_actual=Decimal("0.00"))
    Insumo.objects.filter(codigo__in=['INS-GASOIL-AGRO', 'INS-UREA-46']).delete()

    # 10. Lotes de Cosecha, Eventos de Cuadro y Fenología
    q_lotes = LoteDeCosecha.objects.filter(
        models.Q(calidad_observaciones__startswith='[DEMO]') |
        models.Q(campana__in=["2024/2025", "2025/2026"])
    )
    reporte['lotes_cosecha'] = q_lotes.count()
    q_lotes.delete()

    q_eventos = EventoCuadro.objects.filter(fecha__gte=desde, fecha__lte=hasta)
    reporte['eventos_cuadro'] = q_eventos.count()
    q_eventos.delete()

    q_fenol = RegistroFenologico.objects.filter(fecha__gte=desde, fecha__lte=hasta)
    reporte['registros_fenologicos'] = q_fenol.count()
    q_fenol.delete()

    # 11. Mantenimientos de Maquinaria
    q_mants = MantenimientoMaquina.objects.filter(fecha__gte=desde, fecha__lte=hasta)
    reporte['mantenimientos_maquinaria'] = q_mants.count()
    q_mants.delete()

    # 11.1 Costos por Centro
    q_costos = CostoPorCentro.objects.filter(
        models.Q(descripcion__startswith='[DEMO]') |
        models.Q(fecha__gte=datetime.date(2024, 7, 1), fecha__lte=hasta)
    )
    reporte['costos_por_centro'] = q_costos.count()
    q_costos.delete()

    # 12. Empleados temporarios creados para la demo de cosecha
    q_emp_cosecha = Empleado.objects.filter(legajo__in=['LEG-007', 'LEG-008'])
    reporte['empleados_temporarios'] = q_emp_cosecha.count()
    q_emp_cosecha.delete()

    # 13. Restablecer saldos de entidades y cuentas demo a cero
    CuentaCorriente.objects.filter(
        cuit__in=[
            '30-71234567-0', '30-54668997-1', '30-67891234-9', '30-69123456-7',
            '30-68901234-5', '30-71987654-3', '30-65432198-7', '30-70891234-5',
            '30-55443322-1', '30-99876543-2'
        ]
    ).update(saldo_actual=Decimal('0.00'))

    Cuenta.objects.filter(
        nombre__in=[
            "Banco Galicia CC Operativa ARS", "Banco Santander CC Exportacion USD",
            "Caja Chica Finca Aimogasta", "Caja Administración Central"
        ]
    ).update(saldo_actual=Decimal('0.00'))

    reporte['estado'] = 'OK'
    reporte['mensaje'] = "Limpieza completada: todos los registros de prueba del 1° Trimestre 2026 fueron eliminados exitosamente."
    return reporte
