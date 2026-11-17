import os
import io
import csv
import random
import shutil
import smtplib
import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
import bcrypt
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status, Query, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, or_
from .database import get_db, SessionLocal, engine
from . import models, schemas

# Cargar variables de entorno desde el archivo .env (credenciales DB y SMTP)
load_dotenv()

# Verifica y crea tablas nuevas (como transferencias_equipo) si aún no existen en PostgreSQL.
# Si ya las creaste en pgAdmin, las detecta y continúa sin lanzar error ni alterar datos.
models.Base.metadata.create_all(bind=engine)

# ==========================================================
# CONFIGURACIÓN DE CARPETAS Y CONTROL DE ENVÍO DIARIO
# ==========================================================
CARPETA_DOCUMENTOS = "archivos_subidos"
os.makedirs(os.path.join(CARPETA_DOCUMENTOS, "perfiles"), exist_ok=True)
os.makedirs("frontend", exist_ok=True)

# Archivo oculto para recordar la fecha del último correo automático (persiste ante reinicios)
ARCHIVO_CONTROL_CORREO = os.path.join(CARPETA_DOCUMENTOS, ".ultimo_envio_alertas.txt")

def leer_fecha_ultimo_correo() -> Optional[date]:
    """Lee del disco la fecha del último reporte diario enviado automáticamente."""
    if os.path.exists(ARCHIVO_CONTROL_CORREO):
        try:
            with open(ARCHIVO_CONTROL_CORREO, "r", encoding="utf-8") as f:
                return date.fromisoformat(f.read().strip())
        except Exception:
            return None
    return None

def guardar_fecha_ultimo_correo(fecha_envio: date) -> None:
    """Registra en disco la fecha en que se envió el reporte automático del día."""
    try:
        with open(ARCHIVO_CONTROL_CORREO, "w", encoding="utf-8") as f:
            f.write(fecha_envio.isoformat())
    except Exception:
        pass

