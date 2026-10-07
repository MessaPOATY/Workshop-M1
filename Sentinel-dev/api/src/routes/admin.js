const express = require("express");
const pool = require("../db");
const { requireApiKey } = require("../auth");

// DELETE /api/simulated : supprime les FAUSSES données (simulated = true)
const simulated = express.Router();
simulated.delete("/", requireApiKey, async (req, res) => {
  try {
    const alerts = await pool.query("DELETE FROM alerts WHERE simulated = TRUE");
    const measurements = await pool.query("DELETE FROM measurements WHERE simulated = TRUE");
    res.json({ deletedAlerts: alerts.rowCount, deletedMeasurements: measurements.rowCount });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erreur lors du nettoyage" });
  }
});

// DELETE /api/data : supprime TOUT (à utiliser avant la démo)
const all = express.Router();
all.delete("/", requireApiKey, async (req, res) => {
  try {
    const alerts = await pool.query("DELETE FROM alerts");
    const measurements = await pool.query("DELETE FROM measurements");
    res.json({ deletedAlerts: alerts.rowCount, deletedMeasurements: measurements.rowCount });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erreur lors de la suppression" });
  }
});

module.exports = { simulated, all };
