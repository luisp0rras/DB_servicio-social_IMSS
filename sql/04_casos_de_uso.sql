/*
======================================================
CASOS DE USO DEL SISTEMA

Ejemplos prácticos del flujo de trabajo:

1. Crear hospital
2. Crear inventario
3. Registrar usuarios
4. Asociar usuarios al inventario
5. Registrar equipos
6. Registrar proveedores
7. Registrar mantenimientos
8. Registrar documentos

======================================================
*/

------------------------------------------------------
-- CASO 1. REGISTRAR HOSPITAL
------------------------------------------------------

INSERT INTO hospital (
    id_hospital,
    nombre,
    ciudad,
    estado
)
VALUES (
    15,
    'Hospital 15',
    'Delicias',
    'Chihuahua'
);

------------------------------------------------------
-- CASO 2. CREAR INVENTARIO
------------------------------------------------------

INSERT INTO inventarios (
    id_inventario,
    fecha
)
VALUES (
    16,
    '2026-10-07'
);

------------------------------------------------------
-- CASO 3. REGISTRAR USUARIOS
------------------------------------------------------

INSERT INTO usuarios (
    id_usuario,
    primernombre,
    segundonombre,
    primerapellido,
    segundoapellido,
    correo,
    password_hash
)
VALUES
(
    21,
    'Luis',
    'Carlos',
    'Porras',
    NULL,
    'correo21@gmail.com',
    'contraseña21000'
),
(
    22,
    'Jorge',
    'Eduardo',
    'Campos',
    'Perez',
    'correo22@gmail.com',
    'contraseña22000'
),
(
    23,
    'Hugo',
    NULL,
    'Sánchez',
    NULL,
    'correo23@gmail.com',
    'contraseña23000'
);

------------------------------------------------------
-- CASO 4. ASOCIAR USUARIOS AL INVENTARIO ACTUAL
------------------------------------------------------

INSERT INTO inventario_usuario (
    id_inventario,
    id_usuario
)
VALUES
(
    (SELECT id_inventario FROM inventario_actual),
    21
),
(
    (SELECT id_inventario FROM inventario_actual),
    22
),
(
    (SELECT id_inventario FROM inventario_actual),
    23
);

------------------------------------------------------
-- CASO 5. REGISTRAR EQUIPOS
------------------------------------------------------

INSERT INTO equipos (
    id_proveedor,
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
VALUES
(
    NULL,
    'Equipo 15',
    'Area 03',
    'Subarea 02',
    'Marca 00',
    NULL,
    'SN01035316',
    'NNI20267809001',
    FALSE,
    NULL,
    TRUE,
    'Funcional con chasis desgastado'
);

------------------------------------------------------
-- CASO 6. REGISTRAR PROVEEDORES
------------------------------------------------------

INSERT INTO proveedor (
    nombre_proveedor,
    correo,
    num_tel,
    nombre_contacto
)
VALUES (
    'Proveedor 01',
    'correo_prov01@gmail.com',
    '6140000001',
    'Nombre Prov01'
);

------------------------------------------------------
-- CASO 7. ACTUALIZAR DATOS DE PROVEEDOR
------------------------------------------------------

UPDATE proveedor
SET nombre_contacto = 'Luis Porras'
WHERE id_proveedor = 1;

------------------------------------------------------
-- CASO 8. REGISTRAR MANTENIMIENTO
------------------------------------------------------

INSERT INTO mantenimientos (
    id_proveedor,
    id_equipo,
    tipo_mantenimiento,
    fecha,
    prox_fecha,
    observaciones
)
VALUES (
    (
        SELECT id_proveedor
        FROM proveedor
        WHERE nombre_proveedor = 'Proveedor 01'
    ),

    (
        SELECT id_equipo
        FROM equipos
        WHERE nni = 'NNI20267809001'
    ),

    'PREVENTIVO',
    '2026-05-19',
    '2027-12-21',
    NULL
);

------------------------------------------------------
-- CASO 9. REGISTRAR DOCUMENTO ASOCIADO A INVENTARIO
------------------------------------------------------

INSERT INTO documentos (
    id_mantenimiento,
    id_equipo,
    nombreDocumento,
    rutaArchivo,
    id_inventario
)
VALUES (
    NULL,
    NULL,
    'Minuta supervisión HGR 66',
    'C:\Documentos\Minuta supervisión HGR 66.pdf',

    (
        SELECT id_inventario
        FROM inventarios
        WHERE fecha = '2026-10-03'
        AND id_hospital = 7
    )
);
