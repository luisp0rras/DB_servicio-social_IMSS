# Biomédica IMSS - Sistema de Gestión e Inventario de Activos Biomédicos

## 📋 Descripción General

Proyecto *Full-Stack* desarrollado para la gestión, control y auditoría de equipo médico hospitalario en unidades del **IMSS** (Instituto Mexicano del Seguro Social).
El sistema centraliza la información de hospitales, inventarios, usuarios, equipos médicos, proveedores, mantenimientos y un repositorio documental seguro, garantizando una operación concurrente, trazable y robusta entre el personal de Ingeniería Biomédica.

## 🚀 Características Principales y Funcionalidades

- **Control de Accesso Basado en Roles (RBAC):** Distinción estricta de privilegios entre **Administradores (`ADMIN`)** y **Empleados (`EMPLEADO`)**, con capacidad de bloqueo temporal (*Inactivo*) y eliminación segura de cuentas desde una sección dedicada.
- **Flujo de Inventarios Hospitalarios (5 Pasos):** Asistente interactivo para la selección o creación de unidades médicas, asignación dinámica de participantes, captura manual o importación masiva mediante archivos **CSV** (con omisión automática de duplicados de SN/NNI), y cierre formal de inventarios.
- **Catálogo Maestro y Reportes en Excel (`.xlsx`):** Motor de filtrado en tiempo real combinando inventarios, hospitales, proveedores, áreas, marcas, garantías y estatus funcional, con exportación a hojas de cálculo institucionales estilizadas mediante `openpyxl`.
- **Motor de Alertas y Notificaciones:**
    - Alertas visuales y de escritorio (**Web Notifications API**) para garantías y mantenimientos próximos a expirar (ventana de 30 días).
    - Envío automatizado de reportes en formato **HTML** mediante servidor SMTP a todos los administradores registrados.
- **Recuperación Segura de Contraseña (OTP):** Envío de códigos de verificación de 6 dígitos con vigencia temporal por correo electrónico para restablecer claves mediante cifrado `bcrypt`.
- **Repositorio Documental Seguro:** Almacenamiento centralizado de minutas, manuales y reportes asociados de forma exclusiva a equipos, mantenimientos o inventarios, con nombres protegidos contra colisiones y visualización directa en navegador.

## 🛠️ Stack Tecnológico

### Backend

- **Python 3.10+** & **FastAPI** (API REST asíncrona de alta velocidad).
- **SQLAlchemy** (ORM para mapeo relacional).
- **Pydantic v2** (Validación estricta de esquemas y validadores personalizados).
- **Bcrypt** (Seguridad y encriptación de contraseñas).
- **Openpyxl** (Generación de reportes nativos en Excel).

### Base de Datos y Persistencia

- **PostgreSQL** (Base de datos relacional).
- **pgAdmin 4** (Gestión de esquemas y consultas).
- Sistema de archivos local estructurado para avatares y documentos PDF/imágenes.

### Frontend

- **HTML5**, **Bootstrap 5** & **Bootstrap Icons**.
- **JavaScript (Vanilla)** modular con diseño minimalista e institucional (*Verde IMSS* `#13322B` y *Dorado Sutil* `#A68250`).

## 📐 Arquitectura de la Base de Datos

El modelo relacional en PostgreSQL consta de las siguientes entidades:

1. **`hospital`**: Catálogo de unidades médicas (nombre, ciudad, estado).
2. **`proveedor`**: Empresas externas de soporte biomédico (correo, teléfono con validación regular, contacto).
3. **`usuarios`**: Personal del sistema (`primernombre`, `primerapellido`, `correo` único, `password_hash`, `username`, `foto_perfil` y `rol`).
4. **`equipos`**: Activos biomédicos con número de serie (`sn`, único), NNI único, garantía, fechas de expiración y estatus funcional.
5. **`inventarios`**: Censos hospitalarios con fecha de ejecución y estado (`EN_PROCESO` / `FINALIZADO`).
6. **`mantenimientos`**: Historial de intervenciones preventivas, correctivas u otras (`mantenimiento_enum`).
7. **`documentos`**: Metadatos de archivos adjuntos vinculados de forma exclusiva a equipos, mantenimientos o inventarios.
8. **`inventario_equipo`**: Tabla intermedia (Muchos a Muchos) que mapea el historial de equipos por censo.
9. **`inventario_usuario`**: Tabla intermedia que registra la participación del personal en cada inventario.

## ⚙️ Guía de Instalación y Ejecución Local

### 1. Clonar el repositorio y configurar el entorno virtual

```
git clone https://github.com/tu-usuario/DB_servicio-social_IMSS.git
cd DB_servicio-social_IMSS
python -m venv venv
venv\Scripts\Activate
```

### 2. Instalar dependencias

```
pip install -r requirements.txt
```

### 3. Configurar variables de entorno (`.env`)

Crea un archivo llamado `.env` en la raíz del proyecto con la siguiente estructura:

```
DATABASE_URL=postgresql://tu_usuario:tu_password@localhost:5432/biomedica_imss
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_correo@gmail.com
SMTP_PASSWORD=tu_contraseña_de_aplicacion_de_16_caracteres
```

### 4. Ejecutar el servidor de desarrollo

```
uvicorn app.main:app --reload
```

Una vez encendido el servidor, abre tu navegador e ingresa a:
👉 **`http://127.0.0.1:8000/app/login.html`**

## 🔒 Seguridad y Buenas Prácticas Implementadas

- **Integridad Transaccional:** Todas las operaciones críticas de inserción y modificación se ejecutan mediante sesiones controladas en SQLAlchemy.
- **Protección de Llaves Foráneas:** Eliminación en cascada segura (`ondelete="CASCADE"`) y limpieza previa de relaciones intermedias al borrar registros.
- **Blindaje de Credenciales:** Ocultamiento automático de hashes de contraseña en esquemas Pydantic y separación de credenciales mediante `.gitignore`.