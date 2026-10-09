import json
import base64
import io
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.models import Empresa

logger = logging.getLogger(__name__)

# Mapeo de tipos de comprobantes del ERP a códigos numéricos oficiales de ARCA
CBTE_TIPO_MAP = {
    'F_A': 1,    # Factura A
    'ND_A': 2,   # Nota de Débito A
    'NC_A': 3,   # Nota de Crédito A
    'F_B': 6,    # Factura B
    'ND_B': 7,   # Nota de Débito B
    'NC_B': 8,   # Nota de Crédito B
    'F_C': 11,   # Factura C
    'ND_C': 12,  # Nota de Débito C
    'NC_C': 13,  # Nota de Crédito C
    'F_M': 51,   # Factura M
    'REC_OF': 15 # Recibo A / Comprobante Oficial
}

# Códigos inversos para display
CBTE_TIPO_REV_MAP = {v: k for k, v in CBTE_TIPO_MAP.items()}

# RG 5616 - Códigos obligatorios de Condición Frente al IVA del Receptor en ARCA
CONDICION_IVA_RECEPTOR_MAP = {
    'RI': 1,      # IVA Responsable Inscripto
    'MONO': 6,    # Responsable Monotributo
    'EXENTO': 4,  # IVA Sujeto Exento
    'CF': 5,      # Consumidor Final
}

# Template names oficiales de AfipSDK para emisión de PDF
AFIP_PDF_TEMPLATES = {
    1: 'invoice-a',
    2: 'debit-note-a',
    3: 'credit-note-a',
    6: 'invoice-b',
    7: 'debit-note-b',
    8: 'credit-note-b',
    11: 'invoice-c',
    12: 'debit-note-c',
    13: 'credit-note-c',
}


def clean_cuit(cuit_val) -> str:
    """Limpia caracteres no numéricos de un CUIT/CUIL/DNI."""
    if not cuit_val:
        return ""
    return "".join(ch for ch in str(cuit_val) if ch.isdigit())


def get_afip_client():
    """
    Instancia e inicializa el cliente AfipSDK con las credenciales de entorno.
    """
    try:
        from afip import Afip
    except ImportError:
        import sys
        import os
        venv_site = os.path.join(settings.BASE_DIR, 'venv', 'Lib', 'site-packages')
        if os.path.isdir(venv_site) and venv_site not in sys.path:
            sys.path.insert(0, venv_site)
        try:
            from afip import Afip
        except ImportError as exc:
            raise ValidationError(
                "No se encontró la librería 'afip.py'. "
                "Por favor reinicia el servidor Django (Ctrl+C y 'python manage.py runserver') "
                "con el entorno virtual activo (.\\venv\\Scripts\\activate)."
            ) from exc

    access_token = getattr(settings, 'AFIP_ACCESS_TOKEN', '')
    if not access_token:
        raise ValidationError("AFIP_ACCESS_TOKEN no está configurado en las variables de entorno (.env).")

    cuit = int(getattr(settings, 'AFIP_CUIT', 20409378472))
    production = bool(getattr(settings, 'AFIP_PRODUCTION', False))

    return Afip({
        "CUIT": cuit,
        "production": production,
        "access_token": access_token
    })


