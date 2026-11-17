from sqlalchemy import Column, Integer, String, Boolean, Date, Text, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import ENUM
from .database import Base

# Tipo enumerado nativo de PostgreSQL para clasificar intervenciones de mantenimiento
mantenimiento_enum = ENUM(
    "PREVENTIVO",
    "CORRECTIVO",
    "OTRO",
    name="mantenimiento_enum",
    create_type=False
)


# ==========================================================
# 1. TABLA DE HOSPITALES (UNIDADES MÉDICAS)
# ==========================================================
class Hospital(Base):
    """Representa una unidad médica u hospital del IMSS (ej. UMF 33, HGR 66, HGZ 11)."""
    __tablename__ = "hospital"

    id_hospital = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, index=True)
    ciudad = Column(String(100), nullable=False)
    estado = Column(String(100), nullable=False, default="Chihuahua")


# ==========================================================
# 2. TABLA DE PROVEEDORES EXTERNOS
# ==========================================================
class Proveedor(Base):
    """Directorio de empresas externas encargadas de soporte, garantías y mantenimiento."""
    __tablename__ = "proveedor"

    id_proveedor = Column(Integer, primary_key=True, index=True)
    nombre_proveedor = Column(String(100), nullable=False, index=True)
    correo = Column(String(100), unique=True, nullable=True)
    num_tel = Column(String(20), nullable=True)
    nombre_contacto = Column(String(100), nullable=True)


# ==========================================================
# 3. TABLA DE USUARIOS Y CONTROL DE ACCESO
# ==========================================================
class Usuario(Base):
    """
    Usuarios registrados en la plataforma.
    Niveles de rol soportados: 'ADMIN' (control total), 'EMPLEADO' (consulta) e 'INACTIVO' (bloqueado).
    """
    __tablename__ = "usuarios"

    id_usuario = Column(Integer, primary_key=True, index=True)
    primernombre = Column(String(20), nullable=False)
    segundonombre = Column(String(20), nullable=True)
    primerapellido = Column(String(30), nullable=False)
    segundoapellido = Column(String(30), nullable=True)
    correo = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)

    # Atributos de perfil y permisos de navegación
    username = Column(String(50), unique=True, nullable=True, index=True)
    foto_perfil = Column(String(255), nullable=True)
    rol = Column(String(20), nullable=False, default="EMPLEADO")


# ==========================================================
# 4. TABLA MAESTRA DE EQUIPOS MÉDICOS
# ==========================================================
class Equipo(Base):
    """Catálogo de activos biomédicos con trazabilidad de serie, NNI, garantía y estado funcional."""
    __tablename__ = "equipos"

    id_equipo = Column(Integer, primary_key=True, index=True)
    id_hospital = Column(Integer, ForeignKey("hospital.id_hospital", ondelete="SET NULL"), nullable=True, index=True)
    id_proveedor = Column(Integer, ForeignKey("proveedor.id_proveedor", ondelete="SET NULL"), nullable=True, index=True)
    nombre_equipo = Column(String(100), nullable=True, index=True)
    area = Column(String(60), nullable=True, index=True)
    subarea = Column(String(60), nullable=True)
    marca = Column(String(60), nullable=True, index=True)
    modelo = Column(String(60), nullable=True)
    sn = Column(String(60), unique=True, nullable=True, index=True)
    nni = Column(String(60), unique=True, nullable=True, index=True)
    garantia = Column(Boolean, nullable=False, default=False)
    fecha_expgarantia = Column(Date, nullable=True, index=True)
    estatusfuncional = Column(Boolean, nullable=False, default=True)
    observaciones = Column(Text, nullable=True)


