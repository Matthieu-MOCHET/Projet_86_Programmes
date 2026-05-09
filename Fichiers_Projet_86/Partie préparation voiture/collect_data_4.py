import cv2
import os
import time
import sys
import tty
import termios
import threading
from picar import front_wheels, back_wheels
import picar

# Initialisation
picar.setup()
fw = front_wheels.Front_Wheels()
bw = back_wheels.Back_Wheels()
cam = cv2.VideoCapture(0)

# Paramètres
output_dir = "data_couleur" # Nouveau dossier pour ne pas mélanger
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

angle = 90
moving = False
stop_script = False

def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def auto_capture():
    global moving, angle, stop_script
    print("Enregistrement COULEUR actif...")
    while not stop_script:
        if moving:
            ret, frame = cam.read()
            if ret:
                # On garde l'image en COULEUR (320x240)
                img_color = cv2.resize(frame, (320, 240))
               
                # Sauvegarde : timestamp_angle.jpg
                ts = int(time.time() * 1000)
                cv2.imwrite(f"{output_dir}/{ts}_{angle}.jpg", img_color)
        time.sleep(0.5) # 10 photos par seconde

capture_thread = threading.Thread(target=auto_capture)
capture_thread.start()

print("MODE COULEUR : Z (Avance) | S (Stop) | Q (Gauche) | D (Droite) | X (Quitter)")

try:
    while True:
        key = getch().lower()
        if key == 'z':
            bw.speed = 50 # Vitesse un peu plus lente pour des photos nettes
            bw.forward()
            moving = True
        elif key == 's':
            bw.stop()
            moving = False
        elif key == 'q':
            angle = max(45, angle - 10)
            fw.turn(angle)
        elif key == 'd':
            angle = min(135, angle + 10)
            fw.turn(angle)
        elif key == 'x':
            stop_script = True
            break
finally:
    stop_script = True
    capture_thread.join()
    bw.stop()
    cam.release()
    print(f"Terminé ! Tes {len(os.listdir(output_dir))} images couleurs sont dans {output_dir}")
