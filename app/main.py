import bcrypt
from fastapi import FastAPI, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional

from .database import get_db
from . import models, schemas

app = FastAPI(
    title="API - Gestión de Equipos Médicos IMSS",
    description="Backend para el control de inventarios, mantenimientos y equipos médicos hospitalarios.",
    version="0.2.0"
)

# ==========================================================
# FUNCIONES DE AYUDA PARA CONTRASEÑAS (CANDADOS)
# ==========================================================

def encriptar_password(password_plana: str) -> str:
    """Convierte una contraseña normal (ej. '12345') en un texto secreto encriptado."""
    sal = bcrypt.gensalt()
    encriptada = bcrypt.hashpw(password_plana.encode('utf-8'), sal)
    return encriptada.decode('utf-8')

def verificar_password(password_plana: str, password_guardada: str) -> bool:
    """Compara la contraseña que escribió el usuario con la que está en la base de datos."""
    try:
        # Si la contraseña en la BD está encriptada con bcrypt (empieza con $2b$)
        if password_guardada.startswith("$2b$"):
            return bcrypt.checkpw(password_plana.encode('utf-8'), password_guardada.encode('utf-8'))
        # Por si tienes usuarios viejos de prueba en la BD con contraseñas sin encriptar (ej. 'contraseña21000')
        return password_plana == password_guardada
    except Exception:
        return False


# ==========================================================
# 1. RUTAS GENERALES (PRUEBA DE CONEXIÓN)
# ==========================================================

@app.get("/", tags=["General"])
def inicio():
    return {"mensaje": "API del Servicio Social IMSS funcionando correctamente"}

