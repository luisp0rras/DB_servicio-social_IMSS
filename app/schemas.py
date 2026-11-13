from pydantic import BaseModel, EmailStr
from typing import Optional

# ==========================================================
# MOLDES PARA HOSPITALES
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
# MOLDES PARA USUARIOS Y PERFIL
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