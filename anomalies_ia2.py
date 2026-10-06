"""
Sentinel-X — IA 2 : détection d'anomalies (température / gaz)
==============================================================

Ce script fait 4 choses :
  1. Il SIMULE des mesures « normales » (comme si l'ESP8266 tournait dans la salle).
  2. Il ENTRAÎNE un Isolation Forest sur ces données normales.
  3. Il TESTE le modèle sur de nouvelles données où on a caché 3 anomalies.
  4. Il COMPARE avec un simple seuil fixe, pour montrer que l'IA prévient plus tôt.

Lancer :  pip install scikit-learn pandas matplotlib joblib
          python anomalies_ia2.py

Quand les vrais capteurs marcheront (mardi), il suffira de remplacer
la fonction simuler_mesures() par la lecture des vraies données.
"""

import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use("Agg")  # pas besoin d'écran pour sauvegarder le graphique
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

rng = np.random.default_rng(42)

INTERVALLE_S = 2       # l'ESP envoie une mesure toutes les 2 secondes
FENETRE = 15           # nb de mesures utilisées pour calculer tendance et variation (30 s)
SEUIL_TEMP = 35.0      # seuil fixe « classique », pour comparer
SEUIL_GAZ = 600.0


# ---------------------------------------------------------------------------
# 1. Simulation des mesures
# ---------------------------------------------------------------------------
def simuler_mesures(n, avec_anomalies=False):
    """Fabrique n mesures. Température en °C, gaz = valeur brute du MQ-2 (0-1023)."""
    t = np.arange(n)
    temperature = 22 + 0.5 * np.sin(t / 400) + rng.normal(0, 0.15, n)
    humidite = 45 + 1.0 * np.sin(t / 600) + rng.normal(0, 0.5, n)
    gaz = 300 + rng.normal(0, 6, n)
    anomalie = np.zeros(n, dtype=bool)  # la « vérité », pour vérifier le modèle

    if avec_anomalies:
        # A) Surchauffe LENTE : +0,04 °C par mesure (≈ +1,2 °C par minute)
        a, b = 400, 900
        temperature[a:b] += np.linspace(0, 0.04 * (b - a), b - a)
        temperature[b:b + 150] += 0.04 * (b - a)
        anomalie[a:b + 150] = True

        # B) Fuite de gaz BRUTALE
        a, b = 1300, 1360
        gaz[a:b] += 450
        anomalie[a:b] = True

        # C) Fuite de gaz LENTE qui monte doucement
        a, b = 1700, 2100
        gaz[a:b] += np.linspace(0, 400, b - a)
        anomalie[a:b] = True

    return pd.DataFrame({
        "seconde": t * INTERVALLE_S,
        "temperature": temperature,
        "humidite": humidite,
        "gaz": gaz,
        "anomalie_reelle": anomalie,
    })


# ---------------------------------------------------------------------------
# 2. Les « features » : ce que le modèle regarde
# ---------------------------------------------------------------------------
def calculer_features(df):
    """
    On ne donne pas seulement la valeur, mais aussi :
      - la PENTE (est-ce que ça monte vite ?)
      - la VARIATION récente (est-ce que ça devient instable ?)
    C'est ce qui rend la détection « prédictive » : une montée anormale
    est repérée bien avant d'atteindre un seuil dangereux.
    """
    f = pd.DataFrame(index=df.index)
    for col in ["temperature", "gaz", "humidite"]:
        moyenne = df[col].rolling(FENETRE, min_periods=1).mean()
        f[f"{col}"] = df[col]
        f[f"{col}_pente"] = moyenne.diff(FENETRE).fillna(0)
        f[f"{col}_variation"] = df[col].rolling(FENETRE, min_periods=2).std().fillna(0)
    return f


# ---------------------------------------------------------------------------
# 3. Entraînement
# ---------------------------------------------------------------------------
def entrainer(df_normal):
    X = calculer_features(df_normal)
    scaler = StandardScaler().fit(X)
    modele = IsolationForest(
        n_estimators=200,
        contamination=0.005,  # on suppose ~0,5 % de bruit dans les données « normales »
        random_state=42,
    ).fit(scaler.transform(X))
    # On mémorise aussi la « zone normale » apprise de chaque capteur (moyenne, écart-type).
    # Ce n'est PAS un seuil fixe choisi à la main : il est appris sur VOS données.
    plage = {c: (df_normal[c].mean(), df_normal[c].std()) for c in ["temperature", "gaz"]}
    return {"modele": modele, "scaler": scaler, "plage": plage}


