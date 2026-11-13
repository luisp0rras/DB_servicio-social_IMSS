# Importamos los tipos de datos que existen en una base de datos (Números, Textos, Fechas, etc.)
from sqlalchemy import Column, Integer, String, Boolean, Date, Text, ForeignKey
from sqlalchemy.dialects.postgresql import ENUM
from .database import Base

# Le avisamos a Python que en PostgreSQL ya existe una lista fija para tipos de mantenimiento
mantenimiento_enum = ENUM('PREVENTIVO', 'CORRECTIVO', 'OTRO', name='mantenimiento_enum', create_type=False)


# 1. TABLA DE HOSPITALES
class Hospital(Base):
    __tablename__ = "hospital"  # Nombre exacto de la tabla en PostgreSQL

    id_hospital = Column(Integer, primary_key=True, index=True) # Número único de hospital (se crea solo)
    nombre = Column(String(100))                                # Nombre (ej. HGR 66, UMF 33)
    ciudad = Column(String(100))                                # Ciudad (ej. Delicias, Chihuahua)
    estado = Column(String(100))                                # Estado (ej. Chihuahua)


# 2. TABLA DE PROVEEDORES
class Proveedor(Base):
    __tablename__ = "proveedor"

    id_proveedor = Column(Integer, primary_key=True, index=True)
    nombre_proveedor = Column(String(100), nullable=False)      # nullable=False significa que es OBLIGATORIO
    correo = Column(String(100), unique=True)                   # unique=True significa que NO se puede repetir
    num_tel = Column(String(20))
    nombre_contacto = Column(String(100), nullable=True)        # nullable=True significa que es OPCIONAL


# 3. TABLA DE USUARIOS
class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario = Column(Integer, primary_key=True, index=True)
    primernombre = Column(String(20), nullable=False)
    segundonombre = Column(String(20), nullable=True)
    primerapellido = Column(String(30), nullable=False)
    segundoapellido = Column(String(30), nullable=True)
    correo = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)                # Aquí se guarda la contraseña encriptada
    
    # Columnas nuevas para el perfil y permisos del sistema:
    username = Column(String(50), unique=True, nullable=True)   # Nombre de usuario (opcional al inicio)
    foto_perfil = Column(String(255), nullable=True)            # Ruta o enlace a su foto
    rol = Column(String(20), nullable=False, default="EMPLEADO")# Puede ser 'ADMIN' o 'EMPLEADO'


# 4. TABLA DE EQUIPOS MÉDICOS
class Equipo(Base):
    __tablename__ = "equipos"

    id_equipo = Column(Integer, primary_key=True, index=True)
    # ForeignKey conecta este equipo con el hospital y el proveedor al que pertenece
    id_hospital = Column(Integer, ForeignKey("hospital.id_hospital"))
    id_proveedor = Column(Integer, ForeignKey("proveedor.id_proveedor"), nullable=True)
    nombre_equipo = Column(String(100))
    area = Column(String(60))
    subarea = Column(String(60), nullable=True)
    marca = Column(String(60))
    modelo = Column(String(60), nullable=True)
    sn = Column(String(60), unique=True)                        # Número de Serie (no se puede repetir)
    nni = Column(String(60), unique=True)                       # Número Nacional de Inventario (no se puede repetir)
    garantia = Column(Boolean, nullable=False)                  # True (Sí tiene) o False (No tiene)
    fecha_expgarantia = Column(Date, nullable=True)             # Fecha en que vence la garantía
    estatusfuncional = Column(Boolean, nullable=False)          # True (Funciona) o False (Falla/Fuera de servicio)
    observaciones = Column(Text, nullable=True)


# 5. TABLA DE INVENTARIOS
class Inventario(Base):
    __tablename__ = "inventarios"

    id_inventario = Column(Integer, primary_key=True, index=True)
    id_hospital = Column(Integer, ForeignKey("hospital.id_hospital"), nullable=False)
    fecha = Column(Date, nullable=False)
    # Columna nueva para saber si siguen capturando equipos o ya se cerró:
    estado = Column(String(20), nullable=False, default="EN_PROCESO") # 'EN_PROCESO' o 'FINALIZADO'


# 6. TABLA DE MANTENIMIENTOS
class Mantenimiento(Base):
    __tablename__ = "mantenimientos"

    id_mantenimiento = Column(Integer, primary_key=True, index=True)
    id_proveedor = Column(Integer, ForeignKey("proveedor.id_proveedor"))
    id_equipo = Column(Integer, ForeignKey("equipos.id_equipo"))
    tipo_mantenimiento = Column(mantenimiento_enum, nullable=False)
    fecha = Column(Date, nullable=False)
    prox_fecha = Column(Date, nullable=True)
    observaciones = Column(Text, nullable=True)


# 7. TABLA DE DOCUMENTOS (PDFs, manuales, minutas)
class Documento(Base):
    __tablename__ = "documentos"

    id_documento = Column(Integer, primary_key=True, index=True)
    id_mantenimiento = Column(Integer, ForeignKey("mantenimientos.id_mantenimiento"), nullable=True)
    id_equipo = Column(Integer, ForeignKey("equipos.id_equipo"), nullable=True)
    id_inventario = Column(Integer, ForeignKey("inventarios.id_inventario"), nullable=True)
    nombredocumento = Column(String(100), nullable=False)
    rutaarchivo = Column(String(255), nullable=False)


# 8. TABLA INTERMEDIA: Qué equipos pertenecen a qué inventario
class InventarioEquipo(Base):
    __tablename__ = "inventario_equipo"

    id_inventario = Column(Integer, ForeignKey("inventarios.id_inventario"), primary_key=True)
    id_equipo = Column(Integer, ForeignKey("equipos.id_equipo"), primary_key=True)


# 9. TABLA INTERMEDIA: Qué usuarios participaron en qué inventario
class InventarioUsuario(Base):
    __tablename__ = "inventario_usuario"

    id_inventario = Column(Integer, ForeignKey("inventarios.id_inventario"), primary_key=True)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"), primary_key=True)