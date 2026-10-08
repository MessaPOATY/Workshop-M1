"""
mqtt_alert.py - envoi des alertes d'intrusion (module vision) vers le broker MQTT.

Meme interface qu'avant : connect_mqtt(), publish_intrusion(...), disconnect_mqtt().
Changements : message au format COMMUN a toute l'equipe, reglages par variables d'environnement,
attente reelle de la connexion, reconnexion automatique, et le flux video ne plante jamais si MQTT est coupe.

Reglages (variables d'environnement, tous facultatifs) :
    MQTT_BROKER        adresse du broker          (defaut : localhost)
    MQTT_PORT          port                       (defaut : 1883)
    MQTT_USER / MQTT_PASSWORD   identifiants      (jamais ecrits dans le code)
    MQTT_TOPIC_ALERTES topic des alertes vision   (defaut : sentinelx/alertes/vision)
"""
import json
import os
import threading
from datetime import datetime

import paho.mqtt.client as mqtt          # necessite paho-mqtt >= 2.0

# ============================================================
# CONFIGURATION MQTT
# ============================================================
MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")

# Topic des alertes vision. A valider avec l'equipe (le dashboard s'abonne a "sentinelx/alertes/#").
MQTT_TOPIC_INTRUSION = os.environ.get("MQTT_TOPIC_ALERTES", "sentinelx/alertes/vision")

MQTT_CLIENT_ID = "sentinel-ai-vision"
DEVICE_ID = "sentinel-x-vision"

_connecte = threading.Event()            # allume tant que la connexion au broker est active


# ============================================================
# CALLBACKS
# ============================================================
def on_connect(client, userdata, flags, reason_code, properties=None):
    if not reason_code.is_failure:
        _connecte.set()
        print("[MQTT] Connexion au broker reussie")
    else:
        print(f"[MQTT] Echec de connexion - code : {reason_code}")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    _connecte.clear()
    if reason_code.is_failure:                      # coupure subie (pas une deconnexion voulue)
        print(f"[MQTT] Connexion perdue ({reason_code}) - reconnexion automatique...")


# ============================================================
# CREATION DU CLIENT MQTT
# ============================================================
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID)
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.reconnect_delay_set(min_delay=1, max_delay=15)
if MQTT_USER:
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
# TODO Cyber : activer TLS -> client.tls_set(ca_certs="ca.crt") et utiliser le port 8883


# ============================================================
# CONNEXION AU BROKER
# ============================================================
def connect_mqtt(timeout=3.0):
    """Lance la connexion. Renvoie True si connecte dans le delai.
    Meme si le broker est absent, la tentative continue en arriere-plan : la detection video ne s'arrete jamais."""
    print(f"[MQTT] Connexion a {MQTT_BROKER}:{MQTT_PORT}...")
    try:
        client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_start()
    except Exception as e:
        print(f"[MQTT] Erreur de connexion : {e}")
        return False

    if _connecte.wait(timeout):
        return True
    print("[MQTT] Broker injoignable pour l'instant : les alertes seront envoyees des que possible.")
    return False


# ============================================================
# ENVOYER UNE ALERTE D'INTRUSION
# ============================================================
def publish_intrusion(image_path, confidence, camera="webcam", bbox=None):
    """Publie une alerte au FORMAT COMMUN (le meme que le module capteurs) :
    {ts, device_id, source, type, score, details}"""
    message = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "device_id": DEVICE_ID,
        "source": "vision",
        "type": "intrusion",
        "score": round(float(confidence), 3),
        "details": {
            "camera": camera,
            "snapshot": image_path,
            "bbox": [int(v) for v in bbox] if bbox is not None else None,
        },
    }
    payload = json.dumps(message, ensure_ascii=False)

    try:
        result = client.publish(MQTT_TOPIC_INTRUSION, payload, qos=1)   # ne bloque pas la video
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            etat = "envoyee" if _connecte.is_set() else "en attente (broker injoignable)"
            print(f"[MQTT] Alerte intrusion {etat} -> {MQTT_TOPIC_INTRUSION}")
            return True
        if result.rc == mqtt.MQTT_ERR_NO_CONN:
            print("[MQTT] Broker injoignable : alerte NON envoyee (elle reste dans le terminal et le dossier alerts/)")
        else:
            print(f"[MQTT] Erreur publication : {result.rc}")
    except Exception as e:
        print(f"[MQTT] Erreur lors de la publication : {e}")
    return False


# ============================================================
# FERMER MQTT
# ============================================================
def disconnect_mqtt():
    try:
        client.loop_stop()
        client.disconnect()
        print("[MQTT] Deconnexion")
    except Exception as e:
        print(f"[MQTT] Erreur deconnexion : {e}")