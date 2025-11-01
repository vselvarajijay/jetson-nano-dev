#!/usr/bin/env python3
import serial, time, json, sys
from datetime import datetime

PORT = sys.argv[1]
BAUD = 115200

STEP = 1.5       # mm per micro-move
SLEEP = 0.01     # slow for smoothness
T_ANGLE = 3.3   # keep same IK branch

def send(ser, x, y, z):
    payload = {"T":1041, "x":x, "y":y, "z":z, "t":T_ANGLE}
    ser.write((json.dumps(payload)+"\n").encode())
    print(f"{datetime.utcnow().isoformat()}Z | {payload}")
    time.sleep(SLEEP)

def move_axis(ser, start, end, axis, pos):
    step = STEP if end>start else -STEP
    v = start
    while abs(v-end) > abs(step):
        v += step
        if axis == "x": pos[0] = v
        elif axis == "y": pos[1] = v
        elif axis == "z": pos[2] = v
        send(ser, *pos)
    pos[{"x":0,"y":1,"z":2}[axis]] = end
    send(ser, *pos)

def go(ser, tx, ty, tz, pos):
    # move X first, then Y, then Z
    move_axis(ser, pos[0], tx, "x", pos)
    move_axis(ser, pos[1], ty, "y", pos)
    move_axis(ser, pos[2], tz, "z", pos)

# grid
xs = [-300, 0, 300]
ys = [-200, 0, 200]
zs = [120, 220, 300]

path = []
for z in zs:
    for j, y in enumerate(ys):
        xorder = xs if j%2==0 else list(reversed(xs))
        for x in xorder:
            path.append((x,y,z))

ser = serial.Serial(PORT, BAUD, timeout=0.1)
time.sleep(2)

print("🏠 Homing…")
ser.write(b'{"T":210,"cmd":1}\n')
time.sleep(2)

pos = [0,0,220]  # approximate current pose
print(f"🎯 visiting {len(path)} cubes (no elbow flips)")

try:
    for (x,y,z) in path:
        print(f"➡️ Cube ({x},{y},{z})")
        go(ser, x,y,z, pos)

    print("✅ done — continuous IK branch")

except KeyboardInterrupt:
    print("🛑 stop — going home")
    go(ser, 0,0,220, pos)
