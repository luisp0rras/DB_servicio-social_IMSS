/*
======================================================
TRIGGERS DEL SISTEMA DE INVENTARIO HOSPITALARIO

Orden de ejecución:

1. hospital_activo()
2. inventario_hospital_actual()
3. inventario_activo()
4. usuario_inventario_actual()
5. equipo_inventario_hospital()

Estos triggers permiten asociar automáticamente
hospitales, inventarios, usuarios y equipos durante
el proceso de captura de un inventario.
======================================================
*/

------------------------------------------------------
-- 01. HOSPITAL ACTIVO
------------------------------------------------------

/*
Objetivo:
Actualizar la tabla auxiliar hospital_actual con el
hospital en el que se realizará el inventario.
*/

CREATE OR REPLACE FUNCTION hospital_activo()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM hospital_actual;

    INSERT INTO hospital_actual (id_hospital)
    VALUES (NEW.id_hospital);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_hospital_actual
AFTER INSERT ON hospital
FOR EACH ROW
EXECUTE FUNCTION hospital_activo();

------------------------------------------------------
-- 02. ASIGNAR HOSPITAL AL NUEVO INVENTARIO
------------------------------------------------------

/*
Objetivo:
Asignar automáticamente al inventario el hospital
almacenado en la tabla auxiliar hospital_actual.
*/

CREATE OR REPLACE FUNCTION inventario_hospital_actual()
RETURNS TRIGGER AS $$
DECLARE
    hospital_activo INT;
BEGIN
    SELECT id_hospital
    INTO hospital_activo
    FROM hospital_actual
    LIMIT 1;

    NEW.id_hospital := hospital_activo;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_inventario_hospital_actual
BEFORE INSERT ON inventarios
FOR EACH ROW
EXECUTE FUNCTION inventario_hospital_actual();

------------------------------------------------------
-- 03. INVENTARIO ACTIVO
------------------------------------------------------

/*
Objetivo:
Actualizar la tabla auxiliar inventario_actual con el
inventario recién creado.
*/

CREATE OR REPLACE FUNCTION inventario_activo()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM inventario_actual;

    INSERT INTO inventario_actual (id_inventario)
    VALUES (NEW.id_inventario);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_inventario_activo
AFTER INSERT ON inventarios
FOR EACH ROW
EXECUTE FUNCTION inventario_activo();

------------------------------------------------------
-- 04. USUARIO ASOCIADO AL INVENTARIO ACTUAL
------------------------------------------------------

/*
Objetivo:
Relacionar automáticamente un nuevo usuario con el
inventario actualmente activo.
*/

CREATE OR REPLACE FUNCTION usuario_inventario_actual()
RETURNS TRIGGER AS $$
DECLARE
    inventario_activo INT;
BEGIN
    SELECT id_inventario
    INTO inventario_activo
    FROM inventario_actual
    LIMIT 1;

    INSERT INTO inventario_usuario (
        id_inventario,
        id_usuario
    )
    VALUES (
        inventario_activo,
        NEW.id_usuario
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_inventario_usuario
AFTER INSERT ON usuarios
FOR EACH ROW
EXECUTE FUNCTION usuario_inventario_actual();

------------------------------------------------------
-- 05. EQUIPO ASOCIADO AL INVENTARIO Y HOSPITAL
------------------------------------------------------

/*
Objetivo:
Relacionar automáticamente un equipo con el inventario
activo y asignarle el hospital correspondiente.
*/

CREATE OR REPLACE FUNCTION equipo_inventario_hospital()
RETURNS TRIGGER AS $$
DECLARE
    inventario_activo INT;
    hospital_activo INT;
BEGIN

    SELECT id_inventario
    INTO inventario_activo
    FROM inventario_actual
    LIMIT 1;

    SELECT id_hospital
    INTO hospital_activo
    FROM inventarios
    WHERE id_inventario = inventario_activo;

    INSERT INTO inventario_equipo (
        id_inventario,
        id_equipo
    )
    VALUES (
        inventario_activo,
        NEW.id_equipo
    );

    UPDATE equipos
    SET id_hospital = hospital_activo
    WHERE id_equipo = NEW.id_equipo;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_equipo_inventario_hospital
AFTER INSERT ON equipos
FOR EACH ROW
EXECUTE FUNCTION equipo_inventario_hospital();
