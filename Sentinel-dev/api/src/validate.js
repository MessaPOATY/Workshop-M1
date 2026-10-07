// Vérifie ce que l'ESP / l'IA envoient, avant d'écrire dans la base.
// Renvoie { ok: true, value } ou { ok: false, errors: [...] }.

const SOURCES = ["esp", "vision", "anomalie", "manuel"];
const LEVELS = ["info", "warning", "critical"];

const isObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const isNumber = (v) => typeof v === "number" && Number.isFinite(v);

// accepte true/false ET 1/0 (pratique depuis l'ESP en C++)
function toBool(v) {
  if (typeof v === "boolean") return v;
  if (v === 1) return true;
  if (v === 0) return false;
  return null;
}

function optionalText(body, key, max, errors) {
  const v = body[key];
  if (v === undefined || v === null) return null;
  if (typeof v !== "string" || v.trim() === "" || v.length > max) {
    errors.push(`${key} doit être un texte de 1 à ${max} caractères`);
    return null;
  }
  return v.trim();
}

function optionalSimulated(body, errors) {
  if (body.simulated === undefined || body.simulated === null) return false;
  const b = toBool(body.simulated);
  if (b === null) errors.push("simulated doit être true ou false");
  return b === true;
}

function validateMeasurement(body) {
  const errors = [];
  if (!isObject(body)) return { ok: false, errors: ["Le corps doit être un objet JSON"] };

  const deviceId = optionalText(body, "deviceId", 100, errors);
  if (deviceId === null && !errors.length) errors.push("deviceId est obligatoire (texte)");

  if (!isNumber(body.temperature) || body.temperature < -50 || body.temperature > 150) {
    errors.push("temperature est obligatoire : nombre entre -50 et 150");
  }
  if (!isNumber(body.gaz) || body.gaz < 0 || body.gaz > 100000) {
    errors.push("gaz est obligatoire : nombre entre 0 et 100000");
  }

  // presence est OPTIONNELLE (l'ESP8266 n'a pas forcément de capteur PIR)
  let presence = null;
  if (body.presence !== undefined && body.presence !== null) {
    presence = toBool(body.presence);
    if (presence === null) errors.push("presence doit être true/false (ou 1/0), ou absente");
  }

  const simulated = optionalSimulated(body, errors);

  if (errors.length) return { ok: false, errors };
  return {
    ok: true,
    value: { deviceId, temperature: body.temperature, gaz: body.gaz, presence, simulated },
  };
}

function validateAlert(body) {
  const errors = [];
  if (!isObject(body)) return { ok: false, errors: ["Le corps doit être un objet JSON"] };

  if (!LEVELS.includes(body.level)) {
    errors.push(`level est obligatoire : ${LEVELS.join(" | ")}`);
  }
  if (typeof body.message !== "string" || body.message.trim() === "" || body.message.length > 500) {
    errors.push("message est obligatoire : texte de 1 à 500 caractères");
  }

  let source = "manuel";
  if (body.source !== undefined && body.source !== null) {
    if (!SOURCES.includes(body.source)) errors.push(`source doit être : ${SOURCES.join(" | ")}`);
    else source = body.source;
  }

  let measurementId = null;
  if (body.measurementId !== undefined && body.measurementId !== null) {
    if (!Number.isInteger(body.measurementId) || body.measurementId < 1) {
      errors.push("measurementId doit être un entier positif");
    } else measurementId = body.measurementId;
  }

  const deviceId = optionalText(body, "deviceId", 100, errors);
  const type = optionalText(body, "type", 50, errors);
  const snapshot = optionalText(body, "snapshot", 255, errors);

  let score = null;
  if (body.score !== undefined && body.score !== null) {
    if (!isNumber(body.score) || Math.abs(body.score) > 1000) errors.push("score doit être un nombre");
    else score = body.score;
  }

  let details = null;
  if (body.details !== undefined && body.details !== null) {
    if (!isObject(body.details) || JSON.stringify(body.details).length > 5000) {
      errors.push("details doit être un objet JSON (5000 caractères max)");
    } else details = body.details;
  }

  const simulated = optionalSimulated(body, errors);

  if (errors.length) return { ok: false, errors };
  return {
    ok: true,
    value: {
      level: body.level,
      message: body.message.trim(),
      source, measurementId, deviceId, type, score, details, snapshot, simulated,
    },
  };
}

module.exports = { validateMeasurement, validateAlert, SOURCES, LEVELS };
