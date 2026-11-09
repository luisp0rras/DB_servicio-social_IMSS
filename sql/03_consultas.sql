/*
======================================================
CONSULTAS PRINCIPALES DEL SISTEMA DE INVENTARIO
HOSPITALARIO

Estas consultas permiten consultar información
relacionada con:

- Hospitales
- Inventarios
- Usuarios
- Equipos
- Mantenimientos
- Documentos

======================================================
*/

------------------------------------------------------
-- 01. VER TODOS LOS HOSPITALES REGISTRADOS
------------------------------------------------------

SELECT *
FROM hospital;

------------------------------------------------------
-- 02. VER TODOS LOS INVENTARIOS REGISTRADOS
------------------------------------------------------

SELECT *
FROM inventarios
ORDER BY fecha DESC;

------------------------------------------------------
-- 03. VER HOSPITAL ACTUAL
------------------------------------------------------

SELECT *
FROM hospital_actual;

------------------------------------------------------
-- 04. VER INVENTARIO ACTUAL
------------------------------------------------------

SELECT *
FROM inventario_actual;

------------------------------------------------------
-- 05. VER TODOS LOS USUARIOS
------------------------------------------------------

SELECT *
FROM usuarios;

------------------------------------------------------
-- 06. VER USUARIOS PARTICIPANTES DE UN INVENTARIO
------------------------------------------------------

SELECT iu.id_inventario,
       iu.id_usuario,
       u.primernombre,
       u.primerapellido,
       u.correo
FROM inventario_usuario iu
JOIN usuarios u
    ON u.id_usuario = iu.id_usuario;

------------------------------------------------------
-- 07. VER USUARIOS ASOCIADOS A UN INVENTARIO POR FECHA
------------------------------------------------------

SELECT iu.id_inventario,
       iu.id_usuario,
       u.primernombre,
       u.primerapellido,
       u.correo,
       i.fecha
FROM inventario_usuario iu
JOIN usuarios u
    ON u.id_usuario = iu.id_usuario
JOIN inventarios i
    ON i.id_inventario = iu.id_inventario
WHERE i.fecha = '2026-10-30';

------------------------------------------------------
-- 08. VER TODOS LOS EQUIPOS REGISTRADOS
------------------------------------------------------

SELECT *
FROM equipos;

------------------------------------------------------
-- 09. VER EQUIPOS ASOCIADOS A UN INVENTARIO
------------------------------------------------------

SELECT ie.id_inventario,
       e.id_equipo,
       e.nombre_equipo,
       e.id_hospital,
       i.fecha
FROM inventario_equipo ie
JOIN equipos e
    ON ie.id_equipo = e.id_equipo
JOIN inventarios i
    ON ie.id_inventario = i.id_inventario
WHERE i.fecha = '2026-10-30';

------------------------------------------------------
-- 10. VER EQUIPOS DEL INVENTARIO ACTUAL
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

------------------------------------------------------
-- 11. VER LOS PROVEEDORES REGISTRADOS
------------------------------------------------------

SELECT *
FROM proveedor;

------------------------------------------------------
-- 12. CONSULTAR MANTENIMIENTOS REGISTRADOS
------------------------------------------------------

SELECT *
FROM mantenimientos;

------------------------------------------------------
-- 13. CONSULTAR MANTENIMIENTOS DE UN EQUIPO MEDIANTE NNI
------------------------------------------------------

SELECT m.*
FROM mantenimientos m
JOIN equipos e
    ON m.id_equipo = e.id_equipo
WHERE e.nni = 'NNI20167819006';

------------------------------------------------------
-- 14. CONSULTAR MANTENIMIENTOS DE UN EQUIPO MEDIANTE SN
------------------------------------------------------

SELECT m.*
FROM mantenimientos m
JOIN equipos e
    ON m.id_equipo = e.id_equipo
WHERE e.sn = 'SN01137316';

------------------------------------------------------
-- 15. MANTENIMIENTOS PRÓXIMOS
------------------------------------------------------

SELECT *
FROM mantenimientos
WHERE prox_fecha >= CURRENT_DATE;

------------------------------------------------------
-- 16. MANTENIMIENTOS VENCIDOS
------------------------------------------------------

SELECT *
FROM mantenimientos
WHERE prox_fecha < CURRENT_DATE;

------------------------------------------------------
-- 17. GARANTÍAS PRÓXIMAS A VENCER
------------------------------------------------------

SELECT *
FROM equipos
WHERE garantia = TRUE
AND fecha_expgarantia <= CURRENT_DATE + INTERVAL '30 days'
AND fecha_expgarantia >= CURRENT_DATE;

------------------------------------------------------
-- 18. GARANTÍAS VENCIDAS
------------------------------------------------------

SELECT *
FROM equipos
WHERE garantia = TRUE
AND fecha_expgarantia < CURRENT_DATE;

------------------------------------------------------
-- 19. CONSULTAR TODOS LOS DOCUMENTOS
------------------------------------------------------

SELECT *
FROM documentos;

------------------------------------------------------
-- 20. CONSULTAR DOCUMENTOS DE UN INVENTARIO
------------------------------------------------------

SELECT d.id_documento,
       d.nombreDocumento,
       d.rutaArchivo,
       i.id_inventario,
       i.fecha
FROM documentos d
JOIN inventarios i
    ON d.id_inventario = i.id_inventario;

------------------------------------------------------
-- 21. CONSULTAR DOCUMENTOS DE UN EQUIPO
------------------------------------------------------

SELECT d.*
FROM documentos d
JOIN equipos e
    ON d.id_equipo = e.id_equipo
WHERE e.nni = 'NNI20167819006';

------------------------------------------------------
-- 22. CONSULTAR DOCUMENTOS DE UN MANTENIMIENTO
------------------------------------------------------

SELECT d.*
FROM documentos d
JOIN mantenimientos m
    ON d.id_mantenimiento = m.id_mantenimiento
WHERE m.id_mantenimiento = 1;

------------------------------------------------------
-- 23. CONTAR EQUIPOS POR INVENTARIO
------------------------------------------------------

SELECT i.id_inventario,
       i.fecha,
       COUNT(e.id_equipo) AS total_equipos
FROM inventarios i
JOIN inventario_equipo ie
    ON i.id_inventario = ie.id_inventario
JOIN equipos e
    ON ie.id_equipo = e.id_equipo
GROUP BY i.id_inventario,
         i.fecha
ORDER BY i.fecha DESC;

------------------------------------------------------
-- 24. VERIFICAR IMPORTACIÓN COMPLETA DE EQUIPOS
------------------------------------------------------

SELECT COUNT(*)
FROM equipos;

------------------------------------------------------
-- 25. VERIFICAR RELACIONES INVENTARIO-EQUIPO
------------------------------------------------------

SELECT COUNT(*)
FROM inventario_equipo;
