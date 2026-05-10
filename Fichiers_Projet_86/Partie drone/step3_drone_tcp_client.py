# step3_drone_tcp_client.py — VERSION TEMPS REEL v4
import socket
import threading
import time
import json
import os
import sys
import cv2
import numpy as np

# ─── Config réseau ───────────────────────────────────────────────
TELLO_IP         = '192.168.10.1'
TELLO_PORT       = 8889
TELLO_STATE_PORT = 8890
TELLO_VIDEO_PORT = 11111

RELAY_IP         = '127.0.0.1'
RELAY_PORT_DRONE = 5002

USE_DRONE = True   # False = webcam locale, True = vrai drone

# ─── Hauteur de vol stationnaire ────────────────────────────────
# Le Tello décolle toujours à ~80 cm (non configurable).
# HOVER_HEIGHT_CM = hauteur CIBLE en cm mesurée par le capteur du drone.
# La fonction climb_to_height() monte par paliers de 20 cm jusqu'à
# atteindre cette valeur, puis confirme la stabilisation.
HOVER_HEIGHT_CM     = 120   # hauteur cible (cm) — modifiable
HEIGHT_TOLERANCE_CM = 10    # ±tolérance pour considérer la hauteur atteinte
STABILIZE_WAIT_S    = 3.0   # secondes d'immobilité avant de déclarer stable

# ─── Seuils détection rouge ──────────────────────────────────────
RED_LOWER1 = np.array([0,   100, 80])
RED_UPPER1 = np.array([10,  255, 255])
RED_LOWER2 = np.array([160, 100, 80])
RED_UPPER2 = np.array([180, 255, 255])

MIN_CONTOUR_AREA = 800
ALERT_AREA_PX    = 15000

# ─── Variables globales ──────────────────────────────────────────
battery      = 0
tello_height = 0
response     = None
is_flying    = False

# ─── Sockets UDP Tello ───────────────────────────────────────────
cmd_sock   = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
cmd_sock.bind(('', TELLO_PORT))
state_sock.bind(('', TELLO_STATE_PORT))
cmd_sock.settimeout(5)

cmd_lock = threading.Lock()


# ════════════════════════════════════════════════════════════════
# GRABBER TEMPS REEL
# ════════════════════════════════════════════════════════════════
class RealtimeFrameGrabber:
    """
    Thread dédié qui vide le buffer FFMPEG en continu.
    La boucle principale lit toujours la DERNIERE frame disponible
    → latence <50ms au lieu de plusieurs secondes.

    Pourquoi le décalage apparaît sans ce thread :
      cap.read() est BLOQUANT et FIFO : si la boucle principale
      est plus lente que 30fps (détection, affichage…), le buffer
      grossit et les images lues datent de plusieurs secondes.
    Ce thread consomme les frames dès qu'elles arrivent et ne
    conserve que la plus récente → plus de backlog.
    """

    def __init__(self, source):
        # Options FFMPEG pour décodage à latence minimale
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "fflags;nobuffer|"
            "flags;low_delay|"
            "max_delay;0|"
            "reorder_queue_size;0|"
            "probesize;32|"
            "analyzeduration;0"
        )
        if isinstance(source, int):
            self.cap = cv2.VideoCapture(source)
        else:
            self.cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)

        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self._frame      = None
        self._lock       = threading.Lock()
        self._running    = False
        self._ready      = threading.Event()
        self._thread     = threading.Thread(
            target=self._grab_loop, daemon=True)

    def start(self):
        self._running = True
        self._thread.start()

    def _grab_loop(self):
        """Lit aussi vite que possible, garde seulement la dernière frame."""
        failures = 0
        while self._running:
            ret, frame = self.cap.read()
            if ret and frame is not None and frame.size > 0:
                with self._lock:
                    self._frame = frame
                if not self._ready.is_set():
                    self._ready.set()
                failures = 0
            else:
                failures += 1
                if failures > 60:
                    time.sleep(0.02)
                    failures = 0

    def wait_ready(self, timeout=15) -> bool:
        """Bloque jusqu'à la première frame valide (ou timeout)."""
        return self._ready.wait(timeout=timeout)

    def read(self):
        """Retourne (True, frame_copie) ou (False, None)."""
        with self._lock:
            if self._frame is None:
                return False, None
            return True, self._frame.copy()

    def stop(self):
        self._running = False
        self._thread.join(timeout=2)
        self.cap.release()


