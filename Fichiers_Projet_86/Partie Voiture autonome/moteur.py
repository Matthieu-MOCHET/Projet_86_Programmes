from picar import front_wheels, back_wheels
import time

fw = front_wheels.Front_Wheels()
bw = back_wheels.Back_Wheels()

fw.ready()
bw.ready()

bw.speed = 30
fw.turn_straight()

print("avance")
bw.forward()
time.sleep(3)

print("stop")
bw.stop()
