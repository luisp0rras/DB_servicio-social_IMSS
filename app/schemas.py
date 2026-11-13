import re
from datetime import date
from typing import Optional, List, Literal
from pydantic import BaseModel, EmailStr, model_validator

# ==========================================================
# 1. MOLDES PARA HOSPITALES
# ==========================================================

# Lo que pedimos para registrar un hospital nuevo
class HospitalCrear(BaseModel):
    nombre: str
    ciudad: str
    estado: str = "Chihuahua"  # Si no escriben el estado, pone "Chihuahua" por defecto

# Lo que mostramos cuando alguien consulta un hospital (incluye su ID)
class HospitalRespuesta(HospitalCrear):
    id_hospital: int

    class Config:
        from_attributes = True  # Permite convertir datos de PostgreSQL a formato JSON automáticamente


# ==========================================================
# 2. MOLDES PARA USUARIOS Y PERFIL
# ==========================================================

# 1. Formulario para registrarse por primera vez
class UsuarioRegistro(BaseModel):
    primernombre: str
    segundonombre: Optional[str] = None     # Optional significa que pueden dejarlo vacío
    primerapellido: str
    segundoapellido: Optional[str] = None
    username: Optional[str] = None
    correo: EmailStr                        # EmailStr revisa que tenga un '@' y un dominio válido
    password: str                           # Contraseña normal que escribe el usuario

# 2. Formulario para Iniciar Sesión (Login)
class UsuarioLogin(BaseModel):
    correo: EmailStr
    password: str

# 3. Formulario para que el usuario edite su perfil (username o foto)
class UsuarioActualizarPerfil(BaseModel):
    username: Optional[str] = None
    foto_perfil: Optional[str] = None

# 4. Formulario para cambiar la contraseña
class UsuarioCambiarPassword(BaseModel):
    password_actual: str
    password_nueva: str

# 5. Lo que el sistema devuelve al mostrar un usuario (¡NUNCA devolvemos la contraseña!)
class UsuarioRespuesta(BaseModel):
    id_usuario: int
    primernombre: str
    segundonombre: Optional[str] = None
    primerapellido: str
    segundoapellido: Optional[str] = None
    username: Optional[str] = None
    correo: EmailStr
    foto_perfil: Optional[str] = None
    rol: str                                # Mostrará si es 'ADMIN' o 'EMPLEADO'

    class Config:
        from_attributes = True


# ==========================================================
# 3. MOLDES PARA INVENTARIOS (PASOS 2, 3 Y 5 DEL FLUJO)
# ==========================================================

# Lo que el Administrador envía para iniciar un nuevo inventario
class InventarioCrear(BaseModel):
    id_hospital: int                        # El hospital elegido en el buscador (Paso 1)
    fecha: date                             # Fecha del inventario (ej. "2026-11-13") (Paso 2)
    id_admin_creador: int                   # El ID del Administrador que tiene la sesión iniciada
    ids_usuarios_participantes: List[int] = [] # Lista de IDs de los demás participantes (ej. [22, 23]) (Paso 3)

# Lo que el sistema devuelve al mostrar un inventario
class InventarioRespuesta(BaseModel):
    id_inventario: int
    id_hospital: int
    fecha: date
    estado: str                             # 'EN_PROCESO' o 'FINALIZADO'

    class Config:
        from_attributes = True


# ==========================================================
# 4. MOLDES PARA EQUIPOS MÉDICOS (PASO 4 DEL FLUJO)
# ==========================================================

# Formulario para registrar un equipo médico
class EquipoCrear(BaseModel):
    id_proveedor: Optional[int] = None      # Opcional si no se conoce el proveedor en ese momento
    nombre_equipo: str
    area: str
    subarea: Optional[str] = None
    marca: str
    modelo: Optional[str] = None
    sn: str                                 # Número de serie único
    nni: str                                # Número Nacional de Inventario único
    garantia: bool                          # True (Sí tiene garantía) o False (No tiene)
    fecha_expgarantia: Optional[date] = None
    estatusfuncional: bool                  # True (Funciona) o False (No funciona)
    observaciones: Optional[str] = None

    # El "Cadenero" que revisa tu regla de garantía antes de ir a PostgreSQL:
    @model_validator(mode='after')
    def validar_regla_garantia(self):
        if self.garantia is True and self.fecha_expgarantia is None:
            raise ValueError("Si el equipo tiene garantía (true), es obligatorio poner la fecha_expgarantia.")
        if self.garantia is False and self.fecha_expgarantia is not None:
            raise ValueError("Si el equipo NO tiene garantía (false), fecha_expgarantia debe quedar vacía (null).")
        return self

# Lo que devuelve el sistema cuando consultamos un equipo
class EquipoRespuesta(BaseModel):
    id_equipo: int
    id_hospital: Optional[int] = None
    id_proveedor: Optional[int] = None
    nombre_equipo: str
    area: str
    subarea: Optional[str] = None
    marca: str
    modelo: Optional[str] = None
    sn: str
    nni: str
    garantia: bool
    fecha_expgarantia: Optional[date] = None
    estatusfuncional: bool
    observaciones: Optional[str] = None

    class Config:
        from_attributes = True


# ==========================================================
# 5. MOLDES PARA PROVEEDORES
# ==========================================================

class ProveedorCrear(BaseModel):
    nombre_proveedor: str
    correo: Optional[EmailStr] = None
    num_tel: Optional[str] = None
    nombre_contacto: Optional[str] = None

    # Cadenero que revisa que el teléfono solo tenga números, +, (), espacios o guiones (igual que tu CHECK en SQL)
    @model_validator(mode='after')
    def validar_telefono(self):
        if self.num_tel is not None:
            patron = r'^[0-9+() -]+$'
            if not re.match(patron, self.num_tel):
                raise ValueError("El número de teléfono solo puede contener números y los símbolos + ( ) -")
        return self

class ProveedorRespuesta(ProveedorCrear):
    id_proveedor: int

    class Config:
        from_attributes = True


# ==========================================================
# 6. MOLDES PARA MANTENIMIENTOS
# ==========================================================

class MantenimientoCrear(BaseModel):
    id_proveedor: int
    id_equipo: int
    # Literal obliga a que solo puedan elegir una de estas 3 opciones exactas:
    tipo_mantenimiento: Literal["PREVENTIVO", "CORRECTIVO", "OTRO"]
    fecha: date
    prox_fecha: Optional[date] = None
    observaciones: Optional[str] = None

class MantenimientoRespuesta(MantenimientoCrear):
    id_mantenimiento: int

    class Config:
        from_attributes = True


# ==========================================================
# 7. MOLDES PARA DOCUMENTOS
# ==========================================================

class DocumentoRespuesta(BaseModel):
    id_documento: int
    id_equipo: Optional[int] = None
    id_mantenimiento: Optional[int] = None
    id_inventario: Optional[int] = None
    nombredocumento: str
    rutaarchivo: str

    class Config:
        from_attributes = True