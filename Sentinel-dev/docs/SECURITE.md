# Sentinel-X – notes pour l'équipe Cyber


## Déjà en place
- Écritures HTTP (POST/DELETE) protégées par une clé API (`x-api-key`), comparaison à temps constant.
- Validation stricte de tout ce qui entre, par HTTP **et** par MQTT (types, bornes, tailles) ; un message invalide est rejeté et journalisé.
- Requêtes SQL paramétrées (pas d'injection SQL).
- Le dashboard affiche les textes avec `textContent` (pas d'injection de HTML) ; les images ne sont servies que depuis `/snapshots/` par leur nom de fichier encodé.
- Conteneur de l'API sans droits root.
- En-têtes de sécurité nginx (CSP, nosniff, X-Frame-Options, Referrer-Policy), version de nginx masquée.
- Journal : `docker compose logs -f api` (écritures HTTP, erreurs, messages MQTT rejetés, alertes reçues) et `docker compose logs -f mosquitto`.

## Faiblesses connues (à traiter)
1. **MQTT sans authentification** : dans `mosquitto/config/mosquitto.conf`, remplacer `allow_anonymous true` par un `password_file` (créé avec `mosquitto_passwd`) et un `acl_file` (chaque appareil ne publie que sur son topic). Ensuite renseigner `MQTT_USER` et `MQTT_PASSWORD` dans `.env` : l'API s'en sert déjà pour se connecter. Les modules IA attendent les mêmes variables.
2. **Pas de chiffrement** : activer TLS sur le broker (port 8883, certificats générés avec OpenSSL) et HTTPS dans `dashboard/nginx.conf`. Côté ESP8266, TLS passe par BearSSL, coûteux en mémoire : à tester tôt.
3. **Clé API unique et partagée** pour le chemin HTTP. Piste : une clé par appareil.
4. **Pas de limitation de débit** : on peut saturer l'API ou le broker. Pistes : `limit_req` dans nginx, `max_connections` et limites de taille dans Mosquitto.
5. **Lecture ouverte** : n'importe qui sur le réseau peut lire les mesures (GET). Piste : authentification du dashboard.
6. **Mots de passe de développement** dans `.env` : à changer avant la démo, ne jamais les publier sur Git.
7. **Pare-feu** : n'autoriser que 8080 et 1883 (et SSH depuis l'admin) sur le PC serveur ; durcir l'OS.
8. **Wi-Fi** : WPA2/WPA3, mot de passe fort, réseau dédié au projet.

## Comment travailler dessus
- Récupérer le projet par Git (une branche `cyber`).
- Lancer la stack comme dans `README.md`, et le simulateur : `docker compose exec api node scripts/simulator-mqtt.js`.
- Preuves : Nmap sur le serveur (ports 1883 et 8080), Wireshark (messages MQTT lisibles en clair, puis illisibles après TLS), publication sur `sentinelx/capteurs` sans identifiants (doit être refusée après durcissement), POST HTTP sans clé (doit renvoyer 401).
- Pendant le pentest croisé : `docker compose logs -f api mosquitto`.
