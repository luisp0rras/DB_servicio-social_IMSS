import re
from datetime import date
from typing import Optional, List, Literal
from pydantic import BaseModel, EmailStr, ConfigDict, model_validator


# ==========================================================
# 1. MOLDES PARA HOSPITALES
# ==========================================================

class HospitalCrear(BaseModel):
    """Datos requeridos para dar de alta una nueva unidad médica hospitalaria."""
    nombre: str
    ciudad: str
    estado: str = "Chihuahua"

class HospitalRespuesta(HospitalCrear):
    """Estructura de salida al consultar hospitales (incluye su llave primaria)."""
    id_hospital: int
    model_config = ConfigDict(from_attributes=True)


# ==========================================================
# 2. MOLDES PARA USUARIOS, PERFIL Y RECUPERACIÓN DE ACCESO
# ==========================================================

class UsuarioRegistro(BaseModel):
    """Formulario para registrar una cuenta nueva (inicia siempre con rol EMPLEADO)."""
    primernombre: str
    segundonombre: Optional[str] = None
    primerapellido: str
    segundoapellido: Optional[str] = None
    username: Optional[str] = None
    correo: EmailStr
    password: str

class UsuarioLogin(BaseModel):
    """Credenciales requeridas para iniciar sesión."""
    correo: EmailStr
    password: str

class UsuarioActualizarPerfil(BaseModel):
    """Campos editables por el usuario dentro de la sección Mi Perfil."""
    username: Optional[str] = None
    foto_perfil: Optional[str] = None

class UsuarioCambiarPassword(BaseModel):
    """Formulario para actualizar la contraseña estando con sesión iniciada."""
    password_actual: str
    password_nueva: str

class RecuperarPasswordSolicitud(BaseModel):
    """Paso 1 de recuperación: correo al que se enviará el código OTP de 6 dígitos."""
    correo: EmailStr

class RecuperarPasswordConfirmacion(BaseModel):
    """Paso 2 de recuperación: validación del código OTP y asignación de nueva contraseña."""
    correo: EmailStr
    codigo: str
    nueva_password: str

class UsuarioRespuesta(BaseModel):
    """Datos públicos del usuario devueltos al frontend (omite password_hash por seguridad)."""
    id_usuario: int
    primernombre: str
    segundonombre: Optional[str] = None
    primerapellido: str
    segundoapellido: Optional[str] = None
    username: Optional[str] = None
    correo: EmailStr
    foto_perfil: Optional[str] = None
    rol: str  # 'ADMIN', 'EMPLEADO' o 'INACTIVO'

    model_config = ConfigDict(from_attributes=True)


# ==========================================================
# 3. MOLDES PARA INVENTARIOS HOSPITALARIOS
# ==========================================================

class InventarioCrear(BaseModel):
    """Datos enviados por un Administrador para abrir un nuevo levantamiento de inventario."""
    id_hospital: int
    fecha: date
    id_admin_creador: int
    ids_usuarios_participantes: List[int] = []

class InventarioRespuesta(BaseModel):
    """Estructura de salida al listar o consultar un inventario."""
    id_inventario: int
    id_hospital: int
    fecha: date
    estado: str  # 'EN_PROCESO' o 'FINALIZADO'

    model_config = ConfigDict(from_attributes=True)


# ==========================================================
# 4. MOLDES PARA EQUIPOS MÉDICOS
# ==========================================================

class EquipoCrear(BaseModel):
    """Datos requeridos para censar un nuevo equipo médico dentro de un inventario activo."""
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

    @model_validator(mode="after")
    def validar_regla_garantia(self):
        """Asegura coherencia entre el booleano de garantía y su fecha de expiración."""
        if self.garantia is True and self.fecha_expgarantia is None:
            raise ValueError("Si el equipo tiene garantía, es obligatorio indicar la fecha de expiración.")
        if self.garantia is False and self.fecha_expgarantia is not None:
            raise ValueError("Si el equipo NO tiene garantía, la fecha de expiración debe quedar vacía.")
        return self


