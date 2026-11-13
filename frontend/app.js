// El backend corre en el mismo host que sirve el frontend, puerto 8000
const API = `http://${window.location.hostname}:8000`;

const $ = (id) => document.getElementById(id);
const botones = document.querySelectorAll("[data-modo]");

async function cargarEstado() {
  try {
    const res = await fetch(`${API}/api/estado`);
    const e = await res.json();

    $("barrera").textContent = e.barrera;
    $("distancia").textContent =
      e.distancia === null ? "–" : e.distancia >= 999 ? "libre" : `${e.distancia.toFixed(1)} cm`; // 999 = sin eco
    $("contador").textContent = e.contador;
    botones.forEach((b) => b.classList.toggle("activo", b.dataset.modo === e.modo));

    // Si la ESP32 lleva más de 5 s sin reportar, se avisa en la página
    const conectada = e.ultima_lectura && Date.now() - new Date(e.ultima_lectura) < 5000;
    $("conexion").textContent = conectada ? "ESP32 conectada ✔" : "ESP32 sin conexión";
    $("conexion").style.color = conectada ? "" : "#b91c1c";

    $("historial").innerHTML = e.historial
      .map((p) => `<tr><td>${p.numero}</td><td>${p.hora}</td><td>${p.resultado}</td></tr>`)
      .join("");
  } catch (err) {
    $("conexion").textContent = "Error conectando al backend";
  }
}

botones.forEach((b) =>
  b.addEventListener("click", async () => {
    await fetch(`${API}/api/modo`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ modo: b.dataset.modo }),
    });
    cargarEstado();
  })
);

cargarEstado();
setInterval(cargarEstado, 1000); // refresco automático
