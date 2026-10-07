// Traduit les messages MQTT (formats IA / ESP8266) vers le format de l'API,
// puis les fait passer par la même validation que les requêtes HTTP.
//
// Messages attendus (d'après le compte rendu IA) :
//   ESP8266  sentinelx/capteurs          {"temp": 23.4, "gaz": 181}
//   Vision   sentinelx/alertes/vision    {"ts","device_id","source":"vision","type":"intrusion","score":0.918,
//                                         "details":{"camera","snapshot":"alerts/xxx.jpg","bbox":[...]}}
//   Capteurs sentinelx/alertes/sensors   {"ts","device_id","source":"sensors","type":"anomalie_temp","score":0.098,
//                                         "details":{"capteur":"temp","temp":23.97,"gaz":181.3}}

const { validateMeasurement, validateAlert } = require("./validate");

const isObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);

function mapMeasurement(raw, defaultDeviceId) {
  if (!isObject(raw)) return { ok: false, errors: ["Le message doit être un objet JSON"] };
  return validateMeasurement({
    deviceId: raw.deviceId ?? raw.device_id ?? defaultDeviceId,
    temperature: raw.temperature ?? raw.temp, // l'ESP8266 envoie "temp"
    gaz: raw.gaz,
    presence: raw.presence, // optionnelle
    simulated: raw.simulated,
  });
}

// "sensors" (IA) devient "anomalie" (API)
function normalizeSource(source, topicSuffix) {
  const s = String(source || topicSuffix || "").toLowerCase();
  if (s === "vision") return "vision";
  if (["sensors", "sensor", "capteurs", "anomalie"].includes(s)) return "anomalie";
  if (s === "esp") return "esp";
  return "manuel";
}

// L'IA n'envoie pas de niveau : on le déduit du type (à confirmer avec l'IA)
function levelFor(type) {
  return /intrus/i.test(type || "") ? "critical" : "warning";
}

function buildMessage(type, score, details) {
  let base;
  if (/intrus/i.test(type)) base = "Intrusion détectée";
  else {
    const what = String(type || "").replace(/^anomalie_?/i, "").replace(/_/g, " ").trim();
    base = "Anomalie : " + (what || "capteur");
  }
  return typeof score === "number" ? `${base} (score ${score})` : base;
}

function mapAlert(raw, topicSuffix) {
  if (!isObject(raw)) return { ok: false, errors: ["Le message doit être un objet JSON"] };

  const type = typeof raw.type === "string" && raw.type.trim() ? raw.type.trim() : "inconnu";
  const score = typeof raw.score === "number" ? raw.score : null;

  // details : on garde tout, et on y ajoute l'heure d'origine ("ts") envoyée par l'IA
  let details = isObject(raw.details) ? { ...raw.details } : null;
  if (typeof raw.ts === "string") details = { ...(details || {}), ts: raw.ts };

  const snapshot =
    (typeof raw.snapshot === "string" && raw.snapshot) ||
    (details && typeof details.snapshot === "string" && details.snapshot) ||
    null;

  return validateAlert({
    level: ["info", "warning", "critical"].includes(raw.level) ? raw.level : levelFor(type),
    message: typeof raw.message === "string" && raw.message.trim() ? raw.message : buildMessage(type, score, details),
    source: normalizeSource(raw.source, topicSuffix),
    deviceId: raw.device_id ?? raw.deviceId ?? undefined,
    type,
    score,
    details,
    snapshot,
    simulated: raw.simulated,
  });
}

module.exports = { mapMeasurement, mapAlert, normalizeSource, levelFor, buildMessage };
