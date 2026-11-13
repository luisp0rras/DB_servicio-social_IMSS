import os
import shutil
import bcrypt
from datetime import date, timedelta
from fastapi import FastAPI, Depends, HTTPException, status, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional

from .database import get_db
from . import models, schemas

app = FastAPI(
    title="API - Gestión de Equipos Médicos IMSS",
    description="Backend para el control de inventarios, mantenimientos y equipos médicos hospitalarios.",
    version="0.3.0"
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
        # Por si tienes usuarios viejos de prueba en la BD con contraseñas sin encriptar
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
    """Verifica correo y contraseña, y devuelve los datos del usuario junto con su rol (ADMIN o EMPLEADO)."""
    
    usuario = db.query(models.Usuario).filter(models.Usuario.correo == credenciales.correo).first()
    
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

    if not verificar_password(datos.password_actual, usuario.password_hash):
        raise HTTPException(status_code=400, detail="La contraseña actual es incorrecta.")

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
    
    admin = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_admin_que_autoriza).first()
    if not admin or admin.rol != "ADMIN":
        raise HTTPException(status_code=403, detail="Acceso denegado: Solo un Administrador puede crear otros administradores.")
    
    usuario_objetivo = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario_objetivo).first()
    if not usuario_objetivo:
        raise HTTPException(status_code=404, detail="El usuario que intentas hacer administrador no existe.")
    
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


# ==========================================================
# 4. FLUJO DE INVENTARIOS (PASOS 2, 3, 4 Y 5)
# ==========================================================

@app.post("/inventarios/", response_model=schemas.InventarioRespuesta, status_code=status.HTTP_201_CREATED, tags=["Inventarios"])
def iniciar_inventario(datos: schemas.InventarioCrear, db: Session = Depends(get_db)):
    """
    PASOS 2 y 3 DEL FLUJO:
    1. Revisa que quien lo crea sea ADMIN.
    2. Crea el inventario en estado 'EN_PROCESO'.
    3. Agrega automáticamente al ADMIN y a los demás usuarios participantes.
    """
    admin = db.query(models.Usuario).filter(models.Usuario.id_usuario == datos.id_admin_creador).first()
    if not admin or admin.rol != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo un Administrador puede iniciar un inventario.")

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
    """
    PASO 4 DEL FLUJO:
    Registra un equipo dentro del inventario activo y le asigna automáticamente el hospital.
    """
    inventario = db.query(models.Inventario).filter(models.Inventario.id_inventario == id_inventario).first()
    if not inventario:
        raise HTTPException(status_code=404, detail="El inventario no existe.")

    if inventario.estado == "FINALIZADO":
        raise HTTPException(status_code=400, detail="Este inventario ya fue FINALIZADO y no permite agregar más equipos.")

    duplicado = db.query(models.Equipo).filter(
        (models.Equipo.sn == equipo.sn) | (models.Equipo.nni == equipo.nni)
    ).first()
    if duplicado:
        raise HTTPException(status_code=400, detail="Ya existe un equipo registrado con ese Número de Serie (SN) o NNI.")

    nuevo_equipo = models.Equipo(
        **equipo.model_dump(),
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
    id_admin: int = Query(..., description="ID del Administrador que finaliza el inventario"),
    db: Session = Depends(get_db)
):
    """
    PASO 5 DEL FLUJO:
    Cambia el estado del inventario a 'FINALIZADO' para cerrar la captura de equipos.
    """
    admin = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_admin).first()
    if not admin or admin.rol != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo un Administrador puede finalizar un inventario.")

    inventario = db.query(models.Inventario).filter(models.Inventario.id_inventario == id_inventario).first()
    if not inventario:
        raise HTTPException(status_code=404, detail="Inventario no encontrado.")

    inventario.estado = "FINALIZADO"
    db.commit()
    db.refresh(inventario)
    return inventario


@app.get("/inventarios/", response_model=List[schemas.InventarioRespuesta], tags=["Inventarios"])
def ver_inventarios(
    id_usuario_consulta: int = Query(..., description="ID del usuario que está viendo la pantalla"),
    id_hospital: Optional[int] = Query(None, description="Filtrar por hospital"),
    estado: Optional[str] = Query(None, description="Filtrar por 'EN_PROCESO' o 'FINALIZADO'"),
    db: Session = Depends(get_db)
):
    """
    Muestra los inventarios según el permiso del usuario:
    - Si es ADMIN: Puede ver TODOS los inventarios de todos los hospitales.
    - Si es EMPLEADO: Solo ve los inventarios en los que él participó.
    """
    usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario_consulta).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    consulta = db.query(models.Inventario)

    if usuario.rol != "ADMIN":
        consulta = consulta.join(
            models.InventarioUsuario,
            models.Inventario.id_inventario == models.InventarioUsuario.id_inventario
        ).filter(models.InventarioUsuario.id_usuario == id_usuario_consulta)

    if id_hospital is not None:
        consulta = consulta.filter(models.Inventario.id_hospital == id_hospital)
    if estado is not None:
        consulta = consulta.filter(models.Inventario.estado == estado)

    return consulta.order_by(models.Inventario.fecha.desc()).all()