# ════════════════════════════════════════════════════════════════
# COMMANDES TELLO
# ════════════════════════════════════════════════════════════════

def safe_decode(data: bytes) -> str:
    """Décode les bytes Tello : essaie UTF-8 puis Latin-1.
    Le Tello envoie parfois des bytes non-UTF-8 (ex: 0xcc) selon
    la version firmware → Latin-1 accepte tous les bytes 0x00-0xFF."""
    for enc in ('utf-8', 'latin-1', 'ascii'):
        try:
            return data.decode(enc).strip()
        except (UnicodeDecodeError, AttributeError):
            continue
    return data.decode('utf-8', errors='replace').strip()

def receive_cmd():
    global response
    while True:
        try:
            response, _ = cmd_sock.recvfrom(1024)
        except Exception:
            pass


def receive_state():
    global battery, tello_height
    while True:
        try:
            data, _ = state_sock.recvfrom(256)
            pairs = {}
            for item in safe_decode(data).split(';'):
                if ':' in item:
                    parts = item.strip().split(':', 1)
                    if len(parts) == 2:
                        pairs[parts[0]] = parts[1]
            battery      = int(pairs.get('bat', 0))
            tello_height = int(pairs.get('h', 0))
        except Exception:
            pass



def send_tello_cmd(cmd, timeout=10):
    global response
    with cmd_lock:
        response = None
        cmd_sock.sendto(cmd.encode('utf-8'), (TELLO_IP, TELLO_PORT))
        print(f"[TELLO→] {cmd}")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if response:
                rep = safe_decode(response)
                print(f"[TELLO←] {rep}")
                return rep
            time.sleep(0.05)
        print(f"[TELLO] Timeout : {cmd}")
        return None


# ════════════════════════════════════════════════════════════════
# DECOLLAGE + VOL STATIONNAIRE
# ════════════════════════════════════════════════════════════════
def wait_stable_height(target_cm, tolerance_cm=HEIGHT_TOLERANCE_CM,
                       stable_duration=STABILIZE_WAIT_S):
    """
    Attend que le drone soit à target_cm ± tolerance_cm
    pendant stable_duration secondes consécutives.
    Retourne True si stabilisé, False si timeout (30s).
    """
    print(f"[DRONE] Attente stabilisation à {target_cm} cm "
          f"(±{tolerance_cm} cm)...")
    stable_since = None
    deadline     = time.time() + 30

    while time.time() < deadline:
        h = tello_height   # mis à jour par receive_state()
        in_range = abs(h - target_cm) <= tolerance_cm

        if in_range:
            if stable_since is None:
                stable_since = time.time()
            elapsed = time.time() - stable_since
            print(f"\r[DRONE]   H={h}cm | stable depuis {elapsed:.1f}s "
                  f"/ {stable_duration}s   ", end='', flush=True)
            if elapsed >= stable_duration:
                print(f"\n[DRONE] ✅ Stable à {h} cm !")
                return True
        else:
            stable_since = None
            print(f"\r[DRONE]   H={h}cm | cible={target_cm}cm "
                  f"| écart={abs(h-target_cm)}cm   ", end='', flush=True)

        time.sleep(0.2)

    print(f"\n[DRONE] ⚠️  Timeout stabilisation (hauteur actuelle={tello_height}cm)")
    return False


