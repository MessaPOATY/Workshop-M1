// Connexion à PostgreSQL (les paramètres viennent de compose.yaml)
const { Pool } = require("pg");

const pool = new Pool({
  host: process.env.DB_HOST || "localhost",
  port: Number(process.env.DB_PORT) || 5432,
  database: process.env.DB_NAME,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  max: 10,
});

pool.on("error", (err) => {
  console.error("Erreur inattendue PostgreSQL :", err.message);
});

module.exports = pool;
