import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ==========================================================
# CONFIGURACIÓN DE CONEXIÓN A POSTGRESQL (SQLALCHEMY)
# ==========================================================

# 1. Cargar las variables de entorno definidas en el archivo .env
load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Validar que la cadena de conexión exista antes de intentar arrancar el servidor
if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError(
        "Error crítico: No se encontró la variable 'DATABASE_URL' en el archivo .env. "
        "Verifica que exista con el formato: postgresql://usuario:password@localhost:5432/nombre_bd"
    )

# Corregir automáticamente el prefijo antiguo 'postgres://' si se llegara a utilizar
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 2. Crear el motor de conexión con blindaje para servidores en producción:
# - pool_pre_ping=True: Verifica que la conexión siga activa antes de cada consulta (evita caídas tras inactividad).
# - pool_recycle=1800: Recicla conexiones cada 30 minutos para mantener limpio el servidor PostgreSQL.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800
)

# 3. Crear la fábrica de sesiones transaccionales
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Clase base de la cual heredan todos los modelos ORM en app/models.py
Base = declarative_base()


# ==========================================================
# DEPENDENCIA DE SESIÓN PARA ENDPOINTS DE FASTAPI
# ==========================================================
def get_db():
    """
    Abre una sesión segura con PostgreSQL al iniciar cada petición HTTP
    y garantiza su cierre inmediato al terminar (incluso si ocurre un error).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()