# ==========================================================
# TAREA EN SEGUNDO PLANO (MONITOREO AUTÓNOMO SIN WEBAPP ABIERTA)
# ==========================================================
async def tarea_vigilante_alertas():
    """
    Corrutina que se ejecuta en segundo plano mientras el servidor FastAPI esté encendido.
    Verifica cada hora si existen alertas próximas (30 días) y envía el correo diario
    a los Administradores aunque nadie tenga abierta la aplicación en el navegador.
    """
    await asyncio.sleep(5)
    while True:
        try:
            hoy = date.today()
            if leer_fecha_ultimo_correo() != hoy:
                db = SessionLocal()
                try:
                    exito, detalle = procesar_envio_correo_alertas(db)
                    if exito:
                        guardar_fecha_ultimo_correo(hoy)
                        print(f"[Auto-Alertas IMSS] {detalle}")
                finally:
                    db.close()
        except Exception as e:
            print(f"[Auto-Alertas IMSS] Aviso en monitoreo automático: {e}")
        await asyncio.sleep(3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Administra el ciclo de vida de FastAPI iniciando y cerrando el vigilante de alertas."""
    tarea_bg = asyncio.create_task(tarea_vigilante_alertas())
    yield
    tarea_bg.cancel()

app = FastAPI(
    title="API - Gestión de Equipos Médicos IMSS",
    description="Backend para el control de inventarios, mantenimientos, transferencias, usuarios y equipos médicos hospitalarios.",
    version="1.2.0",
    lifespan=lifespan
)

app.mount("/app", StaticFiles(directory="frontend"), name="frontend")
app.mount("/archivos", StaticFiles(directory=CARPETA_DOCUMENTOS), name="archivos")

@app.get("/", include_in_schema=False)
def pagina_principal():
    """Redirige automáticamente la raíz del servidor hacia la pantalla de Login."""
    return RedirectResponse(url="/app/login.html")

# ==========================================================
# FUNCIONES AUXILIARES DE SEGURIDAD Y VALIDACIÓN
# ==========================================================
def encriptar_password(password_plana: str) -> str:
    """Genera un hash seguro con bcrypt para no guardar contraseñas en texto plano."""
    sal = bcrypt.gensalt()
    encriptada = bcrypt.hashpw(password_plana.encode("utf-8"), sal)
    return encriptada.decode("utf-8")

def verificar_password(password_plana: str, password_guardada: str) -> bool:
    """Compara la contraseña ingresada contra el hash guardado (soporta texto plano legado)."""
    try:
        if password_guardada.startswith("$2b$"):
            return bcrypt.checkpw(password_plana.encode("utf-8"), password_guardada.encode("utf-8"))
        return password_plana == password_guardada
    except Exception:
        return False

def verificar_es_admin(db: Session, id_admin: int) -> models.Usuario:
    """Verifica que el ID proporcionado corresponda a un usuario con rol ADMIN activo."""
    admin = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_admin).first()
    if not admin or admin.rol != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acción restringida: Solo un Administrador puede realizar esta operación."
        )
    return admin

def buscar_equipo_duplicado(
    db: Session,
    sn: Optional[str],
    nni: Optional[str],
    excluir_id_equipo: Optional[int] = None
):
    """
    Verifica si ya existe un equipo con el mismo SN o NNI en la base de datos,
    comparando únicamente los valores que no estén vacíos (evita falsos positivos con NULL).
    """
    condiciones = []
    if sn and sn.strip():
        condiciones.append(models.Equipo.sn == sn.strip())
    if nni and nni.strip():
        condiciones.append(models.Equipo.nni == nni.strip())
    if not condiciones:
        return None
    consulta = db.query(models.Equipo).filter(or_(*condiciones))
    if excluir_id_equipo is not None:
        consulta = consulta.filter(models.Equipo.id_equipo != excluir_id_equipo)
    return consulta.first()

def eliminar_archivo_fisico_seguro(ruta_archivo: Optional[str]) -> None:
    """Borra un archivo físico del disco sin lanzar error si ya no existe."""
    if ruta_archivo and os.path.exists(ruta_archivo):
        try:
            os.remove(ruta_archivo)
        except OSError:
            pass

# ==========================================================
# 1. RUTAS GENERALES (DIAGNÓSTICO DE BASE DE DATOS)
# ==========================================================
@app.get("/health-db", tags=["General"])
def probar_conexion_bd(db: Session = Depends(get_db)):
    """Verifica que FastAPI tenga conexión activa con PostgreSQL."""
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
# 2. REGISTRO, LOGIN, RECUPERACIÓN Y ADMINISTRACIÓN DE USUARIOS
# ==========================================================
@app.post("/usuarios/registro", response_model=schemas.UsuarioRespuesta, status_code=status.HTTP_201_CREATED, tags=["Usuarios y Login"])
def registrar_usuario(datos: schemas.UsuarioRegistro, db: Session = Depends(get_db)):
    """Crea una cuenta nueva con rol EMPLEADO por defecto."""
    correo_ocupado = db.query(models.Usuario).filter(models.Usuario.correo == datos.correo).first()
    if correo_ocupado:
        raise HTTPException(status_code=400, detail="Ese correo electrónico ya está registrado.")
    
    if datos.username:
        username_ocupado = db.query(models.Usuario).filter(models.Usuario.username == datos.username).first()
        if username_ocupado:
            raise HTTPException(status_code=400, detail="Ese nombre de usuario ya está en uso.")

    nuevo_usuario = models.Usuario(
        primernombre=datos.primernombre,
        segundonombre=datos.segundonombre,
        primerapellido=datos.primerapellido,
        segundoapellido=datos.segundoapellido,
        username=datos.username,
        correo=datos.correo,
        password_hash=encriptar_password(datos.password),
        rol="EMPLEADO"
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario

@app.post("/usuarios/login", tags=["Usuarios y Login"])
def iniciar_sesion(credenciales: schemas.UsuarioLogin, db: Session = Depends(get_db)):
    """Valida credenciales de acceso y bloquea el paso a cuentas marcadas como INACTIVO."""
    usuario = db.query(models.Usuario).filter(models.Usuario.correo == credenciales.correo).first()
    if not usuario or not verificar_password(credenciales.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")
    
    if usuario.rol == "INACTIVO":
        raise HTTPException(status_code=403, detail="Esta cuenta ha sido desactivada por un Administrador.")
    
    return {
        "mensaje": f"Bienvenido, {usuario.primernombre}",
        "usuario": schemas.UsuarioRespuesta.model_validate(usuario)
    }

@app.get("/usuarios/", response_model=List[schemas.UsuarioRespuesta], tags=["Usuarios y Login"])
def listar_usuarios(db: Session = Depends(get_db)):
    """Devuelve la lista completa de usuarios ordenada por su ID."""
    return db.query(models.Usuario).order_by(models.Usuario.id_usuario).all()

@app.put("/usuarios/{id_usuario}/perfil", response_model=schemas.UsuarioRespuesta, tags=["Usuarios y Login"])
def actualizar_perfil(id_usuario: int, datos: schemas.UsuarioActualizarPerfil, db: Session = Depends(get_db)):
    """Permite al usuario cambiar su nombre de usuario (username) o ruta de foto."""
    usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if datos.username is not None:
        otro = db.query(models.Usuario).filter(
            models.Usuario.id_usuario != id_usuario,
            models.Usuario.username == datos.username
        ).first()
        if otro:
            raise HTTPException(status_code=400, detail="Ese nombre de usuario ya está ocupado.")
        usuario.username = datos.username
    if datos.foto_perfil is not None:
        usuario.foto_perfil = datos.foto_perfil
    db.commit()
    db.refresh(usuario)
    return usuario

@app.post("/usuarios/{id_usuario}/foto", response_model=schemas.UsuarioRespuesta, tags=["Usuarios y Login"])
def subir_foto_perfil(
    id_usuario: int,
    foto: UploadFile = File(..., description="Imagen JPG o PNG desde la computadora"),
    db: Session = Depends(get_db)
):
    """Guarda físicamente la foto de perfil en archivos_subidos/perfiles/ y actualiza el usuario."""
    usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    extension = os.path.splitext(foto.filename)[1] or ".png"
    nombre_archivo = f"avatar_usuario_{id_usuario}{extension}"
    ruta_fisica = os.path.join(CARPETA_DOCUMENTOS, "perfiles", nombre_archivo)
    with open(ruta_fisica, "wb") as buffer:
        shutil.copyfileobj(foto.file, buffer)
    usuario.foto_perfil = f"/archivos/perfiles/{nombre_archivo}"
    db.commit()
    db.refresh(usuario)
    return usuario

@app.put("/usuarios/{id_usuario}/cambiar-password", tags=["Usuarios y Login"])
def cambiar_password(id_usuario: int, datos: schemas.UsuarioCambiarPassword, db: Session = Depends(get_db)):
    """Actualiza la contraseña desde el perfil tras verificar la contraseña actual."""
    usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if not verificar_password(datos.password_actual, usuario.password_hash):
        raise HTTPException(status_code=400, detail="La contraseña actual es incorrecta.")
    usuario.password_hash = encriptar_password(datos.password_nueva)
    db.commit()
    return {"mensaje": "Contraseña actualizada exitosamente."}

@app.put("/usuarios/{id_usuario_objetivo}/hacer-admin", response_model=schemas.UsuarioRespuesta, tags=["Usuarios y Login"])
def convertir_en_administrador(
    id_usuario_objetivo: int, 
    id_admin_que_autoriza: int = Query(...), 
    db: Session = Depends(get_db)
):
    """Otorga el rol ADMIN a otro usuario (exclusivo para Administradores)."""
    verificar_es_admin(db, id_admin_que_autoriza)
    
    usuario_objetivo = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario_objetivo).first()
    if not usuario_objetivo:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    
    usuario_objetivo.rol = "ADMIN"
    db.commit()
    db.refresh(usuario_objetivo)
    return usuario_objetivo

@app.put("/usuarios/{id_usuario_objetivo}/cambiar-rol", response_model=schemas.UsuarioRespuesta, tags=["Usuarios y Login"])
def cambiar_rol_o_estado_usuario(
    id_usuario_objetivo: int,
    nuevo_rol: str = Query(..., description="Valores permitidos: ADMIN, EMPLEADO, INACTIVO"),
    id_admin_que_autoriza: int = Query(...),
    db: Session = Depends(get_db)
):
    """Permite a un Administrador cambiar el rol de un usuario o bloquear su acceso (INACTIVO)."""
    verificar_es_admin(db, id_admin_que_autoriza)
    if id_usuario_objetivo == id_admin_que_autoriza and nuevo_rol != "ADMIN":
        raise HTTPException(status_code=400, detail="No puedes quitarte el rol de Administrador ni desactivar tu propia cuenta.")
    nuevo_rol = nuevo_rol.upper().strip()
    if nuevo_rol not in ["ADMIN", "EMPLEADO", "INACTIVO"]:
        raise HTTPException(status_code=400, detail="Rol no válido. Usa ADMIN, EMPLEADO o INACTIVO.")
    usuario_objetivo = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario_objetivo).first()
    if not usuario_objetivo:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    usuario_objetivo.rol = nuevo_rol
    db.commit()
    db.refresh(usuario_objetivo)
    return usuario_objetivo

@app.delete("/usuarios/{id_usuario_objetivo}", tags=["Usuarios y Login"])
def eliminar_usuario(
    id_usuario_objetivo: int,
    id_admin_que_autoriza: int = Query(...),
    db: Session = Depends(get_db)
):
    """Elimina permanentemente a un usuario limpiando antes sus vínculos en inventario_usuario."""
    verificar_es_admin(db, id_admin_que_autoriza)
    if id_usuario_objetivo == id_admin_que_autoriza:
        raise HTTPException(status_code=400, detail="Por seguridad, no puedes eliminar tu propia cuenta de Administrador.")
    usuario_objetivo = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario_objetivo).first()
    if not usuario_objetivo:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    
    # Desvincular de inventarios y transferencias antes de eliminar
    db.query(models.InventarioUsuario).filter(
        models.InventarioUsuario.id_usuario == id_usuario_objetivo
    ).delete()
    db.query(models.TransferenciaEquipo).filter(
        models.TransferenciaEquipo.id_usuario == id_usuario_objetivo
    ).update({"id_usuario": None})

    if usuario_objetivo.foto_perfil and usuario_objetivo.foto_perfil.startswith("/archivos/perfiles/"):
        ruta_foto = usuario_objetivo.foto_perfil.replace("/archivos/", f"{CARPETA_DOCUMENTOS}/")
        eliminar_archivo_fisico_seguro(ruta_foto)
    nombre_borrado = f"{usuario_objetivo.primernombre} {usuario_objetivo.primerapellido}"
    db.delete(usuario_objetivo)
    db.commit()
    return {"mensaje": f"El usuario '{nombre_borrado}' fue eliminado permanentemente del sistema."}

codigos_recuperacion = {}

@app.post("/usuarios/recuperar-password/solicitar", tags=["Usuarios y Login"])
def solicitar_codigo_recuperacion(datos: schemas.RecuperarPasswordSolicitud, db: Session = Depends(get_db)):
    """Envía un código OTP de 6 dígitos con vigencia de 15 minutos al correo del usuario."""
    usuario = db.query(models.Usuario).filter(models.Usuario.correo == datos.correo).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="No existe ninguna cuenta registrada con ese correo electrónico.")
    
    if usuario.rol == "INACTIVO":
        raise HTTPException(status_code=403, detail="Esta cuenta está desactivada. Contacta a un Administrador.")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    if not smtp_user or not smtp_password or "tu_correo" in smtp_user:
        raise HTTPException(status_code=400, detail="El servidor aún no tiene configurado SMTP_USER y SMTP_PASSWORD en .env.")
    codigo = f"{random.randint(100000, 999999)}"
    codigos_recuperacion[usuario.correo] = {
        "codigo": codigo,
        "expira": datetime.now() + timedelta(minutes=15)
    }
    cuerpo_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #1E293B;">
        <div style="background-color:#13322B; color:white; padding:16px; border-bottom:3px solid #A68250;">
            <h3 style="margin:0;">Biomédica IMSS - Recuperación de Contraseña</h3>
        </div>
        <div style="padding: 16px;">
            <p>Hola, <strong>{usuario.primernombre} {usuario.primerapellido}</strong>:</p>
            <p>Recibimos una solicitud para restablecer tu contraseña. Ingresa el siguiente código de verificación en la pantalla de inicio de sesión:</p>
            <div style="background:#F1F5F9; border:1px solid #CBD5E1; border-radius:8px; padding:14px; text-align:center; font-size:24px; font-weight:bold; letter-spacing:6px; color:#13322B; margin:20px 0;">
                {codigo}
            </div>
            <p style="font-size:12px; color:#64748B;">Este código expira en 15 minutos. Si tú no solicitaste este cambio, puedes ignorar este correo.</p>
        </div>
    </body>
    </html>
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "[Biomédica IMSS] Código para restablecer tu contraseña"
    msg["From"] = smtp_user
    msg["To"] = usuario.correo
    msg.attach(MIMEText(cuerpo_html, "html"))
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, [usuario.correo], msg.as_string())
        return {"mensaje": f"Se envió un código de 6 dígitos a {usuario.correo}."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo enviar el correo de recuperación: {str(e)}")

@app.post("/usuarios/recuperar-password/confirmar", tags=["Usuarios y Login"])
def confirmar_recuperacion_password(datos: schemas.RecuperarPasswordConfirmacion, db: Session = Depends(get_db)):
    """Verifica el código OTP de 6 dígitos y guarda la nueva contraseña encriptada."""
    registro = codigos_recuperacion.get(datos.correo)
    if not registro:
        raise HTTPException(status_code=400, detail="No hay una solicitud activa para este correo o el código ya fue usado.")
    if datetime.now() > registro["expira"]:
        del codigos_recuperacion[datos.correo]
        raise HTTPException(status_code=400, detail="El código ha expirado. Solicita uno nuevo.")
    if datos.codigo.strip() != registro["codigo"]:
        raise HTTPException(status_code=400, detail="El código ingresado es incorrecto.")
    usuario = db.query(models.Usuario).filter(models.Usuario.correo == datos.correo).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    usuario.password_hash = encriptar_password(datos.nueva_password)
    db.commit()
    del codigos_recuperacion[datos.correo]
    return {"mensaje": "Contraseña restablecida con éxito. Ya puedes iniciar sesión."}

# ==========================================================
# 3. CATÁLOGO Y BUSCADOR DE HOSPITALES
# ==========================================================
@app.get("/hospitales/", response_model=List[schemas.HospitalRespuesta], tags=["Hospitales"])
def buscar_o_listar_hospitales(
    buscar: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Lista todos los hospitales o filtra por coincidencias en nombre o ciudad."""
    consulta = db.query(models.Hospital)
    if buscar:
        consulta = consulta.filter(
            (models.Hospital.nombre.ilike(f"%{buscar}%")) | 
            (models.Hospital.ciudad.ilike(f"%{buscar}%"))
        )
    return consulta.order_by(models.Hospital.nombre).all()

@app.post("/hospitales/", response_model=schemas.HospitalRespuesta, status_code=status.HTTP_201_CREATED, tags=["Hospitales"])
def registrar_hospital(hospital: schemas.HospitalCrear, db: Session = Depends(get_db)):
    """Registra una nueva unidad médica hospitalaria."""
    nuevo_hospital = models.Hospital(**hospital.model_dump())
    db.add(nuevo_hospital)
    db.commit()
    db.refresh(nuevo_hospital)
    return nuevo_hospital

# ==========================================================
# 4. FLUJO DE INVENTARIOS (CREACIÓN, CAPTURA, CIERRE Y CANCELACIÓN)
# ==========================================================
@app.post("/inventarios/", response_model=schemas.InventarioRespuesta, status_code=status.HTTP_201_CREATED, tags=["Inventarios"])
def iniciar_inventario(datos: schemas.InventarioCrear, db: Session = Depends(get_db)):
    """Abre un nuevo inventario en estado EN_PROCESO y vincula a los usuarios participantes."""
    verificar_es_admin(db, datos.id_admin_creador)
    hospital = db.query(models.Hospital).filter(models.Hospital.id_hospital == datos.id_hospital).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="El hospital seleccionado no existe.")
    nuevo_inventario = models.Inventario(
        id_hospital=datos.id_hospital,
        fecha=datos.fecha,
        estado="EN_PROCESO"
    )
    db.add(nuevo_inventario)
    db.flush()
    todos_los_participantes = set(datos.ids_usuarios_participantes)
    todos_los_participantes.add(datos.id_admin_creador)
    for id_usr in todos_los_participantes:
        usuario_existe = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usr).first()
        if not usuario_existe:
            raise HTTPException(status_code=404, detail=f"El usuario participante con ID {id_usr} no existe.")
        
        vinculo_usuario = models.InventarioUsuario(
            id_inventario=nuevo_inventario.id_inventario,
            id_usuario=id_usr
        )
        db.add(vinculo_usuario)
    db.commit()
    db.refresh(nuevo_inventario)
    return nuevo_inventario

