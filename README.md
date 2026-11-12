# DB_servicio-social_IMSS

## Descripción

Proyecto desarrollado durante el servicio social para la gestión e inventario de equipo médico hospitalario en unidades del IMSS.

El objetivo es centralizar la información de hospitales, inventarios, usuarios participantes, equipos médicos, proveedores, mantenimientos y documentación asociada, permitiendo un control eficiente, trazable y concurrente de los recursos biomédicos.

---

## Objetivos

- Registrar hospitales y sus levantamientos de inventario.
- Asociar usuarios participantes y sus roles a cada inventario.
- Gestionar equipos médicos mediante Número Nacional de Inventario (NNI) y número de serie (SN).
- Registrar mantenimientos preventivos, correctivos y otros.
- Gestionar el catálogo de proveedores externos y su contacto.
- Asociar documentación única a equipos, mantenimientos o inventarios.
- Implementar alertas para garantías y mantenimientos próximos.
- Proveer una API REST con FastAPI para el manejo seguro de sesiones y transacciones concurrentes.

---

## Tecnologías utilizadas

### Base de datos y control de versiones
- PostgreSQL
- pgAdmin 4 / pgModeler
- Git & GitHub

### En integración (Backend y Frontend)
- Python 3 + FastAPI (API REST y lógica de negocio)
- SQLAlchemy & Pydantic (ORM y validación de esquemas)
- HTML/CSS/Bootstrap o React (Frontend planeado)
- Almacenamiento local/externo para gestión documental

---

## Modelo de datos

El sistema está compuesto por las siguientes entidades principales y tablas asociativas:

### 1. Hospitales (`hospital`)
Permite registrar las unidades médicas (nombre, ciudad, estado) donde se realizan los inventarios.

### 2. Inventarios (`inventarios`)
Representa cada proceso de levantamiento de inventario realizado en un hospital determinado y en una fecha específica.

### 3. Usuarios (`usuarios`)
Personal registrado en el sistema (nombre completo, correo único y contraseña encriptada mediante `password_hash`).

### 4. Relación Inventario - Usuarios (`inventario_usuario`)
Tabla intermedia que vincula a los usuarios con cada inventario realizado, definiendo su rol mediante el tipo `rol_enum` (`ENCARGADO`, `PARTICIPANTE`).

### 5. Equipos (`equipos`)
Registro maestro de equipo médico vinculado a su hospital y proveedor, que incluye:
- Nombre del equipo
- Área y Subárea
- Marca y Modelo
- Número de serie (`sn`, único)
- Número Nacional de Inventario (`nni`, único)
- Vigencia de garantía (`garantia` y `fecha_expgarantia`)
- Estado funcional (`estatusfuncional`) y observaciones

### 6. Relación Inventario - Equipos (`inventario_equipo`)
Tabla intermedia que mantiene el historial de qué equipos fueron censados en cada proceso de inventario.

### 7. Proveedores (`proveedor`)
Empresas externas encargadas de suministros y mantenimientos (incluye validación por expresión regular para formato telefónico y datos de contacto).

### 8. Mantenimientos (`mantenimientos`)
Registro histórico de intervenciones asociadas a un equipo y un proveedor, clasificadas mediante `mantenimiento_enum` (`PREVENTIVO`, `CORRECTIVO`, `OTRO`), fecha de realización y próxima fecha programada.

### 9. Documentos (`documentos`)
Permite asociar archivos (minutas, manuales, reportes, garantías) mediante su nombre y ruta de almacenamiento a una entidad específica:
- Equipos
- Mantenimientos
- Inventarios

---

## Integridad de datos y arquitectura

Para garantizar la consistencia de la información y permitir que múltiples usuarios trabajen de manera simultánea desde la aplicación web sin condiciones de carrera (*race conditions*), el sistema implementa:

- **Control transaccional desde el Backend:** La asociación entre el hospital activo, el inventario en curso, los usuarios participantes y los equipos registrados se gestiona de forma explícita mediante transacciones en los *endpoints* de FastAPI, prescindiendo de tablas de estado global o *triggers* de sesión única.
- **Validación de Garantías (`CHECK`):** Restricción a nivel base de datos y esquema que exige una fecha de expiración (`fecha_expgarantia`) sí y solo sí el campo booleano `garantia` es verdadero.
- **Exclusividad Documental (`CHECK`):** Restricción `documentos_check` que asegura que cada documento subido pertenezca estrictamente a una sola entidad a la vez (`id_equipo`, `id_mantenimiento` o `id_inventario`).
- **Unicidad de Identificadores:** Restricciones `UNIQUE` en números de serie (`sn`), `nni` y correos electrónicos.

---

## Flujo de inventario (Arquitectura API)

### 1. Selección o registro de hospital
Se identifica o da de alta la unidad médica donde se llevará a cabo el levantamiento.

### 2. Apertura de inventario
Se crea un registro en `inventarios` vinculando explícitamente el `id_hospital` y la fecha de ejecución.

### 3. Asignación de participantes
Se vinculan los usuarios participantes al `id_inventario` correspondiente dentro de `inventario_usuario` especificando su rol (`ENCARGADO` o `PARTICIPANTE`).

### 4. Registro o importación masiva de equipos
Los equipos pueden registrarse individualmente o importarse de forma masiva mediante archivos CSV:

```text
Archivo CSV / Petición API
↓
Validación de estructura y duplicados (SN / NNI)
↓
Inserción en tabla `equipos` (con `id_hospital` asociado)
↓
Vinculación transaccional en `inventario_equipo`
