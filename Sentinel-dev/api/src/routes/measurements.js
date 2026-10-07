const express = require("express");
const pool = require("../db");
const store = require("../store");
const { requireApiKey } = require("../auth");
const { validateMeasurement } = require("../validate");

const router = express.Router();

function parseLimit(value, def, max) {
  const n = parseInt(value, 10);
  if (!Number.isFinite(n) || n < 1) return def;
  return Math.min(n, max);
}

// GET /api/measurements?limit=100&deviceId=ESP001   (les plus récentes d'abord)
router.get("/", async (req, res) => {
  try {
    const limit = parseLimit(req.query.limit, 100, 500);
    const deviceId = typeof req.query.deviceId === "string" ? req.query.deviceId : null;
    const result = await pool.query(
      `SELECT * FROM measurements
       WHERE ($1::text IS NULL OR device_id = $1)
       ORDER BY created_at DESC, id DESC
       LIMIT $2`,
      [deviceId, limit]
    );
    res.json(result.rows.map(store.measurementToApi));
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erreur lors de la lecture des mesures" });
  }
});

// GET /api/measurements/latest
router.get("/latest", async (req, res) => {
  try {
    const result = await pool.query(
      "SELECT * FROM measurements ORDER BY created_at DESC, id DESC LIMIT 1"
    );
    if (result.rows.length === 0) return res.status(404).json({ error: "Aucune mesure" });
    res.json(store.measurementToApi(result.rows[0]));
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erreur lors de la lecture de la mesure" });
  }
});

// POST /api/measurements   (chemin HTTP, en plus de MQTT)
router.post("/", requireApiKey, async (req, res) => {
  const check = validateMeasurement(req.body);
  if (!check.ok) return res.status(400).json({ error: "Données invalides", details: check.errors });
  try {
    res.status(201).json({ measurement: await store.insertMeasurement(check.value) });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erreur lors de l'enregistrement de la mesure" });
  }
});

module.exports = router;
