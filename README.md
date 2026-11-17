# Biomédica IMSS - Sistema de Gestión e Inventario de Equipo Médico

Sistema web *Full-Stack* desarrollado durante mi Servicio Social en Ingeniería Biomédica para digitalizar, centralizar y auditar el inventario de equipo médico hospitalario en unidades del **IMSS** (Instituto Mexicano del Seguro Social) en Chihuahua.

La aplicación permite administrar hospitales, levantamientos de inventario, altas individuales de equipo, transferencias de activos entre unidades médicas, mantenimientos preventivos/correctivos, proveedores, usuarios y documentación técnica, operando de forma fluida incluso **sin conexión a internet (Modo Offline)** dentro de las áreas hospitalarias.

---

## Características Principales

- **Operación 100% Funcional Sin Internet (Offline-Ready):** Todas las dependencias visuales (`Bootstrap 5`, `Bootstrap Icons` y fuentes locales en `vendor/`) así como los íconos institucionales (`favicon.svg`) están alojados localmente dentro del servidor, garantizando que la interfaz cargue completa en redes hospitalarias internas sin salida a internet.
- **Control de Acceso Basado en Roles (RBAC):** Diferenciación de permisos entre **Administradores (`ADMIN`)**, **Empleados (`EMPLEADO`)** y cuentas bloqueadas (**`INACTIVO`**), con módulo exclusivo para gestión de cuentas.
- **Gestión Integral de Activos Biomédicos:**
  - **Catálogo Maestro y Filtros en Tiempo Real:** Búsqueda instantánea por nombre, Número Nacional de Inventario (`NNI`), Número de Serie (`SN`), hospital actual, inventario/fecha, proveedor, área, marca, garantía y estatus funcional.
  - **Alta Individual de Equipos:** Registro directo de nuevas adquisiciones asignándolas a una unidad médica sin necesidad de abrir un levantamiento de inventario completo.
  - **Transferencias entre Hospitales con Bitácora Histórica:** Reubicación o préstamo de equipos médicos de un hospital a otro, actualizando su ubicación actual y registrando cada movimiento en una bitácora inmutable (`transferencias_equipo`) con hospital origen, destino, fecha/hora, motivo u oficio y usuario responsable.
  - **Importación Masiva por CSV:** Descarga de plantilla compatible con Excel y carga masiva de lotes dentro de inventarios activos, omitiendo duplicados de `SN` o `NNI` automáticamente.
- **Levantamiento e Historial de Inventarios:** Apertura de censos por unidad médica y fecha, asignación de personal participante, captura manual o por CSV, cierre formal (`FINALIZADO`) y cancelación controlada.
- **Control de Mantenimientos y Proveedores:** Registro y seguimiento de intervenciones preventivas, correctivas u otras (`mantenimiento_enum`), programación de próximas fechas y directorio de empresas proveedoras.
- **Repositorio Documental:** Carga, consulta en navegador, edición y reemplazo físico de minutas, manuales y reportes (PDF e imágenes) asociados a inventarios, equipos o mantenimientos.
- **Reportes Institucionales en Excel (`.xlsx`):** Exportación dinámica de inventarios completos o selecciones filtradas con formato institucional IMSS mediante `openpyxl`.
- **Motor de Alertas Autónomo:**
  - Tarea en segundo plano (`asyncio` + `lifespan`) con persistencia en disco que envía un correo HTML diario a los Administradores cuando existen garantías próximas a vencer o mantenimientos programados dentro de los próximos 30 días.
  - Notificaciones de escritorio (**Web Notifications API**) al iniciar sesión.
- **Seguridad y Recuperación de Contraseña:** Cifrado de claves con `bcrypt` y restablecimiento mediante códigos temporales OTP de 6 dígitos (vigencia de 15 minutos) enviados por correo SMTP.

---

## Stack Tecnológico

- **Backend:** Python 3.10+, FastAPI, Uvicorn (ASGI), SQLAlchemy (ORM con `pool_pre_ping`), Pydantic v2, Bcrypt, Openpyxl.
- **Base de Datos:** PostgreSQL 18 (administrada con pgAdmin 4).
- **Frontend:** HTML5, CSS3 personalizado (paleta institucional Verde IMSS `#13322B` y Dorado `#A68250`), JavaScript (Vanilla) y Bootstrap 5 + Bootstrap Icons en local.

---

## Arquitectura de la Base de Datos

El esquema relacional en PostgreSQL (`sql/01_tablas.sql`) está conformado por **10 tablas**:

1. **`hospital`**: Catálogo de unidades médicas (nombre, ciudad, estado).
2. **`proveedor`**: Directorio de empresas de soporte biomédico (correo único, teléfono validado con regex, contacto).
3. **`usuarios`**: Cuentas de acceso, credenciales cifradas (`password_hash`), perfil (`username`, `foto_perfil`) y rol (`ADMIN`, `EMPLEADO`, `INACTIVO`).
4. **`equipos`**: Catálogo maestro de activos biomédicos (`id_hospital`, `id_proveedor`, `nombre_equipo`, `area`, `subarea`, `marca`, `modelo`, `sn`, `nni`, `garantia`, `fecha_expgarantia` con validación `CHECK`, `estatusfuncional` y `observaciones`).
5. **`inventarios`**: Censos hospitalarios por unidad y fecha con control de estado (`EN_PROCESO` / `FINALIZADO`).
6. **`mantenimientos`**: Historial y programación de intervenciones (`PREVENTIVO`, `CORRECTIVO`, `OTRO`).
7. **`documentos`**: Metadatos de archivos físicos vinculados a un equipo, mantenimiento o inventario.
8. **`inventario_equipo`**: Tabla intermedia (N:M) que conserva el historial de qué equipos fueron censados en cada inventario.
9. **`inventario_usuario`**: Tabla intermedia (N:M) que registra qué usuarios participaron en cada levantamiento.
10. **`transferencias_equipo`**: Bitácora histórica de movimientos de equipos entre hospitales (`id_equipo`, `id_hospital_origen`, `id_hospital_destino`, `id_usuario`, `fecha`, `motivo`).

---

## Estructura del Proyecto

```text
├── app/
│   ├── __init__.py
│   ├── database.py          # Configuración de motor SQLAlchemy, pool_pre_ping y sesiones DB
│   ├── main.py              # Endpoints REST, lógica de negocio, Excel, SMTP y vigilante en segundo plano
│   ├── models.py            # Modelos ORM de las 10 tablas en PostgreSQL
│   └── schemas.py           # Esquemas Pydantic v2 de validación y respuesta
├── frontend/
│   ├── css/
│   │   └── styles.css       # Estilos minimalistas institucionales y menú lateral colapsable
│   ├── vendor/              # Dependencias locales para operación offline (Bootstrap 5 y Bootstrap Icons)
│   │   ├── fonts/
│   │   │   └── bootstrap-icons.woff2
│   │   ├── bootstrap-icons.min.css
│   │   ├── bootstrap.bundle.min.js
│   │   └── bootstrap.min.css
│   ├── dashboard.html       # Interfaz principal SPA (8 módulos y modales CRUD/Transferencias)
│   ├── favicon.svg          # Ícono institucional local para pestañas y notificaciones
│   └── login.html           # Inicio de sesión, registro y recuperación OTP
├── sql/
│   └── 01_tablas.sql        # Script DDL completo de creación de tablas, restricciones e índices
├── archivos_subidos/        # Almacenamiento local de PDFs, imágenes y avatares (ignorado en Git)
├── .env                     # Variables de entorno locales (ignorado en Git)
├── .gitignore
├── README.md
└── requirements.txt