# ==========================================================
# 5. CONSULTA Y FILTROS DE EQUIPOS MÉDICOS
# ==========================================================

@app.get("/equipos/", response_model=List[schemas.EquipoRespuesta], tags=["Equipos"])
def filtrar_equipos(
    id_hospital: Optional[int] = Query(None, description="Filtrar por ID de hospital"),
    id_inventario: Optional[int] = Query(None, description="Filtrar equipos de un inventario específico"),
    area: Optional[str] = Query(None, description="Buscar por área (ej. 'Urgencias' o 'Area 03')"),
    marca: Optional[str] = Query(None, description="Buscar por marca"),
    garantia: Optional[bool] = Query(None, description="True = Con garantía, False = Sin garantía"),
    estatusfuncional: Optional[bool] = Query(None, description="True = Funcional, False = Dañado"),
    buscar_texto: Optional[str] = Query(None, description="Buscar por nombre, NNI o Número de Serie (SN)"),
    db: Session = Depends(get_db)
):
    """Permite buscar y filtrar equipos combinando todos los requisitos que necesites."""
    consulta = db.query(models.Equipo)

    if id_inventario is not None:
        consulta = consulta.join(
            models.InventarioEquipo,
            models.Equipo.id_equipo == models.InventarioEquipo.id_equipo
        ).filter(models.InventarioEquipo.id_inventario == id_inventario)

    if id_hospital is not None:
        consulta = consulta.filter(models.Equipo.id_hospital == id_hospital)
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


# ==========================================================
# 6. PROVEEDORES (VER Y AGREGAR)
# ==========================================================

@app.get("/proveedores/", response_model=List[schemas.ProveedorRespuesta], tags=["Proveedores"])
def listar_proveedores(
    buscar: Optional[str] = Query(None, description="Buscar por nombre de empresa o contacto"),
    db: Session = Depends(get_db)
):
    """Muestra todos los proveedores registrados o los filtra si escribes en el buscador."""
    consulta = db.query(models.Proveedor)
    if buscar:
        consulta = consulta.filter(
            (models.Proveedor.nombre_proveedor.ilike(f"%{buscar}%")) |
            (models.Proveedor.nombre_contacto.ilike(f"%{buscar}%"))
        )
    return consulta.order_by(models.Proveedor.nombre_proveedor).all()


@app.post("/proveedores/", response_model=schemas.ProveedorRespuesta, status_code=status.HTTP_201_CREATED, tags=["Proveedores"])
def agregar_proveedor(proveedor: schemas.ProveedorCrear, db: Session = Depends(get_db)):
    """Registra un nuevo proveedor externo."""
    if proveedor.correo:
        existe = db.query(models.Proveedor).filter(models.Proveedor.correo == proveedor.correo).first()
        if existe:
            raise HTTPException(status_code=400, detail="Ya existe un proveedor con ese correo electrónico.")

    nuevo_proveedor = models.Proveedor(**proveedor.model_dump())
    db.add(nuevo_proveedor)
    db.commit()
    db.refresh(nuevo_proveedor)
    return nuevo_proveedor


# ==========================================================
# 7. MANTENIMIENTOS (REGISTRAR Y CONSULTAR HISTORIAL)
# ==========================================================

@app.post("/mantenimientos/", response_model=schemas.MantenimientoRespuesta, status_code=status.HTTP_201_CREATED, tags=["Mantenimientos"])
def registrar_mantenimiento(datos: schemas.MantenimientoCrear, db: Session = Depends(get_db)):
    """Registra un mantenimiento (PREVENTIVO, CORRECTIVO u OTRO) a un equipo médico."""
    equipo = db.query(models.Equipo).filter(models.Equipo.id_equipo == datos.id_equipo).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="El equipo indicado no existe.")

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
    id_equipo: Optional[int] = Query(None, description="Filtrar historial de un equipo específico"),
    tipo: Optional[str] = Query(None, description="Filtrar por PREVENTIVO, CORRECTIVO u OTRO"),
    db: Session = Depends(get_db)
):
    """Muestra el historial de mantenimientos realizados."""
    consulta = db.query(models.Mantenimiento)
    if id_equipo is not None:
        consulta = consulta.filter(models.Mantenimiento.id_equipo == id_equipo)
    if tipo is not None:
        consulta = consulta.filter(models.Mantenimiento.tipo_mantenimiento == tipo)
    return consulta.order_by(models.Mantenimiento.fecha.desc()).all()


