// Dashboard Sentinel-X : demande les données à l'API chaque seconde et les affiche.
// Il ne sait pas d'où viennent les données (ESP, IA, simulateur) : il lit seulement l'API.
// Aucune bibliothèque externe : ça marche aussi sans Internet (démo en réseau isolé).

const API_URL = "/api"; // nginx transmet laroute à l'API
const REFRESH_MS = 1000;
const STALE_MS = 15000; // plus ,on considère qu'iln'y a plus de données fraîches

const $ = (id) => document.getElementById(id);
let derniereSerie = { labels: [], temps: [], gaz: [] };
let signatureAlertes = "";

async function getJson(chemin) {
  const reponse = await fetch(API_URL + chemin, { cache: "no-store" });
  if (!reponse.ok) throw new Error("HTTP " + reponse.status);
  return reponse.json();
}

function depuis(date) {
  const s = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (s < 60) return s + " s";
  if (s < 3600) return Math.round(s / 60) + " min";
  return Math.round(s / 3600) + " h";
}

function heure(date) {
  return date.toLocaleTimeString("fr-FR");
}

function statut(classe, texte) {
  const el = $("statut");
  el.className = "statut " + classe;
  el.textContent = texte;
}

// ---------- affichage ----------

function afficherMesures(mesures) {
  if (mesures.length === 0) {
    statut("warn", "API connectée – aucune mesure reçue pour l'instant");
    $("simu").classList.add("hidden");
    derniereSerie = { labels: [], temps: [], gaz: [] };
    dessinerTout();
    return;
  }

  const derniere = mesures[0]; // les plus récentes d'abord
  const date = new Date(derniere.createdAt);

  $("temp").textContent = derniere.temperature;
  $("gaz").textContent = derniere.gaz;
  $("presence").textContent =
    derniere.presence === null ? "--" : derniere.presence ? "Détectée" : "Aucune";
  $("appareil").textContent = derniere.deviceId;
  $("maj").textContent = "Dernière mesure : " + heure(date);
  $("simu").classList.toggle("hidden", !derniere.simulated);

  if (Date.now() - date.getTime() > STALE_MS) {
    statut("warn", "Pas de nouvelle donnée depuis " + depuis(date));
  } else {
    statut("ok", "En ligne – dernière mesure il y a " + depuis(date));
  }

  const serie = mesures.slice().reverse(); // du plus ancien au plus récent
  derniereSerie = {
    labels: serie.map((m) => heure(new Date(m.createdAt))),
    temps: serie.map((m) => m.temperature),
    gaz: serie.map((m) => m.gaz),
  };
  dessinerTout();
}

// Capture d'image d'une alerte : on n'utilise que le nom du fichier dans snapshots
function creerVignette(chemin) {
  const nom = String(chemin).split(/[\\/]/).pop();
  const url = "/snapshots/" + encodeURIComponent(nom);

  const conteneur = document.createElement("div");
  conteneur.className = "vignette";

  const lien = document.createElement("a");
  lien.href = url;
  lien.target = "_blank";
  lien.rel = "noopener";

  const img = document.createElement("img");
  img.src = url;
  img.alt = "Capture : " + nom;
  img.addEventListener("error", () => {
    const absente = document.createElement("span");
    absente.className = "absente";
    absente.textContent = "Capture « " + nom + " » : fichier absent du dossier snapshots";
    lien.replaceWith(absente);
  });

  lien.appendChild(img);
  conteneur.appendChild(lien);
  return conteneur;
}

