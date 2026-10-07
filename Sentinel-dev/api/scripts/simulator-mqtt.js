// Simulateur MQTT : joue le rôle de l'ESP8266 ET de l'IA, avec EXACTEMENT leurs formats.
// Permet de tester tout le circuit (broker -> API -> base -> dashboard) sans eux.
// Tout est marqué "simulated": true, donc effaçable avec scripts/clean.js.
//
// Usage :
//   docker compose exec api node scripts/simulator-mqtt.js            -> en continu (Ctrl+C pour arrêter)
//   docker compose exec api node scripts/simulator-mqtt.js 60 200     -> 60 mesures, une toutes les 200 ms

const mqtt = require("mqtt");

const url = process.env.MQTT_URL && process.env.MQTT_URL !== "off" ? process.env.MQTT_URL : "mqtt://localhost:1883";
const count = parseInt(process.argv[2], 10) || Infinity;
const interval = parseInt(process.argv[3], 10) || 1000;

const options = {};
if (process.env.MQTT_USER) {
  options.username = process.env.MQTT_USER;
  options.password = process.env.MQTT_PASSWORD || "";
}

const client = mqtt.connect(url, options);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const publish = (topic, obj) =>
  new Promise((resolve) => client.publish(topic, JSON.stringify(obj), () => resolve()));
const ts = () => new Date().toISOString().slice(0, 19);

client.on("error", (e) => console.log("MQTT :", e.message));

client.on("connect", async () => {
  console.log(`Simulateur MQTT connecté à ${url} (Ctrl+C pour arrêter)`);
  for (let i = 1; i <= count; i++) {
    const anomalie = i % 45 === 0;

    // Mesure de l'ESP8266 : {"temp": 23.4, "gaz": 181}
    const temp = anomalie ? +(43 + Math.random() * 3).toFixed(1) : +(23 + Math.sin(i / 6) * 1.5 + Math.random() * 0.5).toFixed(1);
    const gaz = anomalie ? Math.round(430 + Math.random() * 60) : Math.round(175 + Math.random() * 15);
    await publish("sentinelx/capteurs", { temp, gaz, simulated: true });
    console.log(`#${i} temp ${temp} gaz ${gaz}`);

    // Alerte vision (format IA)
    if (i % 20 === 0) {
      await publish("sentinelx/alertes/vision", {
        ts: ts(), device_id: "sentinel-x-vision", source: "vision", type: "intrusion", score: 0.918,
        details: { camera: "webcam", snapshot: "alerts/intrusion_demo.jpg", bbox: [57, 27, 633, 479] },
        simulated: true,
      });
      console.log("  -> alerte VISION");
    }
    // Alerte capteurs (format IA)
    if (anomalie || i % 30 === 0) {
      await publish("sentinelx/alertes/sensors", {
        ts: ts(), device_id: "sentinel-x-sensors", source: "sensors", type: anomalie ? "anomalie_gaz" : "anomalie_temp",
        score: anomalie ? 0.021 : 0.098, details: { capteur: anomalie ? "gaz" : "temp", temp, gaz },
        simulated: true,
      });
      console.log("  -> alerte CAPTEURS");
    }
    await sleep(interval);
  }
  client.end();
  console.log("Terminé.");
});