def detecter(ia, df):
    X = ia["scaler"].transform(calculer_features(df))
    # a) L'Isolation Forest repère les comportements bizarres (montée rapide, instabilité…)
    bizarre = ia["modele"].predict(X) == -1        # -1 = anomalie pour Isolation Forest
    # b) Hors de la zone apprise : la valeur est à plus de 6 écarts-types du normal
    #    (sert quand la valeur reste bloquée très haut : la courbe ne bouge plus,
    #    mais ce n'est pas normal pour autant)
    hors_zone = np.zeros(len(df), dtype=bool)
    for c, (moy, ecart) in ia["plage"].items():
        hors_zone |= (np.abs(df[c] - moy) / ecart).values > 6
    brut = pd.Series(bizarre | hors_zone)
    # Anti-fausse-alerte : il faut au moins 3 mesures anormales sur les 5 dernières…
    confirme = brut.rolling(5, min_periods=1).sum() >= 3
    # …et une fois déclenchée, l'alerte reste allumée 30 s (15 mesures) pour ne pas clignoter
    alerte = confirme.rolling(15, min_periods=1).max().astype(bool)
    score = -ia["modele"].score_samples(X)         # plus c'est haut, plus c'est bizarre
    return alerte.values, score


# ---------------------------------------------------------------------------
# 4. Programme principal
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("1) Simulation de 2 h de données normales…")
    normal = simuler_mesures(3600)

    print("2) Entraînement de l'Isolation Forest…")
    ia = entrainer(normal)
    joblib.dump(ia, "modele_anomalies.joblib")
    print("   Modèle sauvegardé dans modele_anomalies.joblib")

    print("3) Test sur des données avec 3 anomalies cachées…")
    test = simuler_mesures(2400, avec_anomalies=True)
    test["alerte_ia"], test["score"] = detecter(ia, test)
    test["alerte_seuil"] = (test["temperature"] > SEUIL_TEMP) | (test["gaz"] > SEUIL_GAZ)

    # Fausses alertes : alertes qui DÉMARRENT alors que tout est normal
    debut_alerte = test["alerte_ia"] & ~test["alerte_ia"].shift(1, fill_value=False)
    fausses = (debut_alerte & ~test["anomalie_reelle"]).sum()
    duree_min = len(test) * INTERVALLE_S / 60
    print(f"   Fausses alertes IA : {fausses} en {duree_min:.0f} minutes de test")

    print("\n4) Comparaison IA vs seuil fixe (quand l'alerte arrive) :")
    for nom, a, b in [("Surchauffe lente", 400, 1050),
                      ("Fuite de gaz brutale", 1300, 1360),
                      ("Fuite de gaz lente", 1700, 2100)]:
        zone = test.iloc[a:b]
        def premier(col):
            idx = zone.index[zone[col]]
            return (idx[0] - a) * INTERVALLE_S if len(idx) else None
        t_ia, t_seuil = premier("alerte_ia"), premier("alerte_seuil")
        txt_ia = f"{t_ia} s" if t_ia is not None else "jamais"
        txt_seuil = f"{t_seuil} s" if t_seuil is not None else "jamais"
        gain = f"  → l'IA prévient {t_seuil - t_ia} s plus tôt" if (t_ia is not None and t_seuil is not None and t_seuil > t_ia) else ""
        print(f"   {nom:22s} IA : {txt_ia:>7s} | seuil fixe : {txt_seuil:>7s}{gain}")

    # Graphique pour le rapport / la soutenance
    fig, ax = plt.subplots(3, 1, figsize=(11, 7), sharex=True)
    m = test["seconde"] / 60
    ax[0].plot(m, test["temperature"], lw=1, color="#3b5bdb")
    ax[0].axhline(SEUIL_TEMP, ls="--", color="grey", lw=1, label="seuil fixe")
    ax[0].set_ylabel("Température (°C)"); ax[0].legend(loc="upper left")
    ax[1].plot(m, test["gaz"], lw=1, color="#e8590c")
    ax[1].axhline(SEUIL_GAZ, ls="--", color="grey", lw=1)
    ax[1].set_ylabel("Gaz (MQ-2)")
    ax[2].plot(m, test["score"], lw=1, color="#5f3dc4")
    ax[2].set_ylabel("Score d'anomalie"); ax[2].set_xlabel("Temps (minutes)")
    for a in ax:
        a.fill_between(m, 0, 1, where=test["alerte_ia"], color="red", alpha=0.15,
                       transform=a.get_xaxis_transform(), label="alerte IA")
    ax[2].legend(loc="upper left")
    fig.suptitle("Sentinel-X : l'IA détecte les anomalies avant le seuil fixe")
    fig.tight_layout()
    fig.savefig("resultat_anomalies.png", dpi=120)
    print("\nGraphique sauvegardé dans resultat_anomalies.png")
