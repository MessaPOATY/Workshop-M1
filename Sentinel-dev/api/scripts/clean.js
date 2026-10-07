// Supprime les FAUSSES données (simulated = true) :   docker compose exec api node scripts/clean.js
// Supprime TOUT (avant la démo) :                      docker compose exec api node scripts/clean.js --all
const API_URL = process.env.API_URL || "http://127.0.0.1:3000";
const API_KEY = process.env.API_KEY || "";
const tout = process.argv.includes("--all");

fetch(API_URL + (tout ? "/api/data" : "/api/simulated"), {
  method: "DELETE",
  headers: API_KEY ? { "x-api-key": API_KEY } : {},
})
  .then((r) => r.json())
  .then((d) => console.log(tout ? "Tout a été supprimé :" : "Fausses données supprimées :", d))
  .catch((e) => console.log("Erreur :", e.message));
