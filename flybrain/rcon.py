"""Консоль сервера: RCON-клиент и «сухая» консоль для запуска без сервера."""

from __future__ import annotations

import socket
import struct
import sys
import time

_LOGIN, _COMMAND, _RESPONSE = 3, 2, 0


class RconError(RuntimeError):
    pass


class Rcon:
    """Минимальный клиент протокола Source RCON (им пользуется Minecraft)."""

    def __init__(self, host: str, port: int, password: str, timeout: float = 5.0):
        self.host, self.port, self.password, self.timeout = host, port, password, timeout
        self._sock: socket.socket | None = None
        self._req = 0

    def connect(self):
        self.close()
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        rid = self._send(_LOGIN, self.password)
        got_id, _, _ = self._recv()
        if got_id == -1 or got_id != rid:
            self.close()
            raise RconError("неверный RCON-пароль")

    def close(self):
        if self._sock:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def command(self, cmd: str) -> str:
        if self._sock is None:
            self.connect()
        try:
            self._send(_COMMAND, cmd)
            _, _, body = self._recv()
            return body
        except OSError:
            self.close()
            raise

    def _send(self, ptype: int, body: str) -> int:
        self._req = (self._req % 2_000_000_000) + 1
        payload = struct.pack("<ii", self._req, ptype) + body.encode("utf-8") + b"\x00\x00"
        if len(payload) > 1446:
            raise RconError("команда длиннее лимита RCON (1446 байт)")
        self._sock.sendall(struct.pack("<i", len(payload)) + payload)
        return self._req

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("RCON: соединение закрыто")
            buf += chunk
        return buf

    def _recv(self) -> tuple[int, int, str]:
        (length,) = struct.unpack("<i", self._recv_exact(4))
        data = self._recv_exact(length)
        rid, ptype = struct.unpack("<ii", data[:8])
        return rid, ptype, data[8:-2].decode("utf-8", errors="replace")


class DryConsole:
    """Ничего не отправляет — печатает команды. Для запуска без сервера."""

    def __init__(self, players: list[str] | None = None, out=None):
        self.players = players or ["Steve", "Alex"]
        self.out = out or sys.stdout
        self.sent: list[str] = []
        self._t0 = time.time()

    def command(self, cmd: str) -> str:
        self.sent.append(cmd)
        if cmd == "list":
            return f"There are {len(self.players)} of a max of 20 players online: {', '.join(self.players)}"
        if cmd == "time query daytime":
            return f"The time is {int((time.time() - self._t0) * 20 + 1000) % 24000}"
        print(f"  > /{cmd}", file=self.out, flush=True)
        return ""

    def close(self):
        pass
