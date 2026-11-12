from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from .database import get_db

app = FastAPI(
    title="API - Gestión de Equipos Médicos IMSS",
    description="Backend para el control de inventarios, mantenimientos y equipos médicos hospitalarios.",
    version="0.1.0"
)

@app.get("/")
def inicio():
    return {"mensaje": "API del Servicio Social IMSS funcionando correctamente"}

@app.get("/health-db")
def probar_conexion_bd(db: Session = Depends(get_db)):
    try:
        # Ejecuta una consulta rápida en PostgreSQL para verificar conexión
        resultado = db.execute(text("SELECT current_database(), current_user;")).fetchone()
        return {
            "estatus": "Conectado exitosamente a PostgreSQL",
            "base_de_datos": resultado[0],
            "usuario_db": resultado[1]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {str(e)}")