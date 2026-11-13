# Peaje IoT con ESP32

Proyecto de **Máquinas Digitales (Unillanos 2026-2)**. Una maqueta de peaje: un carrito se acerca, el sensor lo detecta, el sistema lo cuenta y la barrera se levanta. Desde una página web se supervisa el peaje y se cambia su modo.

Integrantes: _(nombres)_

Basado en el repositorio de ejemplo del docente: [RonyTrespalacios/esp32-mensaje-web](https://github.com/RonyTrespalacios/esp32-mensaje-web).

---

## 1. Propuesta

| | |
|---|---|
| **Sensor** | HC-SR04 (distancia por ultrasonido) |
| **Actuador** | Servo SG90 con un palito como barrera |
| **Página web** | Estado de la barrera, distancia, contador de vehículos, historial con hora y selector de modo |

**Modos del peaje** (se eligen en la página):

- **Automático:** la barrera sube cuando llega un vehículo y baja 3 s después de que se va.
- **Abierto:** barrera arriba todo el tiempo.
- **Cerrado:** barrera abajo aunque llegue un vehículo (se cuenta y queda como "bloqueado" en el historial).

### Decisiones de diseño

1. **La ESP32 decide la barrera sola.** La ESP32 consulta al backend solo una vez por segundo. Si esperara al servidor para abrir, la barrera subiría con retraso. Por eso el firmware reacciona al sensor de inmediato y el backend solo guarda el modo y el historial.
2. **Se cuenta el flanco, no cada lectura.** Un carro detenido frente al sensor daría decenas de lecturas cercanas. Solo se cuenta el cambio de "nada delante" a "vehículo delante".
3. **Histéresis.** Se considera que llegó un carro a menos de 10 cm, y que se fue a más de 15 cm. Ese margen evita contar dos veces por ruido del sensor.
4. **Sin `delay()`.** El firmware usa `millis()` para medir cada 60 ms y hablar con el backend cada segundo sin congelarse.
5. **Funciona sin red.** Si no hay WiFi, el peaje sigue funcionando en modo automático.

## 2. Arquitectura

```
                 GET  /api/actuador  (¿qué modo?)
  ESP32  ───────────────────────────────────────▶  Backend FastAPI (Docker, :8000)
 HC-SR04         POST /api/lecturas  (distancia,         ▲
  + servo              barrera, vehiculo)                │ GET /api/estado
                                                         │ PUT /api/modo
                                                  Página web (nginx, :3000)
```

## 3. Hardware y cableado

| Componente | Pin | ESP32 |
|---|---|---|
| HC-SR04 | VCC | VIN (5 V del USB) |
| | GND | GND |
| | TRIG | GPIO 5 |
| | ECHO | GPIO 18 **a través del divisor** |
| Servo SG90 | rojo (+) | VIN |
| | marrón (−) | GND |
| | naranja (señal) | GPIO 13 |

- **Divisor del ECHO:** ECHO → resistencia 1 kΩ → GPIO 18 → resistencia 2 kΩ → GND. El HC-SR04 entrega 5 V y la ESP32 solo aguanta 3.3 V (5 V × 2/3 ≈ 3.3 V).
- **Si el servo reinicia la ESP32:** condensador de 470 µF entre VIN y GND, cerca del servo.
- Todo comparte la misma tierra (GND).

## 4. API

| Método y ruta | Quién la usa | Cuerpo / respuesta |
|---|---|---|
| `GET /api/actuador` | ESP32 | → `{"modo": "automatico"}` |
| `POST /api/lecturas` | ESP32 | `{"distancia": 12.4, "barrera": "cerrada", "vehiculo": false}` |
| `GET /api/estado` | Página | → modo, barrera, distancia, contador, historial |
| `PUT /api/modo` | Página | `{"modo": "automatico" \| "abierto" \| "cerrado"}` |

`vehiculo` es `true` solo en el instante en que llega un carro. Con eso el backend suma al contador y agrega una fila al historial. La documentación interactiva queda en <http://localhost:8000/docs>.

## 5. Puesta en marcha

La instalación de Docker Desktop, Git y Arduino IDE es la misma que en la [guía del docente](https://ronytrespalacios.github.io/esp32-mensaje-web/).

1. **Backend y página:** `docker compose up -d --build`. La página queda en `http://localhost:3000` y, desde el celular, en `http://<IP-del-PC>:3000`.
2. **Firmware:**
   - En Arduino IDE, instalar la librería **ESP32Servo** (Tools → Manage Libraries).
   - Copiar `esp32/peaje/config.example.h` como `config.h` y poner el WiFi y la IP del PC. `config.h` no se sube al repositorio.
   - Abrir `esp32/peaje/peaje.ino` y subirlo a la placa (DOIT ESP32 DEVKIT V1).
3. **Calibrar:** ajustar `CM_LLEGA`, `CM_SALE` y los ángulos del servo al comienzo del `.ino` según la maqueta.

### Probar sin la ESP32

Se puede simular la ESP32 con `curl` y ver cómo cambia la página:

```bash
curl -X POST localhost:8000/api/lecturas -H "Content-Type: application/json" \
     -d '{"distancia": 8, "barrera": "abierta", "vehiculo": true}'
```

## 6. Etapas

| Etapa | Entregable |
|---|---|
| Propuesta | Este documento |
| Hardware | Detección y servo funcionando solo con la ESP32, sin red |
| Comunicación | La ESP32 envía lecturas y lee el modo del backend |
| Despliegue | Backend y página en Docker, visibles desde el celular de un compañero |
| Demostración | Carrito pasando, contador subiendo y cambio de modo desde la página |
