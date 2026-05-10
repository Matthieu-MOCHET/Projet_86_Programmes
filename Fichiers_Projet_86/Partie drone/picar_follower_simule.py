# picar_follower_simule.py
# Simule le PiCar Follower sur ton PC portable
# Affiche toutes les commandes qu'un vrai follower exécuterait
# Lance ce fichier sur ton PC (pas sur le Raspberry Pi)

import socket
import json
import time
import statistics

RELAY_IP   = '127.0.0.1'   # le relay tourne sur le même PC
RELAY_PORT = 5001

# ─── Historique pour le rapport ─────────────────────────────────
latencies       = []
angles_recus    = []
alertes_dist    = 0
alertes_vitesse = 0
nb_messages     = 0
start_time      = time.time()


def connect_relay():
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((RELAY_IP, RELAY_PORT))
            print(f"[FOLLOWER SIMULE] ✅ Connecté au relay {RELAY_IP}:{RELAY_PORT}")
            return s
        except Exception as e:
            print(f"[FOLLOWER SIMULE] Relay non dispo ({e}), retry 3s...")
            time.sleep(3)


def afficher_stats():
    """Affiche un résumé des stats pour le rapport."""
    duree = time.time() - start_time
    print("\n" + "=" * 50)
    print("  STATS SESSION — Pour ton rapport")
    print("=" * 50)
    print(f"  Durée session     : {duree:.1f}s")
    print(f"  Messages reçus    : {nb_messages}")
    if latencies:
        print(f"  Latence moyenne   : {statistics.mean(latencies):.2f}ms")
        print(f"  Latence max       : {max(latencies):.2f}ms")
        print(f"  Latence min       : {min(latencies):.2f}ms")
        print(f"  Écart-type        : {statistics.stdev(latencies):.2f}ms")
    print(f"  Alertes distance  : {alertes_dist}")
    print(f"  Alertes vitesse   : {alertes_vitesse}")
    if angles_recus:
        print(f"  Angle moyen reçu  : {sum(angles_recus)/len(angles_recus):.1f}°")
        print(f"  Angle min / max   : {min(angles_recus):.1f}° / {max(angles_recus):.1f}°")
    print("=" * 50)


# ─── Simulation des commandes PiCar ─────────────────────────────
def simuler_braquage(angle):
    direction = "TOUT DROIT"
    if angle < 85:
        direction = "← GAUCHE"
    elif angle > 95:
        direction = "→ DROITE"
    print(f"  [MOTEUR] Braquage : {angle}° — {direction}")


def simuler_vitesse(speed):
    print(f"  [MOTEUR] Vitesse  : {speed}%")


def simuler_arret():
    print(f"  [MOTEUR] ⛔ ARRÊT D'URGENCE")


if __name__ == '__main__':
    print("=" * 50)
    print("  FOLLOWER SIMULÉ — PC Portable")
    print("  (simule les commandes du PiCar Follower)")
    print("=" * 50)

    sock   = connect_relay()
    buffer = ""

    try:
        while True:
            chunk = sock.recv(1024).decode('utf-8')
            if not chunk:
                print("[FOLLOWER SIMULE] Relay déconnecté. Reconnexion...")
                sock.close()
                sock   = connect_relay()
                buffer = ""
                continue

            buffer += chunk

            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                if not line.strip():
                    continue

                data = json.loads(line)
                nb_messages += 1

                # ── Latence ───────────────────────────────────
                ts         = data.get('timestamp', time.time())
                latency_ms = (time.time() - ts) * 1000
                latencies.append(latency_ms)
                if len(latencies) > 500:
                    latencies.pop(0)
                avg_lat = sum(latencies) / len(latencies)

                print(f"\n[MSG #{nb_messages}] "
                      f"Latence: {latency_ms:.1f}ms | "
                      f"Moy: {avg_lat:.1f}ms")

                # ── Données drone ─────────────────────────────
                inter  = data.get('inter_distance')
                nb_veh = data.get('nb_vehicles_seen', 0)
                bat    = data.get('drone_battery', 0)
                height = data.get('drone_height_cm', 0)
                print(f"  [DRONE]  Véhicules vus: {nb_veh} | "
                      f"Inter-dist: {inter}cm | "
                      f"Bat: {bat}% | H: {height}cm")

                # ── Alerte distance (depuis drone) ────────────
                if data.get('alert_distance'):
                    alertes_dist += 1
                    print(f"  ⚠️  ALERTE DISTANCE — trop proche du leader!")
                    simuler_arret()
                    time.sleep(1)
                    continue

                # ── Alerte vitesse (depuis drone) ─────────────
                if data.get('alert_speed'):
                    alertes_vitesse += 1
                    print(f"  ⚠️  ALERTE VITESSE — leader trop rapide!")
                    simuler_vitesse(20)
                else:
                    simuler_vitesse(40)

                # ── Obstacle détecté par le leader ────────────
                if data.get('obstacle_detected'):
                    print(f"  ⚠️  Obstacle leader détecté → ralentissement")
                    simuler_vitesse(15)

                # ── Panneau détecté par le leader ─────────────
                sign = data.get('sign_detected')
                if sign:
                    print(f"  🚸 Panneau reçu : {sign}")
                    if sign == 'stop':
                        simuler_arret()
                        time.sleep(2)

                # ── Braquage du leader ─────────────────────────
                angle = data.get('steering_angle', 90)
                angles_recus.append(angle)
                simuler_braquage(angle)

                # ── Vitesse estimée par le relay ───────────────
                speed_est = data.get('speed_estimate', 0)
                print(f"  [RELAY]  Vitesse leader: {speed_est:.1f}°/s | "
                      f"Angle: {angle}°")

    except KeyboardInterrupt:
        print("\n[FOLLOWER SIMULE] Arrêt.")
    finally:
        sock.close()
        afficher_stats()