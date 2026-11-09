# Flujo de Trabajo del Sistema

## Descripción

El sistema fue diseñado para gestionar inventarios de equipo médico hospitalario, permitiendo registrar hospitales, inventarios, usuarios participantes, equipos médicos, proveedores, mantenimientos y documentos asociados.

La automatización del flujo se realiza mediante triggers y tablas auxiliares que permiten identificar el hospital y el inventario activos.

---

# Flujo General

```text
Hospital
↓
Inventario
↓
Usuarios participantes
↓
Equipos
↓
Proveedores
↓
Mantenimientos
↓
Documentos
```

---

# 1. Registro de Hospital

Se registra el hospital donde se realizará el inventario.

```sql
INSERT INTO hospital (...);
```

Al registrarse:

```text
hospital
↓
trigger_hospital_actual
↓
hospital_actual
```

La tabla auxiliar `hospital_actual` almacena el hospital activo para los siguientes procesos.

---

# 2. Creación de Inventario

Se registra un nuevo inventario.

```sql
INSERT INTO inventarios (...);
```

Proceso automático:

```text
hospital_actual
↓
trigger_inventario_hospital_actual
↓
inventarios
↓
trigger_inventario_activo
↓
inventario_actual
```

Resultado:

- El inventario queda asociado automáticamente al hospital activo.
- El inventario se convierte en el inventario activo.

---

# 3. Asociación de Usuarios

Los usuarios que participan en el inventario pueden registrarse o asociarse manualmente.

Relación:

```text
usuarios
↓
inventario_usuario
↓
inventarios
```

Consulta de verificación:

```sql
SELECT ...
FROM inventario_usuario;
```

---

# 4. Registro de Equipos

Los equipos pueden registrarse manualmente o mediante importación masiva.

### Registro manual

```sql
INSERT INTO equipos (...);
```

### Registro masivo

```text
Archivo CSV
↓
Tabla temporal
↓
Validación
↓
Tabla equipos
```

Al insertarse un equipo:

```text
equipos
↓
trigger_equipo_inventario_hospital
↓
inventario_equipo
↓
hospital asociado
```

Resultado:

- El equipo se asocia automáticamente al inventario activo.
- El equipo se asocia automáticamente al hospital correspondiente.

---

# 5. Registro de Proveedores

Los proveedores son empresas encargadas de realizar servicios y mantenimientos sobre los equipos.

```sql
INSERT INTO proveedor (...);
```

Información almacenada:

- Nombre del proveedor
- Correo
- Teléfono
- Nombre de contacto

---

# 6. Registro de Mantenimientos

Los mantenimientos pueden registrarse utilizando:

- NNI
- Número de serie
- ID del equipo

Ejemplo:

```sql
INSERT INTO mantenimientos (...);
```

Tipos de mantenimiento:

```text
PREVENTIVO
CORRECTIVO
OTRO
```

Información almacenada:

- Proveedor responsable
- Equipo asociado
- Fecha del mantenimiento
- Próxima fecha programada
- Observaciones

---

# 7. Registro de Documentos

Los documentos permiten almacenar información relacionada con:

- Inventarios
- Equipos
- Mantenimientos

Ejemplos:

```text
Minutas
Actas
Manuales
Garantías
Reportes técnicos
Certificados
```

Relación permitida:

```text
Documento
↓
Inventario

o

Documento
↓
Equipo

o

Documento
↓
Mantenimiento
```

Un documento solamente puede estar asociado a una entidad al mismo tiempo.

---

# Importación Masiva de Inventarios

Proceso utilizado para inventarios reales.

```text
CSV exportado desde Excel
↓
Tabla temporal (equipos_importacion)
↓
Validación de registros
↓
Detección de duplicados
↓
Inserción a tabla equipos
↓
Asignación automática mediante triggers
```

Validaciones realizadas:

- NNI duplicados
- SN duplicados
- Garantías
- Fechas
- Estado funcional

---

# Consultas de Validación

Una vez finalizado un inventario se recomienda verificar:

## Inventario actual

```sql
SELECT *
FROM inventario_actual;
```

## Usuarios participantes

```sql
SELECT ...
FROM inventario_usuario;
```

## Equipos registrados

```sql
SELECT ...
FROM inventario_equipo;
```

## Asociación inventario-equipo-hospital

```sql
SELECT ...
FROM inventarios
JOIN inventario_equipo
JOIN equipos;
```

---

# Funcionalidades Futuras

## Backend

- FastAPI

## Frontend

- JavaScript
- Bootstrap

## Alertas

- Garantías próximas a vencer
- Mantenimientos próximos

## Reportes

- Excel
- PDF

## Documentación

- Visualización de PDFs
- Integración con almacenamiento externo (OneDrive)

---

# Estado Actual

✅ Base de datos implementada

✅ Modelo relacional validado

✅ Triggers funcionales

✅ Importación masiva desde CSV

✅ Gestión de inventarios

✅ Gestión de equipos

✅ Gestión de mantenimientos

✅ Gestión documental

🔜 Desarrollo de API REST con FastAPI

🔜 Desarrollo de interfaz web
