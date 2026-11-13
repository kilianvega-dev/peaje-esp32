from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Peaje API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

COLOMBIA = timezone(timedelta(hours=-5))  # Colombia no tiene horario de verano

# shortcut: estado en memoria, se pierde al reiniciar el contenedor; usar SQLite si hace falta guardar el historial
estado = {
    "modo": "automatico",
    "barrera": "cerrada",
    "distancia": None,
    "contador": 0,
    "ultima_lectura": None,  # cuándo habló la ESP32 por última vez
    "historial": [],         # los 20 pasos más recientes, el más nuevo primero
}


class Modo(BaseModel):
    modo: Literal["automatico", "cerrado", "abierto"]


class Lectura(BaseModel):
    distancia: float
    barrera: Literal["abierta", "cerrada"]
    vehiculo: bool = False  # True solo en el instante en que llega un carro (flanco)


# ---------- Rutas que usa la ESP32 ----------

@app.get("/api/actuador")
def obtener_modo():
    """La ESP32 pregunta cada segundo en qué modo debe estar la barrera."""
    return {"modo": estado["modo"]}


@app.post("/api/lecturas")
def recibir_lectura(lectura: Lectura):
    """La ESP32 reporta distancia y barrera; vehiculo=True cuando detecta un carro."""
    ahora = datetime.now(COLOMBIA)
    estado["distancia"] = lectura.distancia
    estado["barrera"] = lectura.barrera
    estado["ultima_lectura"] = ahora.isoformat()
    if lectura.vehiculo:
        estado["contador"] += 1
        paso = {
            "numero": estado["contador"],
            "hora": ahora.strftime("%H:%M:%S"),
            "resultado": "bloqueado" if estado["modo"] == "cerrado" else "pasó",
        }
        estado["historial"] = [paso] + estado["historial"][:19]
    return {"ok": True}


# ---------- Rutas que usa la página ----------

@app.get("/api/estado")
def obtener_estado():
    return estado


@app.put("/api/modo")
def cambiar_modo(datos: Modo):
    estado["modo"] = datos.modo
    return {"modo": estado["modo"]}