class EquipoActualizar(BaseModel):
    """
    Formulario para que un Administrador edite un equipo existente.
    Permite sn y nni opcionales para poder editar equipos antiguos que no contaban con ese dato.
    """
    id_hospital: Optional[int] = None
    id_proveedor: Optional[int] = None
    nombre_equipo: str
    area: str
    subarea: Optional[str] = None
    marca: str
    modelo: Optional[str] = None
    sn: Optional[str] = None
    nni: Optional[str] = None
    garantia: bool
    fecha_expgarantia: Optional[date] = None
    estatusfuncional: bool
    observaciones: Optional[str] = None

    @model_validator(mode="after")
    def validar_regla_garantia_edicion(self):
        if self.garantia is True and self.fecha_expgarantia is None:
            raise ValueError("Si el equipo tiene garantía, debes indicar la fecha de expiración.")
        if self.garantia is False and self.fecha_expgarantia is not None:
            raise ValueError("Si el equipo NO tiene garantía, la fecha de expiración debe quedar vacía.")
        return self


class EquipoRespuesta(BaseModel):
    """Estructura flexible de salida para listar equipos (tolera valores NULL históricos en BD)."""
    id_equipo: int
    id_hospital: Optional[int] = None
    id_proveedor: Optional[int] = None
    nombre_equipo: Optional[str] = None
    area: Optional[str] = None
    subarea: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    sn: Optional[str] = None
    nni: Optional[str] = None
    garantia: Optional[bool] = False
    fecha_expgarantia: Optional[date] = None
    estatusfuncional: Optional[bool] = True
    observaciones: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================================
# 5. MOLDES PARA PROVEEDORES
# ==========================================================

class ProveedorCrear(BaseModel):
    """Datos para registrar un proveedor externo de soporte biomédico."""
    nombre_proveedor: str
    correo: Optional[EmailStr] = None
    num_tel: Optional[str] = None
    nombre_contacto: Optional[str] = None

    @model_validator(mode="after")
    def validar_telefono(self):
        """Valida que el teléfono cumpla con la restricción CHECK de PostgreSQL."""
        if self.num_tel is not None:
            tel_limpio = self.num_tel.strip()
            if not tel_limpio:
                self.num_tel = None
            else:
                patron = r"^[0-9+() -]+$"
                if not re.match(patron, tel_limpio):
                    raise ValueError("El número de teléfono solo puede contener dígitos y los símbolos + ( ) -")
                self.num_tel = tel_limpio
        return self


class ProveedorRespuesta(ProveedorCrear):
    """Estructura de salida al consultar el directorio de proveedores."""
    id_proveedor: int
    model_config = ConfigDict(from_attributes=True)


# ==========================================================
# 6. MOLDES PARA MANTENIMIENTOS
# ==========================================================

class MantenimientoCrear(BaseModel):
    """Datos requeridos para registrar un mantenimiento preventivo, correctivo u otro."""
    id_proveedor: int
    id_equipo: int
    tipo_mantenimiento: Literal["PREVENTIVO", "CORRECTIVO", "OTRO"]
    fecha: date
    prox_fecha: Optional[date] = None
    observaciones: Optional[str] = None


class MantenimientoRespuesta(MantenimientoCrear):
    """Estructura de salida para el historial de mantenimientos."""
    id_mantenimiento: int
    model_config = ConfigDict(from_attributes=True)


# ==========================================================
# 7. MOLDES PARA DOCUMENTOS (PDFs E IMÁGENES)
# ==========================================================

class DocumentoRespuesta(BaseModel):
    """Metadatos de un documento almacenado en el servidor y vinculado a una entidad."""
    id_documento: int
    id_equipo: Optional[int] = None
    id_mantenimiento: Optional[int] = None
    id_inventario: Optional[int] = None
    nombredocumento: str
    rutaarchivo: str

    model_config = ConfigDict(from_attributes=True)