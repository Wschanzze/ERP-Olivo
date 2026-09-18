from django.test import TestCase
from decimal import Decimal
from django.utils import timezone
from apps.core.models import Empresa, Finca, CentroDeCosto, Usuario
from apps.campos.models import Cuadro
from apps.inventario.models import CategoriaInsumo, Insumo, Deposito, StockPorDeposito, MovimientoStock
from apps.personal.models import Empleado
from apps.costos.models import CostoPorCentro
from apps.parte_diario.models import ParteDiario, ParteDiarioInsumo, ParteDiarioPersonal
from apps.parte_diario.services import confirmar_y_cerrar_parte_diario

class ParteDiarioServiceTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            razon_social="Olivo Test S.A.",
            cuit="30-11223344-5"
        )
        self.finca = Finca.objects.create(
            empresa=self.empresa,
            nombre="Finca Test",
            codigo="F-TEST",
            superficie_total_ha=Decimal("50.0")
        )
        self.centro_costo = CentroDeCosto.objects.create(
            empresa=self.empresa,
            codigo="CC-PROD",
            nombre="Centro Prod Test",
            finca=self.finca,
            tipo="PRODUCTIVO_CAMPO"
        )
        self.cuadro = Cuadro.objects.create(
            finca=self.finca,
            codigo="C1",
            nombre="Cuadro 1",
            hectareas_netas=Decimal("10.0"),
            variedad_olivo=Cuadro.VariedadOlivo.ARBEQUINA,
            ano_plantacion=2020
        )
        self.user = Usuario.objects.create_user(
            username="supervisor_test",
            password="password123",
            rol=Usuario.Rol.ENCARGADO_CAMPO
        )
        self.deposito = Deposito.objects.create(
            finca=self.finca,
            nombre="Depósito Test",
            codigo="DEP-01"
        )
        self.categoria = CategoriaInsumo.objects.create(nombre="Químicos")
        self.insumo = Insumo.objects.create(
            codigo="INS-01",
            nombre="Fungicida Cobre",
            categoria=self.categoria,
            unidad_medida=Insumo.UnidadMedida.KILOS,
            stock_actual=Decimal("100.00"),
            costo_unitario_ars=Decimal("5000.00")
        )
        StockPorDeposito.objects.create(
            deposito=self.deposito,
            insumo=self.insumo,
            cantidad=Decimal("100.00")
        )
        self.empleado = Empleado.objects.create(
            legajo="E01",
            nombre="Juan",
            apellido="Pérez",
            dni_cuil="20-12345678-9",
            finca_habitual=self.finca,
            valor_jornal_base_ars=Decimal("24000.00"),  # 3000 / hora
            fecha_ingreso=timezone.now().date()
        )

    def test_cierre_parte_diario_descuenta_stock_e_imputa_costos(self):
        # Crear Parte Diario en Borrador
        parte = ParteDiario.objects.create(
            finca=self.finca,
            cuadro=self.cuadro,
            fecha=timezone.now().date(),
            supervisor=self.user,
            estado=ParteDiario.Estado.BORRADOR
        )

        # Asignar 10 kg de insumo
        ParteDiarioInsumo.objects.create(
            parte_diario=parte,
            insumo=self.insumo,
            deposito_origen=self.deposito,
            cantidad_utilizada=Decimal("10.00")
        )

        # Asignar empleado con 8 horas
        ParteDiarioPersonal.objects.create(
            parte_diario=parte,
            empleado=self.empleado,
            horas_normales=Decimal("8.0"),
            horas_extras=Decimal("0.0")
        )

        # Ejecutar servicio de cierre
        parte_cerrado = confirmar_y_cerrar_parte_diario(parte.id, usuario=self.user)

        # 1. Verificar cambio de estado
        self.assertEqual(parte_cerrado.estado, ParteDiario.Estado.CONFIRMADO_CERRADO)
        self.assertIsNotNone(parte_cerrado.fecha_cierre)

        # 2. Verificar descuento en Insumo
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock_actual, Decimal("90.00"))

        # 3. Verificar generación de MovimientoStock
        mov = MovimientoStock.objects.filter(referencia_origen=f"ParteDiario #{parte.id}").first()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.tipo, MovimientoStock.TipoMovimiento.SALIDA_PARTE_DIARIO)
        self.assertEqual(mov.cantidad, Decimal("10.00"))

        # 4. Verificar imputación en CostoPorCentro (Insumo: 10 kg * $5000 = $50000)
        costo_insumo = CostoPorCentro.objects.filter(
            documento_origen_id=parte.id,
            tipo_origen=CostoPorCentro.TipoOrigen.INSUMO
        ).first()
        self.assertIsNotNone(costo_insumo)
        self.assertEqual(costo_insumo.importe_ars, Decimal("50000.00"))

        # 5. Verificar imputación en CostoPorCentro (Mano de obra: 8h = 1 jornal = $24000)
        costo_mo = CostoPorCentro.objects.filter(
            documento_origen_id=parte.id,
            tipo_origen=CostoPorCentro.TipoOrigen.MANO_DE_OBRA
        ).first()
        self.assertIsNotNone(costo_mo)
        self.assertEqual(costo_mo.importe_ars, Decimal("24000.00"))
