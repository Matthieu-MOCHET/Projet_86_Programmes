import time
from ultralytics import YOLO
from picar import front_wheels, back_wheels
import picar

# Initialisation PiCar
picar.setup()

fw = front_wheels.Front_Wheels()
bw = back_wheels.Back_Wheels()

fw.turn(90)
bw.speed = 50

# Charger modèle YOLO
model = YOLO("/home/picar/weights.pt")

# Classes considérées comme obstacles
obstacles = ["person", "car"]

def avancer():
    fw.turn(90)
    bw.speed = 50
    bw.forward()

def stop():
    bw.stop()

def contourner():
    print("Contournement en cours...")
   
    stop()
    time.sleep(0.5)

    # Tourner à gauche
    fw.turn(120)
    bw.speed = 45
    bw.forward()
    time.sleep(0.8)

    # Tourner à droite pour revenir
    fw.turn(60)
    bw.forward()
    time.sleep(0.8)

    # Revenir droit
    fw.turn(90)
    bw.forward()
    time.sleep(0.5)

try:
    for results in model.predict(source=0, stream=True, imgsz=320, conf=0.4, show=False):

        obstacle_detecte = False

        for box in results.boxes:
            cls_id = int(box.cls[0])
            nom_classe = model.names[cls_id]

            print("Vu :", nom_classe)

            if nom_classe in obstacles:
                obstacle_detecte = True
                print("Obstacle détecté :", nom_classe)
                break

        if obstacle_detecte:
            contourner()
        else:
            avancer()

        time.sleep(0.05)

except KeyboardInterrupt:
    print("Arrêt manuel")

finally:
    stop()
    fw.turn(90)
