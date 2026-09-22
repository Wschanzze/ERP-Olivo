# ERP Olivícola Agroindustrial (Arquitectura Tipo Odoo)

Sistema ERP modular transaccional diseñado para empresas agroindustriales productoras y exportadoras de aceitunas de mesa y aceite de oliva, con soporte para fincas agrícolas, almazaras y fábricas.

Inspirado en la solidez arquitectónica de **Odoo**, este sistema utiliza un backend relacional con el ORM de Django sobre PostgreSQL 16, garantizando transaccionalidad cruzada estricta entre módulos (inventario, costos, finanzas y liquidaciones) mediante una **capa explícita de servicios (`services.py`)**.

---

## 🏗 Arquitectura y Stack Tecnológico

### Backend
- **Python 3.12+ / 3.13** & **Django 5.1.x**
- **PostgreSQL 16**: Motor de base de datos relacional primario (con soporte local de desarrollo y tests).
- **Django REST Framework**: Endpoints analíticos y de agregación interna (preparado para futura App móvil).
- **Celery + Redis**: Tareas asíncronas para cálculo masivo de jornales rurales (`calcular_liquidacion_periodo_task`), reportes y notificaciones.
- **Django Guardian**: Seguridad y permisos a nivel de objeto para aislar el acceso a fincas y cuadros por usuario o rol (`ADMIN_GENERAL`, `ENCARGADO_CAMPO`, `CONTABLE`, etc.).
- **Transacciones Atómicas**: Implementadas con `transaction.atomic()` y `select_for_update()` en la capa de servicios (`services.py`).

### Frontend
- **90% Server-Driven**: **Django Templates + HTMX + Alpine.js + Tailwind CSS**
  - Tablas CRUD, modales y formularios reactivos sin recargar la página.
  - Paleta de diseño olivícola sobria y profesional: Verde Oliva `#3D4A2A` como color de marca, fondo claro `#F8FAF6` y acentos dorados cosecha `#C29B38`.
  - Sidebar fija oscura colapsable y barra superior con avatar circular con iniciales, rol e indicador de finca activa.
- **10% Isla React (Vite + Recharts)**:
  - Montado como componente aislado en el **Tablero Ejecutivo (`dashboard`)**.
  - Consume la API DRF (`/api/v1/dashboard/kpis/`) en tiempo real y renderiza gráficos de superficie por variedad, cosechas y balance de tesorería.

---

## 📦 Estructura de Módulos y Modelo de Datos

El sistema se estructura en 9 aplicaciones Django con claves foráneas cruzadas:

```text
ERP - olivo/
├── docker-compose.yml       # Orquestación de web, postgres 16, redis, celery_worker, celery_beat
├── Dockerfile               # Imagen productiva Python 3.12-slim
├── requirements.txt         # Dependencias Python fijadas
├── .env.example             # Plantilla de variables de entorno
├── manage.py
├── config/                  # Settings, Celery, URLs y WSGI/ASGI
├── apps/
│   ├── core/                # Empresa, Usuario (AbstractUser con roles), Finca, CentroDeCosto
│   ├── campos/              # Cuadro (variedades, densidad, riego), LoteDeCosecha
│   ├── inventario/          # Insumo, Deposito, StockPorDeposito, MovimientoStock, Maquina, Remito
│   ├── parte_diario/        # OrdenDeTrabajo, ParteDiario, Personal e Insumos consumidos
│   ├── personal/            # Empleado (legajos, jornales), RegistroAsistencia, Inscripcion
│   ├── liquidacion/         # PeriodoLiquidacion, LiquidacionEmpleado, ItemLiquidacion (Celery)
│   ├── finanzas/            # Cuenta (Caja/Bancos), CuentaCorriente, MovimientoFinanciero, Cheque
│   ├── costos/              # CostoPorCentro (imputación directa a cuadro/finca)
│   └── dashboard/           # API DRF de KPIs y vista de montaje para la isla React
├── frontend_react/          # Proyecto Vite con React 18, Lucide-React y Recharts
├── static/dist/             # Bundle compilado de React servido por Django
└── templates/               # Plantillas base, componentes (Sidebar, Header) y vistas HTMX
```

