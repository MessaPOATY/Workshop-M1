"""
ETAPE 2 - Donnees capteurs (temperature + gaz) : simuler, VOIR, detecter.

Ce script fait 4 choses :
  1. Simule des mesures realistes (1 mesure/seconde) : 2 h de "normal" + 1 h avec anomalies injectees
  2. Calcule des "features" (moyenne, variabilite, vitesse de variation...)
  3. Entraine un Isolation Forest UNIQUEMENT sur le normal
  4. Trace un graphique : tu VOIS les donnees et les anomalies detectees

Installation :
    pip install numpy pandas scikit-learn matplotlib joblib

Lancement :
    py etape2_donnees_capteurs.py

Sorties :
    donnees_capteurs.csv   -> les donnees (a ouvrir dans Excel si tu veux)
    resultat_anomalies.png -> le graphique
    modele_capteurs.joblib -> le modele (utilise a l'etape 3 par le service MQTT)
"""
import joblib
import matplotlib
matplotlib.use("Agg")           # pas besoin de fenetre : on sauvegarde en PNG
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

rng = np.random.default_rng(42)

# ------------------------------ Parametres --------------------------------
DUREE_NORMAL_S = 2 * 3600       # 2 h de donnees normales (entrainement)
DUREE_TEST_S = 1 * 3600         # 1 h de test avec anomalies
PERSISTANCE = 5                 # nb de mesures anormales consecutives avant alerte
CONTAMINATION = 0.01            # part d'anomalies "attendue" dans l'entrainement
FENETRE_FIGE = 60               # secondes sans aucune variation = capteur fige
# --------------------------------------------------------------------------


# ===================== 1) SIMULATION DES DONNEES ===========================
def simuler(n, t0=0):
    """Mesures 'normales' : temperature (C) et gaz (valeur analogique ESP8266, 0-1023)."""
    t = np.arange(t0, t0 + n)
    # Temperature : ~23 C, lente oscillation (climatisation / ouverture de porte) + petit bruit
    temp = 23 + 0.8 * np.sin(2 * np.pi * t / 1800) + rng.normal(0, 0.08, n)
    # Gaz (ex. MQ-2) : niveau de base ~180 avec petite derive + bruit
    gaz = 180 + 6 * np.sin(2 * np.pi * t / 2400) + rng.normal(0, 3.0, n)
    return temp, gaz


def injecter_anomalies(temp, gaz):
    """Injecte des anomalies connues et retourne leur etiquette (0 = normal, 1 = anomalie)."""
    n = len(temp)
    label = np.zeros(n, dtype=int)

    def marquer(a, b):
        label[a:b] = 1

    # (a) Pic de gaz rapide : briquet pres du capteur (60 s)
    a = 600
    gaz[a:a + 60] += np.concatenate([np.linspace(0, 260, 20), np.full(30, 260), np.linspace(260, 0, 10)])
    marquer(a, a + 60)

    # (b) Source de chaleur : la temperature monte vite de +6 C (120 s)
    a = 1500
    temp[a:a + 120] += np.concatenate([np.linspace(0, 6, 60), np.linspace(6, 0, 60)])
    marquer(a, a + 120)

    # (c) Fuite lente de gaz : derive progressive sur 5 min (cas "predictif")
    a = 2300
    gaz[a:a + 300] += np.linspace(0, 140, 300)
    marquer(a + 30, a + 300)           # toute la derive

    # (d) Capteur bloque : valeur figee (plus de bruit du tout) pendant 90 s
    a = 3000
    temp[a:a + 90] = temp[a]
    marquer(a, a + 90)

    return temp, gaz, label


# ======================= 2) FEATURES (le "cerveau") ========================
def features(df):
    """Transforme les mesures brutes en indicateurs qui decrivent le COMPORTEMENT."""
    f = pd.DataFrame(index=df.index)
    for col in ["temp", "gaz"]:
        s = df[col]
        f[f"{col}_val"] = s
        f[f"{col}_moy30"] = s.rolling(30, min_periods=1).mean()        # niveau recent
        f[f"{col}_std30"] = s.rolling(30, min_periods=2).std().fillna(0)  # variabilite recente
        f[f"{col}_std10"] = s.rolling(10, min_periods=2).std().fillna(0)  # variabilite tres recente (capteur fige)
        f[f"{col}_vitesse"] = s.diff(10).fillna(0)                     # vitesse de variation (10 s)
        f[f"{col}_ecart"] = s - s.rolling(300, min_periods=1).mean()   # ecart a la normale (5 min)
    return f


def alertes_persistantes(pred_anormal, k):
    """Alerte seulement si k mesures anormales d'affilee (evite les faux positifs)."""
    a = pd.Series(pred_anormal.astype(int))
    return (a.rolling(k).sum() >= k).fillna(False).to_numpy()


