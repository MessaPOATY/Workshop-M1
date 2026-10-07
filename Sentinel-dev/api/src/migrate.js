// Applique schema.sql au démarrage : crée les tables si besoin, ajoute les colonnes manquantes.
const fs = require("fs");
const path = require("path");
const pool = require("./db");

async function migrate() {
  const sql = fs.readFileSync(path.join(__dirname, "schema.sql"), "utf8");
  await pool.query(sql);
  console.log("Base de données prête (schéma à jour).");
}

module.exports = { migrate };
