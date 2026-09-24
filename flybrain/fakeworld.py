"""Игрушечный «сервер Minecraft» для запуска без сервера и для тестов.

Отвечает на те команды, которые муха задаёт консоли (list, time, data get,
summon глаза, tp), и изображает игроков: они бродят, иногда подходят к глазу,
бьют его или кормят с руки.
"""

from __future__ import annotations

import random
import re
import time

from .body import uuid_ints

_TP = re.compile(r"^execute at (\w+) run tp @e\[tag=(flyeye|flyhitbox),limit=1\] ~(-?[\d.]+) ~(-?[\d.]+) ~(-?[\d.]+)$")
_SUMMON = re.compile(r"^execute at (\w+) run summon minecraft:(item_display|interaction) ")
_GET = re.compile(r"^data get entity (\S+) (\S+)$")


class FakeWorld:
    def __init__(self, players=("Steve", "Alex"), seed: int | None = None, event_rate: float = 1.0):
        self.rng = random.Random(seed)
        self.event_rate = event_rate
        self.players = {p: [self.rng.uniform(-5, 5), 64.0, self.rng.uniform(-5, 5)] for p in players}
        self.uuids = {p: uuid_ints(self.rng.getrandbits(128)) for p in players}
        self.items = {p: None for p in players}
        self.eye = None
        self.hitbox = None
        self.attack = self.interaction = None
        self.gametime = 1000
        self._t0 = time.time()
        self.log: list[str] = []

    # «мир живёт» между тиками мухи
    def step(self):
        self.gametime += 20
        r = self.rng.random
        for name, pos in self.players.items():
            if self.eye and r() < 0.15 * self.event_rate:  # идёт к глазу
                for i in (0, 2):
                    pos[i] += (self.eye[i] - pos[i]) * 0.5
            else:
                pos[0] += self.rng.uniform(-1.5, 1.5)
                pos[2] += self.rng.uniform(-1.5, 1.5)
            if self.hitbox and r() < 0.03 * self.event_rate:
                self.attack = (name, self.gametime)
            if self.hitbox and r() < 0.04 * self.event_rate:
                self.items[name] = self.rng.choice(["sugar", "cake", "rotten_flesh", None, "stone"])
                self.interaction = (name, self.gametime)

    def command(self, cmd: str) -> str:
        self.log.append(cmd)
        if cmd == "list":
            return f"There are {len(self.players)} of a max of 20 players online: {', '.join(self.players)}"
        if cmd == "time query daytime":
            return f"The time is {int(6000 + (time.time() - self._t0) * 20) % 24000}"
        if cmd == "seed":
            return "Seed: [-4172144997902289642]"
        if cmd.startswith("kill @e[tag=flybody]"):
            self.eye = self.hitbox = None
            return "Killed 2 entities"
        if m := _SUMMON.match(cmd):
            p = self.players.get(m.group(1))
            if p:
                if m.group(2) == "item_display":
                    self.eye = [p[0], p[1] + 6, p[2]]
                else:
                    self.hitbox = [p[0], p[1] + 3, p[2]]
            return "Summoned new entity"
        if m := _TP.match(cmd):
            p = self.players.get(m.group(1))
            if p:
                new = [p[0] + float(m.group(3)), p[1] + float(m.group(4)), p[2] + float(m.group(5))]
                if m.group(2) == "flyeye" and self.eye:
                    self.eye = new
                elif m.group(2) == "flyhitbox" and self.hitbox:
                    self.hitbox = new
            return "Teleported"
        if m := _GET.match(cmd):
            return self._get(m.group(1), m.group(2))
        if m := re.match(r"^clear (\w+) minecraft:(\w+) 1$", cmd):
            if self.items.get(m.group(1)) == m.group(2):
                self.items[m.group(1)] = None
                return f"Removed 1 item(s) from player {m.group(1)}"
        return ""

    def _get(self, target: str, path: str) -> str:
        if target == "@e[tag=flyeye,limit=1]":
            if not self.eye:
                return "No entity was found"
            return f"Item Display has the following entity data: [{self.eye[0]}d, {self.eye[1]}d, {self.eye[2]}d]"
        if target == "@e[tag=flyhitbox,limit=1]":
            if not self.hitbox:
                return "No entity was found"
            ev = self.attack if path == "attack" else self.interaction
            if not ev:
                return f"Found no elements matching {path}"
            u = self.uuids[ev[0]]
            return f"Interaction has the following entity data: {{player: [I; {u[0]}, {u[1]}, {u[2]}, {u[3]}], timestamp: {ev[1]}L}}"
        if target in self.players:
            p = self.players[target]
            if path == "Pos":
                return f"{target} has the following entity data: [{p[0]}d, {p[1]}d, {p[2]}d]"
            if path == "UUID":
                u = self.uuids[target]
                return f"{target} has the following entity data: [I; {u[0]}, {u[1]}, {u[2]}, {u[3]}]"
            if path == "Health":
                return f"{target} has the following entity data: 20.0f"
            if path == "playerGameType":
                return f"{target} has the following entity data: 0"
            if path == "SelectedItem.id":
                it = self.items.get(target)
                return f'{target} has the following entity data: "minecraft:{it}"' if it else "Found no elements matching SelectedItem.id"
        return "No entity was found"
