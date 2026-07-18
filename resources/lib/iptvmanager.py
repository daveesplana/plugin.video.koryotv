import json
import socket

class IPTVManager:
    def __init__(self, port):
        self.port = int(port)
        self._sock = None

    def connect(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect(('127.0.0.1', self.port))

    def send(self, data):
        if self._sock is None:
            raise RuntimeError('Not connected — call connect() first')
        payload = json.dumps(data).encode('utf-8')
        self._sock.sendall(payload)
        self._sock.close()
        self._sock = None

    def abort(self):
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
