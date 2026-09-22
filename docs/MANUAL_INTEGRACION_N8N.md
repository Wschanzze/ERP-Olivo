# 🤖 Manual de Integración: ERP Olivo + n8n + ARCA (ex AFIP)

Este manual documenta la arquitectura, configuración y flujos de trabajo paso a paso para conectar **n8n** (plataforma de orquestación y automatización de procesos) con el **ERP Olivo** y **ARCA (ex AFIP)**.

---

## 📋 Índice
1. [Arquitectura y Casos de Uso](#1-arquitectura-y-casos-de-uso)
2. [Requisitos Previos](#2-requisitos-previos)
3. [Flujo 1: Envío Automático de Facturas con CAE por WhatsApp y Email](#3-flujo-1-envío-automático-de-facturas-con-cae-por-whatsapp-y-email)
4. [Flujo 2: Recepción y Validación de Facturas de Proveedores](#4-flujo-2-recepción-y-validación-de-facturas-de-proveedores)
5. [Flujo 3: Recordatorios Automáticos de Cobranzas Vencidas](#5-flujo-3-recordatorios-automáticos-de-cobranzas-vencidas)
6. [Template JSON Importable para n8n](#6-template-json-importable-para-n8n)
7. [Seguridad y Buenas Prácticas](#7-seguridad-y-buenas-prácticas)

---

## 1. Arquitectura y Casos de Uso

El ERP Olivo gestiona transaccionalmente las finanzas, cuentas corrientes y la facturación electrónica ante ARCA. **n8n** actúa como el orquestador periférico para comunicación externa, tareas asíncronas e inteligencia de negocio:

```
┌─────────────────┐       (1) Emisión Factura      ┌──────────────────┐
│    ERP Olivo    │ ─────────────────────────────> │  ARCA / WSFE     │
│    (Django)     │ <───────────────────────────── │  (con AfipSDK)   │
└────────┬────────┘            CAE + N° Comp       └──────────────────┘
         │
         │ (2) Webhook POST
         ▼
┌─────────────────┐
│       n8n       │ ───► WhatsApp API (Envío de PDF al cliente)
│   (Workflow)    │ ───► Email SMTP / Resend / Gmail (Factura formal)
└─────────────────┘ ───► Notificación a Tesorería en Telegram / Slack
```

### Casos de uso habilitados:
* **Envío instantáneo omnicanal:** El cliente recibe la factura formal con CAE y código QR por WhatsApp y correo apenas el operador la aprueba en el ERP.
* **Procesamiento de compras:** Lectura automática de facturas de proveedores que llegan al email corporativo, verificación de CAE en ARCA y precarga de borrador en Cuentas por Pagar.
* **Cobranzas preventivas:** Avisos automáticos a clientes con saldos vencidos en sus cuentas corrientes comerciales.

---

## 2. Requisitos Previos

1. **Instancia de n8n activa:**
   * n8n Cloud o Self-Hosted (vía Docker en el servidor de la empresa).
2. **Acceso a la configuración del ERP Olivo:**
   * Archivo `.env` en la raíz del proyecto.
3. **Servicio de Mensajería (a elección para n8n):**
   * **WhatsApp:** Evolution API, Z-API, Baileys, o WhatsApp Cloud API oficial de Meta.
   * **Email:** Servidor SMTP corporativo, Gmail OAuth2, Resend, o SendGrid.

---

## 3. Flujo 1: Envío Automático de Facturas con CAE por WhatsApp y Email

Cada vez que se emite o autoriza una factura en el ERP (`apps/finanzas/afip_service.py`), el sistema dispara automáticamente un webhook HTTP hacia n8n si la variable `N8N_WEBHOOK_URL` está definida.

### Paso 1: Crear el Webhook Trigger en n8n
1. En n8n, crea un nuevo Workflow llamado **"ERP Olivo - Envío de Factura ARCA"**.
2. Agrega un nodo **Webhook**:
   * **HTTP Method:** `POST`
   * **Path:** `factura-emitida`
   * **Response Mode:** `When Last Node Finishes` (o `Immediately` con código `200`).
3. Copia la URL generada:
   * Modo Test: `https://tu-n8n.com/webhook-test/factura-emitida`
   * Modo Producción: `https://tu-n8n.com/webhook/factura-emitida`

### Paso 2: Configurar la URL en el ERP Olivo
En el archivo `.env` del ERP, configura:
```env
N8N_WEBHOOK_URL=https://tu-n8n.com/webhook/factura-emitida
```

### Paso 3: Estructura del Payload enviado por Django
El ERP envía automáticamente el siguiente JSON estandarizado:
```json
{
  "evento": "comprobante.autorizado",
  "timestamp": "2026-09-22T15:30:00Z",
  "comprobante_id": 45,
  "tipo_comprobante": "F_B",
  "numero_completo": "00001-00035201",
  "total": 15420.50,
  "cae": "86380918421149",
  "vto_cae": "2026-10-02",
  "cliente": {
    "razon_social": "Distribuidora Aceitera Mayorista S.A.",
    "cuit": "30-99887766-5",
    "email": "compras@distribuidora.com",
    "telefono": "+5493804123456"
  }
}
```

### Paso 4: Configurar los Nodos en n8n
1. **Nodo 1 (Webhook):** Recibe el payload anterior.
2. **Nodo 2 (HTTP Request - Obtener PDF Oficial):**
   * **Method:** `GET`
   * **URL:** `https://tu-erp-olivo.com/finanzas/comprobante/{{ $json.comprobante_id }}/pdf-oficial/`
   * **Response:** File / Binary data (Nombre de propiedad: `data`).
3. **Nodo 3 (Switch / IF):**
   * Evalúa si `$json.cliente.telefono` o `$json.cliente.email` están presentes.
4. **Nodo 4 (Envío WhatsApp):**
   * Envía mensaje con texto:
     > *"Estimado {{ $json.cliente.razon_social }}, adjuntamos su Factura Electrónica N° {{ $json.numero_completo }} por un total de ${{ $json.total }}. CAE N° {{ $json.cae }} con vto {{ $json.vto_cae }}. ¡Gracias por confiar en Olivar del Valle S.A.!"*
   * Adjunta el archivo binario del PDF.
5. **Nodo 5 (Envío Email):**
   * Destinatario: `{{ $json.cliente.email }}`
   * Asunto: `Factura {{ $json.numero_completo }} - Olivar del Valle S.A.`
   * Adjunto: Archivo binario.

---

## 4. Flujo 2: Recepción y Validación de Facturas de Proveedores

Permite automatizar la carga de facturas de compras de proveedores de insumos (fertilizantes, botellas, fletes).

### Arquitectura del Flujo:
1. **Trigger Email (IMAP / Gmail):** Monitorea la casilla `proveedores@empresa.com` buscando correos nuevos con asunto que contenga *"Factura"* y archivos adjuntos `.pdf` o `.xml`.
2. **Nodo de Extracción (OCR / LLM):** Extrae CUIT del emisor, punto de venta, número de factura, importe neto, alícuotas de IVA y CAE.
3. **Consulta de Validez en ARCA:**
   * n8n puede consultar la validez del comprobante con AfipSDK mediante el método `getVoucherInfo`.
4. **Creación en ERP Olivo:**
   * n8n ejecuta un `POST` al endpoint `/finanzas/comprobante/crear/` con los datos validados para que quede cargada en estado *"Pendiente de Pago"* en el Libro de IVA Compras.

---

## 5. Flujo 3: Recordatorios Automáticos de Cobranzas Vencidas

Para optimizar el flujo de caja de la empresa:

1. **Trigger Schedule (Cron):** Se ejecuta todos los lunes a las 09:00 AM.
2. **Consulta a Django:** n8n consulta las cuentas corrientes con saldo deudor y comprobantes con fecha de vencimiento superada.
3. **Generación de Estado de Cuenta:**
   * n8n descarga el extracto en PDF.
4. **Notificación personalizada:**
   * Envía un mensaje recordatorio al cliente con el detalle de las facturas adeudadas y el CBU bancario para realizar la transferencia.

---

## 6. Template JSON Importable para n8n

Para crear el flujo de envío de facturas rápidamente en n8n:
1. Abre tu panel de n8n.
2. Menú superior derecho &rarr; **Import from JSON**.
3. Pega el siguiente bloque:

```json
{
  "name": "ERP Olivo - Notificacion Factura ARCA",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "factura-emitida",
        "options": {}
      },
      "id": "webhook-trigger-1",
      "name": "Webhook ERP Olivo",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [240, 300]
    },
    {
      "parameters": {
        "conditions": {
          "options": {
            "caseSensitive": true,
            "leftValue": "",
            "typeValidation": "strict"
          },
          "conditions": [
            {
              "id": "cond-email",
              "leftValue": "={{ $json.cliente.email }}",
              "rightValue": "",
              "operator": {
                "type": "string",
                "operation": "notEmpty"
              }
            }
          ],
          "combinator": "and"
        }
      },
      "id": "check-email",
      "name": "¿Tiene Email?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [480, 300]
    },
    {
      "parameters": {
        "chatId": "=@tu_canal_tesoreria",
        "text": "=🧾 *Nueva Factura Emitida en ERP Olivo*\n\n• *Comprobante:* {{ $json.numero_completo }}\n• *Cliente:* {{ $json.cliente.razon_social }}\n• *Total:* ${{ $json.total }}\n• *CAE:* `{{ $json.cae }}` (Vto: {{ $json.vto_cae }})\n\n_Emitido exitosamente ante ARCA (ex AFIP)_",
        "additionalFields": {
          "parse_mode": "Markdown"
        }
      },
      "id": "notify-telegram",
      "name": "Aviso a Tesorería (Telegram)",
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1.2,
      "position": [480, 500]
    }
  ],
  "connections": {
    "Webhook ERP Olivo": {
      "main": [
        [
          {
            "node": "¿Tiene Email?",
            "type": "main",
            "index": 0
          },
          {
            "node": "Aviso a Tesorería (Telegram)",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  },
  "settings": {
    "executionOrder": "v1"
  }
}
```

---

## 7. Seguridad y Buenas Prácticas

1. **Protección de Webhooks con Token Secreto:**
   * Es recomendable incluir un encabezado de autorización en la petición desde el ERP:
     ```python
     headers = {
         'Content-Type': 'application/json',
         'X-ERP-Secret': settings.N8N_WEBHOOK_SECRET
     }
     ```
   * En el nodo Webhook de n8n, se valida que el encabezado `X-ERP-Secret` coincida con la clave definida.
2. **Idempotencia:**
   * Cada comprobante posee un `comprobante_id` único y correlativo de ARCA. Configura el nodo de n8n para no reenviar mensajes duplicados si el webhook se dispara más de una vez.
3. **Resguardo de Archivos en Almacenamiento Seguro:**
   * Si guardas copias de las facturas en Google Drive o AWS S3 mediante n8n, organízalas por carpetas:
     `Facturacion_ARCA / {Año} / {Mes} / {Tipo}_{Numero}.pdf`.