@app.post("/inventarios/{id_inventario}/equipos/", response_model=schemas.EquipoRespuesta, status_code=status.HTTP_201_CREATED, tags=["Inventarios"])
def registrar_equipo_en_inventario(
    id_inventario: int,
    equipo: schemas.EquipoCrear,
    db: Session = Depends(get_db)
):
    """Agrega un equipo individual a un inventario activo y le asigna el hospital correspondiente."""
    inventario = db.query(models.Inventario).filter(models.Inventario.id_inventario == id_inventario).first()
    if not inventario:
        raise HTTPException(status_code=404, detail="El inventario no existe.")
    if inventario.estado == "FINALIZADO":
        raise HTTPException(status_code=400, detail="Este inventario ya fue FINALIZADO y no permite agregar más equipos.")
    duplicado = buscar_equipo_duplicado(db, equipo.sn, equipo.nni)
    if duplicado:
        raise HTTPException(status_code=400, detail="Ya existe un equipo registrado con ese Número de Serie (SN) o NNI.")
    
    # Se excluye id_hospital del esquema para usar siempre el hospital del inventario activo
    datos_equipo = equipo.model_dump(exclude={"id_hospital"})
    nuevo_equipo = models.Equipo(
        **datos_equipo,
        id_hospital=inventario.id_hospital
    )
    db.add(nuevo_equipo)
    db.flush()
    vinculo_equipo = models.InventarioEquipo(
        id_inventario=id_inventario,
        id_equipo=nuevo_equipo.id_equipo
    )
    db.add(vinculo_equipo)
    db.commit()
    db.refresh(nuevo_equipo)
    return nuevo_equipo

@app.put("/inventarios/{id_inventario}/finalizar", response_model=schemas.InventarioRespuesta, tags=["Inventarios"])
def finalizar_inventario(
    id_inventario: int,
    id_admin: int = Query(...),
    db: Session = Depends(get_db)
):
    """Cambia el estado de un inventario a FINALIZADO para impedir futuras modificaciones."""
    verificar_es_admin(db, id_admin)
    inventario = db.query(models.Inventario).filter(models.Inventario.id_inventario == id_inventario).first()
    if not inventario:
        raise HTTPException(status_code=404, detail="Inventario no encontrado.")
    inventario.estado = "FINALIZADO"
    db.commit()
    db.refresh(inventario)
    return inventario

@app.delete("/inventarios/{id_inventario}", tags=["Inventarios"])
def cancelar_o_eliminar_inventario(
    id_inventario: int,
    id_admin: int = Query(...),
    eliminar_equipos_censados: bool = Query(True, description="Si es True, también da de baja los equipos registrados exclusivamente en este inventario"),
    db: Session = Depends(get_db)
):
    """
    Cancela y elimina un inventario del sistema (exclusivo para Administradores).
    Limpia participantes, documentos asociados y opcionalmente los equipos que se estaban capturando.
    """
    verificar_es_admin(db, id_admin)
    inventario = db.query(models.Inventario).filter(models.Inventario.id_inventario == id_inventario).first()
    if not inventario:
        raise HTTPException(status_code=404, detail="El inventario no existe.")
    # 1. Obtener los IDs de los equipos vinculados a este inventario
    vinculos_eq = db.query(models.InventarioEquipo).filter(
        models.InventarioEquipo.id_inventario == id_inventario
    ).all()
    ids_equipos = [v.id_equipo for v in vinculos_eq]
    # 2. Eliminar vínculos en inventario_equipo e inventario_usuario
    db.query(models.InventarioEquipo).filter(
        models.InventarioEquipo.id_inventario == id_inventario
    ).delete()
    db.query(models.InventarioUsuario).filter(
        models.InventarioUsuario.id_inventario == id_inventario
    ).delete()
    # 3. Eliminar documentos vinculados directamente a este inventario
    docs_inv = db.query(models.Documento).filter(models.Documento.id_inventario == id_inventario).all()
    for d in docs_inv:
        eliminar_archivo_fisico_seguro(d.rutaarchivo)
        db.delete(d)
    # 4. Si se indicó eliminar los equipos que se estaban registrando en este levantamiento
    if eliminar_equipos_censados and ids_equipos:
        for id_eq in ids_equipos:
            # Verificar que el equipo no pertenezca a otro inventario histórico
            en_otro_inv = db.query(models.InventarioEquipo).filter(
                models.InventarioEquipo.id_equipo == id_eq
            ).first()
            if not en_otro_inv:
                docs_eq = db.query(models.Documento).filter(models.Documento.id_equipo == id_eq).all()
                for deq in docs_eq:
                    eliminar_archivo_fisico_seguro(deq.rutaarchivo)
                    db.delete(deq)
                db.query(models.Mantenimiento).filter(models.Mantenimiento.id_equipo == id_eq).delete()
                db.query(models.TransferenciaEquipo).filter(models.TransferenciaEquipo.id_equipo == id_eq).delete()
                db.query(models.Equipo).filter(models.Equipo.id_equipo == id_eq).delete()
    # 5. Eliminar el registro del inventario
    db.delete(inventario)
    db.commit()
    return {"mensaje": f"El Inventario #{id_inventario} fue cancelado y eliminado correctamente."}

