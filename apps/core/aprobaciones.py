"""
Motor genérico del circuito de aprobaciones (Tablero Kanban).

Centraliza en un único punto transaccional las reglas que comparten todos los
documentos aprobables del ERP:
  1. Sólo usuarios aprobadores (Admin General / Contable) pueden mover tarjetas.
  2. Cada tipo de documento define sus columnas y transiciones válidas.
  3. Los movimientos que lo requieran exigen un motivo.
  4. Cada movimiento queda auditado en HistorialAprobacion.

Cada tipo de documento se conecta mediante un "adaptador". Hoy existe el de
Órdenes de Compra (inventario). Para sumar Órdenes de Pago (finanzas) basta con
crear `apps/finanzas/aprobaciones.py` con un `AdaptadorOrdenPago` y registrarlo
en ADAPTADORES_REGISTRADOS: el tablero, la confirmación y la auditoría se reutilizan.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils.module_loading import import_string


ADAPTADORES_REGISTRADOS = {
    'OC': 'apps.inventario.aprobaciones.AdaptadorOrdenCompra',
    # 'OP': 'apps.finanzas.aprobaciones.AdaptadorOrdenPago',  # Próximamente (Finanzas)
}


@dataclass(frozen=True)
class Columna:
    """Columna del tablero kanban."""
    clave: str
    titulo: str
    descripcion: str
    tono: str                       # Color Tailwind base: slate | amber | emerald | rose
    efecto: str = ''                # Texto mostrado en el modal de confirmación
    requiere_motivo: bool = False
    solo_destino: bool = False      # Zona de soltar: no muestra tarjetas propias


@dataclass
class Tarjeta:
    """Representación normalizada de un documento dentro del tablero."""
    pk: int
    referencia: str
    titulo: str
    subtitulo: str
    importe: Decimal
    fecha: Optional[date]
    url_detalle: str
    columna: str
    destinos: list = field(default_factory=list)      # list[Columna]
    etiquetas: list = field(default_factory=list)     # list[tuple[texto, tono]]
    nota: str = ''
    meta: str = ''
    motivo_bloqueo: str = ''

    @property
    def destinos_csv(self) -> str:
        return ','.join(c.clave for c in self.destinos)

    @property
    def bloqueada(self) -> bool:
        return not self.destinos


class AdaptadorAprobacion:
    """Contrato que debe implementar cada tipo de documento aprobable."""
    tipo_documento: str = ''
    etiqueta: str = ''
    etiqueta_plural: str = ''
    columnas: tuple = ()

    # ── Metadatos de columnas ────────────────────────────────────────────────
    def columna(self, clave: str) -> Columna:
        for col in self.columnas:
            if col.clave == clave:
                return col
        raise ValidationError(f"La columna de destino '{clave}' no existe en el tablero.")

    # ── Permisos ────────────────────────────────────────────────────────────
    def puede_mover(self, usuario) -> bool:
        return bool(usuario and usuario.is_authenticated and getattr(usuario, 'puede_aprobar_documentos', False))

    # ── Métodos a implementar por cada documento ─────────────────────────────
    def obtener_para_actualizar(self, pk):
        """Devuelve el documento bloqueado con select_for_update."""
        raise NotImplementedError

    def referencia(self, doc) -> str:
        raise NotImplementedError

    def estado(self, doc) -> str:
        raise NotImplementedError

    def columna_actual(self, doc) -> str:
        raise NotImplementedError

    def destinos_permitidos(self, doc) -> list:
        """Claves de columnas a las que el documento puede moverse."""
        raise NotImplementedError

    def aplicar_movimiento(self, doc, destino: str, usuario, motivo: str) -> None:
        """Actualiza el estado real del documento en su propio módulo."""
        raise NotImplementedError


_cache_adaptadores = {}


def obtener_adaptador(tipo_documento: str) -> AdaptadorAprobacion:
    ruta = ADAPTADORES_REGISTRADOS.get((tipo_documento or '').upper())
    if not ruta:
        raise ValidationError(f"Tipo de documento '{tipo_documento}' no soportado por el tablero de aprobaciones.")
    if ruta not in _cache_adaptadores:
        _cache_adaptadores[ruta] = import_string(ruta)()
    return _cache_adaptadores[ruta]


def mover_documento(tipo_documento: str, pk, destino: str, usuario, motivo: str = '') -> dict:
    """
    Mueve un documento a otra columna del tablero de forma atómica y auditada.

    Lanza PermissionDenied si el usuario no es aprobador y ValidationError si la
    transición no es válida o falta el motivo. Retorna dict con 'ok' y 'mensaje'.
    """
    from apps.core.models import HistorialAprobacion

    adaptador = obtener_adaptador(tipo_documento)
    if not adaptador.puede_mover(usuario):
        raise PermissionDenied("Tu rol no tiene permisos para aprobar, anular o pedir represupuesto de documentos.")

    destino = (destino or '').upper()
    columna_destino = adaptador.columna(destino)
    motivo = (motivo or '').strip()
    if columna_destino.requiere_motivo and not motivo:
        raise ValidationError(f"Para mover a «{columna_destino.titulo}» es obligatorio indicar un motivo.")

    with transaction.atomic():
        doc = adaptador.obtener_para_actualizar(pk)
        referencia = adaptador.referencia(doc)
        origen = adaptador.columna_actual(doc)

        if destino not in adaptador.destinos_permitidos(doc):
            titulo_origen = adaptador.columna(origen).titulo
            raise ValidationError(
                f"{adaptador.etiqueta} {referencia} no puede pasar de «{titulo_origen}» a «{columna_destino.titulo}»."
            )

        estado_anterior = adaptador.estado(doc)
        adaptador.aplicar_movimiento(doc, destino, usuario, motivo)

        HistorialAprobacion.objects.create(
            tipo_documento=adaptador.tipo_documento,
            objeto_id=doc.pk,
            referencia=referencia,
            columna_origen=origen,
            columna_destino=destino,
            estado_anterior=estado_anterior,
            estado_nuevo=adaptador.estado(doc),
            motivo=motivo,
            usuario=usuario,
        )

    return {
        'ok': True,
        'mensaje': f"{adaptador.etiqueta} {referencia} movida a «{columna_destino.titulo}».",
        'referencia': referencia,
    }


def historial_documento(tipo_documento: str, pk):
    from apps.core.models import HistorialAprobacion
    return (
        HistorialAprobacion.objects
        .filter(tipo_documento=tipo_documento, objeto_id=pk)
        .select_related('usuario')
        .order_by('-created_at')
    )
