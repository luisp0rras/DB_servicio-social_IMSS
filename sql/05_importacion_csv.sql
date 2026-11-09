/*
======================================================
IMPORTACIÓN MASIVA DE EQUIPOS DESDE CSV

Caso real utilizado:

Hospital:
UMF 33

Proceso:

1. Registrar hospital
2. Crear inventario
3. Asociar participantes
4. Crear tabla temporal
5. Importar CSV mediante pgAdmin
6. Detectar duplicados
7. Limpiar datos
8. Insertar registros en tabla equipos
9. Verificar asociaciones automáticas

======================================================
*/

------------------------------------------------------
-- PASO 1. REGISTRAR HOSPITAL
------------------------------------------------------

INSERT INTO hospital (
    nombre,
    ciudad,
    estado
)
VALUES (
    'UMF 33',
    'Chihuahua',
    'Chihuahua'
);

------------------------------------------------------
-- PASO 2. CREAR INVENTARIO
------------------------------------------------------

INSERT INTO inventarios (
    fecha
)
VALUES (
    '2026-10-30'
);

------------------------------------------------------
-- PASO 3. VERIFICAR HOSPITAL E INVENTARIO ACTUALES
------------------------------------------------------

SELECT *
FROM hospital_actual;

SELECT *
FROM inventario_actual;

------------------------------------------------------
-- PASO 4. CREAR TABLA TEMPORAL
------------------------------------------------------

CREATE TABLE equipos_importacion (
    hospital TEXT,
    area TEXT,
    subarea TEXT,
    nombre_equipo TEXT,
    marca TEXT,
    modelo TEXT,
    sn TEXT,
    nni TEXT,
    garantia BOOLEAN,
    fecha_expgarantia DATE,
    estatusfuncional BOOLEAN,
    observaciones TEXT
);

------------------------------------------------------
-- PASO 5. IMPORTAR CSV DESDE PGADMIN
------------------------------------------------------

/*
Import/Export Data
↓

Import

↓

Seleccionar archivo CSV

↓

Tabla:
equipos_importacion
*/

------------------------------------------------------
-- PASO 6. VERIFICAR DATOS IMPORTADOS
------------------------------------------------------

SELECT *
FROM equipos_importacion;

------------------------------------------------------
-- PASO 7. DETECTAR NNI DUPLICADOS
------------------------------------------------------

SELECT nni,
       COUNT(*)
FROM equipos_importacion
WHERE nni IS NOT NULL
GROUP BY nni
HAVING COUNT(*) > 1;

------------------------------------------------------
-- PASO 8. ELIMINAR REGISTROS DUPLICADOS
------------------------------------------------------

DELETE FROM equipos_importacion
WHERE nni = '200600045157'
   OR nni = '200600022870';

------------------------------------------------------
-- PASO 9. MIGRAR A TABLA EQUIPOS
------------------------------------------------------

INSERT INTO equipos (
    nombre_equipo,
    area,
    subarea,
    marca,
    modelo,
    sn,
    nni,
    garantia,
    fecha_expgarantia,
    estatusfuncional,
    observaciones
)
SELECT
    nombre_equipo,
    area,
    subarea,
    marca,
    modelo,
    sn,
    nni,
    garantia,
    fecha_expgarantia,
    estatusfuncional,
    observaciones
FROM equipos_importacion;

------------------------------------------------------
-- PASO 10. VERIFICAR IMPORTACIÓN
------------------------------------------------------

SELECT *
FROM equipos;

------------------------------------------------------
-- PASO 11. VALIDAR RELACIÓN INVENTARIO-HOSPITAL-EQUIPO
------------------------------------------------------

SELECT i.id_inventario,
       i.fecha,
       i.id_hospital,
       e.id_equipo,
       e.nombre_equipo,
       e.sn,
       e.nni
FROM inventario_actual ia
JOIN inventarios i
    ON ia.id_inventario = i.id_inventario
JOIN inventario_equipo ie
    ON i.id_inventario = ie.id_inventario
JOIN equipos e
    ON ie.id_equipo = e.id_equipo
ORDER BY e.id_equipo;
