"""Органы чувств: события сервера -> частота стимуляции сенсорных нейронов."""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

MAX_HZ = 200.0


class Senses:
    """Накопитель стимулов: событие добавляет Гц, дальше экспоненциально затухает."""

    def __init__(self, half_life_s: float = 3.0):
        self.half_life_s = half_life_s
        self.level: dict[str, float] = {}

    def add(self, sense: str, hz: float):
        self.level[sense] = min(MAX_HZ, self.level.get(sense, 0.0) + hz)

    def decay(self, dt_s: float):
        k = math.exp(-math.log(2) * dt_s / self.half_life_s)
        self.level = {s: v * k for s, v in self.level.items() if v * k > 1.0}

    def rates(self) -> dict[str, float]:
        return dict(self.level)

    def total(self) -> float:
        return sum(self.level.values())


@dataclass
class Event:
    kind: str  # chat, join, leave, death, advancement
    player: str
    stimuli: list[tuple[str, float]] = field(default_factory=list)
    text: str = ""


# «[12:34:56] [Server thread/INFO]: ...» (vanilla) и «[12:34:56 INFO]: ...» (Paper)
_LOG_PREFIX = re.compile(r"^\[[^\]]*\](?: \[[^\]]*\])?:? ?")
_NAME = r"(?P<p>[A-Za-z0-9_]{2,16})"
_CHAT = re.compile(rf"^(?:\[Not Secure\] )?<{_NAME}> (?P<msg>.*)$")
_JOIN = re.compile(rf"^{_NAME} joined the game$")
_LEAVE = re.compile(rf"^{_NAME} left the game$")
_ADV = re.compile(rf"^{_NAME} has (?:made the advancement|completed the challenge|reached the goal) \[(?P<a>.+)\]$")
_DEATH = re.compile(
    rf"^{_NAME} (?P<how>was |drowned|blew up|fell|hit the ground|burned|went up in flames|walked into|"
    r"tried to swim|died|starved|suffocated|froze|withered|experienced kinetic|discovered the floor|"
    r"went off with a bang|didn't want to live|left the confines)"
)

FOOD_WORDS = ("еда", "торт", "сахар", "мёд", "мед", "яблок", "варень", "cake", "sugar", "honey", "apple", "food", "candy")
RUDE_WORDS = ("мухобой", "тупая", "дура", "убью", "прихлоп", "фу ", "swatter", "stupid", "kill", "die")
FLY_WORDS = ("муха", "мух", "fly", "бзз", "bzz")


def strip_log_prefix(line: str) -> str:
    return _LOG_PREFIX.sub("", line.rstrip("\r\n"), count=1)


def parse_line(line: str) -> Event | None:
    msg = strip_log_prefix(line)
    if "Rcon" in msg[:30]:
        return None  # эхо собственных команд мухи
    if m := _CHAT.match(msg):
        text = m["msg"]
        low = text.lower()
        loud = 1.0 + min(2.0, text.count("!") * 0.3 + (1.0 if text.isupper() and len(text) > 3 else 0.0))
        stim = [("auditory", 40.0 * loud)]
        if any(w in low for w in FOOD_WORDS):
            stim.append(("sugar", 120.0))
        rude = any(w in low for w in RUDE_WORDS)
        if rude:
            stim += [("bitter", 200.0), ("looming", 40.0)]
        elif any(w in low for w in FLY_WORDS):
            stim.append(("touch", 60.0))  # к мухе обратились по-доброму — щекотно
        return Event("chat", m["p"], stim, text)
    if m := _JOIN.match(msg):
        return Event("join", m["p"], [("pheromone", 100.0), ("looming", 60.0)])
    if m := _LEAVE.match(msg):
        return Event("leave", m["p"], [("wind", 40.0)])
    if m := _ADV.match(msg):
        return Event("advancement", m["p"], [("sugar", 150.0)], m["a"])
    if m := _DEATH.match(msg):
        low = msg.lower()
        stim = [("bitter", 200.0)]
        if any(w in low for w in ("blew up", "blown up", "bang", "lightning", "fireball")):
            stim += [("auditory", 150.0), ("co2", 80.0)]
        if any(w in low for w in ("fell", "hit the ground", "floor", "kinetic")):
            stim.append(("wind", 150.0))
        if any(w in low for w in ("lava", "burn", "flames", "fire")):
            stim.append(("heat", 120.0))
        if "drown" in low:
            stim.append(("humidity", 120.0))
        return Event("death", m["p"], stim, msg)
    return None


class LogTailer:
    """Читает новые строки из latest.log, переживает ротацию лога."""

    def __init__(self, path: str | Path, from_end: bool = True):
        self.path = Path(path)
        self._pos = None if from_end else 0
        self._inode = None
        self._buf = ""

    def poll(self) -> list[str]:
        try:
            st = os.stat(self.path)
        except FileNotFoundError:
            return []
        if self._inode != st.st_ino or (self._pos or 0) > st.st_size:
            first_open = self._inode is None
            self._inode = st.st_ino
            self._pos = st.st_size if (first_open and self._pos is None) else 0
            self._buf = ""
        if st.st_size == self._pos:
            return []
        with open(self.path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(self._pos)
            chunk = f.read()
            self._pos = f.tell()
        data = self._buf + chunk
        lines = data.split("\n")
        self._buf = lines.pop()  # недописанная строка
        return [ln for ln in lines if ln.strip()]
