"""
ETAPE 3 - Service IA capteurs (futur conteneur "ai-sensors")

Lit des mesures {temp, gaz} en continu, applique le modele de l'etape 2 et emet des alertes JSON.

DEUX SOURCES DE MESURES
  --source sim   (defaut) : mesures simulees en direct, AUCUN broker necessaire -> pour tester seul
  --source mqtt           : vraies mesures de l'ESP8266 recues par MQTT

SORTIES : les alertes sont imprimees dans le terminal, et publiees en MQTT si --broker est donne.

EXEMPLES
  py etape3_service_capteurs.py                                  # simulation, tu declenches avec le clavier
  py etape3_service_capteurs.py --auto                           # simulation avec anomalies programmees
  py etape3_service_capteurs.py --source mqtt --broker 192.168.1.10
  py etape3_service_capteurs.py --source mqtt --broker 192.168.1.10 --topic-mesures sentinelx/capteurs

TOUCHES (mode sim, Windows) : g = pic de gaz | t = chaleur | l = fuite lente | f = capteur fige | q = quitter

Installation : pip install paho-mqtt numpy pandas scikit-learn joblib
Prerequis    : avoir lance l'etape 2 (fichier modele_capteurs.joblib dans le meme dossier)
"""
import argparse
import json
import os
import sys
import time
from collections import deque
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

# On reutilise EXACTEMENT les memes indicateurs que pendant l'entrainement (sinon le modele se trompe).
from etape2_donnees_capteurs import features

# ------------------------------ Parametres --------------------------------
DEVICE_ID = "sentinel-x-sensors"
TAMPON = 300            # nb de mesures gardees en memoire (= fenetre la plus longue des indicateurs)
ECHAUFFEMENT = 60       # on n'alerte pas avant d'avoir 60 mesures (le temps de "voir" le normal)
PERSISTANCE = 5         # nb de mesures anormales d'affilee avant alerte (anti faux positifs)
FENETRE_FIGE = 60       # nb de mesures sans aucune variation = capteur fige
REPETE_APRES = 10       # tant que l'anomalie dure, on renvoie l'alerte toutes les 10 mesures
TOPIC_MESURES = "sentinelx/capteurs"
TOPIC_ALERTES = "sentinelx/alertes/sensors"
# --------------------------------------------------------------------------


class DetecteurCapteurs:
    """Recoit une mesure a la fois, renvoie une alerte (dict) ou None."""

    def __init__(self, chemin_modele="modele_capteurs.joblib"):
        if not os.path.exists(chemin_modele):
            raise SystemExit(f"Modele introuvable : {chemin_modele}\n-> lance d'abord : py etape2_donnees_capteurs.py")
        d = joblib.load(chemin_modele)
        self.modele = d["modele"]
        self.colonnes = d["colonnes"]
        self.ref_moy = d["ref_moy"]
        self.ref_std = d["ref_std"]
        self.tampon = deque(maxlen=TAMPON)
        self.n = 0                     # nb total de mesures recues
        self.consecutives = 0          # mesures anormales d'affilee
        self.en_alerte = False
        self.dernier_envoi = -10**9

    def _capteur_responsable(self, ligne):
        """Quel capteur s'ecarte le plus du normal MAINTENANT ?
        On compare seulement l'etat actuel (valeur + vitesse). Les indicateurs a memoire longue
        (moyenne sur 5 min, ecart-type sur 30 s) restent deformes apres la fin d'un pic et
        feraient accuser a tort le capteur qui vient de s'arreter d'etre anormal."""
        z = {}
        for capteur in ("temp", "gaz"):
            cols = [f"{capteur}_val", f"{capteur}_vitesse"]
            z[capteur] = max(abs(ligne[c] - self.ref_moy[c]) / (self.ref_std[c] + 1e-9) for c in cols)
        return max(z, key=z.get), z

    def traiter(self, temp, gaz):
        self.n += 1
        self.tampon.append((float(temp), float(gaz)))
        if self.n < ECHAUFFEMENT:
            return None

        df = pd.DataFrame(list(self.tampon), columns=["temp", "gaz"])
        X = features(df)[self.colonnes].iloc[[-1]]
        anormal = self.modele.predict(X)[0] == -1
        score = float(-self.modele.decision_function(X)[0])

        self.consecutives = self.consecutives + 1 if anormal else 0
        alerte_ia = self.consecutives >= PERSISTANCE

        # regle "capteur fige" (l'Isolation Forest voit mal une valeur qui ne bouge plus)
        fige = None
        if len(df) >= FENETRE_FIGE:
            for capteur in ("temp", "gaz"):
                fin = df[capteur].iloc[-FENETRE_FIGE:]
                if (fin.max() - fin.min()) < 1e-6:
                    fige = capteur

        if not (alerte_ia or fige):
            self.en_alerte = False
            return None

        # alerte : on l'envoie au debut, puis on la repete de temps en temps si elle continue
        if self.en_alerte and (self.n - self.dernier_envoi) < REPETE_APRES:
            return None
        self.en_alerte = True
        self.dernier_envoi = self.n

        if fige:
            type_alerte, capteur, z = "capteur_fige", fige, {}
        else:
            capteur, z = self._capteur_responsable(X.iloc[0])
            type_alerte = "anomalie_temp" if capteur == "temp" else "anomalie_gaz"

        return {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "device_id": DEVICE_ID,
            "source": "sensors",
            "type": type_alerte,
            "score": round(score, 3),
            "details": {"capteur": capteur, "temp": round(float(temp), 2), "gaz": round(float(gaz), 1)},
        }