def consultar_padron_arca(cuit_input: str) -> Dict[str, Any]:
    """
    Consulta en ARCA (ex AFIP) los datos de un contribuyente por su CUIT.
    Intenta consultar RegisterInscriptionProof y RegisterScopeThirteen.
    En entorno de prueba (homologación), si ARCA no tiene el CUIT cargado,
    brinda una respuesta estructurada informativa para testing.
    """
    cuit_clean = clean_cuit(cuit_input)
    if len(cuit_clean) not in (11, 8):
        raise ValidationError(f"El CUIT o documento '{cuit_input}' debe contener 11 dígitos (o DNI de 8 dígitos).")

    afip = get_afip_client()
    cuit_num = int(cuit_clean)

    # Si estamos en entorno de producción o testing, consultamos Padrón
    try:
        # Padrón A5 - Constancia de Inscripción
        taxpayer = afip.RegisterInscriptionProof.getTaxpayerDetails(cuit_num)
        if taxpayer:
            datos = _parsear_contribuyente_a5(cuit_clean, taxpayer)
            datos['modo_prueba'] = False
            return datos
    except Exception as e5:
        logger.info("Consulta Padrón A5 arrojó: %s", e5)
        # Intento secundario con Padrón A13
        try:
            taxpayer_a13 = afip.RegisterScopeThirteen.getTaxpayerDetails(cuit_num)
            if taxpayer_a13:
                datos = _parsear_contribuyente_a13(cuit_clean, taxpayer_a13)
                datos['modo_prueba'] = False
                return datos
        except Exception as e13:
            logger.info("Consulta Padrón A13 arrojó: %s", e13)

    # Si estamos en homologación y ARCA no tiene la réplica de personas físicas
    if not getattr(settings, 'AFIP_PRODUCTION', False):
        # Generamos una respuesta amigable de simulación de homologación
        return {
            "cuit": cuit_clean,
            "razon_social": f"Contribuyente Homologación ({cuit_clean})",
            "condicion_iva": "RI",
            "condicion_iva_display": "IVA Responsable Inscripto",
            "domicilio": "Ruta Provincial 1 - Zona Productiva, Catamarca",
            "localidad": "Tinogasta",
            "provincia": "Catamarca",
            "estado": "ACTIVO",
            "modo_prueba": True,
            "nota": "Consultado en entorno de pruebas ARCA (Homologación). En producción se obtienen los datos oficiales en vivo."
        }

    raise ValidationError(f"No se encontraron datos fiscales en ARCA para el CUIT {cuit_input}.")


def _parsear_contribuyente_a5(cuit: str, data: dict) -> Dict[str, Any]:
    """Interpreta la respuesta de ws_sr_constancia_inscripcion (A5)."""
    persona = data.get('datosGenerales', {})
    razon_social = persona.get('razonSocial') or f"{persona.get('apellido', '')} {persona.get('nombre', '')}".strip()
    
    domicilio_obj = persona.get('domicilioFiscal', {})
    domicilio = domicilio_obj.get('direccion', '')
    localidad = domicilio_obj.get('localidad', '')
    provincia = domicilio_obj.get('descripcionProvincia', '')

    # Determinar Condición IVA
    condicion_iva = "RI"
    condicion_display = "IVA Responsable Inscripto"
    regimen = data.get('datosRegimenGeneral', {})
    monotributo = data.get('datosMonotributo', {})
    
    if monotributo and monotributo.get('categoriaMonotributo'):
        condicion_iva = "MONO"
        condicion_display = f"Responsable Monotributo (Cat. {monotributo.get('categoriaMonotributo')})"
    elif regimen:
        impuestos = regimen.get('impuesto', [])
        if isinstance(impuestos, dict):
            impuestos = [impuestos]
        ids_imp = [str(imp.get('idImpuesto')) for imp in impuestos if isinstance(imp, dict)]
        if '30' in ids_imp: # 30 = IVA
            condicion_iva = "RI"
            condicion_display = "IVA Responsable Inscripto"
        elif '32' in ids_imp: # Exento
            condicion_iva = "EXENTO"
            condicion_display = "IVA Exento"

    return {
        "cuit": cuit,
        "razon_social": razon_social or f"Contribuyente {cuit}",
        "condicion_iva": condicion_iva,
        "condicion_iva_display": condicion_display,
        "domicilio": domicilio,
        "localidad": localidad,
        "provincia": provincia,
        "estado": persona.get('estadoClave', 'ACTIVO')
    }


