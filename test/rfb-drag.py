# A middle-drag across the middle of the screen, sent the way a VNC viewer sends it:
# RFB pointer events, absolute positions only. Run by run.sh inside the Blender
# container (stdlib only - the image has no VNC client), against wayvnc's own address.
import socket
import struct
import sys
import time

host, port = sys.argv[1], int(sys.argv[2])
MIDDLE = 2  # RFB button mask: 1 left, 2 middle, 4 right

s = socket.create_connection((host, port), 5)


def rx(n: int) -> bytes:
    b = b""
    while len(b) < n:
        c = s.recv(n - len(b))
        assert c, "server closed the connection"
        b += c
    return b


rx(12)
s.sendall(b"RFB 003.008\n")
types = rx(rx(1)[0])
assert 1 in types, f"no 'None' security type offered: {list(types)}"
s.sendall(b"\x01")
assert struct.unpack(">I", rx(4))[0] == 0, "security handshake failed"
s.sendall(b"\x01")  # ClientInit: shared
w, h = struct.unpack(">HH", rx(4))
rx(16)
rx(struct.unpack(">I", rx(4))[0])


def pointer(mask: int, x: int, y: int) -> None:
    s.sendall(struct.pack(">BBHH", 5, mask, x, y))


cx, cy = w // 2, h // 2
pointer(0, cx, cy)
time.sleep(0.3)
pointer(MIDDLE, cx, cy)
time.sleep(0.1)
for i in range(1, 21):
    pointer(MIDDLE, cx + 15 * i, cy)
    time.sleep(0.03)
time.sleep(0.1)
pointer(0, cx + 300, cy)
time.sleep(0.3)
s.close()