# ============================ SOURCE SIMULEE ================================
class FluxSimule:
    """Genere des mesures en direct, avec la possibilite de declencher des anomalies."""

    def __init__(self, seed=7):
        self.rng = np.random.default_rng(seed)
        self.t = 0
        self.effets = []          # (type, debut, duree, valeur_figee)

    def declencher(self, kind):
        valeur = None
        duree = {"gaz": 60, "temp": 120, "fuite": 300, "fige": 90}[kind]
        self.effets.append([kind, self.t, duree, valeur])
        print(f"  >>> anomalie declenchee : {kind}")

    def suivant(self):
        t = self.t
        temp = 23 + 0.8 * np.sin(2 * np.pi * t / 1800) + self.rng.normal(0, 0.08)
        gaz = 180 + 6 * np.sin(2 * np.pi * t / 2400) + self.rng.normal(0, 3.0)
        for e in list(self.effets):
            kind, debut, duree, fige = e
            k = t - debut
            if k >= duree:
                self.effets.remove(e)
                continue
            if kind == "gaz":
                gaz += np.interp(k, [0, 20, 50, 60], [0, 260, 260, 0])
            elif kind == "temp":
                temp += np.interp(k, [0, 60, 120], [0, 6, 0])
            elif kind == "fuite":
                gaz += 140 * k / duree
            elif kind == "fige":
                if e[3] is None:
                    e[3] = temp
                temp = e[3]
        self.t += 1
        return temp, gaz


def touche_pressee():
    """Lecture clavier sans bloquer (Windows uniquement). Renvoie None sinon."""
    try:
        import msvcrt
        if msvcrt.kbhit():
            return msvcrt.getwch().lower()
    except ImportError:
        pass
    return None


# ================================ MQTT ======================================
def client_mqtt(broker, port, user, mdp):
    import paho.mqtt.client as mqtt
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)   # paho-mqtt >= 2.0
    except AttributeError:
        client = mqtt.Client()                                   # paho-mqtt 1.x
    if user:
        client.username_pw_set(user, mdp)
    # TODO Cyber : activer TLS ici -> client.tls_set(ca_certs="ca.crt") et utiliser le port 8883
    client.connect(broker, port, keepalive=60)
    return client


def publier(client, topic, alerte):
    if client is not None:
        client.publish(topic, json.dumps(alerte, ensure_ascii=False), qos=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["sim", "mqtt"], default="sim")
    ap.add_argument("--broker", default=None, help="adresse du broker MQTT (ex. 192.168.1.10)")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--user", default=os.environ.get("MQTT_USER"))
    ap.add_argument("--mdp", default=os.environ.get("MQTT_PASSWORD"))   # jamais de mot de passe dans le code
    ap.add_argument("--topic-mesures", default=TOPIC_MESURES)
    ap.add_argument("--topic-alertes", default=TOPIC_ALERTES)
    ap.add_argument("--auto", action="store_true", help="sim : anomalies programmees (sans clavier)")
    ap.add_argument("--dt", type=float, default=1.0, help="sim : secondes entre deux mesures (0.05 = rapide)")
    ap.add_argument("--duree", type=int, default=0, help="sim : s'arreter apres N mesures (0 = sans fin)")
    args = ap.parse_args()

    detecteur = DetecteurCapteurs()
    client = client_mqtt(args.broker, args.port, args.user, args.mdp) if args.broker else None

    def sur_mesure(temp, gaz):
        alerte = detecteur.traiter(temp, gaz)
        if alerte:
            print(json.dumps(alerte, ensure_ascii=False))
            publier(client, args.topic_alertes, alerte)

    # ---------------- Source : MQTT (vraies mesures) ----------------
    if args.source == "mqtt":
        if client is None:
            raise SystemExit("--source mqtt demande --broker <adresse>")

        def on_message(cl, userdata, msg):
            try:
                m = json.loads(msg.payload)
                sur_mesure(float(m["temp"]), float(m["gaz"]))
            except (ValueError, KeyError, TypeError):
                print(f"Message ignore (format invalide) : {msg.payload[:80]!r}")   # ne jamais planter

        client.on_message = on_message
        client.subscribe(args.topic_mesures, qos=1)
        print(f"Ecoute de '{args.topic_mesures}' sur {args.broker}... (Ctrl+C pour arreter)")
        client.loop_forever()
        return

    # ---------------- Source : simulation ----------------
    flux = FluxSimule()
    programme = {100: "gaz", 250: "temp", 400: "fuite", 800: "fige"}   # mode --auto
    touches = {"g": "gaz", "t": "temp", "l": "fuite", "f": "fige"}
    print("Simulation en cours. Touches : g=pic de gaz  t=chaleur  l=fuite lente  f=capteur fige  q=quitter")
    if client:
        client.loop_start()
    n = 0
    try:
        while args.duree == 0 or n < args.duree:
            if args.auto and n in programme:
                flux.declencher(programme[n])
            k = touche_pressee()
            if k == "q":
                break
            if k in touches:
                flux.declencher(touches[k])
            temp, gaz = flux.suivant()
            sur_mesure(temp, gaz)
            n += 1
            time.sleep(args.dt)
    except KeyboardInterrupt:
        pass
    if client:
        client.loop_stop()
    print("Arret.")


if __name__ == "__main__":
    main()