@app.get("/inventarios/", response_model=List[schemas.InventarioRespuesta], tags=["Inventarios"])
def ver_inventarios(
    id_usuario_consulta: Optional[int] = Query(None),
    id_hospital: Optional[int] = Query(None),
    estado: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Devuelve el historial completo de inventarios para cualquier usuario activo (ADMIN o EMPLEADO),
    permitiendo que todos los empleados consulten equipos y descarguen reportes Excel sin restricción de participación.
    """
    if id_usuario_consulta is not None:
        usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario_consulta).first()
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        if usuario.rol == "INACTIVO":
            raise HTTPException(status_code=403, detail="Cuenta inactiva.")
    consulta = db.query(models.Inventario)
    if id_hospital is not None:
        consulta = consulta.filter(models.Inventario.id_hospital == id_hospital)
    if estado is not None:
        consulta = consulta.filter(models.Inventario.estado == estado)
    return consulta.order_by(models.Inventario.fecha.desc(), models.Inventario.id_inventario.desc()).all()

# ==========================================================
# 5. CONSULTA, ALTA INDIVIDUAL, TRANSFERENCIAS, EDICIÓN Y BAJA DE EQUIPOS
# ==========================================================
def construir_consulta_equipos(
    db: Session,
    id_hospital: Optional[int] = None,
    id_inventario: Optional[int] = None,
    id_proveedor: Optional[int] = None,
    area: Optional[str] = None,
    marca: Optional[str] = None,
    garantia: Optional[bool] = None,
    estatusfuncional: Optional[bool] = None,
    buscar_texto: Optional[str] = None
):
    """Aplica los filtros combinados tanto para la tabla en pantalla como para el reporte Excel."""
    consulta = db.query(models.Equipo)
    if id_inventario is not None:
        consulta = consulta.join(
            models.InventarioEquipo,
            models.Equipo.id_equipo == models.InventarioEquipo.id_equipo
        ).filter(models.InventarioEquipo.id_inventario == id_inventario)
    if id_hospital is not None:
        consulta = consulta.filter(models.Equipo.id_hospital == id_hospital)
    if id_proveedor is not None:
        consulta = consulta.filter(models.Equipo.id_proveedor == id_proveedor)
    if area:
        consulta = consulta.filter(models.Equipo.area.ilike(f"%{area}%"))
    if marca:
        consulta = consulta.filter(models.Equipo.marca.ilike(f"%{marca}%"))
    if garantia is not None:
        consulta = consulta.filter(models.Equipo.garantia == garantia)
    if estatusfuncional is not None:
        consulta = consulta.filter(models.Equipo.estatusfuncional == estatusfuncional)
    if buscar_texto:
        consulta = consulta.filter(
            (models.Equipo.nombre_equipo.ilike(f"%{buscar_texto}%")) |
            (models.Equipo.nni.ilike(f"%{buscar_texto}%")) |
            (models.Equipo.sn.ilike(f"%{buscar_texto}%"))
        )
    return consulta.order_by(models.Equipo.id_equipo).all()

@app.get("/equipos/", response_model=List[schemas.EquipoRespuesta], tags=["Equipos"])
def filtrar_equipos(
    id_hospital: Optional[int] = Query(None),
    id_inventario: Optional[int] = Query(None),
    id_proveedor: Optional[int] = Query(None),
    area: Optional[str] = Query(None),
    marca: Optional[str] = Query(None),
    garantia: Optional[bool] = Query(None),
    estatusfuncional: Optional[bool] = Query(None),
    buscar_texto: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Endpoint de consulta filtrada en tiempo real para el catálogo de equipos médicos."""
    return construir_consulta_equipos(
        db, id_hospital, id_inventario, id_proveedor, area, marca, garantia, estatusfuncional, buscar_texto
    )

@app.post("/equipos/", response_model=schemas.EquipoRespuesta, status_code=status.HTTP_201_CREATED, tags=["Equipos"])
def registrar_equipo_individual(
    equipo: schemas.EquipoCrear,
    id_admin: int = Query(..., description="ID del Administrador que da de alta la nueva adquisición"),
    db: Session = Depends(get_db)
):
    """
    Da de alta un equipo médico de forma individual (ej. nuevas adquisiciones)
    asignándolo directamente a un hospital sin requerir un inventario en curso.
    """
    verificar_es_admin(db, id_admin)

    if not equipo.id_hospital:
        raise HTTPException(
            status_code=400,
            detail="Debes seleccionar el hospital al que se asignará el nuevo equipo."
        )

    hospital = db.query(models.Hospital).filter(models.Hospital.id_hospital == equipo.id_hospital).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="El hospital seleccionado no existe.")

    if equipo.id_proveedor is not None:
        proveedor = db.query(models.Proveedor).filter(models.Proveedor.id_proveedor == equipo.id_proveedor).first()
        if not proveedor:
            raise HTTPException(status_code=404, detail="El proveedor seleccionado no existe.")

    duplicado = buscar_equipo_duplicado(db, equipo.sn, equipo.nni)
    if duplicado:
        raise HTTPException(
            status_code=400,
            detail="Ya existe un equipo registrado con ese Número de Serie (SN) o NNI."
        )

    nuevo_equipo = models.Equipo(**equipo.model_dump())
    db.add(nuevo_equipo)
    db.commit()
    db.refresh(nuevo_equipo)
    return nuevo_equipo

@app.post("/equipos/{id_equipo}/transferir", response_model=schemas.TransferenciaRespuesta, status_code=status.HTTP_201_CREATED, tags=["Equipos"])
def transferir_equipo_hospital(
    id_equipo: int,
    datos: schemas.TransferenciaCrear,
    id_admin: int = Query(..., description="ID del Administrador que autoriza la transferencia"),
    db: Session = Depends(get_db)
):
    """
    Transfiere un equipo médico de su hospital actual hacia otra unidad médica,
    actualizando su ubicación en tiempo real y guardando el movimiento en la bitácora histórica.
    """
    admin = verificar_es_admin(db, id_admin)

    equipo = db.query(models.Equipo).filter(models.Equipo.id_equipo == id_equipo).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="El equipo médico no existe.")

    if not equipo.id_hospital:
        raise HTTPException(
            status_code=400,
            detail="Este equipo no tiene un hospital origen asignado actualmente.Asígnale uno desde Editar primero."
        )

    if equipo.id_hospital == datos.id_hospital_destino:
        raise HTTPException(
            status_code=400,
            detail="El hospital destino debe ser diferente al hospital donde ya se encuentra el equipo."
        )

    hospital_origen = db.query(models.Hospital).filter(models.Hospital.id_hospital == equipo.id_hospital).first()
    hospital_destino = db.query(models.Hospital).filter(models.Hospital.id_hospital == datos.id_hospital_destino).first()
    if not hospital_destino:
        raise HTTPException(status_code=404, detail="El hospital destino seleccionado no existe.")

    # 1. Crear el registro en la bitácora histórica de transferencias
    id_usr_registro = datos.id_usuario or id_admin
    nueva_transferencia = models.TransferenciaEquipo(
        id_equipo=id_equipo,
        id_hospital_origen=equipo.id_hospital,
        id_hospital_destino=datos.id_hospital_destino,
        id_usuario=id_usr_registro,
        motivo=datos.motivo.strip()
    )
    db.add(nueva_transferencia)

    # 2. Actualizar el hospital actual en la tabla maestra de equipos
    equipo.id_hospital = datos.id_hospital_destino

    db.commit()
    db.refresh(nueva_transferencia)

    nombre_usr = f"{admin.primernombre} {admin.primerapellido}"
    return schemas.TransferenciaRespuesta(
        id_transferencia=nueva_transferencia.id_transferencia,
        id_equipo=nueva_transferencia.id_equipo,
        id_hospital_origen=nueva_transferencia.id_hospital_origen,
        hospital_origen_nombre=f"{hospital_origen.nombre} ({hospital_origen.ciudad})" if hospital_origen else f"Hospital #{nueva_transferencia.id_hospital_origen}",
        id_hospital_destino=nueva_transferencia.id_hospital_destino,
        hospital_destino_nombre=f"{hospital_destino.nombre} ({hospital_destino.ciudad})",
        id_usuario=nueva_transferencia.id_usuario,
        usuario_nombre=nombre_usr,
        fecha=nueva_transferencia.fecha,
        motivo=nueva_transferencia.motivo
    )

