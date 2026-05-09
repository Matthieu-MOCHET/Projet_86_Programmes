from picar import back_wheels, back_wheels
import time
bw = back_wheels.Back_Wheels()
bw.speed = 80
print("AVANCE")
bw.forward()
time.sleep(5)
bw.stop()
print("STOP")
