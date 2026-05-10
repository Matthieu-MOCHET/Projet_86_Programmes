import time
from ultralytics import YOLO
from picar import front_wheels, back_wheels
from picar.SunFounder_PCA9685 import Servo
import picar

import cv2
import numpy as np

import os

picar.setup()

# Init voiture
picar.setup()
fw = front_wheels.Front_Wheels()
bw = back_wheels.Back_Wheels()

fw.turn(90)
bw.speed = 25

# Charger modèle
model = YOLO("/home/picar/weights.pt")

# Classes obstacles (à adapter selon ton dataset)
obstacles = ["car", "person", "bike"]

def avancer():
    fw.turn(90)
    bw.forward()

def stop():
    bw.stop()

def contourner():
    stop()
    time.sleep(0.5)

    # tourner à gauche
    fw.turn(120)
    bw.forward()
    time.sleep(1)

    # revenir à droite
    fw.turn(60)
    bw.forward()
    time.sleep(1)

    fw.turn(90)

try:
    for results in model.predict(source=0, stream=True, imgsz=320, conf=0.4, show=False):
        

        obstacle_detecte = False

        for box in results.boxes:
            cls_id = int(box.cls[0])
            nom = model.names[cls_id]

            if nom in obstacles:
                print("Obstacle :", nom)
                obstacle_detecte = True
                break

        if obstacle_detecte:
            contourner()
        else:
            avancer()

except KeyboardInterrupt:
    print("Arrêt manuel")

finally:
    stop()
    Fw.turn(90)
