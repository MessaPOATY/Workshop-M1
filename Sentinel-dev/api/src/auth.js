// Protection des routes qui ÉCRIVENT des données (POST / DELETE).
// L'appelant (ESP, IA...) doit envoyer l'en-tête :  x-api-key: <API_KEY>
// Les routes qui LISENT (GET) restent ouvertes : le dashboard en a besoin.
const crypto = require("crypto");

function requireApiKey(req, res, next) {
  const expected = process.env.API_KEY;
  if (!expected) return next(); // pas de clé configurée = pas de protection (déconseillé)

  const provided = Buffer.from(req.get("x-api-key") || "");
  const wanted = Buffer.from(expected);

  if (provided.length === wanted.length && crypto.timingSafeEqual(provided, wanted)) {
    return next();
  }
  return res
    .status(401)
    .json({ error: "Clé API manquante ou invalide (en-tête x-api-key)" });
}

module.exports = { requireApiKey };
