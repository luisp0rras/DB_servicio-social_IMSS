# Biomédica IMSS - Sistema de Gestión e Inventario de Activos Biomédicos

## 📋 Descripción General
Proyecto *Full-Stack* desarrollado para la gestión, control y auditoría de equipo médico hospitalario en unidades del **IMSS** (Instituto Mexicano del Seguro Social).
El sistema centraliza la información de hospitales, inventarios, usuarios, equipos médicos, proveedores, mantenimientos y un repositorio documental seguro, garantizando una operación concurrente, trazable y robusta entre el personal de Ingeniería Biomédica, con soporte completo para **operación local sin conexión a internet (Modo Offline)** en entornos clínicos.

---

## 🚀 Características Principales y Funcionalidades

- **Operación 100% Funcional Sin Internet (Offline-Ready):** Dependencias visuales (`Bootstrap 5`, `Bootstrap Icons`) y activos gráficos (`favicon.svg`) alojados de forma local dentro del servidor, garantizando que la interfaz renderice con su diseño institucional completo incluso en áreas hospitalarias sin acceso a la red externa.
- **Control de Acceso Basado en Roles (RBAC):** Distinción estricta de privilegios entre **Administradores (`ADMIN`)** y **Empleados (`EMPLEADO`)**, con capacidad de bloqueo temporal (*Inactivo*) y eliminación segura de cuentas desde un módulo dedicado.
- **Gestión Completa (CRUD) por Administradores:**
  - **Equipos Médicos:** Alta individual o masiva, edición de datos/garantías/estatus funcional y baja permanente con limpieza automática de historial y archivos asociados.
  - **Inventarios Hospitalarios:** Asistente de apertura, captura manual o por CSV, cierre formal (`FINALIZADO`) y opción de cancelación/eliminación de levantamientos en curso.
  - **Mantenimientos:** Registro, edición (cambio de proveedor, programación o actualización de próxima fecha y observaciones) y eliminación.
  - **Proveedores:** Directorio con alta, edición de contacto/empresa y eliminación segura sin pérdida de historial en equipos vinculados.
  - **Repositorio Documental:** Subida de minutas, manuales y reportes (PDF/imágenes), edición de título/asociación, reemplazo físico de archivos en servidor y eliminación.
- **Acceso Global de Consulta y Reportes Excel para Empleados:** Cualquier usuario activo puede consultar el historial completo de inventarios de las unidades médicas, filtrar el catálogo maestro en tiempo real y descargar hojas de cálculo institucionales (`.xlsx`) estilizadas mediante `openpyxl`.
- **Importación Masiva con Guía y Plantilla CSV:** Descarga directa de plantilla de ejemplo compatible con Excel y procesamiento automático de lotes omitiendo duplicados de Número de Serie (`SN`) o `NNI`.
- **Motor de Alertas Autónomo (Segundo Plano):**
  - Vigilante asíncrono (`asyncio` + `lifespan`) con persistencia diaria en disco que envía reportes HTML por correo SMTP a los administradores aunque el navegador esté cerrado.
  - Notificaciones de escritorio (**Web Notifications API**) al iniciar sesión cuando existen garantías o mantenimientos próximos a vencer (ventana de 30 días).
- **Recuperación Segura de Contraseña (OTP):** Envío de códigos de verificación de 6 dígitos con vigencia de 15 minutos por correo electrónico para restablecer claves mediante cifrado `bcrypt`.
- **Interfaz Minimalista Adaptativa:** Diseño institucional en *Verde IMSS* (`#13322B`) y *Dorado Sutil* (`#A68250`), con menú lateral colapsable, identidad visual personalizada y vista optimizada para pantallas de laptop y dispositivos móviles.

---

## 🛠️ Stack Tecnológico

### Backend
- **Python 3.10+** & **FastAPI** (API REST asíncrona con tareas en segundo plano).
- **SQLAlchemy** (ORM para mapeo relacional y control de sesiones con `pool_pre_ping`).
- **Pydantic v2** (Validación estricta de esquemas con `ConfigDict` y reglas de negocio).
- **Bcrypt** (Encriptación segura de contraseñas).
- **Openpyxl** (Generación dinámica de reportes nativos en Excel `.xlsx`).

### Base de Datos y Persistencia
- **PostgreSQL** (Base de datos relacional).
- **pgAdmin 4** (Administración de esquemas y consultas).
- Sistema de archivos local estructurado (`archivos_subidos/`) con prefijos únicos de tiempo para evitar colisiones.

### Frontend
- **HTML5**, **Bootstrap 5** & **Bootstrap Icons** (empaquetados localmente en `vendor/` para disponibilidad sin internet).
- **JavaScript (Vanilla)** modular y **CSS3** personalizado.

---

## 📐 Arquitectura de la Base de Datos

El modelo relacional en PostgreSQL consta de 9 entidades principales:

1. **`hospital`**: Catálogo de unidades médicas (nombre, ciudad, estado).
2. **`proveedor`**: Empresas externas de soporte biomédico (correo, teléfono con validación regular, contacto).
3. **`usuarios`**: Personal del sistema (`primernombre`, `primerapellido`, `correo` único, `password_hash`, `username`, `foto_perfil` y `rol`).
4. **`equipos`**: Activos biomédicos con número de serie (`sn`, único), `nni` único, garantía, fechas de expiración y estatus funcional.
5. **`inventarios`**: Censos hospitalarios con fecha de ejecución y estado (`EN_PROCESO` / `FINALIZADO`).
6. **`mantenimientos`**: Historial de intervenciones preventivas, correctivas u otras (`mantenimiento_enum`).
7. **`documentos`**: Metadatos de archivos adjuntos vinculados de forma exclusiva a equipos, mantenimientos o inventarios.
8. **`inventario_equipo`**: Tabla intermedia (Muchos a Muchos) que mapea el historial de equipos por censo.
9. **`inventario_usuario`**: Tabla intermedia que registra la participación del personal en cada inventario.

---

## 📂 Estructura del Proyecto

```text
├── app/
│   ├── __init__.py
│   ├── database.py      # Conexión SQLAlchemy a PostgreSQL con pool_pre_ping
│   ├── main.py          # Endpoints FastAPI, lógica de negocio, Excel, SMTP y tarea en segundo plano
│   ├── models.py        # Modelos ORM de PostgreSQL con índices y borrado en cascada
│   └── schemas.py       # Esquemas Pydantic v2 de entrada/salida y validadores
├── frontend/
│   ├── css/
│   │   └── styles.css   # Estilos minimalistas institucionales y menú colapsable
│   ├── vendor/          # Dependencias locales (Bootstrap 5 CSS/JS y Bootstrap Icons + fuentes)
│   │   ├── fonts/
│   │   │   └── bootstrap-icons.woff2
│   │   ├── bootstrap-icons.min.css
│   │   ├── bootstrap.bundle.min.js
│   │   └── bootstrap.min.css
│   ├── dashboard.html   # Panel principal SPA (8 módulos y modales CRUD)
│   ├── favicon.svg      # Ícono institucional local para pestañas del navegador
│   └── login.html       # Inicio de sesión, registro y recuperación OTP por correo
├── archivos_subidos/    # Almacenamiento local de PDFs, imágenes y avatares (ignorado en Git)
├── .env                 # Variables de entorno (credenciales DB y SMTP, ignorado en Git)
├── .gitignore
├── README.md
└── requirements.txt