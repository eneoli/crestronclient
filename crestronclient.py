import time
import threading
import socket


class CIPMessage:
    def __init__(self, msgType, body):
        self.type = msgType
        self.length = len(body)
        self.payload = bytearray(map(lambda x: ord(chr(x % 256)), body))

    def create(self):
        msg = bytearray(3)
        msg[0] = self.type
        msg[1] = self.length >> 8
        msg[2] = self.length & 0xFF
        return msg + self.payload


class HeartbeatThread(threading.Thread):
    def __init__(self, parent):
        threading.Thread.__init__(self)
        self._stopit = threading.Event()
        self.parent = parent
        self.counter = 0

    def stop(self):
        self._stopit.set()

    def run(self):
        while 1:
            if self.parent.send_heartbeat() == 0:
                break
            while self.counter < 5 and not self._stopit.isSet():
                time.sleep(1)
                self.counter += 1
            self.counter = 0
            if self._stopit.isSet():
                break


class CrestronClient:
    button_mapping = {}

    def __init__(self, ip, port=41794, pid=0x03):
        self.pid = pid
        self.digitalCallbacks = []
        self.analogCallbacks = []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((ip, port))
        self.sock.settimeout(.1)
        self.heartbeat = HeartbeatThread(self)
        self.heartbeat.start()
        self.poll()  # read first data and send connection message

    def poll(self):
        while True:
            try:
                self.receive_data()
            except:
                break

    def send_message(self, cip):
        try:
            sent = self.sock.send(cip.create())
            return sent
        except:
            return 0

    def addDigitalCallback(self, fun):
        self.digitalCallbacks.append(fun)

    def addAnalogCallback(self, fun):
        self.analogCallbacks.append(fun)

    def destroy_callback(self):
        self.heartbeat.stop()
        self.sock.shutdown(2)

    def send_digital(self, join, v):
        join = join - 1
        print('join')
        print((join >> 8) | 0x80)
        if v is True:
            self.send_message(CIPMessage(0x05, [0x00, 0x00, 0x03, 0x27, join & 0xFF, join >> 8]))
        else:
            self.send_message(CIPMessage(0x05, [0x00, 0x00, 0x03, 0x27, join & 0xFF, (join >> 8) | 0x80] ))

    def send_analog(self, join, v):
        join = join - 1
        value = int(v)
        self.send_message(CIPMessage(0x05, [0x00, 0x00, 0x05, 0x14, join >> 8, join & 0xFF, value >> 8, value & 0xFF]))

    def send_heartbeat(self):
        return self.send_message(CIPMessage(0x0D, [0x00, 0x00]))

    def send_updaterequest(self):
        return self.send_message(CIPMessage(0x05, [0x00, 0x00, 0x02, 0x03, 0x00]))

    def handle_feedback(self, cip):
        if cip.type == 0x02:  # IP registration
            if cip.payload[0] == 0xFF and cip.payload[1] == 0xFF and cip.payload[2] == 0x02:
                raise RuntimeError("Crestron ID bad")
            elif cip.length == 4:
                self.send_heartbeat()
                self.send_updaterequest()
        elif cip.type == 0x05:  # Data
            self.handle_data(cip)
        elif cip.type == 0x03:  # Program stop or disconnect
            pass
        elif cip.type == 0x0D:  # Heartbeat disconnect
            pass
        elif cip.type == 0x0E:  # Heartbeat ack
            pass
        elif cip.type == 0x0F:
            if cip.length == 1 and cip.payload[0] == 0x02:  # connection start
                self.send_message(CIPMessage(0x01, [0x7F, 0x00, 0x00, 0x01, 0x00, self.pid, 0x40]))  # 0x04 is the ID
            else:
                raise RuntimeError("Bad registration")

    def handle_data(self, cip):
        value = 0
        join = 0
        jType = cip.payload[3]
        if jType == 0x00:  # Digital
            value = 0
            if cip.payload[5] & 0x80 == 0:
                value = 1
            join = cip.payload[5] & 0x7F
            join = (join << 8) + (cip.payload[4] & 0xFF) + 1
        elif jType == 0x01:  # Analog
            if cip.payload[2] == 0x04:  # Join < 256
                join = (cip.payload[4] & 0xFF) + 1
                value = cip.payload[5] & 0x00FF
                value = (value << 8) + (cip.payload[6] & 0xFF)
            elif cip.payload[2] == 0x05:
                join = cip.payload[4] & 0xFF
                join = (join << 8) + (cip.payload[5] & 0xFF) + 1
                value = cip.payload[6] & 0x00FF
                value = (value << 8) + (cip.payload[7] & 0xFF)
        elif jType == 0x02:  # Serial
            pass
        elif jType == 0x03:  # Update request confirmation
            pass
        if jType == 0x00:  # digital
            for f in self.digitalCallbacks:
                f(join, value)
        elif jType == 0x01:  # analog
            for f in self.analogCallbacks:
                f(join, value)

    def receive_data(self):
        buf = bytearray(b" " * 1024)
        rx = self.sock.recv_into(buf, 1024)
        index = 0
        while index < rx:
            t = buf[index]
            l = buf[index + 1] << 8
            l += buf[index + 2]
            index += 3
            self.handle_feedback(CIPMessage(t, buf[index:index + l]))
            index += l
        return True