def _parsear_contribuyente_a13(cuit: str, data: dict) -> Dict[str, Any]:
    """Interpreta la respuesta de ws_sr_padron_a13."""
    persona = data.get('persona', {})
    razon_social = persona.get('razonSocial') or f"{persona.get('apellido', '')} {persona.get('nombre', '')}".strip()
    
    domicilios = persona.get('domicilio', [])
    domicilio_str = ""
    localidad = ""
    provincia = ""
    if isinstance(domicilios, list) and domicilios:
        d = domicilios[0]
        domicilio_str = d.get('direccion', '')
        localidad = d.get('localidad', '')
        provincia = d.get('descripcionProvincia', '')
    elif isinstance(domicilios, dict):
        domicilio_str = domicilios.get('direccion', '')
        localidad = domicilios.get('localidad', '')
        provincia = domicilios.get('descripcionProvincia', '')

    return {
        "cuit": cuit,
        "razon_social": razon_social or f"Contribuyente {cuit}",
        "condicion_iva": "RI",
        "condicion_iva_display": "IVA Responsable Inscripto",
        "domicilio": domicilio_str,
        "localidad": localidad,
        "provincia": provincia,
        "estado": persona.get('estadoClave', 'ACTIVO')
    }


def obtener_ultimo_comprobante_arca(pto_vta: int, tipo_cbte_arca: int) -> int:
    """Consulta el último número de comprobante autorizado en ARCA para un Punto de Venta y Tipo."""
    afip = get_afip_client()
    return afip.ElectronicBilling.getLastVoucher(int(pto_vta), int(tipo_cbte_arca))