@app.get("/health-db", tags=["General"])
def probar_conexion_bd(db: Session = Depends(get_db)):
    try:
        resultado = db.execute(text("SELECT current_database(), current_user;")).fetchone()
        return {
            "estatus": "Conectado exitosamente a PostgreSQL",
            "base_de_datos": resultado[0],
            "usuario_db": resultado[1]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {str(e)}")


# ==========================================================
# 2. REGISTRO, LOGIN Y PERFIL DE USUARIOS
# ==========================================================

@app.post("/usuarios/registro", response_model=schemas.UsuarioRespuesta, status_code=status.HTTP_201_CREATED, tags=["Usuarios y Login"])
def registrar_usuario(datos: schemas.UsuarioRegistro, db: Session = Depends(get_db)):
    """Registra un usuario nuevo. Por seguridad, todos nacen con el rol 'EMPLEADO'."""
    
    # Paso 1: Revisar que el correo no esté ocupado
    correo_ocupado = db.query(models.Usuario).filter(models.Usuario.correo == datos.correo).first()
    if correo_ocupado:
        raise HTTPException(status_code=400, detail="Ese correo electrónico ya está registrado.")
    
    # Paso 2: Si eligió un username, revisar que no esté ocupado
    if datos.username:
        username_ocupado = db.query(models.Usuario).filter(models.Usuario.username == datos.username).first()
        if username_ocupado:
            raise HTTPException(status_code=400, detail="Ese nombre de usuario ya está en uso.")

    # Paso 3: Encriptar la contraseña y guardar el usuario
    nuevo_usuario = models.Usuario(
        primernombre=datos.primernombre,
        segundonombre=datos.segundonombre,
        primerapellido=datos.primerapellido,
        segundoapellido=datos.segundoapellido,
        username=datos.username,
        correo=datos.correo,
        password_hash=encriptar_password(datos.password),
        rol="EMPLEADO"  # Nadie puede auto-registrarse como ADMIN por su cuenta
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario


@app.post("/usuarios/login", tags=["Usuarios y Login"])
def iniciar_sesion(credenciales: schemas.UsuarioLogin, db: Session = Depends(get_db)):
    """Verifica correo y contraseña, y devuelve los datos del usuario junto con su rol (ADMIN o EMPLEADO)."""
    
    # Buscar al usuario por su correo
    usuario = db.query(models.Usuario).filter(models.Usuario.correo == credenciales.correo).first()
    
    # Si no existe el correo o la contraseña no coincide, rechazar el acceso
    if not usuario or not verificar_password(credenciales.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")
    
    return {
        "mensaje": f"Bienvenido, {usuario.primernombre}",
        "usuario": schemas.UsuarioRespuesta.model_validate(usuario)
    }


@app.get("/usuarios/", response_model=List[schemas.UsuarioRespuesta], tags=["Usuarios y Login"])
def listar_usuarios(db: Session = Depends(get_db)):
    """Muestra la lista de todos los usuarios registrados (útil para elegir participantes de un inventario)."""
    return db.query(models.Usuario).all()


@app.put("/usuarios/{id_usuario}/perfil", response_model=schemas.UsuarioRespuesta, tags=["Usuarios y Login"])
def actualizar_perfil(id_usuario: int, datos: schemas.UsuarioActualizarPerfil, db: Session = Depends(get_db)):
    """Permite al usuario cambiar su nombre de usuario (username) o su foto de perfil."""
    
    usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if datos.username is not None:
        usuario.username = datos.username
    if datos.foto_perfil is not None:
        usuario.foto_perfil = datos.foto_perfil

    db.commit()
    db.refresh(usuario)
    return usuario


@app.put("/usuarios/{id_usuario}/cambiar-password", tags=["Usuarios y Login"])
def cambiar_password(id_usuario: int, datos: schemas.UsuarioCambiarPassword, db: Session = Depends(get_db)):
    """Permite al usuario cambiar su contraseña verificando primero que conozca la actual."""
    
    usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    # Verificar que la contraseña actual sea correcta
    if not verificar_password(datos.password_actual, usuario.password_hash):
        raise HTTPException(status_code=400, detail="La contraseña actual es incorrecta.")

    # Guardar la nueva contraseña encriptada
    usuario.password_hash = encriptar_password(datos.password_nueva)
    db.commit()
    return {"mensaje": "Contraseña actualizada exitosamente."}


@app.put("/usuarios/{id_usuario_objetivo}/hacer-admin", response_model=schemas.UsuarioRespuesta, tags=["Usuarios y Login"])
def convertir_en_administrador(
    id_usuario_objetivo: int, 
    id_admin_que_autoriza: int = Query(..., description="ID del administrador que está dando el permiso"), 
    db: Session = Depends(get_db)
):
    """Permite que un Administrador convierta a otro usuario en ADMIN."""
    
    # 1. Revisar que quien autoriza realmente sea un ADMIN
    admin = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_admin_que_autoriza).first()
    if not admin or admin.rol != "ADMIN":
        raise HTTPException(status_code=403, detail="Acceso denegado: Solo un Administrador puede crear otros administradores.")
    
    # 2. Buscar al usuario que queremos ascender
    usuario_objetivo = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario_objetivo).first()
    if not usuario_objetivo:
        raise HTTPException(status_code=404, detail="El usuario que intentas hacer administrador no existe.")
    
    # 3. Cambiar su rol a ADMIN
    usuario_objetivo.rol = "ADMIN"
    db.commit()
    db.refresh(usuario_objetivo)
    return usuario_objetivo


# ==========================================================
# 3. HOSPITALES (CON BUSCADOR TIPO LISTA DESPLEGABLE)
# ==========================================================

@app.get("/hospitales/", response_model=List[schemas.HospitalRespuesta], tags=["Hospitales"])
def buscar_o_listar_hospitales(
    buscar: Optional[str] = Query(None, description="Escribe parte del nombre o ciudad del hospital (ej. 'UMF' o 'Delicias')"),
    db: Session = Depends(get_db)
):
    """
    Si no escribes nada en 'buscar', devuelve todos los hospitales.
    Si escribes algo (ej. '33' o 'Delicias'), filtra la lista como un buscador desplegable.
    """
    consulta = db.query(models.Hospital)
    
    if buscar:
        # ILIKE busca coincidencias sin importar mayúsculas o minúsculas
        consulta = consulta.filter(
            (models.Hospital.nombre.ilike(f"%{buscar}%")) | 
            (models.Hospital.ciudad.ilike(f"%{buscar}%"))
        )
        
    return consulta.order_by(models.Hospital.nombre).all()


@app.post("/hospitales/", response_model=schemas.HospitalRespuesta, status_code=status.HTTP_201_CREATED, tags=["Hospitales"])
def registrar_hospital(hospital: schemas.HospitalCrear, db: Session = Depends(get_db)):
    """Si el hospital no apareció en el buscador, aquí se registra uno nuevo."""
    nuevo_hospital = models.Hospital(**hospital.model_dump())
    db.add(nuevo_hospital)
    db.commit()
    db.refresh(nuevo_hospital)
    return nuevo_hospital