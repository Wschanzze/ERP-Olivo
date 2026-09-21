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
    ConciliacionBancaria, CuadroResultado, LineaCuadroResultado, TipoCambioMensual
)
from apps.finanzas.services import poblar_lineas_cuadro
from apps.costos.models import CostoPorCentro

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
            'saldo_actual': Decimal("28450000.00")
        }
    )
    cta_banco_usd, _ = Cuenta.objects.get_or_create(
        nombre="Banco Santander CC Exportacion USD",
        defaults={
            'empresa': empresa,
            'tipo': Cuenta.TipoCuenta.CUENTA_BANCARIA,
            'moneda': Cuenta.Moneda.USD,
            'banco_nombre': "Banco Santander",
            'numero_cuenta': "072-000098765/4",
            'saldo_actual': Decimal("142500.00")
        }
    )
    caja_finca, _ = Cuenta.objects.get_or_create(
        nombre="Caja Chica Finca Aimogasta",
        defaults={
            'empresa': empresa,
            'tipo': Cuenta.TipoCuenta.CAJA_EFECTIVO,
            'moneda': Cuenta.Moneda.ARS,
            'saldo_actual': Decimal("1850000.00")
        }
    )

    prov_agroquimica, _ = CuentaCorriente.objects.get_or_create(
        cuit="30-71234567-0",
        defaults={
            'tipo_entidad': CuentaCorriente.TipoEntidad.PROVEEDOR,
            'razon_social': "Agroquímica Cuyo & Cía S.A.",
            'nombre_comercial': "AgroQuím Cuyo",
            'saldo_actual': Decimal("-3200000.00")
        }
    )
    prov_ypf, _ = CuentaCorriente.objects.get_or_create(
        cuit="30-54668997-1",
        defaults={
            'tipo_entidad': CuentaCorriente.TipoEntidad.PROVEEDOR,
            'razon_social': "YPF Directo Agro La Rioja S.A.",
            'nombre_comercial': "YPF Directo",
            'saldo_actual': Decimal("-1450000.00")
        }
    )
    prov_envases, _ = CuentaCorriente.objects.get_or_create(
        cuit="30-68901234-5",
        defaults={
            'tipo_entidad': CuentaCorriente.TipoEntidad.PROVEEDOR,
            'razon_social': "Envases y Cristales Cuyanos S.A.",
            'nombre_comercial': "Envases Cuyanos",
            'saldo_actual': Decimal("-2100000.00")
        }
    )

    cli_exterior, _ = CuentaCorriente.objects.get_or_create(
        cuit="30-99876543-2",
        defaults={
            'tipo_entidad': CuentaCorriente.TipoEntidad.CLIENTE,
            'razon_social': "Mediterráneo Trading Imports LLC / Suc. Arg.",
            'nombre_comercial': "Mediterráneo Trading",
            'saldo_actual': Decimal("24500000.00")
        }
    )
    cli_local, _ = CuentaCorriente.objects.get_or_create(
        cuit="30-55443322-1",
        defaults={
            'tipo_entidad': CuentaCorriente.TipoEntidad.CLIENTE,
            'razon_social': "Aceites del Sol Mayorista S.A.",
            'nombre_comercial': "Aceites del Sol",
            'saldo_actual': Decimal("8900000.00")
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
        orden_de_trabajo=ot_riego_ene,
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
        orden_de_trabajo=ot_laboreo,
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

    # Movimientos Financieros Enero
    MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 1, 20),
        importe=Decimal("5025000.00"),
        moneda="ARS",
        concepto="[DEMO] Pago Factura Insumos Agroquímica Cuyo S.A.",
        cuenta_corriente=prov_agroquimica,
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        usuario=usuario
    )
    MovimientoFinanciero.objects.create(
        cuenta=cta_banco_usd,
        tipo=MovimientoFinanciero.TipoMovimiento.INGRESO,
        fecha=datetime.date(2026, 1, 28),
        importe=Decimal("45000.00"),
        moneda="USD",
        tipo_cambio=Decimal("1050.00"),
        concepto="[DEMO] Anticipo Carta de Crédito Exportación Aceite Virgendeheza a Mediterráneo Trading",
        cuenta_corriente=cli_exterior,
        centro_de_costo=cc_admin,
        usuario=usuario
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
        orden_de_trabajo=ot_cura_feb,
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
        orden_de_trabajo=ot_desm,
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

    # Movimientos Financieros Febrero
    MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.INGRESO,
        fecha=datetime.date(2026, 2, 12),
        importe=Decimal("14200000.00"),
        moneda="ARS",
        concepto="[DEMO] Cobranza Venta Aceite Fraccionado Botellas Dorica - Factura A0001-0000115",
        cuenta_corriente=cli_local,
        centro_de_costo=cc_almazara,
        finca=finca_norte,
        usuario=usuario
    )
    MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 2, 18),
        importe=Decimal("5820000.00"),
        moneda="ARS",
        concepto="[DEMO] Pago Liquidación Haberes UATRE Enero 2026",
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        usuario=usuario
    )
    MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 2, 22),
        importe=Decimal("1250000.00"),
        moneda="ARS",
        concepto="[DEMO] Pago Factura Energía Eléctrica Bombeo Pozo 1 - EDELAR",
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        usuario=usuario
    )

    # Cheques Febrero
    Cheque.objects.get_or_create(
        numero="CH-GAL-00458921",
        defaults={
            'cuenta_bancaria_origen': cta_banco_ars,
            'banco_emisor': "Banco Galicia",
            'emisor_firmante': "Olivar del Valle Agroindustrial S.A.",
            'cuit_emisor': "30-71458923-4",
            'tipo': 'EMITIDO',
            'cuenta_corriente': prov_envases,
            'importe': Decimal("3500000.00"),
            'fecha_emision': datetime.date(2026, 2, 15),
            'fecha_cobro': datetime.date(2026, 3, 20),
            'estado': 'EN_CARTERA',
            'observaciones': "[DEMO] Pago diferido a 30 días factura envases"
        }
    )

    # Conciliación Bancaria Enero 2026 (Cerrada)
    ConciliacionBancaria.objects.get_or_create(
        cuenta=cta_banco_ars,
        fecha_extracto=datetime.date(2026, 1, 31),
        defaults={
            'saldo_extracto': Decimal("28450000.00"),
            'saldo_sistema': Decimal("28450000.00"),
            'diferencia': Decimal("0.00"),
            'estado': 'CERRADA',
            'observaciones': "[DEMO] Conciliación bancaria cerrada conforme extracto Galicia Enero 2026.",
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

    # Lotes de Cosecha Marzo
    lote_arauco, _ = LoteDeCosecha.objects.get_or_create(
        cuadro=cuadro_a1,
        campana="2025/2026",
        defaults={
            'fecha_inicio': datetime.date(2026, 3, 5),
            'fecha_fin': datetime.date(2026, 3, 20),
            'kg_cosechados': Decimal("48000.00"),
            'destino': LoteDeCosecha.Destino.ACEITUNA_MESA_VERDE,
            'rendimiento_graso_porcentaje': Decimal("16.80"),
            'estado': LoteDeCosecha.Estado.FINALIZADO,
            'calidad_observaciones': '[DEMO] Cosecha manual en fresco variedad Arauco, calibre comercial 140-160.'
        }
    )
    lote_arbequina, _ = LoteDeCosecha.objects.get_or_create(
        cuadro=cuadro_b2,
        campana="2025/2026",
        defaults={
            'fecha_inicio': datetime.date(2026, 3, 15),
            'fecha_fin': datetime.date(2026, 3, 30),
            'kg_cosechados': Decimal("92000.00"),
            'destino': LoteDeCosecha.Destino.ACEITE_ALMAZARA,
            'rendimiento_graso_porcentaje': Decimal("17.80"),
            'estado': LoteDeCosecha.Estado.FINALIZADO,
            'calidad_observaciones': '[DEMO] Cosecha mecánica cabalgante con traslado inmediato a molienda almazara.'
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
        orden_de_trabajo=ot_cosecha,
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
        orden_de_trabajo=ot_cos_mec,
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
        orden_de_trabajo=ot_riego_post,
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

    # Movimientos Financieros Marzo
    MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.INGRESO,
        fecha=datetime.date(2026, 3, 22),
        importe=Decimal("18500000.00"),
        moneda="ARS",
        concepto="[DEMO] Cobranza Venta Aceituna Fresca Mercado Interno - Factura A0001-0000128",
        cuenta_corriente=cli_local,
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        usuario=usuario
    )
    MovimientoFinanciero.objects.create(
        cuenta=cta_banco_usd,
        tipo=MovimientoFinanciero.TipoMovimiento.INGRESO,
        fecha=datetime.date(2026, 3, 27),
        importe=Decimal("68000.00"),
        moneda="USD",
        tipo_cambio=Decimal("1050.00"),
        concepto="[DEMO] Liquidación Divisas Exportación Aceite Virgen Extra a Granel - Permiso Embarque 26001",
        cuenta_corriente=cli_exterior,
        centro_de_costo=cc_admin,
        usuario=usuario
    )
    MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 3, 20),
        importe=Decimal("6140000.00"),
        moneda="ARS",
        concepto="[DEMO] Pago Liquidación Haberes UATRE Febrero 2026",
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        usuario=usuario
    )
    MovimientoFinanciero.objects.create(
        cuenta=cta_banco_ars,
        tipo=MovimientoFinanciero.TipoMovimiento.EGRESO,
        fecha=datetime.date(2026, 3, 25),
        importe=Decimal("1980000.00"),
        moneda="ARS",
        concepto="[DEMO] Pago Flete y Servicio de Cosecha Mecánica Vibradora",
        centro_de_costo=cc_prod_norte,
        finca=finca_norte,
        usuario=usuario
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

    # 7.1 Imputación de Costos por Centro (Q1 2026) - Calidad y Trazabilidad Completa
    costos_q1_data = [
        # ── ENERO 2026 ────────────────────────────────────────────────────────
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2026, 1, 18), Decimal("320000.00"), Decimal("1050.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Jornales fertirriego nocturno Cuadro Arbequina", "ParteDiario", pd_riego_ene.id),
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2026, 1, 18), Decimal("247500.00"), Decimal("1050.00"), CostoPorCentro.TipoOrigen.INSUMO, "[DEMO] Nitrato de potasio soluble aplicado en fertirriego", "ParteDiario", pd_riego_ene.id),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 1, 22), Decimal("35000.00"), Decimal("1050.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Jornal tractorista pasada de rastra Cuadro Arauco", "ParteDiario", pd_laboreo.id),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 1, 22), Decimal("392000.00"), Decimal("1050.00"), CostoPorCentro.TipoOrigen.COMBUSTIBLE_MAQUINARIA, "[DEMO] Gasoil tractor John Deere laboreo y desmalezado", "ParteDiario", pd_laboreo.id),
        (cc_prod_norte, finca_norte, None, datetime.date(2026, 1, 25), Decimal("520000.00"), Decimal("1050.00"), CostoPorCentro.TipoOrigen.ENERGIA_RIEGO, "[DEMO] Factura EDELAR bombeo Pozo 1 - Enero 2026", "FacturaServicio", 101),
        (cc_prod_sur, finca_sur, cuadro_c3, datetime.date(2026, 1, 20), Decimal("280000.00"), Decimal("1050.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Jornales de riego y mantenimiento de goteros Finca Sur", "ParteDiario", None),
        (cc_prod_sur, finca_sur, None, datetime.date(2026, 1, 26), Decimal("380000.00"), Decimal("1050.00"), CostoPorCentro.TipoOrigen.ENERGIA_RIEGO, "[DEMO] Energía eléctrica trifásica bombeo de pozo Finca Sur", "FacturaServicio", 102),

        # ── FEBRERO 2026 ──────────────────────────────────────────────────────
        (cc_prod_norte, finca_norte, None, datetime.date(2026, 2, 10), Decimal("480000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.MANTENIMIENTO, "[DEMO] Service preventivo, lubricantes y filtros Tractor John Deere", "FacturaTaller", 201),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 2, 16), Decimal("48125.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Jornal tractorista atomizadora cura repilo", "ParteDiario", pd_cura_feb.id),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 2, 16), Decimal("1015000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.INSUMO, "[DEMO] Oxicloruro de cobre 50% cura sanitaria repilo", "ParteDiario", pd_cura_feb.id),
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2026, 2, 20), Decimal("35000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Jornal tractorista aplicación herbicida", "ParteDiario", pd_desm.id),
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2026, 2, 20), Decimal("368000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.INSUMO, "[DEMO] Glifosato 48% control de malezas en ruedo", "ParteDiario", pd_desm.id),
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2026, 2, 20), Decimal("280000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.COMBUSTIBLE_MAQUINARIA, "[DEMO] Gasoil tractor pulverizador malezas", "ParteDiario", pd_desm.id),
        (cc_prod_norte, finca_norte, None, datetime.date(2026, 2, 22), Decimal("1250000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.ENERGIA_RIEGO, "[DEMO] Factura EDELAR energía eléctrica bombeo Pozo 1 - Febrero 2026", "FacturaServicio", 202),
        (cc_prod_sur, finca_sur, cuadro_c3, datetime.date(2026, 2, 18), Decimal("310000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Tratamiento preventivo repilo en Cuadro Picual Pomán", "ParteDiario", None),
        (cc_prod_sur, finca_sur, cuadro_c3, datetime.date(2026, 2, 18), Decimal("725000.00"), Decimal("1080.00"), CostoPorCentro.TipoOrigen.INSUMO, "[DEMO] Oxicloruro de cobre aplicado en Finca Sur", "ParteDiario", None),

        # ── MARZO 2026 ────────────────────────────────────────────────────────
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 3, 8), Decimal("114000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Jornales cuadrilla cosecha manual aceituna Arauco", "ParteDiario", pd_cosecha.id),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 3, 8), Decimal("517500.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.COMBUSTIBLE_MAQUINARIA, "[DEMO] Gasoil tractores acarreo de bines de cosecha a playón", "ParteDiario", pd_cosecha.id),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 3, 12), Decimal("1336000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Continuación cuadrilla cosecha manual aceituna verde mesa", "ParteDiario", None),
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2026, 3, 18), Decimal("48125.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Operador cosechadora cabalgante vibradora", "ParteDiario", pd_cos_mec.id),
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2026, 3, 18), Decimal("1035000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.COMBUSTIBLE_MAQUINARIA, "[DEMO] Gasoil cosechadora vibradora y tractores acarreadores", "ParteDiario", pd_cos_mec.id),
        (cc_prod_norte, finca_norte, cuadro_b2, datetime.date(2026, 3, 20), Decimal("1841875.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Operadores y choferes cierre de cosecha mecánica", "ParteDiario", None),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 3, 22), Decimal("32000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Regador turno fertirriego post-cosecha", "ParteDiario", pd_riego_post.id),
        (cc_prod_norte, finca_norte, cuadro_a1, datetime.date(2026, 3, 22), Decimal("170000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.INSUMO, "[DEMO] Urea soluble fertirriego recuperador post-cosecha", "ParteDiario", pd_riego_post.id),
        (cc_prod_norte, finca_norte, None, datetime.date(2026, 3, 25), Decimal("1980000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.SERVICIO_CONTRATISTA, "[DEMO] Servicio contratado de cosecha mecánica cabalgante y flete", "FacturaProveedor", 301),
        (cc_prod_sur, finca_sur, cuadro_c3, datetime.date(2026, 3, 24), Decimal("950000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.MANO_DE_OBRA, "[DEMO] Cuadrilla de cosecha manual variedad Picual Pomán", "ParteDiario", None),
        (cc_almazara, finca_norte, None, datetime.date(2026, 3, 25), Decimal("980000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.ENERGIA_RIEGO, "[DEMO] Energía eléctrica molienda, batido y centrífuga almazara", "FacturaServicio", 302),
        (cc_admin, finca_norte, None, datetime.date(2026, 3, 28), Decimal("750000.00"), Decimal("1100.00"), CostoPorCentro.TipoOrigen.ESTRUCTURA_ADMIN, "[DEMO] Gastos operativos de estructura, logística y aduana exportación", "LiquidacionGasto", 303),
    ]
    for cc, fin, cua, fec, imp, tc_mes, torig, desc, d_tipo, d_id in costos_q1_data:
        CostoPorCentro.objects.get_or_create(
            centro_de_costo=cc,
            finca=fin,
            cuadro=cua,
            fecha=fec,
            tipo_origen=torig,
            defaults={
                'importe_ars': imp,
                'importe_usd': round(imp / tc_mes, 2),
                'descripcion': desc,
                'documento_origen_tipo': d_tipo,
                'documento_origen_id': d_id,
            }
        )

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
    # Expresamos las líneas en Pesos Argentinos (ARS) para el 1° Trimestre
    for l in cuadro_q1.lineas.all():
        l.monto_real = round(l.monto_real * Decimal("294.00"), 2)
        l.monto_presupuestado = round(l.monto_presupuestado * Decimal("294.00"), 2)
        l.save(update_fields=['monto_real', 'monto_presupuestado'])
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
    q_concil = ConciliacionBancaria.objects.filter(fecha_extracto__gte=desde, fecha_extracto__lte=hasta)
    reporte['conciliaciones'] = q_concil.count()
    q_concil.delete()

    # 3. Cheques
    q_cheques = Cheque.objects.filter(fecha_emision__gte=desde, fecha_emision__lte=hasta)
    reporte['cheques'] = q_cheques.count()
    q_cheques.delete()

    # 4. Movimientos Financieros
    q_movs = MovimientoFinanciero.objects.filter(fecha__gte=desde, fecha__lte=hasta)
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
    q_lotes = LoteDeCosecha.objects.filter(campana="2025/2026", fecha_inicio__gte=desde, fecha_inicio__lte=hasta)
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
    q_costos = CostoPorCentro.objects.filter(fecha__gte=desde, fecha__lte=hasta)
    reporte['costos_por_centro'] = q_costos.count()
    q_costos.delete()

    # 12. Empleados temporarios creados para la demo de cosecha
    q_emp_cosecha = Empleado.objects.filter(legajo__in=['LEG-007', 'LEG-008'])
    reporte['empleados_temporarios'] = q_emp_cosecha.count()
    q_emp_cosecha.delete()

    reporte['estado'] = 'OK'
    reporte['mensaje'] = "Limpieza completada: todos los registros de prueba del 1° Trimestre 2026 fueron eliminados exitosamente."
    return reporte