def autorizar_comprobante_arca(comprobante) -> Dict[str, Any]:
    """
    Envía un ComprobanteFiscal de VENTA a los Web Services de ARCA (WSFE)
    y obtiene el CAE correspondiente, actualizando el modelo atómicamente.
    """
    if comprobante.tipo_operacion != 'VENTA':
        raise ValidationError("Solo los comprobantes fiscales de VENTA se autorizan ante ARCA en el sistema emisor.")

    if comprobante.cae:
        raise ValidationError(f"El comprobante ya cuenta con CAE autorizado ({comprobante.cae}).")

    afip = get_afip_client()

    cbte_tipo_arca = CBTE_TIPO_MAP.get(comprobante.tipo_comprobante)
    if not cbte_tipo_arca:
        raise ValidationError(f"Tipo de comprobante '{comprobante.tipo_comprobante}' no admitido para facturación electrónica.")

    pto_vta = int(comprobante.punto_de_venta)
    cuit_receptor = clean_cuit(comprobante.cuit)
    
    # DocTipo ARCA: 80 = CUIT, 96 = DNI, 99 = Consumidor Final sin identificar
    if len(cuit_receptor) == 11:
        doc_tipo = 80
        doc_nro = int(cuit_receptor)
    elif len(cuit_receptor) == 8:
        doc_tipo = 96
        doc_nro = int(cuit_receptor)
    else:
        doc_tipo = 99
        doc_nro = 0

    # RG 5616 - Condicion de IVA del Receptor obligatoria
    cond_iva_id = CONDICION_IVA_RECEPTOR_MAP.get(comprobante.condicion_iva, 5) # Default CF

    # Fecha de emisión en formato AAAAMMDD
    fecha_emision = comprobante.fecha_emision or timezone.now().date()
    cbte_fch = fecha_emision.strftime('%Y%m%d')

    # Alícuotas de IVA
    iva_list = []
    for desglose in comprobante.desglose_iva():
        iva_list.append({
            'Id': desglose['id_arca'],
            'BaseImp': float(desglose['base_imponible']),
            'Importe': float(desglose['importe'])
        })

    neto_total = comprobante.neto_gravado_total
    total_iva = comprobante.total_iva
    no_gravado = comprobante.no_gravado or Decimal('0')
    exento = comprobante.exento or Decimal('0')
    percepciones = comprobante.total_tributos
    total = comprobante.total or (neto_total + total_iva + no_gravado + exento + percepciones)
    
    # Moneda (ARCA: PES, DOL, etc)
    moneda_arca = 'DOL' if comprobante.moneda == 'USD' else 'PES'
    cotizacion = float(comprobante.tipo_cambio) if moneda_arca != 'PES' else 1.0

    # Armado del payload para ARCA WSFE
    voucher_data = {
        'CantReg': 1,
        'PtoVta': pto_vta,
        'CbteTipo': cbte_tipo_arca,
        'Concepto': 1, # 1 = Productos (Aceite de oliva / Aceitunas / etc)
        'DocTipo': doc_tipo,
        'DocNro': doc_nro,
        'CondicionIVAReceptorId': cond_iva_id,
        'CbteFch': cbte_fch,
        'ImpTotal': float(total),
        'ImpTotConc': float(no_gravado),
        'ImpNeto': float(neto_total),
        'ImpOpEx': float(exento),
        'ImpIVA': float(total_iva),
        'ImpTrib': float(percepciones),
        'MonId': moneda_arca,
        'MonCotiz': cotizacion,
    }

    if iva_list:
        voucher_data['Iva'] = iva_list

    # Percepciones y otros tributos si aplican
    if percepciones > 0:
        tributos = []
        if (comprobante.percepcion_iibb or 0) > 0:
            tributos.append({'Id': 2, 'Desc': 'Percepción IIBB', 'BaseImp': float(neto_total), 'Alic': 0, 'Importe': float(comprobante.percepcion_iibb)})
        if (comprobante.percepcion_ganancias or 0) > 0:
            tributos.append({'Id': 1, 'Desc': 'Percepción Ganancias', 'BaseImp': float(neto_total), 'Alic': 0, 'Importe': float(comprobante.percepcion_ganancias)})
        if (comprobante.impuestos_municipales or 0) > 0:
            tributos.append({'Id': 3, 'Desc': 'Impuestos Municipales', 'BaseImp': float(neto_total), 'Alic': 0, 'Importe': float(comprobante.impuestos_municipales)})
        if (comprobante.impuestos_internos or 0) > 0:
            tributos.append({'Id': 4, 'Desc': 'Impuestos Internos', 'BaseImp': float(neto_total), 'Alic': 0, 'Importe': float(comprobante.impuestos_internos)})
        if (comprobante.percepcion_iva or 0) > 0:
            tributos.append({'Id': 1, 'Desc': 'Percepción IVA', 'BaseImp': float(neto_total), 'Alic': 0, 'Importe': float(comprobante.percepcion_iva)})
        
        if tributos:
            voucher_data['Tributos'] = tributos

    # Emisión con correlativo automático en ARCA
    res = afip.ElectronicBilling.createNextVoucher(voucher_data)

    cae = str(res.get('CAE', ''))
    cae_vto_str = res.get('CAEFchVto', '')
    voucher_number = res.get('voucherNumber')

    if not cae:
        raise ValidationError("ARCA no devolvió un CAE válido para el comprobante.")

    # Parsear vencimiento de CAE
    cae_vto = None
    if cae_vto_str:
        try:
            cae_vto = datetime.strptime(cae_vto_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    # Actualizar el comprobante en la base de datos
    comprobante.cae = cae
    comprobante.vto_cae = cae_vto
    if voucher_number:
        comprobante.numero_comprobante = str(voucher_number).zfill(8)
    comprobante.save(update_fields=['cae', 'vto_cae', 'numero_comprobante', 'updated_at'])

    # Si hay un webhook configurado para n8n, lo notificamos
    _notificar_webhook_n8n(comprobante, res)

    return {
        "success": True,
        "cae": cae,
        "vto_cae": cae_vto,
        "numero_comprobante": comprobante.numero_comprobante,
        "punto_de_venta": comprobante.punto_de_venta,
        "numero_completo": comprobante.numero_completo
    }


def generar_qr_arca_url(comprobante) -> str:
    """
    Construye la URL oficial de ARCA para el Código QR según normativa RG 4291 / RG 4892.
    """
    cuit_emisor = int(clean_cuit(getattr(settings, 'AFIP_CUIT', 20409378472)))
    pto_vta = int(comprobante.punto_de_venta or 1)
    cbte_tipo = CBTE_TIPO_MAP.get(comprobante.tipo_comprobante, 6)
    nro_cbte = int(comprobante.numero_comprobante or 1)
    
    cuit_rec = clean_cuit(comprobante.cuit)
    doc_tipo_rec = 80 if len(cuit_rec) == 11 else (96 if len(cuit_rec) == 8 else 99)
    doc_nro_rec = int(cuit_rec) if cuit_rec else 0

    fecha_str = (comprobante.fecha_emision or timezone.now().date()).strftime("%Y-%m-%d")
    cae_cod = int(comprobante.cae) if comprobante.cae and comprobante.cae.isdigit() else 0

    qr_payload = {
        "ver": 1,
        "fecha": fecha_str,
        "cuit": cuit_emisor,
        "ptoVta": pto_vta,
        "tipoCmp": cbte_tipo,
        "nroCmp": nro_cbte,
        "importe": float(comprobante.total or 0.0),
        "moneda": "DOL" if comprobante.moneda == "USD" else "PES",
        "ctz": float(comprobante.tipo_cambio) if comprobante.moneda == "USD" else 1.0,
        "tipoDocRec": doc_tipo_rec,
        "nroDocRec": doc_nro_rec,
        "tipoCodAut": "E", # CAE
        "codAut": cae_cod
    }

    json_str = json.dumps(qr_payload, separators=(',', ':'))
    b64_str = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
    
    # URL oficial de validación ARCA
    return f"https://www.arca.gob.ar/fe/qr/?p={b64_str}"


def generar_qr_arca_base64(comprobante) -> str:
    """
    Genera el código QR en memoria como una imagen PNG codificada en base64 (Data URI)
    para poder embeberla en el HTML/PDF de la factura sin conexiones externas.
    """
    try:
        import qrcode
        url = generar_qr_arca_url(comprobante)

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=1,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#1e293b", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        b64_img = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{b64_img}"
    except Exception as e:
        logger.error("Error al generar imagen de Código QR ARCA: %s", e)
        return ""


def generar_pdf_oficial_afipsdk(comprobante) -> Dict[str, Any]:
    """
    Llama al servicio de generación de PDF oficial de AfipSDK para el comprobante autorizado.
    """
    if not comprobante.cae:
        raise ValidationError("El comprobante debe estar previamente autorizado con CAE para emitir el PDF oficial.")

    afip = get_afip_client()
    cbte_tipo_num = CBTE_TIPO_MAP.get(comprobante.tipo_comprobante, 6)
    template_name = AFIP_PDF_TEMPLATES.get(cbte_tipo_num, 'invoice-b')

    cuit_clean = clean_cuit(comprobante.cuit)
    doc_tipo_num = 80 if len(cuit_clean) == 11 else (96 if len(cuit_clean) == 8 else 99)
    
    empresa = Empresa.objects.first()

    vat_breakdown = []
    for desglose in comprobante.desglose_iva():
        vat_breakdown.append({
            "vat_rate": float(desglose['alicuota']),
            "taxable_base": float(desglose['base_imponible']),
            "vat_amount": float(desglose['importe'])
        })

    # Fallback si no hay desgloses pero es Factura A (evitar arreglo vacío que AfipSDK rechazaría)
    if not vat_breakdown and template_name == 'invoice-a':
        vat_breakdown.append({
            "vat_rate": 21.0,
            "taxable_base": float(comprobante.neto_gravado_total or comprobante.total or 0),
            "vat_amount": float(comprobante.total_iva or 0)
        })
        
    # Construir líneas del comprobante (ítems)
    pdf_items = []
    detalles = comprobante.detalles.all()
    if detalles.exists():
        for det in detalles:
            pdf_items.append({
                "description": det.descripcion,
                "quantity": float(det.cantidad),
                "unit_price": float(det.precio_unitario),
                "subtotal": float(det.subtotal_neto),
                "vat_rate": float(det.porcentaje_iva)
            })
    else:
        # Fallback de compatibilidad
        pdf_items.append({
            "description": comprobante.concepto or "Productos Olivícolas",
            "quantity": 1,
            "unit_price": float(comprobante.neto_gravado_total or comprobante.total),
            "subtotal": float(comprobante.neto_gravado_total or comprobante.total),
            "vat_rate": 21.0
        })

    moneda_arca = 'DOL' if comprobante.moneda == 'USD' else 'PES'
    cotizacion = float(comprobante.tipo_cambio) if moneda_arca != 'PES' else 1.0

    pdf_payload = {
        "file_name": f"{comprobante.get_tipo_comprobante_display()}_{comprobante.numero_completo}.pdf",
        "template": {
            "name": template_name,
            "params": {
                "issuer_business_name": empresa.razon_social if empresa and empresa.razon_social else "Empresa S.A.",
                "issuer_cuit": str(getattr(settings, 'AFIP_CUIT', empresa.cuit if empresa else 20409378472)),
                "issuer_address": empresa.direccion if empresa and empresa.direccion else "-",
                "issuer_iva_condition": empresa.condicion_iva if empresa and empresa.condicion_iva else "IVA Responsable Inscripto",
                "issuer_activity_start_date": empresa.inicio_actividades.strftime("%d/%m/%Y") if empresa and empresa.inicio_actividades else "01/01/2020",
                "issuer_gross_income": empresa.ingresos_brutos if empresa and empresa.ingresos_brutos else "0",
                "sales_point": int(comprobante.punto_de_venta),
                "voucher_number": int(comprobante.numero_comprobante),
                "issue_date": comprobante.fecha_emision.strftime("%d/%m/%Y"),
                "cae": comprobante.cae,
                "cae_due_date": comprobante.vto_cae.strftime("%d/%m/%Y") if comprobante.vto_cae else "",
                "concept": 1,
                "sale_condition": "Contado",
                "currency_id": moneda_arca,
                "currency_rate": cotizacion,
                "receiver_name": comprobante.razon_social,
                "receiver_document_type": doc_tipo_num,
                "receiver_document_number": cuit_clean or "0",
                "receiver_address": comprobante.cuenta_corriente.direccion if comprobante.cuenta_corriente else "-",
                "receiver_iva_condition": comprobante.get_condicion_iva_display(),
                "items": pdf_items,
                "vat_breakdown": vat_breakdown,
                "net_amount_taxed": float(comprobante.neto_gravado_total),
                "net_amount_untaxed": float(comprobante.no_gravado or 0),
                "exempt_amount": float(comprobante.exento or 0),
                "tributes_amount": float(comprobante.total_tributos),
                "vat_amount": float(comprobante.total_iva),
                "total_amount": float(comprobante.total)
            }
        }
    }

    return afip.ElectronicBilling.createPDF(pdf_payload)


def _notificar_webhook_n8n(comprobante, resultado_arca: dict):
    """Dispara un webhook HTTP a n8n si la variable N8N_WEBHOOK_URL está configurada."""
    n8n_url = getattr(settings, 'N8N_WEBHOOK_URL', '')
    if not n8n_url:
        return

    import urllib.request
    try:
        payload = {
            "evento": "comprobante.autorizado",
            "timestamp": timezone.now().isoformat(),
            "comprobante_id": comprobante.pk,
            "tipo_comprobante": comprobante.tipo_comprobante,
            "numero_completo": comprobante.numero_completo,
            "total": float(comprobante.total),
            "cae": comprobante.cae,
            "vto_cae": comprobante.vto_cae.strftime("%Y-%m-%d") if comprobante.vto_cae else None,
            "cliente": {
                "razon_social": comprobante.razon_social,
                "cuit": comprobante.cuit,
                "email": comprobante.cuenta_corriente.email if comprobante.cuenta_corriente else None,
                "telefono": comprobante.cuenta_corriente.telefono if comprobante.cuenta_corriente else None,
            }
        }
        data_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            n8n_url,
            data=data_bytes,
            headers={'Content-Type': 'application/json', 'User-Agent': 'ERP-Olivo/ARCA-Webhook'}
        )
        urllib.request.urlopen(req, timeout=4)
        logger.info("Notificación enviada con éxito a n8n: %s", n8n_url)
    except Exception as e:
        logger.warning("No se pudo contactar al webhook n8n (%s): %s", n8n_url, e)
