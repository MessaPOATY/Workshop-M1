"""
ETAPE 1 - Baseline vision Sentinel-X
Webcam -> YOLOv8n (COCO, classe 'person') -> zone de surveillance -> alerte d'intrusion.

Installation :
    pip install ultralytics opencv-python

Lancement :
    python etape1_vision_baseline.py            # webcam 0
    python etape1_vision_baseline.py --cam 1    # autre webcam
    python etape1_vision_baseline.py --video test.mp4

Touches :
    z  -> dessiner la zone (clics gauche pour poser les points, Entree pour valider)
    r  -> remettre la zone par defaut
    q  -> quitter
"""
import argparse
import json
import os
import time
from datetime import datetime

import cv2
import numpy as np
from ultralytics import YOLO
from mqtt_alert import connect_mqtt, publish_intrusion, disconnect_mqtt

# ----------------------------- Parametres ---------------------------------
MODEL_PATH = "yolov8n.pt"      # telecharge automatiquement la 1ere fois
CONF = 0.45                    # seuil de confiance
IMGSZ = 416                    # 320/416 = plus rapide (utile sur Raspberry Pi)
PERSIST_FRAMES = 5             # nb d'images consecutives dans la zone avant alerte
COOLDOWN_S = 5                 # delai min entre deux alertes
ALERT_DIR = "alerts"           # captures des intrus
DEVICE_ID = "sentinel-x-vision"

# Zone par defaut (coordonnees relatives 0..1) : moitie droite de l'image
DEFAULT_ZONE = [(0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0)]
# --------------------------------------------------------------------------


def to_pixels(zone_rel, w, h):
    return np.array([(int(x * w), int(y * h)) for x, y in zone_rel], dtype=np.int32)


class ZoneDrawer:
    """Permet de dessiner la zone a la souris."""

    def __init__(self):
        self.points = []
        self.active = False

    def on_mouse(self, event, x, y, flags, param):
        if self.active and event == cv2.EVENT_LBUTTONDOWN:
            self.points.append((x, y))


def build_alert(box, conf):
    x1, y1, x2, y2 = [int(v) for v in box]
    return {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "device_id": DEVICE_ID,
        "source": "vision",
        "type": "intrusion",
        "score": round(float(conf), 3),
        "details": {"bbox": [x1, y1, x2, y2]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=0)
    ap.add_argument("--video", type=str, default=None)
    args = ap.parse_args()

    os.makedirs(ALERT_DIR, exist_ok=True)
    model = YOLO(MODEL_PATH)
    connect_mqtt()

    cap = cv2.VideoCapture(args.video if args.video else args.cam)
    if not cap.isOpened():
        raise SystemExit("Impossible d'ouvrir la camera/video.")

    zone_rel = list(DEFAULT_ZONE)
    drawer = ZoneDrawer()
    cv2.namedWindow("Sentinel-X vision")
    cv2.setMouseCallback("Sentinel-X vision", drawer.on_mouse)

    in_zone_count = 0
    last_alert = 0.0
    prev = time.time()
    fps = 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]

        # ---- Mode dessin de zone ----
        if drawer.active:
            for p in drawer.points:
                cv2.circle(frame, p, 4, (0, 255, 255), -1)
            if len(drawer.points) > 1:
                cv2.polylines(frame, [np.array(drawer.points)], False, (0, 255, 255), 2)
            cv2.putText(frame, "Clic = point | Entree = valider | Echap = annuler",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.imshow("Sentinel-X vision", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == 13 and len(drawer.points) >= 3:  # Entree
                zone_rel = [(x / w, y / h) for x, y in drawer.points]
                drawer.active = False
            elif key == 27:  # Echap
                drawer.active = False
            continue

        zone_px = to_pixels(zone_rel, w, h)

        # ---- Inference ----
        results = model.predict(frame, classes=[0], conf=CONF, imgsz=IMGSZ, verbose=False)[0]

        intruder_box, intruder_conf = None, 0.0
        for box in results.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            c = float(box.conf[0])
            foot = (int((x1 + x2) / 2), int(y2))           # point des pieds
            inside = cv2.pointPolygonTest(zone_px, foot, False) >= 0
            color = (0, 0, 255) if inside else (0, 200, 0)
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
            cv2.putText(frame, f"person {c:.2f}", (int(x1), int(y1) - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            cv2.circle(frame, foot, 4, color, -1)
            if inside and c > intruder_conf:
                intruder_box, intruder_conf = (x1, y1, x2, y2), c

        # ---- Persistance temporelle (anti faux positifs) ----
        in_zone_count = in_zone_count + 1 if intruder_box else 0
        alarm = in_zone_count >= PERSIST_FRAMES

        if alarm and (time.time() - last_alert) > COOLDOWN_S:
            last_alert = time.time()
            alert = build_alert(intruder_box, intruder_conf)
            fname = os.path.join(ALERT_DIR, f"intrusion_{datetime.now():%Y%m%d_%H%M%S}.jpg")
            cv2.imwrite(fname, frame)
            alert["details"]["snapshot"] = fname
            print(json.dumps(alert, ensure_ascii=False))   # <- plus tard : publie en MQTT
            publish_intrusion(fname, intruder_conf, bbox=intruder_box)

        # ---- Affichage ----
        overlay = frame.copy()
        cv2.fillPoly(overlay, [zone_px], (0, 0, 255) if alarm else (255, 200, 0))
        frame = cv2.addWeighted(overlay, 0.25, frame, 0.75, 0)
        cv2.polylines(frame, [zone_px], True, (0, 0, 255) if alarm else (255, 200, 0), 2)

        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / max(now - prev, 1e-6))
        prev = now
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        if alarm:
            cv2.putText(frame, "INTRUSION", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)

        cv2.imshow("Sentinel-X vision", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("z"):
            drawer.points, drawer.active = [], True
        elif key == ord("r"):
            zone_rel = list(DEFAULT_ZONE)

    cap.release()
    disconnect_mqtt()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()





