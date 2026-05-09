from ultralytics import YOLO
import cv2
from picar import front_wheels, back_wheels

fw = front_wheels.Front_Wheels()
bw = back_wheels.Back_Wheels()

fw.ready()
bw.ready()

model = YOLO("bebe.pt")
cap = cv2.VideoCapture(0)

SPEED = 70
CENTER_TOL = 40
CONF_MIN = 0.45

print("Mode autonome sans retour caméra. CTRL+C pour arrêter.")

try:
    while True:
        ret, frame = cap.read()

        if not ret:
            print("Erreur caméra")
            bw.stop()
            fw.turn_straight()
            break

        h, w, _ = frame.shape
        image_center = w / 2

        results = model(frame, conf=CONF_MIN, verbose=False)
        boxes = results[0].boxes

        if boxes is not None and len(boxes) > 0:
            best_box = boxes[0]
            x1, y1, x2, y2 = best_box.xyxy[0].tolist()

            line_center = (x1 + x2) / 2
            error = line_center - image_center

            if error < -CENTER_TOL:
                fw.turn_left()
                print("GAUCHE")

            elif error > CENTER_TOL:
                fw.turn_right()
                print("DROITE")

            else:
                fw.turn_straight()
                print("TOUT DROIT")

            bw.speed = SPEED
            bw.forward()

        else:
            print("PAS DE LIGNE -> STOP")
            bw.stop()
            fw.turn_straight()

except KeyboardInterrupt:
    print("Arrêt manuel")

finally:
    bw.stop()
    fw.turn_straight()
    cap.release()
