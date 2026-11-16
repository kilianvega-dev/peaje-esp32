// El backend corre en el mismo host que sirve el frontend, puerto 8000
const API = `http://${window.location.hostname}:8000`;

const $ = (id) => document.getElementById(id);
const botones = document.querySelectorAll("[data-modo]");

function conexion(texto, clase) {
  $("conexion").textContent = texto;
  $("conexion").className = `pill ${clase}`;
}

function sinDatos(motivo) {
  $("escena").classList.add("sin-datos");
  $("aviso").textContent = motivo;
}

async function cargarEstado() {
  let e;
  try {
    const res = await fetch(`${API}/api/estado`);
    e = await res.json();
  } catch {
    conexion("Backend desconectado", "mal");
    sinDatos("Sin conexión con el backend");
    botones.forEach((b) => (b.disabled = true));
    return;
  }
  botones.forEach((b) => {
    b.disabled = false;
    b.classList.toggle("activo", b.dataset.modo === e.modo);
  });

  const escena = $("escena");
  escena.classList.remove("sin-datos");
  escena.classList.toggle("abierta", e.barrera === "abierta");
  escena.classList.toggle("presente", e.presente);
  escena.classList.toggle("falla", !e.sensor_ok);

  $("barrera").textContent = e.barrera;
  $("distancia").textContent =
    !e.sensor_ok ? "sin eco" : e.distancia === null || e.distancia >= 999 ? "–" : `${e.distancia.toFixed(1)} cm`; // 999 = sin eco
  $("contador").textContent = e.contador;

  if (!e.esp32_conectada) {
    conexion("ESP32 sin señal", "mal");
    sinDatos("La ESP32 no está reportando");
  } else if (!e.sensor_ok) {
    conexion("Falla del sensor", "mal");
  } else {
    conexion("En línea", "ok");
  }

  // Los eventos los arma el backend con texto fijo, así que no hay HTML de usuarios aquí
  $("historial").innerHTML = e.historial
    .map((f) => `<tr class="${f.alerta ? "alerta" : ""}"><td>${f.hora}</td><td>${f.origen}</td><td>${f.evento}</td></tr>`)
    .join("");
  $("vacio").hidden = e.historial.length > 0;
}

botones.forEach((b) =>
  b.addEventListener("click", async () => {
    await fetch(`${API}/api/modo`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ modo: b.dataset.modo }),
    }).catch(() => {});
    cargarEstado();
  })
);

cargarEstado();
setInterval(cargarEstado, 1000); // refresco automático