function afficherAlertes(alertes) {
  // On ne reconstruit la liste que si elle a changé comme ca les images ne sont pas chargé chaque seconde
  const signature = alertes.map((a) => a.id).join(",");
  if (signature === signatureAlertes) return;
  signatureAlertes = signature;

  const liste = $("alertes");
  liste.textContent = "";

  if (alertes.length === 0) {
    const li = document.createElement("li");
    li.className = "vide";
    li.textContent = "Aucune alerte";
    liste.appendChild(li);
    return;
  }

  for (const a of alertes) {
    const li = document.createElement("li");

    const badge = document.createElement("span");
    badge.className = "badge " + a.level;
    badge.textContent = a.level.toUpperCase();

    const message = document.createElement("span");
    message.textContent = a.message; 

    const source = document.createElement("span");
    source.className = "source";
    source.textContent =
      "(" + a.source + (a.score !== null ? " · score " + a.score.toFixed(2) : "") + ")";

    const h = document.createElement("span");
    h.className = "heure";
    h.textContent = heure(new Date(a.createdAt));

    li.append(badge, message, source, h);
    if (a.snapshot) li.appendChild(creerVignette(a.snapshot));
    liste.appendChild(li);
  }
}

// ---------- graphiques (dessinés à la main, sans bibliothèque) ----------

function dessinerGraphique(canvas, labels, valeurs, couleur) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  canvas.width = w * dpr;
  canvas.height = h * dpr;

  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);
  ctx.font = "12px Arial, sans-serif";
  ctx.fillStyle = "#261E48";

  if (valeurs.length < 2) {
    ctx.textAlign = "center";
    ctx.fillText("En attente de données...", w / 2, h / 2);
    return;
  }

  const gauche = 48, droite = 12, haut = 12, bas = 26;
  let min = Math.min(...valeurs);
  let max = Math.max(...valeurs);
  if (max - min < 1) { min -= 1; max += 1; }
  const marge = (max - min) * 0.1;
  min -= marge;
  max += marge;

  const largeur = w - gauche - droite;
  const hauteur = h - haut - bas;
  const x = (i) => gauche + (i * largeur) / (valeurs.length - 1);
  const y = (v) => haut + hauteur - ((v - min) / (max - min)) * hauteur;
  const decimales = max - min > 20 ? 0 : 1;

  ctx.strokeStyle = "#E4E6F3";
  ctx.textAlign = "right";
  for (let k = 0; k <= 4; k++) {
    const v = min + ((max - min) * k) / 4;
    ctx.beginPath();
    ctx.moveTo(gauche, y(v));
    ctx.lineTo(w - droite, y(v));
    ctx.stroke();
    ctx.fillText(v.toFixed(decimales), gauche - 6, y(v) + 4);
  }

  ctx.strokeStyle = couleur;
  ctx.lineWidth = 2;
  ctx.beginPath();
  valeurs.forEach((v, i) => (i === 0 ? ctx.moveTo(x(i), y(v)) : ctx.lineTo(x(i), y(v))));
  ctx.stroke();

  ctx.fillStyle = couleur;
  ctx.beginPath();
  ctx.arc(x(valeurs.length - 1), y(valeurs[valeurs.length - 1]), 4, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = "#261E48";
  ctx.textAlign = "left";
  ctx.fillText(labels[0], gauche, h - 6);
  ctx.textAlign = "right";
  ctx.fillText(labels[labels.length - 1], w - droite, h - 6);
}

function dessinerTout() {
  dessinerGraphique($("graph-temp"), derniereSerie.labels, derniereSerie.temps, "#261E48");
  dessinerGraphique($("graph-gaz"), derniereSerie.labels, derniereSerie.gaz, "#d84315");
}


let enCours = false;
async function actualiser() {
  if (enCours) return; // ne pas empiler les requêtes si l'API est lente
  enCours = true;
  try {
    const [mesures, alertes] = await Promise.all([
      getJson("/measurements?limit=120"),
      getJson("/alerts?limit=20"),
    ]);
    afficherMesures(mesures);
    afficherAlertes(alertes);
  } catch (e) {
    console.error(e);
    statut("error", "API injoignable");
  } finally {
    enCours = false;
  }
}

window.addEventListener("resize", dessinerTout);
actualiser();
setInterval(actualiser, REFRESH_MS);
