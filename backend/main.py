import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
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
SIN_SENAL_S = 5  # si la ESP32 no reporta en este tiempo se considera desconectada

estado = {
    "modo": "automatico",
    "barrera": "cerrada",
    "distancia": None,
    "presente": False,       # hay un carro frente al sensor ahora mismo
    "sensor_ok": True,       # False si el HC-SR04 dejó de responder
    "contador": 0,
    "ultima_lectura": None,  # cuándo habló la ESP32 por última vez
    "historial": [],         # los 20 eventos más recientes, el más nuevo primero
}

# Lo que debe sobrevivir a un reinicio se guarda en un archivo; en Docker vive en un volumen (ver docker-compose.yml)
ARCHIVO = Path(os.getenv("ARCHIVO_ESTADO", "estado.json"))
GUARDADO = ("modo", "contador", "historial")
if ARCHIVO.exists():
    estado.update({k: v for k, v in json.loads(ARCHIVO.read_text(encoding="utf-8")).items() if k in GUARDADO})


def guardar():
    tmp = ARCHIVO.with_suffix(".tmp")  # escribir aparte y reemplazar: un corte a mitad no deja el archivo dañado
    tmp.write_text(json.dumps({k: estado[k] for k in GUARDADO}, ensure_ascii=False), encoding="utf-8")
    tmp.replace(ARCHIVO)


class Modo(BaseModel):
    modo: Literal["automatico", "cerrado", "abierto"]


class Lectura(BaseModel):
    distancia: float
    barrera: Literal["abierta", "cerrada"]
    vehiculo: bool = False   # True solo en el instante en que llega un carro (flanco)
    presente: bool = False
    sensor_ok: bool = True


def registrar(origen: str, evento: str, alerta: bool = False):
    fila = {"hora": datetime.now(COLOMBIA).strftime("%H:%M:%S"), "origen": origen, "evento": evento, "alerta": alerta}
    estado["historial"] = [fila] + estado["historial"][:19]
    guardar()  # todo cambio del contador y del modo pasa por aquí


# ---------- Rutas que usa la ESP32 ----------

@app.get("/api/actuador")
def obtener_modo():
    """La ESP32 pregunta cada segundo en qué modo debe estar la barrera."""
    return {"modo": estado["modo"]}


@app.post("/api/lecturas")
def recibir_lectura(lectura: Lectura):
    """La ESP32 reporta distancia y barrera; vehiculo=True cuando detecta un carro."""
    if lectura.sensor_ok != estado["sensor_ok"]:
        registrar("ESP32", "Sensor recuperado" if lectura.sensor_ok else "Falla del sensor", not lectura.sensor_ok)
    estado.update(
        distancia=lectura.distancia,
        barrera=lectura.barrera,
        presente=lectura.presente,
        sensor_ok=lectura.sensor_ok,
        ultima_lectura=datetime.now(COLOMBIA).isoformat(),
    )
    if lectura.vehiculo:
        estado["contador"] += 1
        bloqueado = estado["modo"] == "cerrado"
        registrar("ESP32", f"Vehículo {estado['contador']} {'bloqueado' if bloqueado else 'pasó'}", bloqueado)
    return {"ok": True}


# ---------- Rutas que usa la página ----------

@app.get("/api/estado")
def obtener_estado():
    # La conexión se calcula aquí y no en el navegador: el reloj del celular puede no coincidir con el del PC
    ultima = estado["ultima_lectura"]
    conectada = ultima is not None and datetime.now(COLOMBIA) - datetime.fromisoformat(ultima) < timedelta(seconds=SIN_SENAL_S)
    return {**estado, "esp32_conectada": conectada}


@app.put("/api/modo")
def cambiar_modo(datos: Modo):
    if datos.modo != estado["modo"]:
        estado["modo"] = datos.modo
        registrar("Web", "Modo " + {"automatico": "automático"}.get(datos.modo, datos.modo))
    return {"modo": estado["modo"]}
