// Pont MQTT : l'API s'abonne au broker Mosquitto et range les messages dans la base.
const mqtt = require("mqtt");
const store = require("./store");
const { mapMeasurement, mapAlert } = require("./mqttMap");

const TOPIC_MEASURES = process.env.MQTT_TOPIC_MEASURES || "sentinelx/capteurs";
const TOPIC_ALERTS = process.env.MQTT_TOPIC_ALERTS || "sentinelx/alertes/#";
const ALERT_PREFIX = TOPIC_ALERTS.replace(/#$/, ""); // "sentinelx/alertes/"
const DEFAULT_DEVICE_ID = process.env.DEFAULT_DEVICE_ID || "ESP001";

const state = { connected: false, received: 0, rejected: 0, lastMessageAt: null };
let client = null;

function status() {
  return { connected: state.connected, received: state.received, rejected: state.rejected, lastMessageAt: state.lastMessageAt };
}

async function handleMessage(topic, payload) {
  if (payload.length > 10000) {
    state.rejected++;
    return console.log(`MQTT rejeté (${topic}) : message trop gros`);
  }
  let raw;
  try {
    raw = JSON.parse(payload.toString());
  } catch (e) {
    state.rejected++;
    return console.log(`MQTT rejeté (${topic}) : JSON invalide`);
  }

  try {
    if (topic === TOPIC_MEASURES) {
      const check = mapMeasurement(raw, DEFAULT_DEVICE_ID);
      if (!check.ok) {
        state.rejected++;
        return console.log(`MQTT rejeté (${topic}) :`, check.errors.join(" ; "));
      }
      await store.insertMeasurement(check.value);
    } else if (topic.startsWith(ALERT_PREFIX)) {
      const check = mapAlert(raw, topic.slice(ALERT_PREFIX.length));
      if (!check.ok) {
        state.rejected++;
        return console.log(`MQTT rejeté (${topic}) :`, check.errors.join(" ; "));
      }
      const alert = await store.insertAlert(check.value);
      console.log(`ALERTE ${alert.level} [${alert.source}] ${alert.message}`);
    } else {
      return; // topic qui ne nous concerne pas
    }
    state.received++;
    state.lastMessageAt = new Date().toISOString();
  } catch (err) {
    console.error("Erreur d'enregistrement MQTT :", err.message);
  }
}

function start() {
  const url = process.env.MQTT_URL;
  if (!url || url === "off") {
    return console.log("MQTT désactivé (MQTT_URL vide ou « off »).");
  }
  const options = { reconnectPeriod: 3000, connectTimeout: 5000 };
  if (process.env.MQTT_USER) {
    options.username = process.env.MQTT_USER;
    options.password = process.env.MQTT_PASSWORD || "";
  }

  client = mqtt.connect(url, options);
  client.on("connect", () => {
    state.connected = true;
    console.log("Connecté au broker MQTT :", url);
    client.subscribe([TOPIC_MEASURES, TOPIC_ALERTS], (err) => {
      if (err) console.log("Abonnement MQTT impossible :", err.message);
      else console.log("Abonné à :", TOPIC_MEASURES, "et", TOPIC_ALERTS);
    });
  });
  client.on("close", () => { state.connected = false; });
  client.on("error", (e) => console.log("MQTT :", e.message));
  client.on("message", (topic, payload) => { handleMessage(topic, payload); });
}

function stop() {
  return new Promise((resolve) => (client ? client.end(false, {}, resolve) : resolve()));
}

module.exports = { start, stop, status };
