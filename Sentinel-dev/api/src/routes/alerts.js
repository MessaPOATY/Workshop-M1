const express = require("express");
const pool = require("../db");
const store = require("../store");
const { requireApiKey } = require("../auth");
const { validateAlert } = require("../validate");

const router = express.Router();

// GET /api/alerts?limit=50   (les plus récentes d'abord)
router.get("/", async (req, res) => {
  try {
    const n = parseInt(req.query.limit, 10);
    const limit = Number.isFinite(n) && n >= 1 ? Math.min(n, 200) : 50;
    const result = await pool.query(
      "SELECT * FROM alerts ORDER BY created_at DESC, id DESC LIMIT $1",
      [limit]
    );
    res.json(result.rows.map(store.alertToApi));
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erreur lors de la lecture des alertes" });
  }
});

// POST /api/alerts   (chemin HTTP, en plus de MQTT)
router.post("/", requireApiKey, async (req, res) => {
  const check = validateAlert(req.body);
  if (!check.ok) return res.status(400).json({ error: "Données invalides", details: check.errors });
  try {
    res.status(201).json({ alert: await store.insertAlert(check.value) });
  } catch (err) {
    if (err.code === "23503") {
      return res.status(400).json({ error: "measurementId inconnu (cette mesure n'existe pas)" });
    }
    console.error(err);
    res.status(500).json({ error: "Erreur lors de l'enregistrement de l'alerte" });
  }
});

module.exports = router;