# ==========================================================
# 5. TABLA DE INVENTARIOS (CENSOS HOSPITALARIOS)
# ==========================================================
class Inventario(Base):
    """
    Registro de levantamientos de inventario por hospital y fecha.
    Estados posibles: 'EN_PROCESO' (admite captura de equipos) o 'FINALIZADO' (cerrado).
    """
    __tablename__ = "inventarios"

    id_inventario = Column(Integer, primary_key=True, index=True)
    id_hospital = Column(Integer, ForeignKey("hospital.id_hospital", ondelete="CASCADE"), nullable=False, index=True)
    fecha = Column(Date, nullable=False, index=True)
    estado = Column(String(20), nullable=False, default="EN_PROCESO")


# ==========================================================
# 6. TABLA DE MANTENIMIENTOS PREVENTIVOS Y CORRECTIVOS
# ==========================================================
class Mantenimiento(Base):
    """Historial y programación de mantenimientos realizados a los equipos médicos."""
    __tablename__ = "mantenimientos"

    id_mantenimiento = Column(Integer, primary_key=True, index=True)
    id_proveedor = Column(Integer, ForeignKey("proveedor.id_proveedor", ondelete="SET NULL"), nullable=True)
    id_equipo = Column(Integer, ForeignKey("equipos.id_equipo", ondelete="CASCADE"), nullable=False, index=True)
    tipo_mantenimiento = Column(mantenimiento_enum, nullable=False)
    fecha = Column(Date, nullable=False)
    prox_fecha = Column(Date, nullable=True, index=True)
    observaciones = Column(Text, nullable=True)


# ==========================================================
# 7. TABLA DE REPOSITORIO DOCUMENTAL (PDFs E IMÁGENES)
# ==========================================================
class Documento(Base):
    """Archivos físicos guardados en el servidor asociados a un equipo, mantenimiento o inventario."""
    __tablename__ = "documentos"

    id_documento = Column(Integer, primary_key=True, index=True)
    id_mantenimiento = Column(Integer, ForeignKey("mantenimientos.id_mantenimiento", ondelete="CASCADE"), nullable=True)
    id_equipo = Column(Integer, ForeignKey("equipos.id_equipo", ondelete="CASCADE"), nullable=True)
    id_inventario = Column(Integer, ForeignKey("inventarios.id_inventario", ondelete="CASCADE"), nullable=True)
    nombredocumento = Column(String(100), nullable=False)
    rutaarchivo = Column(String(255), nullable=False)


# ==========================================================
# 8. TABLAS INTERMEDIAS (RELACIONES MUCHOS A MUCHOS)
# ==========================================================
class InventarioEquipo(Base):
    """Vincula cada equipo médico con el inventario en el que fue censado."""
    __tablename__ = "inventario_equipo"

    id_inventario = Column(Integer, ForeignKey("inventarios.id_inventario", ondelete="CASCADE"), primary_key=True)
    id_equipo = Column(Integer, ForeignKey("equipos.id_equipo", ondelete="CASCADE"), primary_key=True)


class InventarioUsuario(Base):
    """Registra qué usuarios (Administradores y Empleados) participaron en cada inventario."""
    __tablename__ = "inventario_usuario"

    id_inventario = Column(Integer, ForeignKey("inventarios.id_inventario", ondelete="CASCADE"), primary_key=True)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), primary_key=True)


# ==========================================================
# 8. TABLA DE TRANSFERENCIAS DE EQUIPOS ENTRE HOSPITALES
# ==========================================================

class TransferenciaEquipo(Base):
    """Bitácora histórica de reubicaciones y préstamos de equipos entre unidades médicas."""
    __tablename__ = "transferencias_equipo"

    id_transferencia = Column(Integer, primary_key=True, index=True)
    id_equipo = Column(Integer, ForeignKey("equipos.id_equipo", ondelete="CASCADE"), nullable=False, index=True)
    id_hospital_origen = Column(Integer, ForeignKey("hospital.id_hospital", ondelete="RESTRICT"), nullable=False)
    id_hospital_destino = Column(Integer, ForeignKey("hospital.id_hospital", ondelete="RESTRICT"), nullable=False)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    fecha = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    motivo = Column(String(300), nullable=False)