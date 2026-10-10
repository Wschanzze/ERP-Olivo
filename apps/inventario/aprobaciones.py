"""
Adaptador de Órdenes de Compra para el Tablero de Aprobaciones (kanban).

Mapeo columnas ↔ estados reales de la OC:
  PENDIENTE      ← BORRADOR (con o sin etiqueta "Represupuesto")
  REPRESUPUESTO  → zona de soltar: la OC vuelve a BORRADOR con la etiqueta
  APROBADO       ← APROBADA, RECIBIDA_PARCIAL, RECIBIDA (estas dos últimas bloqueadas)
  ANULADO        ← ANULADA (estado final)
"""
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from apps.core.aprobaciones import AdaptadorAprobacion, Columna, Tarjeta
from .models import OrdenDeCompra, RecepcionMercaderia


PENDIENTE = 'PENDIENTE'
REPRESUPUESTO = 'REPRESUPUESTO'
APROBADO = 'APROBADO'
ANULADO = 'ANULADO'


class AdaptadorOrdenCompra(AdaptadorAprobacion):
    tipo_documento = 'OC'
    etiqueta = 'Orden de Compra'
    etiqueta_plural = 'Órdenes de Compra'
    columnas = (
        Columna(
            clave=PENDIENTE,
            titulo='Pendientes',
            descripcion='Borradores esperando revisión. Se muestran todas, sin importar el período.',
            tono='slate',
        ),
        Columna(
            clave=REPRESUPUESTO,
            titulo='Represupuesto',
            descripcion='Soltá una OC aquí para pedir un nuevo presupuesto al proveedor.',
            tono='amber',
            efecto='La OC volverá a «Pendientes» (estado Borrador) con la etiqueta Represupuesto hasta que se apruebe o anule.',
            requiere_motivo=True,
            solo_destino=True,
        ),
        Columna(
            clave=APROBADO,
            titulo='Aprobadas',
            descripcion='Aprobadas / enviadas al proveedor, habilitadas para recepción.',
            tono='emerald',
            efecto='La OC pasará a estado «Aprobada / Enviada al proveedor» y quedará habilitada para registrar recepciones.',
        ),
        Columna(
            clave=ANULADO,
            titulo='Anuladas',
            descripcion='Órdenes rechazadas o canceladas (estado final).',
            tono='rose',
            efecto='La OC quedará en estado «Anulada». Es un estado final y no podrá volver a moverse desde el tablero.',
            requiere_motivo=True,
        ),
    )

    # ── Contrato del motor ──────────────────────────────────────────────────
    def obtener_para_actualizar(self, pk):
        try:
            return OrdenDeCompra.objects.select_for_update().get(pk=pk)
        except (OrdenDeCompra.DoesNotExist, ValueError, TypeError):
            from django.core.exceptions import ValidationError
            raise ValidationError("La Orden de Compra no existe.")

    def referencia(self, oc) -> str:
        return oc.numero

    def estado(self, oc) -> str:
        return oc.estado

    def columna_actual(self, oc) -> str:
        if oc.estado == OrdenDeCompra.Estado.BORRADOR:
            return PENDIENTE
        if oc.estado == OrdenDeCompra.Estado.ANULADA:
            return ANULADO
        return APROBADO

    def _tiene_recepciones(self, oc) -> bool:
        anotado = getattr(oc, 'n_recepciones_activas', None)
        if anotado is not None:
            return anotado > 0
        return oc.tiene_recepciones_activas

    def destinos_permitidos(self, oc) -> list:
        if oc.estado == OrdenDeCompra.Estado.BORRADOR:
            return [APROBADO, REPRESUPUESTO, ANULADO]
        if oc.estado == OrdenDeCompra.Estado.APROBADA and not self._tiene_recepciones(oc):
            return [REPRESUPUESTO, ANULADO]
        return []

    def motivo_bloqueo(self, oc) -> str:
        if oc.estado == OrdenDeCompra.Estado.ANULADA:
            return 'OC anulada: estado final.'
        if oc.estado in (OrdenDeCompra.Estado.RECIBIDA, OrdenDeCompra.Estado.RECIBIDA_PARCIAL):
            return 'Mercadería recibida: la aprobación ya no puede modificarse.'
        if self._tiene_recepciones(oc):
            return 'Tiene recepciones registradas: la aprobación ya no puede modificarse.'
        return ''

    def aplicar_movimiento(self, oc, destino, usuario, motivo) -> None:
        campos = ['estado', 'requiere_represupuesto', 'motivo_represupuesto', 'updated_at']
        if destino == APROBADO:
            oc.estado = OrdenDeCompra.Estado.APROBADA
            oc.requiere_represupuesto = False
            oc.motivo_represupuesto = ''
            oc.aprobada_por = usuario
            oc.fecha_aprobacion = timezone.now()
            campos += ['aprobada_por', 'fecha_aprobacion']
        elif destino == REPRESUPUESTO:
            oc.estado = OrdenDeCompra.Estado.BORRADOR
            oc.requiere_represupuesto = True
            oc.motivo_represupuesto = motivo
            oc.aprobada_por = None
            oc.fecha_aprobacion = None
            campos += ['aprobada_por', 'fecha_aprobacion']
        elif destino == ANULADO:
            oc.estado = OrdenDeCompra.Estado.ANULADA
            oc.requiere_represupuesto = False
            oc.motivo_represupuesto = ''
            oc.motivo_anulacion = motivo
            campos += ['motivo_anulacion']
        oc.save(update_fields=campos)

    # ── Construcción del tablero ─────────────────────────────────────────────
    def construir_tablero(self, *, desde=None, hasta=None, q='', finca_id=None, usuario=None) -> dict:
        """
        Arma las columnas del tablero. Las OC pendientes se muestran siempre;
        aprobadas y anuladas se filtran por período de emisión.
        """
        qs = (
            OrdenDeCompra.objects
            .select_related('proveedor', 'finca_destino', 'aprobada_por')
            .annotate(
                n_items=Count('items', distinct=True),
                n_recepciones_activas=Count(
                    'recepciones',
                    filter=~Q(recepciones__estado=RecepcionMercaderia.Estado.ANULADA),
                    distinct=True,
                ),
            )
        )
        if q:
            qs = qs.filter(
                Q(numero__icontains=q) |
                Q(proveedor__razon_social__icontains=q) |
                Q(proveedor__cuit__icontains=q)
            )
        if finca_id:
            qs = qs.filter(finca_destino_id=finca_id)

        filtro_periodo = Q()
        if desde:
            filtro_periodo &= Q(fecha_emision__gte=desde)
        if hasta:
            filtro_periodo &= Q(fecha_emision__lte=hasta)
        qs = qs.filter(Q(estado=OrdenDeCompra.Estado.BORRADOR) | filtro_periodo)

        puede_mover = self.puede_mover(usuario)
        tarjetas = {col.clave: [] for col in self.columnas}
        en_represupuesto = []
        for oc in qs:
            tarjeta = self._tarjeta(oc, puede_mover)
            tarjetas[tarjeta.columna].append(tarjeta)
            if oc.requiere_represupuesto and oc.estado == OrdenDeCompra.Estado.BORRADOR:
                en_represupuesto.append(tarjeta)

        # Pendientes: las más antiguas primero (más tiempo esperando); resto: más recientes primero.
        tarjetas[PENDIENTE].sort(key=lambda t: (t.fecha or timezone.localdate(), t.pk))
        for clave in (APROBADO, ANULADO):
            tarjetas[clave].sort(key=lambda t: (t.fecha or timezone.localdate(), t.pk), reverse=True)

        columnas = []
        for col in self.columnas:
            items = en_represupuesto if col.solo_destino else tarjetas[col.clave]
            columnas.append({
                'columna': col,
                'tarjetas': [] if col.solo_destino else items,
                'en_espera': items if col.solo_destino else [],
                'cantidad': len(items),
                'total': sum((t.importe for t in items), 0),
            })
        return {
            'columnas': columnas,
            'puede_mover': puede_mover,
            'resumen': {
                'pendientes': len(tarjetas[PENDIENTE]),
                'pendientes_total': sum((t.importe for t in tarjetas[PENDIENTE]), 0),
                'represupuesto': len(en_represupuesto),
                'aprobadas': len(tarjetas[APROBADO]),
                'aprobadas_total': sum((t.importe for t in tarjetas[APROBADO]), 0),
                'anuladas': len(tarjetas[ANULADO]),
                'anuladas_total': sum((t.importe for t in tarjetas[ANULADO]), 0),
            },
        }

    def _tarjeta(self, oc, puede_mover) -> Tarjeta:
        etiquetas, nota = [], ''
        meta = [f"{oc.n_items} ítem{'s' if oc.n_items != 1 else ''}"]

        if oc.estado == OrdenDeCompra.Estado.BORRADOR and oc.requiere_represupuesto:
            etiquetas.append(('Represupuesto', 'amber'))
            nota = oc.motivo_represupuesto
        elif oc.estado == OrdenDeCompra.Estado.RECIBIDA:
            etiquetas.append(('Recibida', 'emerald'))
        elif oc.estado == OrdenDeCompra.Estado.RECIBIDA_PARCIAL:
            etiquetas.append(('Recibida parcial', 'amber'))
        elif oc.estado == OrdenDeCompra.Estado.ANULADA:
            nota = oc.motivo_anulacion

        if oc.estado != OrdenDeCompra.Estado.BORRADOR and oc.aprobada_por_id:
            nombre = oc.aprobada_por.get_full_name() or oc.aprobada_por.username
            meta.append(f"Aprobó {nombre}")

        claves = self.destinos_permitidos(oc) if puede_mover else []
        return Tarjeta(
            pk=oc.pk,
            referencia=oc.numero,
            titulo=oc.proveedor.razon_social,
            subtitulo=oc.finca_destino.nombre,
            importe=oc.total_estimado_ars,
            fecha=oc.fecha_emision,
            url_detalle=reverse('inventario:oc_detalle', args=[oc.pk]),
            columna=self.columna_actual(oc),
            destinos=[self.columna(c) for c in claves],
            etiquetas=etiquetas,
            nota=nota,
            meta=' · '.join(meta),
            motivo_bloqueo=self.motivo_bloqueo(oc),
        )
