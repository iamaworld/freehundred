"""Консоль сервера: RCON-клиент и «сухая» консоль для запуска без сервера."""

from __future__ import annotations

import socket
import struct
import sys

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
    """Ничего не отправляет на сервер — печатает команды мухи, а на вопросы
    отвечает фейковый мир (fakeworld.FakeWorld). Для запуска без сервера."""

    QUIET = ("list", "time query", "data get", "execute at @e[tag=fly", "bossbar", "scoreboard")

    def __init__(self, players: list[str] | None = None, out=None, world=None, seed=None, events: bool = True):
        from .fakeworld import FakeWorld

        self.world = world or FakeWorld(players or ["Steve", "Alex"], seed=seed, event_rate=1.0 if events else 0.0)
        self.players = list(self.world.players)
        self.out = out or sys.stdout
        self.sent: list[str] = []

    def command(self, cmd: str) -> str:
        self.sent.append(cmd)
        reply = self.world.command(cmd)
        if not cmd.startswith(self.QUIET) and " run tp @e[tag=fly" not in cmd:
            print(f"  > /{cmd}", file=self.out, flush=True)
        return reply

    def tick(self):
        self.world.step()

    def close(self):
        pass
