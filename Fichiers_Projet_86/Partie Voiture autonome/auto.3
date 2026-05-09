import time
from ultralytics import YOLO
from picar import front_wheels, back_wheels
import picar

# Initialisation PiCar
picar.setup()

fw = front_wheels.Front_Wheels()
bw = back_wheels.Back_Wheels()

fw.turn(90)
bw.speed = 25

# Charger modèle
model = YOLO("/home/picar/weights.pt")

# Classes considérées comme obstacles
obstacles = ["person", "car"]

def avancer():
    fw.turn(90)
    bw.forward()

def stop():
    bw.stop()

try:
    for results in model.predict(source=0, stream=True, imgsz=320, conf=0.4, show=False):

        obstacle_detecte = False

        for box in results.boxes:
            cls_id = int(box.cls[0])
            nom_classe = model.names[cls_id]

            print("Vu :", nom_classe)  # debug

            if nom_classe in obstacles:
                obstacle_detecte = True
                print("Obstacle :", nom_classe)
                break

        if obstacle_detecte:
            stop()
        else:
            avancer()

        # évite surcharge CPU + mouvements trop brutaux
        time.sleep(0.05)

except KeyboardInterrupt:
    print("Arrêt manuel")

finally:
    stop()
    fw.turn(90)