# ==========================================================
# 8. DOCUMENTOS (SUBIR Y VISUALIZAR ARCHIVOS PDF / IMÁGENES)
# ==========================================================

CARPETA_DOCUMENTOS = "archivos_subidos"
os.makedirs(CARPETA_DOCUMENTOS, exist_ok=True)

@app.post("/documentos/subir", response_model=schemas.DocumentoRespuesta, status_code=status.HTTP_201_CREATED, tags=["Documentos"])
def subir_documento(
    nombre_documento: str = Form(..., description="Título del documento (ej. 'Minuta supervisión HGR 66')"),
    id_equipo: Optional[int] = Form(None, description="Llenar SOLO si el documento pertenece a un Equipo"),
    id_mantenimiento: Optional[int] = Form(None, description="Llenar SOLO si pertenece a un Mantenimiento"),
    id_inventario: Optional[int] = Form(None, description="Llenar SOLO si pertenece a un Inventario"),
    archivo: UploadFile = File(..., description="Selecciona el archivo PDF o imagen de tu computadora"),
    db: Session = Depends(get_db)
):
    """
    Recibe un archivo real desde tu computadora, lo guarda en la carpeta 'archivos_subidos'
    y registra sus datos en PostgreSQL respetando la regla de exclusividad (solo 1 ID lleno).
    """
    ids_proporcionados = [x for x in [id_equipo, id_mantenimiento, id_inventario] if x is not None]
    if len(ids_proporcionados) != 1:
        raise HTTPException(
            status_code=400, 
            detail="Regla de integridad: Debes asociar el documento a UNA SOLA entidad (o id_equipo, o id_mantenimiento, o id_inventario)."
        )

    ruta_guardado = os.path.join(CARPETA_DOCUMENTOS, archivo.filename)
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


@app.get("/documentos/", response_model=List[schemas.DocumentoRespuesta], tags=["Documentos"])
def listar_documentos(
    id_equipo: Optional[int] = Query(None),
    id_mantenimiento: Optional[int] = Query(None),
    id_inventario: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Muestra la lista de documentos registrados (puedes filtrar por equipo, mantenimiento o inventario)."""
    consulta = db.query(models.Documento)
    if id_equipo is not None:
        consulta = consulta.filter(models.Documento.id_equipo == id_equipo)
    if id_mantenimiento is not None:
        consulta = consulta.filter(models.Documento.id_mantenimiento == id_mantenimiento)
    if id_inventario is not None:
        consulta = consulta.filter(models.Documento.id_inventario == id_inventario)
    return consulta.all()


@app.get("/documentos/{id_documento}/ver", tags=["Documentos"])
def ver_o_descargar_documento(id_documento: int, db: Session = Depends(get_db)):
    """Abre o descarga el archivo PDF/imagen real guardado en el servidor."""
    doc = db.query(models.Documento).filter(models.Documento.id_documento == id_documento).first()
    if not doc:
        raise HTTPException(status_code=404, detail="El registro del documento no existe en la base de datos.")
    
    if not os.path.exists(doc.rutaarchivo):
        raise HTTPException(
            status_code=404, 
            detail=f"El archivo físico no se encontró en la ruta: {doc.rutaarchivo}"
        )
    
    return FileResponse(doc.rutaarchivo)


# ==========================================================
# 9. SISTEMA DE ALERTAS (GARANTÍAS Y MANTENIMIENTOS PRÓXIMOS)
# ==========================================================

@app.get("/alertas/", tags=["Alertas"])
def obtener_alertas_proximas(
    dias_anticipacion: int = Query(30, description="¿Con cuántos días de anticipación quieres que te avise? (Por defecto: 30 días)"),
    db: Session = Depends(get_db)
):
    """
    Revisa la fecha de hoy y busca:
    1. Equipos cuya garantía ya venció o vence en los próximos X días.
    2. Mantenimientos cuya próxima fecha programada ya pasó o toca en los próximos X días.
    """
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