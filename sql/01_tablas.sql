-- 01. Tabla de hospitales
CREATE TABLE hospital (
	id_hospital SERIAL PRIMARY KEY, --SERIAL autoincrementa
	nombre VARCHAR (100),
	ciudad VARCHAR (100),
	estado VARCHAR (100)
);

-- 02. Tabla de proveedores
CREATE TABLE proveedor (
	id_proveedor SERIAL PRIMARY KEY,
	nombre_proveedor VARCHAR (100) NOT NULL,
	correo VARCHAR (100) UNIQUE,
	num_tel VARCHAR (20) CHECK (num_tel ~ '^[0-9+() -]+$'), -–verifica que el dato insertado solamente tenga caracteres admitidos
  nombre_contacto VARCHAR (100)
);

-- 03. Tabla de usuarios
CREATE TABLE usuarios (
	id_usuario SERIAL PRIMARY KEY,
	primerNombre VARCHAR (20) NOT NULL,
	segundoNombre VARCHAR (20),
	primerApellido VARCHAR (30) NOT NULL,
	segundoApellido VARCHAR (30),
	correo VARCHAR (100) UNIQUE NOT NULL,
	password_hash TEXT NOT NULL -- el hash no guarda la contraseña real del usuario, sino que se genera un hash o código cifrado
);

-- 04. Tabla de equipos
CREATE TABLE equipos (
	id_equipo SERIAL PRIMARY KEY,
	id_hospital INT REFERENCES hospital (id_hospital),  --foreign key/clave foránea
	id_proveedor INT REFERENCES proveedor (id_proveedor),  --foreign key
	nombre_equipo VARCHAR (100),
	area VARCHAR (60),
	subarea VARCHAR (60),
	marca VARCHAR (60),
	modelo VARCHAR (60),
	sn VARCHAR (60) UNIQUE,
	nni VARCHAR (60) UNIQUE,
	garantia BOOLEAN NOT NULL,
	fecha_expGarantia DATE,
  --mediante CHECK se valida la fecha de expiración de la garantía si es que el equipo tiene una garantía con el proveedor
	CHECK (
		(garantia = TRUE AND fecha_expGarantia IS NOT NULL) OR (garantia = FALSE AND fecha_expGarantia IS NULL)
	),
	estatusFuncional BOOLEAN NOT NULL,
	observaciones TEXT
);

-- 05. Tabla de inventarios
CREATE TABLE inventarios (
	id_inventario SERIAL PRIMARY KEY,
	id_hospital INT NOT NULL REFERENCES hospital (id_hospital),
	fecha DATE NOT NULL
);

-- 06. Tabla de mantenimientos
-- ENUM (es un tipo de dato personalizado) funciona cómo una lista de opciones, solamente se permiten las opciones declaradas
CREATE TYPE mantenimiento_enum AS ENUM ('PREVENTIVO', 'CORRECTIVO', 'OTRO' );

CREATE TABLE mantenimientos (
	id_mantenimiento SERIAL PRIMARY KEY,
	id_proveedor INT REFERENCES proveedor (id_proveedor),
	id_equipo INT REFERENCES equipos (id_equipo),
	tipo_mantenimiento mantenimiento_enum NOT NULL,
	fecha DATE NOT NULL,
	prox_fecha DATE,
	observaciones TEXT
);

-- 07. Tabla de documentos
CREATE TABLE documentos (
	id_documento SERIAL PRIMARY KEY,
	id_mantenimiento INT REFERENCES mantenimientos (id_mantenimiento),
	id_equipo INT REFERENCES equipos (id_equipo),
	nombreDocumento VARCHAR (100) NOT NULL,
	rutaArchivo VARCHAR(255) NOT NULL,
	CHECK (
		(id_equipo IS NOT NULL AND id_mantenimiento IS NULL) OR (id_equipo IS NULL AND id_mantenimiento IS NOT NULL)
	),
  id inventario INT REFERENCES inventarios (id_inventario)
);

-- 08. Tabla intermediaria para relación entre las tablas inventarios y equipos
CREATE TABLE inventario_equipo (
	id_inventario INT REFERENCES inventarios (id_inventario) NOT NULL,
	id_equipo INT REFERENCES equipos (id_equipo) NOT NULL,
	PRIMARY KEY (id_inventario, id_equipo)
);

-- 09. Tabla intermediaria para relación entre inventarios y usuario
CREATE TABLE inventario_usuario (
	id_inventario INT REFERENCES inventarios (id_inventario),
	id_usuario INT REFERENCES usuarios (id_usuario),
	PRIMARY KEY (id_inventario, id_usuario)
);

-- 10. Se crea una tabla para el registro del inventario que se esté realizando en el momento
-- La tabla almacena el id del inventario y mediante triggers se registra de manera automática
CREATE TABLE inventario_actual (
	id_inventario INT
);

-- 11. Se crea una tabla para registrar el hospital en donde se esté realizando el inventario
-- Mediante triggers se almacena el valor del id_hospital
CREATE TABLE hospital_actual (
	Id_hospital INT
);
