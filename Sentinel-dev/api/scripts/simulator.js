// Simulateur de FAUSSES données : joue le rôle de l'ESP8266 et de l'IA.
// Tout est marqué simulated:true, donc effaçable avec scripts/clean.js.
//
// Usage (depuis le dossier du projet) :
//   docker compose exec api node scripts/simulator.js            -> en continu (Ctrl+C pour arrêter)
//   docker compose exec api node scripts/simulator.js 30 200     -> 30 mesures, une toutes les 200 ms

const API_URL = process.env.API_URL || "http://127.0.0.1:3000";
const API_KEY = process.env.API_KEY || "";
const count = parseInt(process.argv[2], 10) || Infinity;
const interval = parseInt(process.argv[3], 10) || 2000;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function post(path, body) {
  try {
    const res = await fetch(API_URL + path, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(API_KEY ? { "x-api-key": API_KEY } : {}) },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      console.log("Erreur", res.status, JSON.stringify(data));
      return null;
    }
    return data;
  } catch (e) {
    console.log("API injoignable :", e.message);
    return null;
  }
}

async function main() {
  console.log(`Simulateur -> ${API_URL} (Ctrl+C pour arrêter)`);
  for (let i = 1; i <= count; i++) {
    const anomalie = i % 25 === 0;
    const intrus = i % 17 === 0;

    const mesure = {
      deviceId: "ESP001",
      temperature: anomalie ? 43 + Math.random() * 3 : +(24 + Math.sin(i / 5) * 2 + Math.random()).toFixed(1),
      gaz: anomalie ? Math.round(430 + Math.random() * 60) : Math.round(300 + Math.random() * 40),
      presence: intrus || Math.random() < 0.05,
      simulated: true,
    };
    const res = await post("/api/measurements", mesure);
    if (res) console.log(`#${res.measurement.id}`, mesure.temperature, "°C", "gaz", mesure.gaz);

    if (res && anomalie) {
      await post("/api/alerts", {
        measurementId: res.measurement.id,
        deviceId: "ESP001",
        source: "anomalie",
        level: "critical",
        message: "Température et gaz anormaux (simulation)",
        simulated: true,
      });
      console.log("  -> alerte ANOMALIE");
    }
    if (res && intrus) {
      await post("/api/alerts", {
        measurementId: res.measurement.id,
        deviceId: "ESP001",
        source: "vision",
        level: "warning",
        message: "Personne détectée par la caméra (simulation)",
        simulated: true,
      });
      console.log("  -> alerte VISION");
    }
    await sleep(interval);
  }
  console.log("Terminé.");
}

main();
