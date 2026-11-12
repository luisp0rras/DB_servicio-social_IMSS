import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Cargar las variables del archivo .env
load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Crear el motor de conexión a PostgreSQL
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Crear la fábrica de sesiones para hacer consultas
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base para mapear tus tablas más adelante
Base = declarative_base()

# Dependencia que abre y cierra la conexión en cada petición
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()