@app.get("/equipos/{id_equipo}/transferencias", response_model=List[schemas.TransferenciaRespuesta], tags=["Equipos"])
def obtener_historial_transferencias_equipo(
    id_equipo: int,
    db: Session = Depends(get_db)
):
    """Devuelve la bitácora histórica de transferencias de un equipo específico, de la más reciente a la más antigua."""
    equipo = db.query(models.Equipo).filter(models.Equipo.id_equipo == id_equipo).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")

    hospitales = {
        h.id_hospital: f"{h.nombre} ({h.ciudad})"
        for h in db.query(models.Hospital).all()
    }
    usuarios = {
        u.id_usuario: f"{u.primernombre} {u.primerapellido}"
        for u in db.query(models.Usuario).all()
    }

    registros = db.query(models.TransferenciaEquipo).filter(
        models.TransferenciaEquipo.id_equipo == id_equipo
    ).order_by(models.TransferenciaEquipo.fecha.desc(), models.TransferenciaEquipo.id_transferencia.desc()).all()

    respuesta = []
    for r in registros:
        respuesta.append(
            schemas.TransferenciaRespuesta(
                id_transferencia=r.id_transferencia,
                id_equipo=r.id_equipo,
                id_hospital_origen=r.id_hospital_origen,
                hospital_origen_nombre=hospitales.get(r.id_hospital_origen, f"Hospital #{r.id_hospital_origen}"),
                id_hospital_destino=r.id_hospital_destino,
                hospital_destino_nombre=hospitales.get(r.id_hospital_destino, f"Hospital #{r.id_hospital_destino}"),
                id_usuario=r.id_usuario,
                usuario_nombre=usuarios.get(r.id_usuario, "Usuario eliminado") if r.id_usuario else "Sistema",
                fecha=r.fecha,
                motivo=r.motivo
            )
        )
    return respuesta

