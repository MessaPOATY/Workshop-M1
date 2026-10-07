# Sentinel-X – stack serveur (broker MQTT + API + base de données + dashboard)

```
ESP8266 ──MQTT──►┐
ai-sensors ─MQTT─┤──► Mosquitto (1883) ──► API Node.js ──► PostgreSQL
ai-vision ──MQTT─┘                              │
                                                └──► nginx (8080) ──► Dashboard (page web)
(l'API accepte aussi les envois HTTP : POST /api/measurements et /api/alerts)
```

Deux ports sont ouverts sur le réseau : **1883** (MQTT) et **8080** (dashboard + API HTTP).


```
sentinel-x/
├── compose.yaml            lance les 4 services
├── .env                    mots de passe, clé API (NE PAS mettre sur Git)
├── mosquitto/config/       réglages du broker MQTT
├── api/                    API Node.js : pont MQTT, routes HTTP, base, scripts de test
├── dashboard/              page web + nginx
├── snapshots/              captures d'image de l'IA (copier les fichiers ici)
└── docs/
    ├── CONTRAT-API.md      pour l'ESP et l'IA : topics, formats, exemples
    └── SECURITE.md         
```

Les tables de la base sont créées et mises à jour automatiquement au démarrage de l'API.

## Prérequis
Docker Desktop (Windows : WSL 2).

## Lancer
Dans le dossier `Sentinel-dev` :

```
docker compose up -d --build
docker compose ps
```
Les services doivent être « running » (l'API et la base : « healthy »). Ouvrir http://localhost:8080

## Mettre à jour une version déjà installée
Remplacer les fichiers du projet (garder `.env`), puis `docker compose up -d --build`.
La base existante est conservée et mise à niveau toute seule.

## Tester sans l'ESP ni l'IA

Simulateur MQTT : envoie des messages dans les formats exacts de l'ESP8266 et de l'IA (mesures, alertes vision avec capture, alertes capteurs).
```
docker compose exec api node scripts/simulator-mqtt.js
```
(Ctrl+C pour arrêter.) Pour un historique rapide : `docker compose exec api node scripts/simulator-mqtt.js 60 100`

Voir ce qui passe sur le broker :
```
docker compose exec mosquitto mosquitto_sub -t "sentinelx/#" -v
```

Envoyer une mesure à la main par MQTT :
```
docker compose exec mosquitto mosquitto_pub -t sentinelx/capteurs -m '{"temp": 24.1, "gaz": 190}'
```

Chemin HTTP (PowerShell), toujours possible :
```
Invoke-RestMethod -Uri "http://localhost:8080/api/measurements" -Method POST `
  -ContentType "application/json" `
  -Headers @{ "x-api-key" = "sentinel-dev-key-change-me" } `
  -Body '{"deviceId":"ESP001","temperature":31.5,"gaz":150,"presence":true}'
```

## Brancher les vrais modules
- **IA** : lancer leurs scripts avec `--broker <IP_DU_SERVEUR>` (le port par défaut est 1883). Exemple : `py etape3_service_capteurs.py --source mqtt --broker 192.168.50.10`
- **Captures d'image** : copier les fichiers de l'IA dans `snapshots/` (voir `snapshots/LISEZMOI.txt`).
- **ESP8266** : publier `{"temp": 23.4, "gaz": 181}` sur `sentinelx/capteurs`, une fois par seconde.
- Détail des formats : `docs/CONTRAT-API.md`.

## Nettoyer
```
docker compose exec api node scripts/clean.js          (fausses données seulement)
docker compose exec api node scripts/clean.js --all    (tout, avant la démo)
```

## Commandes utiles

| Besoin | Commande |
|---|---|
| Journal de l'API (alertes reçues, messages rejetés) | `docker compose logs -f api` |
| Journal du broker | `docker compose logs -f mosquitto` |
| Santé de l'API et du pont MQTT | ouvrir `http://localhost:8080/api/health` |
| Arrêter (données conservées) | `docker compose down` |
| Tout effacer (base comprise) | `docker compose down -v` |
| Reconstruire après modification | `docker compose up -d --build` |
| Regarder dans la base | `docker compose exec database psql -U sentinel_user -d sentinel` |

## Si ça bloque
- « Cannot connect to the Docker daemon » : Docker Desktop n'est pas lancé.
- Port déjà utilisé ou refusé par Windows (message « forbidden by its access permissions ») : changer `DASHBOARD_PORT` ou `MQTT_PORT` dans `.env`. Pour voir les ports réservés : `netsh interface ipv4 show excludedportrange protocol=tcp`.
- `/api/health` indique `"mqtt": {"connected": false}` : le broker n'a pas démarré, voir `docker compose logs mosquitto`.
- Des messages MQTT n'apparaissent pas : `docker compose logs api` affiche « MQTT rejeté » avec la raison (champ manquant, JSON invalide...).
- Une machine du réseau n'atteint pas le serveur : utiliser l'IP du serveur et autoriser les ports 8080 et 1883 dans le pare-feu Windows.
- Code 401 en HTTP : l'en-tête `x-api-key` est absent ou différent de `API_KEY`.

## Sur le vrai PC serveur
Copier ce dossier, **changer les mots de passe et la clé dans `.env`**, lancer `docker compose up -d --build`, réserver une IP fixe, ouvrir les ports 8080 et 1883 dans le pare-feu. `restart: unless-stopped` relance les services après un redémarrage (Docker Desktop doit démarrer avec Windows).