def climb_to_height(target_cm):
    """
    Monte par paliers de 20 cm jusqu'à target_cm.
    Le Tello décolle toujours à ~80 cm (commande takeoff).
    Minimum de 'up' : 20 cm.
    """
    STEP = 20   # cm par commande 'up' (min Tello SDK = 20)

    current = tello_height
    needed  = target_cm - current

    if needed < STEP:
        print(f"[DRONE] Déjà à {current}cm — cible {target_cm}cm dans la tolérance.")
        return

    steps = int(needed // STEP)
    print(f"[DRONE] Montée vers {target_cm}cm : {steps} palier(s) de {STEP}cm")

    for i in range(steps):
        remaining = target_cm - tello_height
        if remaining < STEP:
            break
        move = min(STEP, remaining - (remaining % STEP) or STEP)
        print(f"[DRONE]   Palier {i+1}/{steps} : up {move}cm "
              f"(actuellement {tello_height}cm)")
        send_tello_cmd(f"up {move}", timeout=10)
        time.sleep(1.5)   # pause entre paliers pour stabiliser


def takeoff_and_hover():
    global is_flying

    print("\n[DRONE] === Initialisation Tello ===")

    if send_tello_cmd("command") != 'ok':
        print("[DRONE] Tello ne répond pas.")
        sys.exit(1)
    time.sleep(0.5)

    rep = send_tello_cmd("battery?")
    try:
        bat_level = int(rep)
    except Exception:
        bat_level = 0
    print(f"[DRONE] Batterie : {bat_level}%")
    if bat_level < 15:
        print("[DRONE] ⚠️  Batterie faible.")
        sys.exit(1)

    # streamon envoyé avant décollage — une seule fois.
    print("[DRONE] Activation flux vidéo (streamon)...")
    rep = send_tello_cmd("streamon", timeout=10)
    if rep != 'ok':
        print(f"[DRONE] Avertissement streamon={rep!r} — on continue.")

    # ── Décollage ────────────────────────────────────────────────
    print("[DRONE] Décollage...")
    if send_tello_cmd("takeoff", timeout=15) != 'ok':
        print("[DRONE] Décollage échoué.")
        sys.exit(1)
    is_flying = True

    # Attente que le Tello finisse sa montée initiale (~80 cm)
    print("[DRONE] Montée initiale post-takeoff...")
    time.sleep(4)

    # ── Montée vers la hauteur cible ────────────────────────────
    if HOVER_HEIGHT_CM > tello_height + HEIGHT_TOLERANCE_CM:
        climb_to_height(HOVER_HEIGHT_CM)
    else:
        print(f"[DRONE] Hauteur actuelle {tello_height}cm déjà proche "
              f"de la cible {HOVER_HEIGHT_CM}cm.")

    # ── Stabilisation : on attend que le drone ne bouge plus ────
    # Le Tello stabilise automatiquement grâce à son capteur
    # de flux optique. On attend simplement qu'il soit immobile
    # à la bonne hauteur avant de démarrer la détection.
    stable = wait_stable_height(HOVER_HEIGHT_CM)
    if not stable:
        print("[DRONE] ⚠️  Pas totalement stable mais on continue.")

    print(f"[DRONE] ✅ Stationnaire à {tello_height}cm — détection active !")


def land_safely():
    global is_flying
    if is_flying:
        print("[DRONE] Atterrissage...")
        send_tello_cmd("land", timeout=15)
        is_flying = False
    send_tello_cmd("streamoff")
    print("[DRONE] Posé.")


def keepalive_loop():
    """
    Maintient la connexion Tello active (timeout SDK = 15s).
    Envoie aussi 'rc 0 0 0 0' pour annuler toute dérive
    residuelle et forcer le maintien de position.
    """
    while True:
        time.sleep(10)
        if is_flying:
            # rc lr fb ud yaw — tous à 0 = hover forcé
            send_tello_cmd("rc 0 0 0 0")
            time.sleep(2)
            send_tello_cmd("battery?")


# ════════════════════════════════════════════════════════════════
# CONNEXION RELAY
# ════════════════════════════════════════════════════════════════
def connect_relay():
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((RELAY_IP, RELAY_PORT_DRONE))
            print(f"[DRONE] ✅ Relay connecté {RELAY_IP}:{RELAY_PORT_DRONE}")
            return s
        except Exception as e:
            print(f"[DRONE] Relay non dispo ({e}), retry 3s...")
            time.sleep(3)


# ════════════════════════════════════════════════════════════════
# DETECTION ROUGE HSV
# ════════════════════════════════════════════════════════════════
def detect_red_objects(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    mask1 = cv2.inRange(hsv, RED_LOWER1, RED_UPPER1)
    mask2 = cv2.inRange(hsv, RED_LOWER2, RED_UPPER2)
    mask  = cv2.bitwise_or(mask1, mask2)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask   = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask   = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)

    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detections  = []
    alert_close = False

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < MIN_CONTOUR_AREA:
            continue

        x, y, bw, bh = cv2.boundingRect(cnt)
        cx       = x + bw // 2
        cy       = y + bh // 2
        is_close = area > ALERT_AREA_PX
        if is_close:
            alert_close = True

        detections.append({
            'bbox':     [int(x), int(y), int(x + bw), int(y + bh)],
            'area':     int(area),
            'cx':       cx,
            'cy':       cy,
            'is_close': is_close,
        })

        color = (0, 0, 255) if is_close else (0, 200, 255)
        cv2.rectangle(frame, (x, y), (x + bw, y + bh), color, 2)
        label = f"ROUGE {'!PROCHE!' if is_close else ''} {area}px²"
        cv2.putText(frame, label, (x, max(y - 8, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        cv2.circle(frame, (cx, cy), 4, color, -1)

    return frame, detections, alert_close


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════
if __name__ == '__main__':

    threading.Thread(target=receive_cmd,   daemon=True).start()
    threading.Thread(target=receive_state, daemon=True).start()

    if USE_DRONE:
        # takeoff_and_hover() : command → battery? → streamon → takeoff → up 40
        takeoff_and_hover()

        # Lancer le grabber PENDANT la montée pour gagner du temps
        uri = f'udp://0.0.0.0:{TELLO_VIDEO_PORT}'
        print(f"\n[VIDEO] Démarrage grabber temps réel ({uri})")
        grabber = RealtimeFrameGrabber(uri)
        grabber.start()

        print("[VIDEO] Attente première frame (max 10s)...")
        if not grabber.wait_ready(timeout=10):
            print("[VIDEO] ❌ Aucune frame reçue — flux inaccessible.")
            grabber.stop()
            land_safely()
            sys.exit(1)
        print("[VIDEO] ✅ Flux temps réel actif !")

        # Keepalive démarré après init complète
        threading.Thread(target=keepalive_loop, daemon=True).start()

    else:
        print("[DRONE] Mode webcam locale")
        grabber = RealtimeFrameGrabber(0)
        grabber.start()
        if not grabber.wait_ready(timeout=5):
            print("[ERREUR] Webcam inaccessible.")
            sys.exit(1)

    relay_sock = connect_relay()
    last_send  = 0

    # Compteur FPS
    fps_counter = 0
    fps_display = 0
    fps_timer   = time.time()

    print("[DRONE] ✅ Détection rouge active. 'q' pour quitter.\n")

    try:
        while True:
            ret, frame = grabber.read()
            if not ret:
                time.sleep(0.005)
                continue

            frame = cv2.resize(frame, (640, 480))
            frame, detections, alert_close = detect_red_objects(frame)

            nb_red = len(detections)

            # FPS
            fps_counter += 1
            now = time.time()
            if now - fps_timer >= 1.0:
                fps_display = fps_counter
                fps_counter = 0
                fps_timer   = now

            # Alertes visuelles
            if alert_close:
                cv2.putText(frame, "OBJET ROUGE PROCHE !",
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0, 0, 255), 2)

            cv2.putText(frame,
                        f"Objets rouges : {nb_red}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (0, 200, 255), 2)

            mode = "TELLO" if USE_DRONE else "WEBCAM"
            cv2.putText(frame,
                        f"[{mode}] Bat:{battery}% | "
                        f"H:{tello_height}cm | "
                        f"Rouges:{nb_red} | FPS:{fps_display}",
                        (10, 460), cv2.FONT_HERSHEY_SIMPLEX,
                        0.4, (255, 255, 0), 1)

            # Envoi relay 10 Hz
            if now - last_send >= 0.1:
                msg = json.dumps({
                    'source':      'drone',
                    'timestamp':   now,
                    'nb_red':      nb_red,
                    'detections':  detections,
                    'alert_close': alert_close,
                    'battery':     battery,
                    'height_cm':   tello_height,
                }) + '\n'
                try:
                    relay_sock.send(msg.encode('utf-8'))
                    last_send = now
                except BrokenPipeError:
                    print("[DRONE] Relay perdu. Reconnexion...")
                    relay_sock.close()
                    relay_sock = connect_relay()

            cv2.imshow("Drone — Detection Rouge [TEMPS REEL]", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print("\n[DRONE] Interruption.")
    finally:
        grabber.stop()
        cv2.destroyAllWindows()
        relay_sock.close()
        if USE_DRONE:
            land_safely()
        cmd_sock.close()
        state_sock.close()
        print("[DRONE] Terminé proprement.")
