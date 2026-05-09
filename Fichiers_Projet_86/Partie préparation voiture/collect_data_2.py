import cv2
import os
import time
from picar import front_wheels, back_wheels
import picar

# ======================
# Initialisation PiCar
# ======================
picar.setup()

fw = front_wheels.Front_Wheels()
bw = back_wheels.Back_Wheels()

cam = cv2.VideoCapture(0)

if not cam.isOpened():
    print("Caméra non détectée")
    exit()

# ======================
# Paramètres
# ======================
output_dir = "data_auto"

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

speed = 35
center = 90
left = 60
right = 120

pause_move = 1.0      # temps de déplacement
pause_turn = 0.8      # temps de rotation roues avant
pause_photo = 0.3     # attente avant photo

# ======================
# Fonction photo
# ======================
def take_photo(angle):
    ret, frame = cam.read()

    if ret:
        img = cv2.resize(frame, (320, 240))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        filename = f"{output_dir}/{int(time.time()*1000)}_{angle}.jpg"
        cv2.imwrite(filename, gray)

        print("Photo :", filename)

# ======================
# Début auto
# ======================
print("Mode automatique lancé (CTRL+C pour arrêter)")

try:
    while True:

        # ------------------
        # Avancer tout droit
        # ------------------
        fw.turn(center)
        bw.speed = speed
        bw.forward()

        time.sleep(pause_move)
        bw.stop()

        time.sleep(pause_photo)
        take_photo(center)

        # ------------------
        # Tourner gauche
        # ------------------
        fw.turn(left)
        bw.speed = speed
        bw.forward()

        time.sleep(pause_turn)
        bw.stop()

        time.sleep(pause_photo)
        take_photo(left)

        # ------------------
        # Tourner droite
        # ------------------
        fw.turn(right)
        bw.speed = speed
        bw.forward()

        time.sleep(pause_turn)
        bw.stop()

        time.sleep(pause_photo)
        take_photo(right)

except KeyboardInterrupt:
    print("Arrêt manuel")

finally:
    bw.stop()
    fw.turn(center)
    cam.release()
    print("Arrêt propre")
