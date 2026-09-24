"""Память мухи об игроках: ассоциативное обучение «игрок → сладко/горько».

У настоящей мухи так учатся грибовидные тела: запах, совпавший с сахаром
(дофамин от PAM-нейронов), потом сам вызывает подход, а совпавший с ударом
тока (PPL1) — избегание. Здесь «запах» — это игрок: кто кормит, того муха
любит, кто обижает — того боится и ненавидит. Одно появление игрока потом
само возбуждает сахарные или горькие нейроны (условный рефлекс).
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path


class PlayerMemory:
    def __init__(self, path: str | Path | None = None, learning_rate: float = 0.15, forget_per_hour: float = 0.05):
        self.path = Path(path) if path else None
        self.lr = learning_rate
        self.forget_per_hour = forget_per_hour
        self.valence: dict[str, float] = {}
        self.meta: dict[str, dict[str, int]] = {}  # счётчики: визиты, смерти, игры...
        self._dirty = False
        if self.path and self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                if "valence" in data:  # новый формат
                    self.valence = {k: float(v) for k, v in data["valence"].items()}
                    self.meta = {k: dict(v) for k, v in data.get("meta", {}).items()}
                else:  # старый: {игрок: отношение}
                    self.valence = {k: float(v) for k, v in data.items()}
            except (ValueError, OSError, AttributeError):
                self.valence, self.meta = {}, {}

    def count(self, player: str, key: str, add: int = 1) -> int:
        """Увеличить счётчик (визиты, смерти, игры) и вернуть новое значение."""
        m = self.meta.setdefault(player, {})
        m[key] = m.get(key, 0) + add
        self._dirty = True
        return m[key]

    def counter(self, player: str, key: str) -> int:
        return self.meta.get(player, {}).get(key, 0)

    def get(self, player: str) -> float:
        return self.valence.get(player, 0.0)

    def learn(self, player: str, sugar_hz: float = 0.0, bitter_hz: float = 0.0):
        """Сдвигает отношение к игроку по сладкому/горькому, пришедшему «от него»."""
        if not player or (sugar_hz == 0 and bitter_hz == 0):
            return
        v = self.get(player)
        delta = self.lr * (sugar_hz - bitter_hz) / 200.0
        # насыщение: чем сильнее уже отношение, тем меньше сдвиг в ту же сторону
        delta *= 1.0 - abs(v) if (delta > 0) == (v > 0) else 1.0
        self.valence[player] = max(-1.0, min(1.0, v + delta))
        self._dirty = True

    def conditioned(self, player: str, gain: float = 120.0) -> list[tuple[str, float]]:
        """Условный рефлекс: что муха «чувствует», просто увидев игрока."""
        v = self.get(player)
        if abs(v) < 0.1:
            return []
        return [("sugar", v * gain)] if v > 0 else [("bitter", -v * gain)]

    def forget(self, dt_s: float):
        k = max(0.0, 1.0 - self.forget_per_hour * dt_s / 3600.0)
        if self.valence:
            self.valence = {p: v * k for p, v in self.valence.items() if abs(v * k) > 0.01}

    def pick(self, players: list[str], prefer: str, rng: random.Random) -> str | None:
        """prefer='friend' — чаще любимых, 'enemy' — чаще врагов, иначе случайно."""
        if not players:
            return None
        if prefer not in ("friend", "enemy"):
            return rng.choice(players)
        sign = 1.0 if prefer == "friend" else -1.0
        weights = [max(0.05, 1.0 + 3.0 * sign * self.get(p)) for p in players]
        return rng.choices(players, weights=weights)[0]

    def describe(self, player: str) -> str:
        v = self.get(player)
        if v > 0.6:
            return "лучший друг, кормилец"
        if v > 0.2:
            return "хороший человек"
        if v < -0.6:
            return "ВРАГ. мухобойщик"
        if v < -0.2:
            return "подозрительный тип"
        return "пока не знаю тебя"

    def save(self):
        if not (self.path and self._dirty):
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"valence": self.valence, "meta": self.meta}, ensure_ascii=False, indent=1))
        os.replace(tmp, self.path)
        self._dirty = False
