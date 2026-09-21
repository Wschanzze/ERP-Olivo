from django.test import TestCase
from decimal import Decimal
from django.utils import timezone
from apps.core.models import Empresa, Finca, CentroDeCosto, Usuario
from apps.campos.models import Cuadro, RegistroFenologico
from apps.inventario.models import (
    CategoriaInsumo, Insumo, Deposito, StockPorDeposito, MovimientoStock,
    OrdenDeCompra, ItemOrdenDeCompra, RecepcionMercaderia, ItemRecepcion
)
from apps.inventario.services import confirmar_recepcion
from apps.finanzas.models import CuentaCorriente
from apps.personal.models import Empleado
from apps.liquidacion.models import PeriodoLiquidacion, LiquidacionEmpleado, ItemLiquidacion
from apps.liquidacion.views import _generar_recibo_reportlab


class ERPMejorasCortoPlazoTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(razon_social="Olivícola Test S.A.", cuit="30-99887766-5")
        self.finca = Finca.objects.create(empresa=self.empresa, nombre="Finca Central", codigo="FC-01", superficie_total_ha=Decimal("100.0"))
        self.deposito = Deposito.objects.create(finca=self.finca, nombre="Depósito Principal", codigo="DEP-PRIN")
        self.categoria = CategoriaInsumo.objects.create(nombre="Fertilizantes")
        self.cuadro = Cuadro.objects.create(
            finca=self.finca,
            codigo="CDR-01",
            nombre="Cuadro Arbequina 1",
            hectareas_netas=Decimal("15.0"),
            variedad_olivo=Cuadro.VariedadOlivo.ARBEQUINA,
            ano_plantacion=2018
        )
        self.proveedor = CuentaCorriente.objects.create(
            razon_social="Agroquímica Andina S.R.L.",
            cuit="30-55443322-1",
            tipo_entidad="PROVEEDOR",
            saldo_actual=Decimal("0.00")
        )
        self.insumo = Insumo.objects.create(
            codigo="FERT-N",
            nombre="Nitrato de Calcio",
            categoria=self.categoria,
            unidad_medida=Insumo.UnidadMedida.KILOS,
            stock_actual=Decimal("50.00"),
            costo_unitario_ars=Decimal("1000.00")  # Costo inicial $1000
        )
        StockPorDeposito.objects.create(
            deposito=self.deposito,
            insumo=self.insumo,
            cantidad=Decimal("50.00")
        )
        self.user = Usuario.objects.create_user(username="comprador_test", password="password123")

    def test_orden_compra_y_recepcion_ppp_y_cuenta_corriente(self):
        """Prueba que confirmar una recepción aumente el stock, recalcule el PPP y actualice el saldo del proveedor."""
        # 1. Crear Orden de Compra
        oc = OrdenDeCompra.objects.create(
            proveedor=self.proveedor,
            finca_destino=self.finca,
            numero="OC-2026-0001",
            fecha_emision=timezone.now().date(),
            estado=OrdenDeCompra.Estado.APROBADA
        )
        ItemOrdenDeCompra.objects.create(
            orden=oc,
            insumo=self.insumo,
            cantidad_solicitada=Decimal("50.00"),
            precio_unitario_estimado_ars=Decimal("1200.00")
        )
        oc.recalcular_total()
        self.assertEqual(oc.total_estimado_ars, Decimal("60000.00"))

        # 2. Crear Recepción física por 50 kg a $1200
        recepcion = RecepcionMercaderia.objects.create(
            orden=oc,
            deposito_destino=self.deposito,
            fecha_recepcion=timezone.now().date(),
            numero_remito_proveedor="REM-9988",
            numero_factura_proveedor="FC-0001-00004523",
            registrar_deuda_al_confirmar=True
        )
        ItemRecepcion.objects.create(
            recepcion=recepcion,
            insumo=self.insumo,
            cantidad_en_oc=Decimal("50.00"),
            cantidad_recibida=Decimal("50.00"),
            precio_unitario_real_ars=Decimal("1200.00")
        )

        # 3. Confirmar la recepción
        resultado = confirmar_recepcion(recepcion.id, usuario=self.user)
        self.assertTrue(resultado['ok'])

        # 4. Verificar stock actualizado: 50 iniciales + 50 recibidos = 100
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock_actual, Decimal("100.00"))

        # 5. Verificar recálculo de PPP:
        # Previo: 50 kg * $1000 = $50.000
        # Entrada: 50 kg * $1200 = $60.000
        # Nuevo PPP: $110.000 / 100 kg = $1.100
        self.assertEqual(self.insumo.costo_unitario_ars, Decimal("1100.00"))

        # 6. Verificar actualización de saldo en CuentaCorriente del proveedor (-$60.000)
        self.proveedor.refresh_from_db()
        self.assertEqual(self.proveedor.saldo_actual, Decimal("-60000.00"))

        # 7. Verificar estado de la OC
        oc.refresh_from_db()
        self.assertEqual(oc.estado, "RECIBIDA")

    def test_fenologia_y_semaforo_cuadro(self):
        """Prueba que el registro fenológico determine correctamente el semáforo fitosanitario del cuadro."""
        self.assertEqual(self.cuadro.semaforo_fitosanitario, 'gris')

        reg = RegistroFenologico.objects.create(
            cuadro=self.cuadro,
            campana="2025/2026",
            fecha=timezone.now().date(),
            fase_vegetativa=RegistroFenologico.FaseVegetativa.FLORACION,
            riesgo_fitosanitario=RegistroFenologico.RiesgoFitosanitario.ALTO,
            observaciones="Presencia de repilo incipiente por humedad alta."
        )

        self.assertEqual(reg.semaforo, 'rojo')
        self.assertEqual(self.cuadro.semaforo_fitosanitario, 'rojo')
        self.assertEqual(self.cuadro.registro_fenologico_actual, reg)

    def test_empleado_qr_unico_y_generacion_pdf_recibo(self):
        """Prueba que cada empleado tenga un UUID para QR y que el PDF del recibo se genere sin errores."""
        emp = Empleado.objects.create(
            legajo="LEG-99",
            nombre="Carlos",
            apellido="Gómez",
            dni_cuil="20-33445566-7",
            finca_habitual=self.finca,
            valor_jornal_base_ars=Decimal("25000.00"),
            fecha_ingreso=timezone.now().date()
        )
        self.assertIsNotNone(emp.codigo_qr_uuid)

        periodo = PeriodoLiquidacion.objects.create(
            mes=10,
            ano=2026,
            tipo=PeriodoLiquidacion.TipoPeriodo.PRIMERA_QUINCENA,
            fecha_inicio=timezone.now().date(),
            fecha_fin=timezone.now().date()
        )
        liq = LiquidacionEmpleado.objects.create(
            periodo=periodo,
            empleado=emp,
            dias_jornales_computados=Decimal("10.0"),
            total_bruto_remunerativo_ars=Decimal("250000.00"),
            total_retenciones_ars=Decimal("42500.00"),
            neto_a_cobrar_ars=Decimal("207500.00")
        )
        ItemLiquidacion.objects.create(
            liquidacion=liq,
            codigo_concepto="JORNAL",
            descripcion="Jornales rurales trabajados (10 días)",
            tipo=ItemLiquidacion.TipoConcepto.REMUNERATIVO,
            cantidad_o_porcentaje=Decimal("10.0"),
            importe_ars=Decimal("250000.00")
        )

        pdf_bytes = _generar_recibo_reportlab(liq)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
