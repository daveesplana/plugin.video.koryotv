"""
Lightweight IPTV Manager integration helper.

Sends channel/EPG data to the IPTV Manager Kodi addon over a local TCP
socket on the port it supplies as a query-string parameter.
"""

import json
import socket


class IPTVManager:
    """Send data to IPTV Manager via a local TCP socket."""

    def __init__(self, port):
        self.port = int(port)
        self._sock = None

    def connect(self):
        """Open the TCP connection to IPTV Manager."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect(('127.0.0.1', self.port))

    def send(self, data):
        """Serialise *data* as JSON, write it, then close the socket cleanly."""
        if self._sock is None:
            raise RuntimeError('Not connected — call connect() first')
        payload = json.dumps(data).encode('utf-8')
        self._sock.sendall(payload)
        self._sock.close()
        self._sock = None

    def abort(self):
        """Close the socket without sending data (error path)."""
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
