import time
import picar
from picar import front_wheels, back_wheels

picar.setup()

fw = front_wheels.Front_Wheels()
bw = back_wheels.Back_Wheels()

fw.turn(90)
bw.speed = 30

print("Avance")
bw.forward()
time.sleep(2)

print("Stop")
bw.stop()

