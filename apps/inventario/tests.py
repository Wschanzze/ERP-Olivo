from django.test import TestCase
from decimal import Decimal
from django.utils import timezone
from apps.core.models import Empresa, Finca, CentroDeCosto, Usuario
from apps.campos.models import Cuadro, RegistroFenologico
from apps.inventario.models import (
    CategoriaInsumo, Insumo, Deposito, StockPorDeposito, MovimientoStock,
    OrdenDeCompra, ItemOrdenDeCompra, RecepcionMercaderia, ItemRecepcion
)
from django.core.exceptions import ValidationError
from django.urls import reverse
from apps.inventario.services import (
    confirmar_recepcion, realizar_transferencia_stock, realizar_ajuste_stock, obtener_kardex_insumo,
    calcular_clasificacion_abc_inventario, calcular_matriz_cobertura_y_reorden,
    obtener_valorizacion_por_plan_de_cuentas, crear_orden_compra_sugerida
)
from apps.finanzas.models import CuentaCorriente, CuentaContable
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

    def test_transferencia_stock_entre_depositos(self):
        """Prueba traslados de existencias entre dos depósitos físicos sin alterar stock global."""
        deposito_secundario = Deposito.objects.create(
            finca=self.finca,
            nombre="Depósito Finca Norte",
            codigo="DEP-NORTE"
        )
        # Inicial: Depósito Principal = 50 kg, Depósito Norte = 0 kg, Insumo total = 50 kg
        res = realizar_transferencia_stock(
            insumo_id=self.insumo.id,
            deposito_origen_id=self.deposito.id,
            deposito_destino_id=deposito_secundario.id,
            cantidad=Decimal("20.00"),
            motivo="Traslado preventivo para cura",
            usuario=self.user
        )
        self.assertTrue(res['ok'])

        # Verificar existencias
        st_origen = StockPorDeposito.objects.get(deposito=self.deposito, insumo=self.insumo)
        st_destino = StockPorDeposito.objects.get(deposito=deposito_secundario, insumo=self.insumo)
        self.insumo.refresh_from_db()

        self.assertEqual(st_origen.cantidad, Decimal("30.00"))
        self.assertEqual(st_destino.cantidad, Decimal("20.00"))
        self.assertEqual(self.insumo.stock_actual, Decimal("50.00"))  # Intacto a nivel global

        # Verificar movimiento de auditoría
        mov = MovimientoStock.objects.filter(tipo=MovimientoStock.TipoMovimiento.TRANSFERENCIA).first()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.cantidad, Decimal("20.00"))
        self.assertEqual(mov.deposito, self.deposito)
        self.assertEqual(mov.deposito_destino, deposito_secundario)

        # Probar error si se pide más de lo disponible en origen
        with self.assertRaises(ValidationError):
            realizar_transferencia_stock(
                insumo_id=self.insumo.id,
                deposito_origen_id=self.deposito.id,
                deposito_destino_id=deposito_secundario.id,
                cantidad=Decimal("100.00"),  # Solo quedan 30
                usuario=self.user
            )

    def test_ajustes_stock_positivo_negativo_y_merma(self):
        """Prueba ajustes manuales de stock: positivo con recálculo PPP, negativo y salida por merma."""
        # 1. Ajuste positivo: +30 kg a costo $1500
        # Previo: 50 kg a $1000 = $50.000
        # Nuevo: 50 kg ($1000) + 30 kg ($1500 = $45.000) => 80 kg total = $95.000 / 80 = $1.187,50
        res_pos = realizar_ajuste_stock(
            insumo_id=self.insumo.id,
            deposito_id=self.deposito.id,
            tipo_ajuste=MovimientoStock.TipoMovimiento.AJUSTE_POSITIVO,
            cantidad=Decimal("30.00"),
            costo_unitario=Decimal("1500.00"),
            motivo="Hallazgo en estiba fondo",
            usuario=self.user
        )
        self.assertTrue(res_pos['ok'])
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock_actual, Decimal("80.00"))
        self.assertEqual(self.insumo.costo_unitario_ars, Decimal("1187.50"))

        # 2. Merma / Vencimiento: -10 kg
        res_merma = realizar_ajuste_stock(
            insumo_id=self.insumo.id,
            deposito_id=self.deposito.id,
            tipo_ajuste=MovimientoStock.TipoMovimiento.SALIDA_MERMA,
            cantidad=Decimal("10.00"),
            motivo="Bolsa rota con humedad",
            usuario=self.user
        )
        self.assertTrue(res_merma['ok'])
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock_actual, Decimal("70.00"))

        # 3. Validar error por ajuste negativo que supere existencias
        with self.assertRaises(ValidationError):
            realizar_ajuste_stock(
                insumo_id=self.insumo.id,
                deposito_id=self.deposito.id,
                tipo_ajuste=MovimientoStock.TipoMovimiento.AJUSTE_NEGATIVO,
                cantidad=Decimal("500.00"),
                motivo="Ajuste excesivo",
                usuario=self.user
            )

    def test_kardex_insumo_calculo_saldos(self):
        """Prueba que el servicio de Kardex devuelva el historial cronológico y los saldos acumulados."""
        # Generar movimientos
        # Entrada: +20
        realizar_ajuste_stock(
            insumo_id=self.insumo.id,
            deposito_id=self.deposito.id,
            tipo_ajuste=MovimientoStock.TipoMovimiento.AJUSTE_POSITIVO,
            cantidad=Decimal("20.00"),
            costo_unitario=Decimal("1000.00"),
            motivo="Entrada 1",
            usuario=self.user
        )
        # Salida: -15
        realizar_ajuste_stock(
            insumo_id=self.insumo.id,
            deposito_id=self.deposito.id,
            tipo_ajuste=MovimientoStock.TipoMovimiento.SALIDA_MERMA,
            cantidad=Decimal("15.00"),
            motivo="Salida 1",
            usuario=self.user
        )

        kardex = obtener_kardex_insumo(insumo_id=self.insumo.id)
        self.assertEqual(kardex['total_movimientos'], 2)
        self.assertEqual(kardex['total_entradas_cant'], Decimal("20.00"))
        self.assertEqual(kardex['total_salidas_cant'], Decimal("15.00"))
        self.assertEqual(kardex['saldo_final_unidades'], Decimal("5.00"))

    def test_views_inventario_status_code(self):
        """Prueba que las vistas principales de inventario respondan HTTP 200."""
        self.client.force_login(self.user)

        # 1. Insumos List
        r1 = self.client.get(reverse('inventario:insumos_list'))
        self.assertEqual(r1.status_code, 200)

        # 2. Kardex Insumo
        r2 = self.client.get(reverse('inventario:insumo_kardex', kwargs={'pk': self.insumo.pk}))
        self.assertEqual(r2.status_code, 200)

        # 3. Movimientos List
        r3 = self.client.get(reverse('inventario:movimientos_list'))
        self.assertEqual(r3.status_code, 200)

        # 4. Análisis de Stock (Fase 2)
        r4 = self.client.get(reverse('inventario:analisis_stock'))
        self.assertEqual(r4.status_code, 200)

    def test_clasificacion_abc_pareto_y_plan_cuentas(self):
        """Prueba que el motor clasifique insumos según Pareto y agrupe según el Plan de Cuentas."""
        cuenta_fert = CuentaContable.objects.create(
            codigo="1.1.5.01.000001",
            nombre="Fertilizantes y Enmiendas",
            clase=CuentaContable.ClaseCuenta.ACTIVO
        )
        self.categoria.cuenta_contable_activo = cuenta_fert
        self.categoria.save()

        # Insumo de muy alto valor (debe ser Clase A)
        insumo_caro = Insumo.objects.create(
            codigo="AGRO-CARO",
            nombre="Fitosanitario Especial Importado",
            categoria=self.categoria,
            unidad_medida=Insumo.UnidadMedida.LITROS,
            stock_actual=Decimal("100.00"),
            costo_unitario_ars=Decimal("50000.00")  # Valor = $5.000.000
        )
        # self.insumo tiene 50 kg a $1000 = $50.000

        abc = calcular_clasificacion_abc_inventario()
        self.assertEqual(abc['total_insumos'], 2)
        self.assertGreater(abc['total_valor'], Decimal("5000000.00"))

        # El insumo caro debe estar primero y ser Clase A
        primer_item = abc['items'][0]
        self.assertEqual(primer_item['insumo'].id, insumo_caro.id)
        self.assertEqual(primer_item['clase'], 'A')
        self.assertGreater(primer_item['pct_individual'], Decimal("90.0"))

        # Verificar agrupación por Plan de Cuentas (Rubro 1.1.5)
        pc = obtener_valorizacion_por_plan_de_cuentas()
        self.assertGreater(len(pc['cuentas']), 0)
        cuenta_grupo = pc['cuentas'][0]
        self.assertEqual(cuenta_grupo['cuenta'].codigo, "1.1.5.01.000001")
        self.assertEqual(cuenta_grupo['total_articulos'], 2)

    def test_matriz_cobertura_y_orden_compra_sugerida(self):
        """Prueba el cálculo de días de stock proyectado y la generación de OC sugerida."""
        # Registrar una salida en parte diario
        MovimientoStock.objects.create(
            insumo=self.insumo,
            deposito=self.deposito,
            tipo=MovimientoStock.TipoMovimiento.SALIDA_PARTE_DIARIO,
            cantidad=Decimal("30.00"),
            costo_unitario=self.insumo.costo_unitario_ars,
            fecha=timezone.now(),
            motivo="Cura de prueba",
            usuario=self.user
        )
        self.insumo.stock_actual = Decimal("5.00")  # Menor que stock_minimo (10.00)
        self.insumo.save()

        cobertura = calcular_matriz_cobertura_y_reorden(dias_analisis=60)
        self.assertGreaterEqual(cobertura['conteo_criticos'], 1)

        fila = [f for f in cobertura['filas'] if f['insumo'].id == self.insumo.id][0]
        self.assertEqual(fila['nivel'], 'CRITICO')
        self.assertGreater(fila['cantidad_sugerida'], Decimal("0.00"))

        # Crear OC sugerida automáticamente
        res_oc = crear_orden_compra_sugerida(
            insumos_cantidades=[(self.insumo.id, fila['cantidad_sugerida'])],
            proveedor_id=self.proveedor.id,
            finca_id=self.finca.id,
            usuario=self.user
        )
        self.assertTrue(res_oc['ok'])
        oc = res_oc['orden']
        self.assertEqual(oc.estado, OrdenDeCompra.Estado.BORRADOR)
        self.assertEqual(oc.items.count(), 1)
        self.assertEqual(oc.items.first().insumo, self.insumo)


