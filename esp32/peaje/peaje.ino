#include <WiFi.h>
#include <HTTPClient.h>
#include <ESP32Servo.h>  // Library Manager: "ESP32Servo" (Kevin Harrington)

// Credenciales WiFi e IP del backend (NO se sube a GitHub).
// Si no existe, copia "config.example.h" como "config.h" y editalo.
#include "config.h"

// ---------- Pines ----------
const int PIN_TRIG  = 5;
const int PIN_ECHO  = 18;  // pasa por el divisor 1k/2k: el HC-SR04 entrega 5 V
const int PIN_SERVO = 13;

// ---------- Ajustes (calibrar con la maqueta real) ----------
const float CM_LLEGA = 10;  // a menos de esto hay un carro
const float CM_SALE  = 15;  // a más de esto el carro ya se fue (el margen evita contar doble por ruido)
const int ANGULO_CERRADA = 0;
const int ANGULO_ABIERTA = 90;
const unsigned long ESPERA_CIERRE_MS  = 3000;  // baja 3 s después de que el carro se va
const unsigned long PERIODO_SENSOR_MS = 60;    // el HC-SR04 necesita ~60 ms entre medidas
const unsigned long PERIODO_RED_MS    = 1000;  // cada cuánto habla con el backend
const int LECTURAS_FALLA = 33;  // ~2 s seguidos sin eco = sensor desconectado (la maqueta debe tener una pared al frente)

String base = String("http://") + BACKEND_HOST + ":" + BACKEND_PORT;
Servo servo;

String modo = "automatico";  // lo cambia la página; arranca en automático aunque no haya red
bool hayCarro = false;
bool abierta = false;
bool sensorOk = true;
int sinEco = 0;  // lecturas seguidas sin eco
float distancia = 0;
unsigned long ultimoCarro = 0, ultimaMedida = 0, ultimaRed = 0;

float medirDistancia() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);
  unsigned long us = pulseIn(PIN_ECHO, HIGH, 30000);  // máximo 30 ms (~5 m)
  if (us == 0) return 999;  // sin eco: no hay nada al frente
  return us / 58.0;         // el sonido va y vuelve: 58 µs por cm
}

// La barrera la decide la ESP32 sola, sin esperar al servidor: así abre al instante.
void actualizarBarrera(unsigned long ahora) {
  bool abrir;
  if (modo == "abierto")      abrir = true;
  else if (modo == "cerrado") abrir = false;
  else abrir = hayCarro || (ultimoCarro > 0 && ahora - ultimoCarro < ESPERA_CIERRE_MS);

  if (abrir != abierta) {
    abierta = abrir;
    servo.write(abierta ? ANGULO_ABIERTA : ANGULO_CERRADA);
    Serial.println(abierta ? "Barrera abierta" : "Barrera cerrada");
  }
}

void enviarLectura(bool vehiculo) {
  HTTPClient http;
  http.begin(base + "/api/lecturas");
  http.setConnectTimeout(1500);  // si el PC no está en la red, no esperar los 5 s por defecto
  http.setTimeout(1500);  // si el backend no responde, no congelar el peaje mucho tiempo
  http.addHeader("Content-Type", "application/json");
  String body = String("{\"distancia\":") + distancia +
                ",\"barrera\":\"" + (abierta ? "abierta" : "cerrada") +
                "\",\"vehiculo\":" + (vehiculo ? "true" : "false") +
                ",\"presente\":" + (hayCarro ? "true" : "false") +
                ",\"sensor_ok\":" + (sensorOk ? "true" : "false") + "}";
  int code = http.POST(body);
  if (code != 200) Serial.printf("Error POST /api/lecturas: %d\n", code);
  http.end();
}

void consultarModo() {
  HTTPClient http;
  http.begin(base + "/api/actuador");
  http.setConnectTimeout(1500);
  http.setTimeout(1500);
  int code = http.GET();
  if (code == 200) {
    String r = http.getString();  // {"modo":"automatico"} — solo hay 3 valores posibles
    String nuevo = r.indexOf("\"cerrado\"") >= 0 ? "cerrado"
                 : r.indexOf("\"abierto\"") >= 0 ? "abierto"
                 : "automatico";
    if (nuevo != modo) {
      modo = nuevo;
      Serial.println("Nuevo modo: " + modo);
    }
  } else {
    Serial.printf("Error GET /api/actuador: %d\n", code);
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  servo.attach(PIN_SERVO);
  servo.write(ANGULO_CERRADA);

  // No se espera al WiFi: el peaje funciona aunque no haya red
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.println("Peaje listo. Backend: " + base);
}

void loop() {
  unsigned long ahora = millis();
  bool llego = false;

  if (ahora - ultimaMedida >= PERIODO_SENSOR_MS) {
    ultimaMedida = ahora;
    distancia = medirDistancia();
    sinEco = distancia >= 999 ? sinEco + 1 : 0;
    if (sensorOk != (sinEco < LECTURAS_FALLA)) {
      sensorOk = !sensorOk;
      Serial.println(sensorOk ? "Sensor recuperado" : "Falla del sensor: no hay eco");
    }
    // Se cuenta el flanco (no había carro -> ahora sí), no cada lectura cercana
    if (!hayCarro && distancia < CM_LLEGA) {
      hayCarro = llego = true;
      Serial.printf("Vehiculo detectado a %.1f cm\n", distancia);
    } else if (hayCarro && distancia > CM_SALE) {
      hayCarro = false;
    }
    if (hayCarro) ultimoCarro = ahora;
  }

  actualizarBarrera(ahora);  // primero mover la barrera, después avisar al servidor

  if (WiFi.status() == WL_CONNECTED) {
    if (llego) enviarLectura(true);
    if (ahora - ultimaRed >= PERIODO_RED_MS) {
      ultimaRed = ahora;
      consultarModo();
      enviarLectura(false);
    }
  }
}
