# picar_leader_client.py
# Envoie en continu au relay : angle de braquage,
# obstacle détecté, panneau détecté

import socket
import json
import time
import math

# ─── IP du PC relay (sur le réseau Tello) ───────────────────────
RELAY_IP   = '192.168.10.2'   # ← IP de ton PC sur le réseau Tello
RELAY_PORT = 5000

# ─── Fonctions à connecter à ton vrai code PiCar ────────────────
# Remplace ces fonctions par tes vrais modules :
# from picar import front_wheels, back_wheels
# from ton_module_deeplearning import get_angle
# from ton_module_detection import get_obstacle

def get_steering_angle():
    """Retourne l'angle prédit par le réseau de neurones."""
    # Simule une conduite pour les tests
    return round(90 + 25 * math.sin(time.time() * 0.5), 1)

def get_obstacle_detected():
    """True si un obstacle est détecté devant le véhicule."""
    return False

def get_sign_detected():
    """Retourne le panneau détecté : 'stop', 'speed_limit' ou None."""
    return None


def connect_relay():
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((RELAY_IP, RELAY_PORT))
            print(f"[LEADER] ✅ Connecté au relay {RELAY_IP}:{RELAY_PORT}")
            return s
        except Exception as e:
            print(f"[LEADER] Relay non dispo ({e}), retry 3s...")
            time.sleep(3)


if __name__ == '__main__':
    sock = connect_relay()

    while True:
        try:
            msg = json.dumps({
                'steering_angle':    get_steering_angle(),
                'obstacle_detected': get_obstacle_detected(),
                'sign_detected':     get_sign_detected(),
                'timestamp':         time.time(),
            }) + '\n'

            sock.send(msg.encode('utf-8'))
            print(f"[LEADER] Envoi → angle={get_steering_angle()}°")
            time.sleep(0.1)   # 10 Hz

        except BrokenPipeError:
            print("[LEADER] Connexion perdue. Reconnexion...")
            sock.close()
            sock = connect_relay()
        except Exception as e:
            print(f"[LEADER] Erreur: {e}")
            time.sleep(1)