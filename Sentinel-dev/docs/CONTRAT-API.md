# Contrat d'échange Sentinel-X (ESP8266, IA, Dev)

Deux chemins mènent à la base. **MQTT est le chemin principal** (celui prévu par la filière IA) ;
HTTP reste disponible en secours ou pour tester avec Postman.

- **Broker MQTT** : `IP_DU_SERVEUR`, port `1883` (TLS 8883 et authentification : à activer par la Cyber).
- **Dashboard et API HTTP** : `http://IP_DU_SERVEUR:8080`

## 1. MQTT (principal)

| Topic | Qui publie | Contenu |
|---|---|---|
| `sentinelx/capteurs` | ESP8266 (IoT) | Mesures, une par seconde |
| `sentinelx/alertes/vision` | ai-vision (IA) | Alerte d'intrusion |
| `sentinelx/alertes/sensors` | ai-sensors (IA) | Alerte d'anomalie capteur |

L'API est abonnée à `sentinelx/capteurs` et `sentinelx/alertes/#`, et range tout dans la base. Le dashboard l'affiche.

### Mesure ESP8266
```json
{"temp": 23.4, "gaz": 181}
```
- `temp` (ou `temperature`) : nombre entre -50 et 150. `gaz` : nombre entre 0 et 100000.
- `presence` : **optionnel** (`true`/`false` ou `1`/`0`), à ajouter si le capteur PIR est branché.
- `device_id` : optionnel. Sans lui, la mesure est rattachée à l'appareil `ESP001`.

### Alerte vision
```json
{"ts": "2026-10-06T10:00:39", "device_id": "sentinel-x-vision", "source": "vision", "type": "intrusion",
 "score": 0.918, "details": {"camera": "webcam", "snapshot": "alerts/intrusion_20261006_100039.jpg", "bbox": [57, 27, 633, 479]}}
```

### Alerte capteurs
```json
{"ts": "2026-10-06T10:28:48", "device_id": "sentinel-x-sensors", "source": "sensors", "type": "anomalie_temp",
 "score": 0.098, "details": {"capteur": "temp", "temp": 23.97, "gaz": 181.3}}
```

### Ce que fait l'API de ces alertes (hypothèses à confirmer avec l'IA)

| Champ reçu | Devient |
|---|---|
| `source: "sensors"` | `anomalie` (`vision` reste `vision`) |
| `type`, `score`, `details` | conservés tels quels et affichés |
| `ts` | conservé dans `details.ts` ; l'heure affichée est celle de la réception |
| `details.snapshot` | nom de la capture à afficher (voir ci-dessous) |
| pas de `level` | `critical` si le type contient « intrusion », sinon `warning` (un `level` explicite est respecté) |
| pas de `message` | texte généré, par exemple « Intrusion détectée (score 0.918) » |

Un message invalide (JSON cassé, champ manquant) est **rejeté et signalé dans le journal de l'API**, sans rien casser.

### Captures d'image
Le dashboard affiche la capture si le fichier est dans le dossier `snapshots/` du projet (seul le nom du fichier compte, par exemple `intrusion_20261006_100039.jpg`). L'IA doit donc y copier ses images (ou partager/synchroniser un dossier). Sans le fichier, le dashboard indique « fichier absent ».

## 2. HTTP (secours / tests)

Écritures : en-tête `x-api-key: <clé>` obligatoire. Lectures : libres.

| Action | Route |
|---|---|
| Envoyer une mesure | `POST /api/measurements` |
| Lire les mesures (récentes d'abord) | `GET /api/measurements?limit=100&deviceId=ESP001` |
| Dernière mesure | `GET /api/measurements/latest` |
| Envoyer une alerte | `POST /api/alerts` |
| Lire les alertes | `GET /api/alerts?limit=50` |
| Santé (API, base, MQTT) | `GET /api/health` |
| Supprimer les fausses données / tout | `DELETE /api/simulated` / `DELETE /api/data` |

**Mesure** : `{"deviceId": "ESP001", "temperature": 24.5, "gaz": 310, "presence": false}` (`presence` optionnelle)

**Alerte** : `level` (`info`/`warning`/`critical`) et `message` obligatoires ; optionnels : `source` (`esp`, `vision`, `anomalie`, `manuel`), `deviceId`, `type`, `score`, `details`, `snapshot`, `measurementId`.

Erreurs : `400` données invalides (la réponse liste les champs), `401` clé absente ou fausse, `413` message trop gros (10 Ko), `500` erreur serveur.

## 3. Lire les données (IA, par exemple)
```python
import requests
mesures = requests.get("http://192.168.50.10:8080/api/measurements", params={"limit": 50}).json()
```

## 4. Exemple ESP8266 (MQTT, librairie PubSubClient)
```cpp
#include <ESP8266WiFi.h>
#include <PubSubClient.h>

const char* WIFI_SSID = "NOM_DU_WIFI";
const char* WIFI_PASS = "MOT_DE_PASSE";
const char* BROKER    = "192.168.50.10";   // IP du serveur

WiFiClient wifi;
PubSubClient mqtt(wifi);

void connecterMqtt() {
  while (!mqtt.connected()) {
    if (!mqtt.connect("esp8266-sentinel")) delay(2000);   
    mot de passe quand la Cyber les aura activés
  }
}

void publierMesure(float temp, int gaz) {
  connecterMqtt();
  String json = "{\"temp\":" + String(temp, 1) + ",\"gaz\":" + String(gaz) + "}";
  mqtt.publish("sentinelx/capteurs", json.c_str());
}

void setup() {
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) delay(500);
  mqtt.setServer(BROKER, 1883);
}

void loop() {
  mqtt.loop();
  publierMesure(23.4, 181);   
  delay(1000);
}
```
