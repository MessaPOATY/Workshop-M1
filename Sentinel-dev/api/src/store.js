// Lecture / écriture des mesures et alertes. Utilisé par les routes HTTP ET par le pont MQTT.
const pool = require("./db");

const measurementToApi = (r) => ({
  id: Number(r.id),
  deviceId: r.device_id,
  temperature: Number(r.temperature),
  gaz: Number(r.gaz),
  presence: r.presence === null ? null : r.presence,
  simulated: r.simulated,
  createdAt: r.created_at,
});

const alertToApi = (r) => ({
  id: Number(r.id),
  measurementId: r.measurement_id === null ? null : Number(r.measurement_id),
  deviceId: r.device_id,
  source: r.source,
  level: r.level,
  message: r.message,
  type: r.type || null,
  score: r.score === null || r.score === undefined ? null : Number(r.score),
  details: r.details || null,
  snapshot: r.snapshot || null,
  simulated: r.simulated,
  createdAt: r.created_at,
});

async function insertMeasurement(m) {
  const res = await pool.query(
    `INSERT INTO measurements (device_id, temperature, gaz, presence, simulated)
     VALUES ($1, $2, $3, $4, $5)
     RETURNING *`,
    [m.deviceId, m.temperature, m.gaz, m.presence, m.simulated]
  );
  return measurementToApi(res.rows[0]);
}

async function insertAlert(a) {
  const res = await pool.query(
    `INSERT INTO alerts (measurement_id, device_id, source, level, message, type, score, details, snapshot, simulated)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10)
     RETURNING *`,
    [a.measurementId, a.deviceId, a.source, a.level, a.message, a.type, a.score,
     a.details ? JSON.stringify(a.details) : null, a.snapshot, a.simulated]
  );
  return alertToApi(res.rows[0]);
}

module.exports = { measurementToApi, alertToApi, insertMeasurement, insertAlert };
