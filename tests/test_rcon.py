import socket
import struct
import threading

import pytest

from flybrain.rcon import Rcon, RconError


def _serve(sock, password, log):
    conn, _ = sock.accept()
    with conn:
        while True:
            head = conn.recv(4)
            if not head:
                return
            (n,) = struct.unpack("<i", head)
            data = b""
            while len(data) < n:
                data += conn.recv(n - len(data))
            rid, ptype = struct.unpack("<ii", data[:8])
            body = data[8:-2].decode()
            if ptype == 3:
                rid = rid if body == password else -1
                reply = ""
            else:
                log.append(body)
                reply = f"ok: {body}"
            out = struct.pack("<ii", rid, 2 if ptype == 3 else 0) + reply.encode() + b"\x00\x00"
            conn.sendall(struct.pack("<i", len(out)) + out)


@pytest.fixture
def server():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    log = []
    threading.Thread(target=_serve, args=(sock, "secret", log), daemon=True).start()
    yield sock.getsockname()[1], log
    sock.close()


def test_login_and_commands(server):
    port, log = server
    r = Rcon("127.0.0.1", port, "secret")
    r.connect()
    assert r.command("say бзз") == "ok: say бзз"
    assert r.command("list") == "ok: list"
    assert log == ["say бзз", "list"]
    r.close()


def test_wrong_password(server):
    port, _ = server
    with pytest.raises(RconError):
        Rcon("127.0.0.1", port, "nope").connect()
