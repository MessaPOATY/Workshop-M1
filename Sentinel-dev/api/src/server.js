const express = require("express");
const pool = require("./db");
const { migrate } = require("./migrate");
const mqttBridge = require("./mqtt");

const app = express();
const PORT = Number(process.env.PORT) || 3000;

app.disable("x-powered-by");

// Journal : on garde une trace des écritures et des erreurs (utile à l'équipe Cyber)
app.use((req, res, next) => {
  const start = Date.now();
  res.on("finish", () => {
    if (req.method !== "GET" || res.statusCode >= 400) {
      const ip = req.get("x-real-ip") || req.ip;
      console.log(
        `${new Date().toISOString()} ${ip} ${req.method} ${req.originalUrl} -> ${res.statusCode} (${Date.now() - start} ms)`
      );
    }
  });
  next();
});

app.use(express.json({ limit: "10kb" }));

// Santé : vérifie que l'API ET la base répondent (l'état MQTT est donné à titre d'information)
app.get("/api/health", async (req, res) => {
  try {
    await pool.query("SELECT 1");
    res.json({ status: "ok", service: "Sentinel-X API", database: "ok", mqtt: mqttBridge.status() });
  } catch (err) {
    res.status(503).json({ status: "error", service: "Sentinel-X API", database: "injoignable" });
  }
});

const admin = require("./routes/admin");
app.use("/api/measurements", require("./routes/measurements"));
app.use("/api/alerts", require("./routes/alerts"));
app.use("/api/simulated", admin.simulated);
app.use("/api/data", admin.all);

app.use((req, res) => res.status(404).json({ error: "Route inconnue" }));

app.use((err, req, res, next) => {
  if (err.type === "entity.parse.failed") return res.status(400).json({ error: "JSON invalide" });
  if (err.type === "entity.too.large") return res.status(413).json({ error: "Message trop gros" });
  console.error(err);
  res.status(500).json({ error: "Erreur interne" });
});

if (!process.env.API_KEY) {
  console.warn("ATTENTION : API_KEY non définie, les écritures HTTP ne sont pas protégées.");
}

async function main() {
  await migrate();
  const server = app.listen(PORT, "0.0.0.0", () => {
    console.log(`Sentinel-X API démarrée sur le port ${PORT}`);
  });
  mqttBridge.start();

  // Arrêt propre (docker compose down / restart)
  const shutdown = async () => {
    await mqttBridge.stop();
    server.close(() => pool.end().then(() => process.exit(0)));
  };
  process.on("SIGTERM", shutdown);
  process.on("SIGINT", shutdown);
}

main().catch((err) => {
  console.error("Démarrage impossible :", err.message);
  process.exit(1);
});
