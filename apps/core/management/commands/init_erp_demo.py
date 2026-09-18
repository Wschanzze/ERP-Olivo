from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from apps.core.models import Empresa, Finca, CentroDeCosto, Usuario
from apps.campos.models import Cuadro, LoteDeCosecha
from apps.inventario.models import CategoriaInsumo, Insumo, Deposito, StockPorDeposito, Maquina
from apps.personal.models import Empleado, RegistroAsistencia
from apps.finanzas.models import Cuenta, CuentaCorriente, MovimientoFinanciero
from apps.finanzas.services import registrar_movimiento_financiero

class Command(BaseCommand):
    help = "Inicializa datos de demostración para el ERP Olivícola"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando carga de datos de prueba para ERP Olivo..."))

        # 1. Empresa
        empresa, _ = Empresa.objects.get_or_create(
            cuit="30-71458923-4",
            defaults={
                'razon_social': "Olivar del Valle Agroindustrial S.A.",
                'nombre_fantasia': "Olivares del Valle",
                'direccion': "Ruta Nacional 60 Km 1140, Aimogasta, La Rioja",
                'telefono': "+54 3827 421000",
                'email': "administracion@olivaresdelvalle.com.ar",
                'moneda_principal': "ARS",
                'moneda_secundaria': "USD",
            }
        )

        # 2. Superusuario Admin
        if not Usuario.objects.filter(username="admin").exists():
            Usuario.objects.create_superuser(
                username="admin",
                email="admin@olivaresdelvalle.com.ar",
                password="admin",
                first_name="Gonzalo",
                last_name="Olivar",
                rol=Usuario.Rol.ADMIN_GENERAL
            )
            self.stdout.write(self.style.SUCCESS("Usuario 'admin' con password 'admin' creado."))

        # 3. Fincas
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

        # 4. Centros de Costo
        cc_prod_norte, _ = CentroDeCosto.objects.get_or_create(
            codigo="CC-PROD-FNORTE",
            defaults={
                'empresa': empresa,
                'nombre': "Producción Agrícola Finca Norte",
                'tipo': 'PRODUCTIVO_CAMPO',
                'finca': finca_norte
            }
        )
        cc_fabrica, _ = CentroDeCosto.objects.get_or_create(
            codigo="CC-FABRICA-ALMAZARA",
            defaults={
                'empresa': empresa,
                'nombre': "Almazara y Fábrica de Aceite (En Construcción)",
                'tipo': 'FABRICA_ALMAZARA',
                'finca': finca_norte
            }
        )
        cc_admin, _ = CentroDeCosto.objects.get_or_create(
            codigo="CC-ADM-CENTRAL",
            defaults={
                'empresa': empresa,
                'nombre': "Administración Central y Exportaciones",
                'tipo': 'ESTRUCTURA_ADMIN',
            }
        )

        # 5. Cuadros de Olivo
        cuadro_arauco, _ = Cuadro.objects.get_or_create(
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
                'observaciones': 'Variedad autóctona destinada a mesa verde y aceite premium monovarietal.'
            }
        )

        cuadro_arbequina, _ = Cuadro.objects.get_or_create(
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
                'observaciones': 'Diseñado para cosecha mecánica con vibrador cabalgante.'
            }
        )

        cuadro_picual, _ = Cuadro.objects.get_or_create(
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
                'observaciones': 'Alto contenido en ácido oleico y polifenoles naturales.'
            }
        )

        # 6. Lotes de Cosecha
        LoteDeCosecha.objects.get_or_create(
            cuadro=cuadro_arauco,
            campana="2025/2026",
            defaults={
                'fecha_inicio': timezone.now().date() - timezone.timedelta(days=20),
                'fecha_fin': timezone.now().date() - timezone.timedelta(days=5),
                'kg_cosechados': Decimal("182500.00"),
                'destino': LoteDeCosecha.Destino.ACEITUNA_MESA_VERDE,
                'rendimiento_graso_porcentaje': Decimal("17.50"),
                'estado': LoteDeCosecha.Estado.FINALIZADO,
                'calidad_observaciones': 'Excelente calibre y sin daño por moscas.'
            }
        )

        LoteDeCosecha.objects.get_or_create(
            cuadro=cuadro_arbequina,
            campana="2025/2026",
            defaults={
                'fecha_inicio': timezone.now().date() - timezone.timedelta(days=4),
                'kg_cosechados': Decimal("245000.00"),
                'destino': LoteDeCosecha.Destino.ACEITE_ALMAZARA,
                'rendimiento_graso_porcentaje': Decimal("19.80"),
                'estado': LoteDeCosecha.Estado.EN_CURSO,
                'calidad_observaciones': 'Recolección mecanizada continua hacia fábrica.'
            }
        )

        # 7. Depósitos e Insumos
        dep_central, _ = Deposito.objects.get_or_create(
            codigo="DEP-FNORTE-01",
            defaults={
                'finca': finca_norte,
                'nombre': "Depósito Central Insumos y Fertilizantes",
                'es_deposito_central': True
            }
        )

        cat_quim, _ = CategoriaInsumo.objects.get_or_create(nombre="Fitosanitarios y Curas")
        cat_fert, _ = CategoriaInsumo.objects.get_or_create(nombre="Fertilizantes y Nutrición")
        cat_comb, _ = CategoriaInsumo.objects.get_or_create(nombre="Combustibles y Lubricantes")

        cobre, _ = Insumo.objects.get_or_create(
            codigo="INS-COBRE-01",
            defaults={
                'nombre': "Oxicloruro de Cobre 50% (Cura Repilo)",
                'categoria': cat_quim,
                'unidad_medida': Insumo.UnidadMedida.KILOS,
                'stock_actual': Decimal("850.00"),
                'stock_minimo': Decimal("150.00"),
                'costo_unitario_ars': Decimal("14500.00"),
                'costo_unitario_usd': Decimal("11.50")
            }
        )

        urea, _ = Insumo.objects.get_or_create(
            codigo="INS-UREA-46",
            defaults={
                'nombre': "Urea Granulada 46-0-0 (Fertirriego)",
                'categoria': cat_fert,
                'unidad_medida': Insumo.UnidadMedida.KILOS,
                'stock_actual': Decimal("4200.00"),
                'stock_minimo': Decimal("1000.00"),
                'costo_unitario_ars': Decimal("850.00"),
                'costo_unitario_usd': Decimal("0.70")
            }
        )

        gasoil, _ = Insumo.objects.get_or_create(
            codigo="INS-GASOIL-AGRO",
            defaults={
                'nombre': "Gasoil Grado 2 Agro (Cisterna Finca)",
                'categoria': cat_comb,
                'unidad_medida': Insumo.UnidadMedida.LITROS,
                'stock_actual': Decimal("6500.00"),
                'stock_minimo': Decimal("1500.00"),
                'costo_unitario_ars': Decimal("1280.00"),
                'costo_unitario_usd': Decimal("1.05")
            }
        )

        StockPorDeposito.objects.get_or_create(deposito=dep_central, insumo=cobre, defaults={'cantidad': Decimal("850.00")})
        StockPorDeposito.objects.get_or_create(deposito=dep_central, insumo=urea, defaults={'cantidad': Decimal("4200.00")})
        StockPorDeposito.objects.get_or_create(deposito=dep_central, insumo=gasoil, defaults={'cantidad': Decimal("6500.00")})

        # 8. Maquinaria
        Maquina.objects.get_or_create(
            codigo="TRAC-JD-01",
            defaults={
                'nombre': "Tractor John Deere 5075E",
                'tipo': Maquina.TipoMaquina.TRACTOR,
                'marca': "John Deere",
                'modelo': "5075E 4WD",
                'ano_fabricacion': 2022,
                'horas_o_km_acumulados': Decimal("1840.5"),
                'finca_asignada': finca_norte,
                'estado': Maquina.EstadoMaquina.OPERATIVA
            }
        )
        Maquina.objects.get_or_create(
            codigo="ATOM-CAFF-01",
            defaults={
                'nombre': "Atomizadora Caffini 2000L",
                'tipo': Maquina.TipoMaquina.ATOMIZADORA,
                'marca': "Caffini",
                'modelo': "Booster 2000",
                'ano_fabricacion': 2021,
                'horas_o_km_acumulados': Decimal("920.0"),
                'finca_asignada': finca_norte,
                'estado': Maquina.EstadoMaquina.OPERATIVA
            }
        )

        # 9. Personal y Asistencia
        emp1, _ = Empleado.objects.get_or_create(
            legajo="LEG-0101",
            defaults={
                'nombre': "Mario Alberto",
                'apellido': "Giménez",
                'dni_cuil': "20-28491823-7",
                'rol_laboral': Empleado.RolLaboral.CAPATAZ_FINCA,
                'modalidad': Empleado.ModalidadContratacion.MENSUAL,
                'finca_habitual': finca_norte,
                'valor_jornal_base_ars': Decimal("850000.00"),
                'fecha_ingreso': timezone.now().date() - timezone.timedelta(days=900),
                'telefono': "+54 3827 554411"
            }
        )

        emp2, _ = Empleado.objects.get_or_create(
            legajo="LEG-0102",
            defaults={
                'nombre': "Ramón",
                'apellido': "Carrizo",
                'dni_cuil': "20-33219482-3",
                'rol_laboral': Empleado.RolLaboral.TRACTORISTA,
                'modalidad': Empleado.ModalidadContratacion.JORNAL_RURAL,
                'finca_habitual': finca_norte,
                'valor_jornal_base_ars': Decimal("32000.00"),
                'valor_hora_extra_ars': Decimal("6000.00"),
                'fecha_ingreso': timezone.now().date() - timezone.timedelta(days=400),
                'telefono': "+54 3827 667788"
            }
        )

        emp3, _ = Empleado.objects.get_or_create(
            legajo="LEG-0103",
            defaults={
                'nombre': "Esteban",
                'apellido': "Flores",
                'dni_cuil': "20-39482019-5",
                'rol_laboral': Empleado.RolLaboral.PODADOR,
                'modalidad': Empleado.ModalidadContratacion.JORNAL_RURAL,
                'finca_habitual': finca_norte,
                'valor_jornal_base_ars': Decimal("30000.00"),
                'valor_hora_extra_ars': Decimal("5500.00"),
                'fecha_ingreso': timezone.now().date() - timezone.timedelta(days=250),
                'telefono': "+54 3827 991122"
            }
        )

        # Asistencias de hoy
        today = timezone.now().date()
        RegistroAsistencia.objects.get_or_create(empleado=emp1, fecha=today, defaults={'finca': finca_norte, 'estado': 'PRESENTE', 'horas_normales': 8, 'jornal_computado': 1.0})
        RegistroAsistencia.objects.get_or_create(empleado=emp2, fecha=today, defaults={'finca': finca_norte, 'estado': 'PRESENTE', 'horas_normales': 8, 'horas_extras': 2, 'jornal_computado': 1.0})
        RegistroAsistencia.objects.get_or_create(empleado=emp3, fecha=today, defaults={'finca': finca_norte, 'estado': 'PRESENTE', 'horas_normales': 8, 'jornal_computado': 1.0})

        # 10. Cuentas Financieras y Cuentas Corrientes
        caja_chica, _ = Cuenta.objects.get_or_create(
            nombre="Caja Chica Finca Aimogasta",
            defaults={
                'empresa': empresa,
                'tipo': Cuenta.TipoCuenta.CAJA_EFECTIVO,
                'moneda': Cuenta.Moneda.ARS,
                'saldo_actual': Decimal("1450000.00")
            }
        )

        banco_galicia, _ = Cuenta.objects.get_or_create(
            nombre="Banco Galicia CC Operativa ARS",
            defaults={
                'empresa': empresa,
                'tipo': Cuenta.TipoCuenta.CUENTA_BANCARIA,
                'moneda': Cuenta.Moneda.ARS,
                'banco_nombre': "Banco Galicia",
                'cbu_cvu': "0070123420000012345678",
                'saldo_actual': Decimal("18940000.00")
            }
        )

        banco_usd, _ = Cuenta.objects.get_or_create(
            nombre="Banco Santander CC Exportación USD",
            defaults={
                'empresa': empresa,
                'tipo': Cuenta.TipoCuenta.CUENTA_BANCARIA,
                'moneda': Cuenta.Moneda.USD,
                'banco_nombre': "Banco Santander",
                'cbu_cvu': "0720987620000098765432",
                'saldo_actual': Decimal("85400.00")
            }
        )

        prov_agroquimica, _ = CuentaCorriente.objects.get_or_create(
            cuit="30-68192834-9",
            defaults={
                'razon_social': "Agroquímica Cuyo & Cía S.A.",
                'nombre_comercial': "AgroCuyo",
                'tipo_entidad': CuentaCorriente.TipoEntidad.PROVEEDOR,
                'telefono': "+54 261 4981234",
                'email': "cuentas@agrocuyo.com.ar",
                'saldo_actual': Decimal("-4250000.00"),  # Debemos 4.25M
                'limite_credito': Decimal("15000000.00")
            }
        )

        cliente_export, _ = CuentaCorriente.objects.get_or_create(
            cuit="30-79881234-2",
            defaults={
                'razon_social': "Mediterráneo Trading Imports LLC / Suc. Arg.",
                'nombre_comercial': "Mediterráneo Imports",
                'tipo_entidad': CuentaCorriente.TipoEntidad.CLIENTE,
                'telefono': "+54 11 43219876",
                'email': "logistica@mediterraneotrading.com",
                'saldo_actual': Decimal("12800000.00"),  # Nos deben 12.8M
                'limite_credito': Decimal("50000000.00")
            }
        )

        self.stdout.write(self.style.SUCCESS("[OK] Datos de demostracion cargados exitosamente."))
