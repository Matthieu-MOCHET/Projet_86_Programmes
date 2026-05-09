import cv2
import os
import time
import sys
import tty
import termios
from picar import front_wheels, back_wheels
import picar

# Initialisation PiCar
picar.setup()

fw = front_wheels.Front_Wheels()
bw = back_wheels.Back_Wheels()

# Caméra
cam = cv2.VideoCapture(0)

if not cam.isOpened():
    print("Caméra non détectée")
    exit()

# Direction initiale
angle = 90
fw.turn(angle)

# Etat mouvement
moving = False

# Dossier images
output_dir = "data"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Lecture touche clavier
def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return ch

print("Commandes : Z avancer | S stop | Q gauche | D droite | X quitter")

try:
    while True:
        key = getch().lower()

        # Avancer
        if key == 'z':
            bw.speed = 40
            bw.forward()
            moving = True

        # Stop
        elif key == 's':
            bw.stop()
            moving = False

        # Gauche
        elif key == 'q':
            angle = max(45, angle - 10)
            fw.turn(angle)

        # Droite
        elif key == 'd':
            angle = min(135, angle + 10)
            fw.turn(angle)

        # Quitter
        elif key == 'x':
            break

        # Capture image si la voiture roule
        if moving:
            ret, frame = cam.read()

            if ret:
                img = cv2.resize(frame, (320, 240))
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                filename = f"{output_dir}/{int(time.time()*1000)}_{angle}.jpg"
                cv2.imwrite(filename, gray)

                print(f"Image enregistrée : {filename}")

finally:
    bw.stop()
    cam.release()
    print("Arrêt propre")