---

## ⚡ Reglas y Servicios de Negocio Clave (`services.py`)

1. **Cierre de Parte Diario (`apps/parte_diario/services.py`)**:
   - Valida existencias en depósito y genera automáticamente un `MovimientoStock` de tipo `SALIDA_PARTE_DIARIO`.
   - Descuenta el stock global y el stock específico del depósito.
   - Calcula el costo de insumos y mano de obra e imputa automáticamente un `CostoPorCentro` asociado al Cuadro y Finca.
   - Cambia el estado a `CONFIRMADO_CERRADO` de forma atómica.

2. **Movimientos Financieros y Cuentas Corrientes (`apps/finanzas/services.py`)**:
   - Todo pago a proveedor actualiza el saldo de la `Cuenta` y amortiza la deuda en la `CuentaCorriente` del proveedor.
   - Todo cobro a cliente impacta la caja/banco y reduce el crédito pendiente de cobro.

3. **Cálculo de Sueldos y Jornales (`apps/liquidacion/tasks.py`)**:
   - Tarea Celery que recorre las planillas de `RegistroAsistencia` del período.
   - Calcula días computados, horas extras, aportes jubilatorios y obra social (UATRE), generando el recibo en `LiquidacionEmpleado`.

---

## 🚀 Despliegue con Docker Compose (Recomendado)

### 1. Clonar y configurar variables de entorno
```bash
cp .env.example .env
```

### 2. Levantar los contenedores
```bash
docker compose up -d --build
```
Este comando levantará:
- `db`: PostgreSQL 16 (`localhost:5432`)
- `redis`: Redis 7 (`localhost:6379`)
- `web`: Django + Gunicorn (`localhost:8000`)
- `celery_worker`: Procesador de tareas asíncronas
- `celery_beat`: Planificador de tareas periódicas

### 3. Ejecutar migraciones y cargar datos de demostración
```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py init_erp_demo
```

### 4. Acceder al sistema
- **URL**: [http://localhost:8000](http://localhost:8000)
- **Panel de Administración**: [http://localhost:8000/admin/](http://localhost:8000/admin/)
- **Credenciales por defecto**:
  - **Usuario**: `admin`
  - **Contraseña**: `admin`

---

## 💻 Instalación y Desarrollo Local (Sin Docker)

Si deseas ejecutarlo de forma nativa en tu estación de trabajo:

### 1. Crear y activar entorno virtual
```bash
py -m venv venv
# En Windows (PowerShell):
.\venv\Scripts\Activate.ps1
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Ejecutar migraciones e inicializar datos
```bash
# Para desarrollo rápido local con SQLite o PostgreSQL:
$env:USE_SQLITE="True"
python manage.py migrate
python manage.py init_erp_demo
```

### 4. Compilar el componente React del Dashboard (Opcional si deseas modificarlo)
El bundle compilado ya se encuentra en `static/dist/assets/dashboard.js`. Si deseas recompilarlo:
```bash
cd frontend_react
npm install
npm run build
cd ..
```

### 5. Iniciar el servidor Django
```bash
python manage.py runserver
```

---

## 🧪 Ejecución de Pruebas Automatizadas

El sistema incluye tests unitarios e integrados que validan la capa transaccional, los endpoints de la API y el renderizado HTMX:

```bash
python manage.py test
```

Salida esperada:
```text
Creating test database for alias 'default'...
Ran 17 tests in 2.208s
OK
```

---

## 🏛️ Facturación Electrónica ARCA y Automatizaciones n8n

* **ARCA (ex AFIP):** Integración nativa con Web Services (WSFE y Padrón A5/A13) mediante AfipSDK para emisión de Facturas A, B, C con CAE y código QR oficial (RG 4291 / RG 5616).
* **Manual de Automatización con n8n:** Ver [docs/MANUAL_INTEGRACION_N8N.md](docs/MANUAL_INTEGRACION_N8N.md) para la configuración paso a paso de envío de facturas por WhatsApp/Email, lectura de comprobantes de proveedores y recordatorios de cobranza.