@app.get("/exportar/equipos-excel", tags=["Equipos"])
def exportar_equipos_excel(
    id_hospital: Optional[int] = Query(None),
    id_inventario: Optional[int] = Query(None),
    id_proveedor: Optional[int] = Query(None),
    area: Optional[str] = Query(None),
    marca: Optional[str] = Query(None),
    garantia: Optional[bool] = Query(None),
    estatusfuncional: Optional[bool] = Query(None),
    buscar_texto: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Genera un archivo Excel (.xlsx) con diseño institucional IMSS según los filtros activos."""
    equipos = construir_consulta_equipos(
        db, id_hospital, id_inventario, id_proveedor, area, marca, garantia, estatusfuncional, buscar_texto
    )
    hospitales = {h.id_hospital: f"{h.nombre} ({h.ciudad})" for h in db.query(models.Hospital).all()}
    proveedores = {p.id_proveedor: p.nombre_proveedor for p in db.query(models.Proveedor).all()}
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Equipos Biomédicos"
    relleno_verde = PatternFill(start_color="13322B", end_color="13322B", fill_type="solid")
    relleno_subtitulo = PatternFill(start_color="EBF3F0", end_color="EBF3F0", fill_type="solid")
    fuente_titulo = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
    fuente_encabezado = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fuente_subtitulo = Font(name="Calibri", size=10, italic=True, color="13322B")
    borde_fino = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )
    ws.merge_cells("A1:L1")
    ws["A1"] = "INSTITUTO MEXICANO DEL SEGURO SOCIAL - REPORTE DE EQUIPO BIOMÉDICO"
    ws["A1"].fill = relleno_verde
    ws["A1"].font = fuente_titulo
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 26
    resumen_filtros = []
    if id_inventario:
        inv = db.query(models.Inventario).filter(models.Inventario.id_inventario == id_inventario).first()
        if inv:
            resumen_filtros.append(f"Inventario #{inv.id_inventario} ({inv.fecha})")
            if not id_hospital:
                resumen_filtros.append(f"Hospital: {hospitales.get(inv.id_hospital, inv.id_hospital)}")
    if id_hospital:
        resumen_filtros.append(f"Hospital: {hospitales.get(id_hospital, id_hospital)}")
    if id_proveedor:
        resumen_filtros.append(f"Proveedor: {proveedores.get(id_proveedor, id_proveedor)}")
    if area:
        resumen_filtros.append(f"Área: {area}")
    if marca:
        resumen_filtros.append(f"Marca: {marca}")
    if garantia is not None:
        resumen_filtros.append(f"Garantía: {'Con garantía' if garantia else 'Sin garantía'}")
    if estatusfuncional is not None:
        resumen_filtros.append(f"Estatus: {'Funcional' if estatusfuncional else 'Inactivo'}")
    if buscar_texto:
        resumen_filtros.append(f"Búsqueda: '{buscar_texto}'")
    texto_criterios = " | ".join(resumen_filtros) if resumen_filtros else "Catálogo General"
    ws.merge_cells("A2:L2")
    ws["A2"] = f"Fecha de emisión: {date.today()}   —   Criterios aplicados: {texto_criterios}   —   Total de equipos: {len(equipos)}"
    ws["A2"].fill = relleno_subtitulo
    ws["A2"].font = fuente_subtitulo
    ws["A2"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[2].height = 20
    encabezados = [
        "ID", "Nombre del Equipo", "Hospital", "Área", "Subárea",
        "Marca", "Modelo", "NNI", "Número de Serie (SN)", "Proveedor",
        "Garantía / Vigencia", "Estatus Funcional"
    ]
    ws.append([])
    ws.append(encabezados)
    ws.row_dimensions[4].height = 22
    for col_num in range(1, len(encabezados) + 1):
        celda = ws.cell(row=4, column=col_num)
        celda.fill = relleno_verde
        celda.font = fuente_encabezado
        celda.alignment = Alignment(horizontal="center", vertical="center")
    for eq in equipos:
        vigencia = f"Vence: {eq.fecha_expgarantia}" if eq.garantia else "Sin garantía"
        estatus = "FUNCIONAL" if eq.estatusfuncional else "FUERA DE SERVICIO"
        fila = [
            eq.id_equipo,
            eq.nombre_equipo or "Sin información",
            hospitales.get(eq.id_hospital, "Sin hospital"),
            eq.area or "Sin información",
            eq.subarea or "-",
            eq.marca or "Sin información",
            eq.modelo or "-",
            eq.nni or "Sin información",
            eq.sn or "Sin información",
            proveedores.get(eq.id_proveedor, "Sin proveedor asignado"),
            vigencia,
            estatus
        ]
        ws.append(fila)
        fila_actual = ws.max_row
        for col_num in range(1, len(encabezados) + 1):
            ws.cell(row=fila_actual, column=col_num).border = borde_fino
    for col in ws.columns:
        letra_col = openpyxl.utils.get_column_letter(col[0].column)
        max_len = 0
        for celda in col:
            if celda.row >= 4 and celda.value:
                max_len = max(max_len, len(str(celda.value)))
        ws.column_dimensions[letra_col].width = max(max_len + 4, 12)
    flujo = io.BytesIO()
    wb.save(flujo)
    flujo.seek(0)
    nombre_archivo = f"Inventario_{id_inventario}_{date.today()}.xlsx" if id_inventario else f"Equipos_Filtrados_{date.today()}.xlsx"
    return StreamingResponse(
        flujo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"}
    )

@app.put("/equipos/{id_equipo}", response_model=schemas.EquipoRespuesta, tags=["Equipos"])
def actualizar_equipo(
    id_equipo: int,
    datos: schemas.EquipoActualizar,
    id_admin: int = Query(...),
    db: Session = Depends(get_db)
):
    """Permite a un Administrador editar la información, garantía o estado funcional de un equipo."""
    verificar_es_admin(db, id_admin)
    equipo = db.query(models.Equipo).filter(models.Equipo.id_equipo == id_equipo).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")
    duplicado = buscar_equipo_duplicado(db, datos.sn, datos.nni, excluir_id_equipo=id_equipo)
    if duplicado:
        raise HTTPException(status_code=400, detail="Otro equipo ya tiene registrado ese Número de Serie (SN) o NNI.")
    for campo, valor in datos.model_dump().items():
        setattr(equipo, campo, valor)
    db.commit()
    db.refresh(equipo)
    return equipo

@app.delete("/equipos/{id_equipo}", tags=["Equipos"])
def eliminar_equipo(
    id_equipo: int,
    id_admin: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Da de baja (elimina permanentemente) un equipo médico del sistema (exclusivo para Administradores).
    Limpia previamente sus vínculos en inventarios, transferencias, mantenimientos y documentos asociados.
    """
    verificar_es_admin(db, id_admin)
    equipo = db.query(models.Equipo).filter(models.Equipo.id_equipo == id_equipo).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")
    # 1. Eliminar documentos asociados a este equipo (y sus archivos físicos)
    docs_eq = db.query(models.Documento).filter(models.Documento.id_equipo == id_equipo).all()
    for doc in docs_eq:
        eliminar_archivo_fisico_seguro(doc.rutaarchivo)
        db.delete(doc)
    # 2. Eliminar documentos asociados a los mantenimientos de este equipo
    mants_eq = db.query(models.Mantenimiento).filter(models.Mantenimiento.id_equipo == id_equipo).all()
    for m in mants_eq:
        docs_mant = db.query(models.Documento).filter(models.Documento.id_mantenimiento == m.id_mantenimiento).all()
        for dm in docs_mant:
            eliminar_archivo_fisico_seguro(dm.rutaarchivo)
            db.delete(dm)
        db.delete(m)
    # 3. Eliminar relación en inventario_equipo y en historial de transferencias
    db.query(models.InventarioEquipo).filter(models.InventarioEquipo.id_equipo == id_equipo).delete()
    db.query(models.TransferenciaEquipo).filter(models.TransferenciaEquipo.id_equipo == id_equipo).delete()
    # 4. Eliminar el equipo
    nombre_eq = equipo.nombre_equipo or f"#{id_equipo}"
    db.delete(equipo)
    db.commit()
    return {"mensaje": f"El equipo '{nombre_eq}' fue dado de baja y eliminado del sistema."}

# ==========================================================
# 6. DIRECTORIO DE PROVEEDORES (ALTA, EDICIÓN Y BAJA)
# ==========================================================
@app.get("/proveedores/", response_model=List[schemas.ProveedorRespuesta], tags=["Proveedores"])
def listar_proveedores(
    buscar: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Lista proveedores registrados o filtra por empresa/contacto."""
    consulta = db.query(models.Proveedor)
    if buscar:
        consulta = consulta.filter(
            (models.Proveedor.nombre_proveedor.ilike(f"%{buscar}%")) |
            (models.Proveedor.nombre_contacto.ilike(f"%{buscar}%"))
        )
    return consulta.order_by(models.Proveedor.nombre_proveedor).all()

@app.post("/proveedores/", response_model=schemas.ProveedorRespuesta, status_code=status.HTTP_201_CREATED, tags=["Proveedores"])
def agregar_proveedor(proveedor: schemas.ProveedorCrear, db: Session = Depends(get_db)):
    """Registra un nuevo proveedor externo de mantenimiento biomédico."""
    if proveedor.correo:
        existe = db.query(models.Proveedor).filter(models.Proveedor.correo == proveedor.correo).first()
        if existe:
            raise HTTPException(status_code=400, detail="Ya existe un proveedor con ese correo electrónico.")
    nuevo_proveedor = models.Proveedor(**proveedor.model_dump())
    db.add(nuevo_proveedor)
    db.commit()
    db.refresh(nuevo_proveedor)
    return nuevo_proveedor

@app.put("/proveedores/{id_proveedor}", response_model=schemas.ProveedorRespuesta, tags=["Proveedores"])
def actualizar_proveedor(
    id_proveedor: int,
    datos: schemas.ProveedorActualizar,
    id_admin: int = Query(...),
    db: Session = Depends(get_db)
):
    """Permite a un Administrador modificar los datos de contacto o empresa de un proveedor."""
    verificar_es_admin(db, id_admin)
    proveedor = db.query(models.Proveedor).filter(models.Proveedor.id_proveedor == id_proveedor).first()
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado.")
    if datos.correo:
        correo_duplicado = db.query(models.Proveedor).filter(
            models.Proveedor.id_proveedor != id_proveedor,
            models.Proveedor.correo == datos.correo
        ).first()
        if correo_duplicado:
            raise HTTPException(status_code=400, detail="Otro proveedor ya tiene registrado ese correo electrónico.")
    for campo, valor in datos.model_dump().items():
        setattr(proveedor, campo, valor)
    db.commit()
    db.refresh(proveedor)
    return proveedor

@app.delete("/proveedores/{id_proveedor}", tags=["Proveedores"])
def eliminar_proveedor(
    id_proveedor: int,
    id_admin: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Elimina un proveedor del directorio (exclusivo para Administradores).
    Desvincula previamente sus equipos y mantenimientos (poniendo id_proveedor = NULL) para no perder historial.
    """
    verificar_es_admin(db, id_admin)
    proveedor = db.query(models.Proveedor).filter(models.Proveedor.id_proveedor == id_proveedor).first()
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado.")
    db.query(models.Equipo).filter(models.Equipo.id_proveedor == id_proveedor).update({"id_proveedor": None})
    db.query(models.Mantenimiento).filter(models.Mantenimiento.id_proveedor == id_proveedor).update({"id_proveedor": None})
    nombre_prov = proveedor.nombre_proveedor
    db.delete(proveedor)
    db.commit()
    return {"mensaje": f"El proveedor '{nombre_prov}' fue eliminado correctamente."}

# ==========================================================
# 7. CONTROL DE MANTENIMIENTOS (ALTA, EDICIÓN Y BAJA)
# ==========================================================
@app.post("/mantenimientos/", response_model=schemas.MantenimientoRespuesta, status_code=status.HTTP_201_CREATED, tags=["Mantenimientos"])
def registrar_mantenimiento(datos: schemas.MantenimientoCrear, db: Session = Depends(get_db)):
    """Registra una intervención de mantenimiento preventivo o correctivo."""
    equipo = db.query(models.Equipo).filter(models.Equipo.id_equipo == datos.id_equipo).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="El equipo indicado no existe.")
    if datos.id_proveedor is not None:
        proveedor = db.query(models.Proveedor).filter(models.Proveedor.id_proveedor == datos.id_proveedor).first()
        if not proveedor:
            raise HTTPException(status_code=404, detail="El proveedor indicado no existe.")
    nuevo_mant = models.Mantenimiento(**datos.model_dump())
    db.add(nuevo_mant)
    db.commit()
    db.refresh(nuevo_mant)
    return nuevo_mant

@app.get("/mantenimientos/", response_model=List[schemas.MantenimientoRespuesta], tags=["Mantenimientos"])
def listar_mantenimientos(
    id_equipo: Optional[int] = Query(None),
    tipo: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Lista el historial de mantenimientos ordenado por fecha más reciente."""
    consulta = db.query(models.Mantenimiento)
    if id_equipo is not None:
        consulta = consulta.filter(models.Mantenimiento.id_equipo == id_equipo)
    if tipo is not None:
        consulta = consulta.filter(models.Mantenimiento.tipo_mantenimiento == tipo)
    return consulta.order_by(models.Mantenimiento.fecha.desc(), models.Mantenimiento.id_mantenimiento.desc()).all()

@app.put("/mantenimientos/{id_mantenimiento}", response_model=schemas.MantenimientoRespuesta, tags=["Mantenimientos"])
def actualizar_mantenimiento(
    id_mantenimiento: int,
    datos: schemas.MantenimientoActualizar,
    id_admin: int = Query(...),
    db: Session = Depends(get_db)
):
    """Permite a un Administrador modificar proveedor, fechas u observaciones de un mantenimiento."""
    verificar_es_admin(db, id_admin)
    mant = db.query(models.Mantenimiento).filter(models.Mantenimiento.id_mantenimiento == id_mantenimiento).first()
    if not mant:
        raise HTTPException(status_code=404, detail="Registro de mantenimiento no encontrado.")
    equipo = db.query(models.Equipo).filter(models.Equipo.id_equipo == datos.id_equipo).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="El equipo seleccionado no existe.")
    if datos.id_proveedor is not None:
        proveedor = db.query(models.Proveedor).filter(models.Proveedor.id_proveedor == datos.id_proveedor).first()
        if not proveedor:
            raise HTTPException(status_code=404, detail="El proveedor seleccionado no existe.")
    for campo, valor in datos.model_dump().items():
        setattr(mant, campo, valor)
    db.commit()
    db.refresh(mant)
    return mant

@app.delete("/mantenimientos/{id_mantenimiento}", tags=["Mantenimientos"])
def eliminar_mantenimiento(
    id_mantenimiento: int,
    id_admin: int = Query(...),
    db: Session = Depends(get_db)
):
    """Elimina un registro de mantenimiento y sus documentos asociados (exclusivo para Administradores)."""
    verificar_es_admin(db, id_admin)
    mant = db.query(models.Mantenimiento).filter(models.Mantenimiento.id_mantenimiento == id_mantenimiento).first()
    if not mant:
        raise HTTPException(status_code=404, detail="Mantenimiento no encontrado.")
    docs_mant = db.query(models.Documento).filter(models.Documento.id_mantenimiento == id_mantenimiento).all()
    for d in docs_mant:
        eliminar_archivo_fisico_seguro(d.rutaarchivo)
        db.delete(d)
    db.delete(mant)
    db.commit()
    return {"mensaje": f"El Mantenimiento #{id_mantenimiento} fue eliminado correctamente."}

# ==========================================================
# 8. REPOSITORIO DOCUMENTAL (SUBIDA, EDICIÓN, REEMPLAZO Y BAJA)
# ==========================================================
@app.post("/documentos/subir", response_model=schemas.DocumentoRespuesta, status_code=status.HTTP_201_CREATED, tags=["Documentos"])
def subir_documento(
    nombre_documento: str = Form(...),
    id_equipo: Optional[int] = Form(None),
    id_mantenimiento: Optional[int] = Form(None),
    id_inventario: Optional[int] = Form(None),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Recibe un archivo PDF o imagen, le asigna un prefijo único de tiempo para evitar
    sobrescrituras en disco y lo vincula a un equipo, mantenimiento o inventario.
    """
    ids_proporcionados = [x for x in [id_equipo, id_mantenimiento, id_inventario] if x is not None]
    if len(ids_proporcionados) != 1:
        raise HTTPException(
            status_code=400, 
            detail="Debes asociar el documento a UNA SOLA entidad (equipo, mantenimiento o inventario)."
        )
    nombre_limpio = os.path.basename(archivo.filename or "documento.pdf")
    nombre_unico = f"{int(datetime.now().timestamp())}_{nombre_limpio}"
    ruta_guardado = os.path.join(CARPETA_DOCUMENTOS, nombre_unico)
    with open(ruta_guardado, "wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)
    nuevo_doc = models.Documento(
        nombredocumento=nombre_documento,
        rutaarchivo=ruta_guardado,
        id_equipo=id_equipo,
        id_mantenimiento=id_mantenimiento,
        id_inventario=id_inventario
    )
    db.add(nuevo_doc)
    db.commit()
    db.refresh(nuevo_doc)
    return nuevo_doc

@app.put("/documentos/{id_documento}", response_model=schemas.DocumentoRespuesta, tags=["Documentos"])
def actualizar_o_reemplazar_documento(
    id_documento: int,
    id_admin: int = Query(...),
    nombre_documento: str = Form(...),
    id_equipo: Optional[int] = Form(None),
    id_mantenimiento: Optional[int] = Form(None),
    id_inventario: Optional[int] = Form(None),
    archivo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Permite a un Administrador cambiar el nombre del documento, reasignar su entidad
    (inventario, equipo o mantenimiento) y opcionalmente reemplazar el archivo físico en el servidor.
    """
    verificar_es_admin(db, id_admin)
    doc = db.query(models.Documento).filter(models.Documento.id_documento == id_documento).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    ids_proporcionados = [x for x in [id_equipo, id_mantenimiento, id_inventario] if x is not None]
    if len(ids_proporcionados) != 1:
        raise HTTPException(
            status_code=400,
            detail="El documento debe estar asociado exactamente a una entidad (equipo, mantenimiento o inventario)."
        )
    doc.nombredocumento = nombre_documento.strip()
    doc.id_equipo = id_equipo
    doc.id_mantenimiento = id_mantenimiento
    doc.id_inventario = id_inventario
    # Si el administrador subió un archivo nuevo para reemplazar el anterior
    if archivo and archivo.filename:
        eliminar_archivo_fisico_seguro(doc.rutaarchivo)
        nombre_limpio = os.path.basename(archivo.filename)
        nombre_unico = f"{int(datetime.now().timestamp())}_{nombre_limpio}"
        nueva_ruta = os.path.join(CARPETA_DOCUMENTOS, nombre_unico)
        with open(nueva_ruta, "wb") as buffer:
            shutil.copyfileobj(archivo.file, buffer)
        doc.rutaarchivo = nueva_ruta
    db.commit()
    db.refresh(doc)
    return doc

@app.delete("/documentos/{id_documento}", tags=["Documentos"])
def eliminar_documento(
    id_documento: int,
    id_admin: int = Query(...),
    db: Session = Depends(get_db)
):
    """Elimina un documento de la base de datos y borra su archivo físico del servidor."""
    verificar_es_admin(db, id_admin)
    doc = db.query(models.Documento).filter(models.Documento.id_documento == id_documento).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    eliminar_archivo_fisico_seguro(doc.rutaarchivo)
    titulo = doc.nombredocumento
    db.delete(doc)
    db.commit()
    return {"mensaje": f"El documento '{titulo}' fue eliminado permanentemente."}

@app.get("/documentos/", response_model=List[schemas.DocumentoRespuesta], tags=["Documentos"])
def listar_documentos(
    id_equipo: Optional[int] = Query(None),
    id_mantenimiento: Optional[int] = Query(None),
    id_inventario: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Lista los documentos registrados en el sistema."""
    consulta = db.query(models.Documento)
    if id_equipo is not None:
        consulta = consulta.filter(models.Documento.id_equipo == id_equipo)
    if id_mantenimiento is not None:
        consulta = consulta.filter(models.Documento.id_mantenimiento == id_mantenimiento)
    if id_inventario is not None:
        consulta = consulta.filter(models.Documento.id_inventario == id_inventario)
    return consulta.order_by(models.Documento.id_documento.desc()).all()

@app.get("/documentos/{id_documento}/ver", tags=["Documentos"])
def ver_o_descargar_documento(id_documento: int, db: Session = Depends(get_db)):
    """Abre o descarga el documento físico almacenado en el servidor."""
    doc = db.query(models.Documento).filter(models.Documento.id_documento == id_documento).first()
    if not doc:
        raise HTTPException(status_code=404, detail="El documento no existe en la base de datos.")
    
    if not os.path.exists(doc.rutaarchivo):
        raise HTTPException(status_code=404, detail="El archivo físico no se encontró en el servidor.")
    
    return FileResponse(doc.rutaarchivo)

# ==========================================================
# 9. MOTOR DE ALERTAS Y ENVÍO AUTOMÁTICO / MANUAL POR CORREO
# ==========================================================
@app.get("/alertas/", tags=["Alertas"])
def obtener_alertas_proximas(
    dias_anticipacion: int = Query(30),
    db: Session = Depends(get_db)
):
    """Calcula garantías vencidas/por vencer y mantenimientos próximos/atrasados."""
    hoy = date.today()
    fecha_limite = hoy + timedelta(days=dias_anticipacion)
    equipos_alerta_garantia = db.query(models.Equipo).filter(
        models.Equipo.garantia == True,
        models.Equipo.fecha_expgarantia != None,
        models.Equipo.fecha_expgarantia <= fecha_limite
    ).order_by(models.Equipo.fecha_expgarantia).all()
    alertas_garantias = []
    for eq in equipos_alerta_garantia:
        dias_restantes = (eq.fecha_expgarantia - hoy).days
        estado_alerta = "VENCIDA" if dias_restantes < 0 else "POR_VENCER"
        alertas_garantias.append({
            "id_equipo": eq.id_equipo,
            "nombre_equipo": eq.nombre_equipo,
            "nni": eq.nni,
            "id_hospital": eq.id_hospital,
            "fecha_expiracion": eq.fecha_expgarantia,
            "dias_restantes": dias_restantes,
            "semaforo": estado_alerta
        })
    mantenimientos_alerta = db.query(models.Mantenimiento).filter(
        models.Mantenimiento.prox_fecha != None,
        models.Mantenimiento.prox_fecha <= fecha_limite
    ).order_by(models.Mantenimiento.prox_fecha).all()
    alertas_mantenimientos = []
    for mant in mantenimientos_alerta:
        dias_restantes = (mant.prox_fecha - hoy).days
        estado_alerta = "ATRASADO" if dias_restantes < 0 else "PROXIMO"
        alertas_mantenimientos.append({
            "id_mantenimiento": mant.id_mantenimiento,
            "id_equipo": mant.id_equipo,
            "tipo_mantenimiento": mant.tipo_mantenimiento,
            "proxima_fecha": mant.prox_fecha,
            "dias_restantes": dias_restantes,
            "semaforo": estado_alerta
        })
    return {
        "fecha_consulta": hoy,
        "dias_anticipacion_configurados": dias_anticipacion,
        "total_alertas_garantia": len(alertas_garantias),
        "alertas_garantias": alertas_garantias,
        "total_alertas_mantenimiento": len(alertas_mantenimientos),
        "alertas_mantenimientos": alertas_mantenimientos
    }

def procesar_envio_correo_alertas(db: Session) -> tuple[bool, str]:
    """
    Función central reutilizable que construye y envía el correo HTML de alertas
    a todos los usuarios con rol ADMIN cuando existen garantías o mantenimientos próximos.
    """
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    if not smtp_user or not smtp_password or "tu_correo" in smtp_user:
        return False, "Falta configurar SMTP_USER y SMTP_PASSWORD en el archivo .env."
    admins = db.query(models.Usuario).filter(models.Usuario.rol == "ADMIN").all()
    correos_destino = [a.correo for a in admins if a.correo]
    if not correos_destino:
        return False, "No hay administradores con correo registrado."
    datos_alertas = obtener_alertas_proximas(dias_anticipacion=30, db=db)
    total_pendientes = datos_alertas["total_alertas_garantia"] + datos_alertas["total_alertas_mantenimiento"]
    if total_pendientes == 0:
        return False, "No hay alertas pendientes en los próximos 30 días."
    mapa_equipos = {
        e.id_equipo: f"{e.nombre_equipo or 'Equipo #' + str(e.id_equipo)} (NNI: {e.nni or 'S/N'})"
        for e in db.query(models.Equipo).all()
    }
    filas_garantias = "".join([
        f"<tr><td style='padding:6px;border:1px solid #ddd;'>{g['nombre_equipo'] or 'S/N'}</td>"
        f"<td style='padding:6px;border:1px solid #ddd;'>{g['nni'] or 'Sin información'}</td>"
        f"<td style='padding:6px;border:1px solid #ddd;'>{g['fecha_expiracion']}</td>"
        f"<td style='padding:6px;border:1px solid #ddd;'>{g['dias_restantes']} días ({g['semaforo']})</td></tr>"
        for g in datos_alertas["alertas_garantias"]
    ]) or "<tr><td colspan='4' style='padding:8px;'>Sin alertas de garantía</td></tr>"
    filas_mant = "".join([
        f"<tr><td style='padding:6px;border:1px solid #ddd;'>{mapa_equipos.get(m['id_equipo'], 'Equipo #' + str(m['id_equipo']))}</td>"
        f"<td style='padding:6px;border:1px solid #ddd;'>{m['tipo_mantenimiento']}</td>"
        f"<td style='padding:6px;border:1px solid #ddd;'>{m['proxima_fecha']}</td>"
        f"<td style='padding:6px;border:1px solid #ddd;'>{m['dias_restantes']} días ({m['semaforo']})</td></tr>"
        for m in datos_alertas["alertas_mantenimientos"]
    ]) or "<tr><td colspan='4' style='padding:8px;'>Sin mantenimientos próximos</td></tr>"
    cuerpo_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #1E293B;">
        <div style="background-color:#13322B; color:white; padding:16px; border-bottom:3px solid #A68250;">
            <h3 style="margin:0;">Biomédica IMSS - Reporte Automático de Alertas</h3>
            <small>Fecha de corte: {date.today()}</small>
        </div>
        <p>Se presenta el resumen de garantías próximas a expirar y mantenimientos programados (próximos 30 días):</p>
        <h4>1. Garantías Vencidas o por Vencer ({datos_alertas['total_alertas_garantia']})</h4>
        <table style="border-collapse:collapse; width:100%; font-size:13px;">
            <tr style="background:#F1F5F9;">
                <th style="padding:6px;border:1px solid #ddd;text-align:left;">Equipo</th>
                <th style="padding:6px;border:1px solid #ddd;text-align:left;">NNI</th>
                <th style="padding:6px;border:1px solid #ddd;text-align:left;">Expiración</th>
                <th style="padding:6px;border:1px solid #ddd;text-align:left;">Estado</th>
            </tr>
            {filas_garantias}
        </table>
        <h4 style="margin-top:20px;">2. Mantenimientos Próximos o Atrasados ({datos_alertas['total_alertas_mantenimiento']})</h4>
        <table style="border-collapse:collapse; width:100%; font-size:13px;">
            <tr style="background:#F1F5F9;">
                <th style="padding:6px;border:1px solid #ddd;text-align:left;">Equipo</th>
                <th style="padding:6px;border:1px solid #ddd;text-align:left;">Tipo</th>
                <th style="padding:6px;border:1px solid #ddd;text-align:left;">Próxima Fecha</th>
                <th style="padding:6px;border:1px solid #ddd;text-align:left;">Estado</th>
            </tr>
            {filas_mant}
        </table>
    </body>
    </html>
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Biomédica IMSS] Alertas de Garantías y Mantenimiento ({date.today()})"
    msg["From"] = smtp_user
    msg["To"] = ", ".join(correos_destino)
    msg.attach(MIMEText(cuerpo_html, "html"))
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, correos_destino, msg.as_string())
        return True, f"Reporte enviado con éxito a {len(correos_destino)} administrador(es): {', '.join(correos_destino)}"
    except Exception as e:
        return False, f"No se pudo enviar el correo: {str(e)}"

@app.post("/alertas/auto-notificar-diario", tags=["Alertas"])
def auto_notificar_alertas_diarias(
    id_usuario: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Endpoint invocado silenciosamente al abrir el panel web.
    Si el vigilante en segundo plano aún no ha enviado el correo de hoy, lo dispara una sola vez.
    """
    hoy = date.today()
    usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario).first()
    if not usuario or usuario.rol != "ADMIN":
        return {"enviado": False, "detalle": "Modo consulta (Empleado)."}
    if leer_fecha_ultimo_correo() == hoy:
        return {"enviado": False, "detalle": f"El reporte automático del día ({hoy}) ya fue enviado."}
    exito, detalle = procesar_envio_correo_alertas(db)
    if exito:
        guardar_fecha_ultimo_correo(hoy)
        return {"enviado": True, "mensaje": f"Sincronización diaria automática: {detalle}"}
    return {"enviado": False, "detalle": detalle}

@app.post("/alertas/enviar-correo", tags=["Alertas"])
def enviar_alertas_correo_admins(
    id_admin_solicitante: int = Query(...),
    db: Session = Depends(get_db)
):
    """Permite forzar manualmente el envío del reporte de alertas desde Swagger (/docs) si se requiere."""
    verificar_es_admin(db, id_admin_solicitante)
    exito, detalle = procesar_envio_correo_alertas(db)
    if not exito:
        raise HTTPException(status_code=400, detail=detalle)
    guardar_fecha_ultimo_correo(date.today())
    return {"mensaje": detalle}

# ==========================================================
# 10. IMPORTACIÓN MASIVA DE EQUIPOS DESDE CSV
# ==========================================================
@app.post("/inventarios/{id_inventario}/importar-csv", tags=["Inventarios"])
def importar_equipos_csv(
    id_inventario: int,
    archivo_csv: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Importa lotes de equipos desde un archivo CSV omitiendo duplicados de SN o NNI de forma segura."""
    inventario = db.query(models.Inventario).filter(models.Inventario.id_inventario == id_inventario).first()
    if not inventario:
        raise HTTPException(status_code=404, detail="El inventario no existe.")
    if inventario.estado == "FINALIZADO":
        raise HTTPException(status_code=400, detail="Este inventario ya está FINALIZADO y no admite más equipos.")
    contenido_bytes = archivo_csv.file.read()
    try:
        texto_csv = contenido_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto_csv = contenido_bytes.decode("latin-1")
    lector = csv.DictReader(io.StringIO(texto_csv))
    equipos_insertados = 0
    equipos_omitidos = []
    for num_fila, fila in enumerate(lector, start=2):
        fila_limpia = {k.strip().lower(): (v.strip() if v else None) for k, v in fila.items() if k}
        sn = fila_limpia.get("sn")
        nni = fila_limpia.get("nni")
        if not sn and not nni:
            continue
        duplicado = buscar_equipo_duplicado(db, sn, nni)
        if duplicado:
            equipos_omitidos.append(f"Fila {num_fila}: NNI '{nni}' o SN '{sn}' ya registrado.")
            continue
        garantia_txt = str(fila_limpia.get("garantia", "")).upper()
        tiene_garantia = garantia_txt in ["TRUE", "1", "SI", "SÍ", "T", "YES"]
        estatus_txt = str(fila_limpia.get("estatusfuncional", "TRUE")).upper()
        es_funcional = estatus_txt in ["TRUE", "1", "SI", "SÍ", "T", "YES", "FUNCIONAL"]
        fecha_garantia = fila_limpia.get("fecha_expgarantia") if tiene_garantia else None
        nuevo_equipo = models.Equipo(
            id_hospital=inventario.id_hospital,
            nombre_equipo=fila_limpia.get("nombre_equipo"),
            area=fila_limpia.get("area"),
            subarea=fila_limpia.get("subarea"),
            marca=fila_limpia.get("marca"),
            modelo=fila_limpia.get("modelo"),
            sn=sn,
            nni=nni,
            garantia=tiene_garantia,
            fecha_expgarantia=fecha_garantia,
            estatusfuncional=es_funcional,
            observaciones=fila_limpia.get("observaciones")
        )
        db.add(nuevo_equipo)
        db.flush()
        vinculo = models.InventarioEquipo(
            id_inventario=id_inventario,
            id_equipo=nuevo_equipo.id_equipo
        )
        db.add(vinculo)
        equipos_insertados += 1
    db.commit()
    return {
        "mensaje": "Importación de CSV completada con éxito",
        "id_inventario": id_inventario,
        "id_hospital_asignado": inventario.id_hospital,
        "equipos_registrados": equipos_insertados,
        "duplicados_omitidos": len(equipos_omitidos),
        "detalle_omitidos": equipos_omitidos
    }