# relay_server.py
# Rôle : recevoir les données du leader ET du drone,
#        calculer les alertes, transmettre au follower
# Ports : Leader→5000 | Follower←5001 | Drone→5002

import socket
import threading
import json
import time

RELAY_HOST          = '0.0.0.0'
RELAY_PORT_LEADER   = 5000
RELAY_PORT_FOLLOWER = 5001
RELAY_PORT_DRONE    = 5002

# Seuils
SPEED_LIMIT_DEG_S   = 60   # variation angle/seconde → excès vitesse
MIN_DISTANCE_CM     = 30   # distance minimale inter-véhicules

# Mémoire partagée entre tous les threads
shared_data = {
    # Données du leader
    'steering_angle':    90,
    'obstacle_detected': False,
    'sign_detected':     None,
    'timestamp':         0,
    # Calculé par le relay
    'speed_estimate':    0.0,
    'alert_speed':       False,
    # Données du drone (caméra)
    'inter_distance':    None,
    'alert_distance':    False,
    'nb_vehicles_seen':  0,
    'drone_battery':     0,
    'drone_height_cm':   0,
}
lock = threading.Lock()


# ═══════════════════════════════════════════
# THREAD 1 : reçoit les données du LEADER
# ═══════════════════════════════════════════
def handle_leader(conn, addr):
    print(f"[RELAY] ✅ Leader connecté : {addr}")
    prev_angle = 90
    prev_time  = time.time()
    buffer     = ""

    while True:
        try:
            chunk = conn.recv(1024).decode('utf-8')
            if not chunk:
                print("[RELAY] Leader déconnecté.")
                break
            buffer += chunk

            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                if not line.strip():
                    continue
                msg = json.loads(line)

                now           = time.time()
                dt            = max(now - prev_time, 0.001)
                current_angle = msg.get('steering_angle', 90)

                # Estimation vitesse = variation angulaire / temps
                speed_est = abs(current_angle - prev_angle) / dt

                with lock:
                    shared_data['steering_angle']    = current_angle
                    shared_data['obstacle_detected'] = msg.get('obstacle_detected', False)
                    shared_data['sign_detected']     = msg.get('sign_detected', None)
                    shared_data['timestamp']         = now
                    shared_data['speed_estimate']    = round(speed_est, 2)
                    shared_data['alert_speed']       = speed_est > SPEED_LIMIT_DEG_S

                prev_angle = current_angle
                prev_time  = now

                print(f"[RELAY] Leader → angle={current_angle}° | "
                      f"vitesse={speed_est:.1f} | "
                      f"alerte_vitesse={speed_est > SPEED_LIMIT_DEG_S}")

        except json.JSONDecodeError:
            continue
        except Exception as e:
            print(f"[RELAY] Erreur leader: {e}")
            break
    conn.close()


def start_leader_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((RELAY_HOST, RELAY_PORT_LEADER))
    srv.listen(5)
    print(f"[RELAY] En attente du LEADER sur port {RELAY_PORT_LEADER}...")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_leader,
                         args=(conn, addr), daemon=True).start()


# ═══════════════════════════════════════════
# THREAD 2 : reçoit les données du DRONE
# ═══════════════════════════════════════════
def handle_drone(conn, addr):
    print(f"[RELAY] ✅ Drone connecté : {addr}")
    buffer = ""

    while True:
        try:
            chunk = conn.recv(2048).decode('utf-8')
            if not chunk:
                print("[RELAY] Drone déconnecté.")
                break
            buffer += chunk

            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                if not line.strip():
                    continue
                msg = json.loads(line)

                inter  = msg.get('inter_distance')
                alerte = msg.get('alert_distance', False)

                with lock:
                    shared_data['inter_distance']   = inter
                    shared_data['alert_distance']   = alerte
                    shared_data['nb_vehicles_seen'] = msg.get('nb_vehicles', 0)
                    shared_data['drone_battery']    = msg.get('battery', 0)
                    shared_data['drone_height_cm']  = msg.get('height_cm', 0)

                print(f"[RELAY] Drone → inter={inter}cm | "
                      f"alerte_dist={alerte} | "
                      f"vehicules={msg.get('nb_vehicles')}")

        except json.JSONDecodeError:
            continue
        except Exception as e:
            print(f"[RELAY] Erreur drone: {e}")
            break
    conn.close()


def start_drone_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((RELAY_HOST, RELAY_PORT_DRONE))
    srv.listen(1)
    print(f"[RELAY] En attente du DRONE sur port {RELAY_PORT_DRONE}...")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_drone,
                         args=(conn, addr), daemon=True).start()


# ═══════════════════════════════════════════
# THREAD 3 : envoie les données au FOLLOWER
# ═══════════════════════════════════════════
def handle_follower(conn, addr):
    print(f"[RELAY] ✅ Follower connecté : {addr}")
    while True:
        try:
            with lock:
                data_to_send = dict(shared_data)
            msg = json.dumps(data_to_send) + '\n'
            conn.send(msg.encode('utf-8'))
            time.sleep(0.1)   # 10 Hz
        except Exception as e:
            print(f"[RELAY] Follower déconnecté: {e}")
            break
    conn.close()


def start_follower_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((RELAY_HOST, RELAY_PORT_FOLLOWER))
    srv.listen(5)
    print(f"[RELAY] En attente du FOLLOWER sur port {RELAY_PORT_FOLLOWER}...")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_follower,
                         args=(conn, addr), daemon=True).start()


# ═══════════════════════════════════════════
# POINT D'ENTRÉE
# ═══════════════════════════════════════════
if __name__ == '__main__':
    print("=" * 55)
    print("  RELAY SERVER — Drone superviseur inter-véhicule")
    print("=" * 55)
    print(f"  Drone    → port {RELAY_PORT_DRONE}")
    print(f"  Leader   → port {RELAY_PORT_LEADER}")
    print(f"  Follower ← port {RELAY_PORT_FOLLOWER}")
    print("  Ctrl+C pour arrêter")
    print("=" * 55)

    threads = [
        threading.Thread(target=start_drone_server,    daemon=True),
        threading.Thread(target=start_leader_server,   daemon=True),
        threading.Thread(target=start_follower_server, daemon=True),
    ]
    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[RELAY] Arrêt du serveur.")