# ============================== PROGRAMME ==================================
def main():
    # --- donnees ---
    n1, n2 = DUREE_NORMAL_S, DUREE_TEST_S
    temp1, gaz1 = simuler(n1, 0)
    temp2, gaz2 = simuler(n2, n1)
    temp2, gaz2, label2 = injecter_anomalies(temp2, gaz2)

    train = pd.DataFrame({"temp": temp1, "gaz": gaz1})
    test = pd.DataFrame({"temp": temp2, "gaz": gaz2, "anomalie_reelle": label2})
    pd.concat([train.assign(anomalie_reelle=0), test], ignore_index=True).to_csv(
        "donnees_capteurs.csv", index_label="seconde")

    # --- entrainement sur le NORMAL uniquement ---
    Xtr = features(train)
    modele = IsolationForest(n_estimators=200, contamination=CONTAMINATION, random_state=42)
    modele.fit(Xtr)
    # on garde aussi la moyenne/ecart-type du normal : le service de l'etape 3 s'en sert
    # pour dire QUEL capteur (gaz ou temperature) est a l'origine de l'alerte
    joblib.dump({"modele": modele, "colonnes": list(Xtr.columns),
                 "ref_moy": Xtr.mean().to_dict(), "ref_std": Xtr.std().to_dict()},
                "modele_capteurs.joblib")

    # --- detection sur le test ---
    Xte = features(test)
    pred = modele.predict(Xte) == -1                 # True = anormal
    score = -modele.decision_function(Xte)           # plus haut = plus anormal
    alerte_ia = alertes_persistantes(pred, PERSISTANCE)

    # Regle complementaire "capteur fige" : l'Isolation Forest voit mal une valeur qui ne bouge plus
    # (elle reste dans la plage normale). Une regle simple la couvre : aucune variation pendant 60 s.
    # ATTENTION avec un vrai capteur peu precis (ex. DHT11 : 1 C de resolution) : allonger la fenetre.
    def immobile(serie):
        w = serie.rolling(FENETRE_FIGE)
        return (w.max() - w.min()) < 1e-6          # max - min = 0 -> la valeur n'a pas bouge
    fige = (immobile(test["temp"]) | immobile(test["gaz"])).fillna(False).to_numpy()
    alerte = alerte_ia | fige

    # --- metriques simples (au niveau de chaque anomalie) ---
    reel = test["anomalie_reelle"].to_numpy().astype(bool)
    segments, debut = [], None
    for i, v in enumerate(reel):
        if v and debut is None:
            debut = i
        if (not v) and debut is not None:
            segments.append((debut, i)); debut = None
    detectees = 0
    print("\n=== Resultats par anomalie ===")
    noms = ["Pic de gaz (briquet)", "Source de chaleur", "Fuite lente de gaz", "Capteur bloque"]
    for nom, (a, b) in zip(noms, segments):
        idx = np.where(alerte[a:b])[0]
        if len(idx):
            detectees += 1
            print(f"  [OK]   {nom:24s} detectee apres {idx[0]} s")
        else:
            print(f"  [RATE] {nom:24s} NON detectee")
    proche = np.convolve(reel.astype(int), np.ones(121, dtype=int), mode="same") > 0   # +-60 s
    fausses = alerte & ~proche
    print(f"\nAnomalies detectees : {detectees}/{len(segments)}")
    print(f"Fausses alertes : {int(fausses.sum())} mesures sur {int((~proche).sum())} mesures normales "
          f"({100 * fausses.sum() / (~proche).sum():.1f} %)")

    # --- graphique ---
    fig, ax = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
    t = np.arange(len(test)) / 60                       # minutes

    def zones(axe):
        for a, b in segments:
            axe.axvspan(a / 60, b / 60, color="orange", alpha=0.25, label="anomalie injectee")
        # evite les doublons de legende
        h, l = axe.get_legend_handles_labels()
        uniq = dict(zip(l, h))
        axe.legend(uniq.values(), uniq.keys(), loc="upper left")

    ax[0].plot(t, test["temp"], color="tab:red", lw=1)
    ax[0].set_ylabel("Temperature (C)")
    ax[0].set_title("Ce que le capteur envoie (donnees brutes)")
    zones(ax[0])

    ax[1].plot(t, test["gaz"], color="tab:green", lw=1)
    ax[1].set_ylabel("Gaz (0-1023)")
    zones(ax[1])

    ax[2].plot(t, score, color="tab:blue", lw=1, label="score d'anomalie")
    ax[2].fill_between(t, 0, score.max(), where=alerte, color="red", alpha=0.35, label="ALERTE declenchee")
    ax[2].set_ylabel("Score du modele")
    ax[2].set_xlabel("Temps (minutes)")
    ax[2].set_title("Ce que le modele en deduit")
    ax[2].legend(loc="upper left")

    plt.tight_layout()
    plt.savefig("resultat_anomalies.png", dpi=110)
    print("\nFichiers crees : donnees_capteurs.csv, resultat_anomalies.png, modele_capteurs.joblib")


if __name__ == "__main__":
    main()