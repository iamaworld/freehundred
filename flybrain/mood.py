"""Настроение из частот нисходящих нейронов + режим сна."""

from __future__ import annotations

import math
from dataclasses import dataclass

MOOD_RU = {
    "feeding": "СЫТОСТЬ",
    "escape": "ПАНИКА",
    "grooming": "ЧИСТОПЛОТНОСТЬ",
    "aversion": "ЗЛОСТЬ",
    "curious": "ЛЮБОПЫТСТВО",
    "alert": "ТРЕВОГА",
    "bored": "СКУКА",
    "asleep": "СОН",
}


@dataclass
class Mood:
    name: str
    intensity: float  # 0..1
    scores: dict[str, float]

    @property
    def label(self) -> str:
        return MOOD_RU.get(self.name, self.name)


class MoodEngine:
    """Частоты групп DN -> настроение.

    Привыкание: пока одна эмоция держится, она устаёт (как адаптация
    нейронов) и уступает место другим — муха не залипает в одном состоянии.
    """

    def __init__(self, reference_hz: dict[str, float], smoothing: float = 0.5, bored_below: float = 0.1,
                 gains: dict[str, float] | None = None, habituation: float = 0.0, recovery: float = 0.9,
                 stickiness: float = 0.15, min_hold: int = 4, override: float = 1.5):
        self.ref = reference_hz
        self.gains = gains or {}  # усиление отдельных настроений (ненависть в режиме am)
        self.smoothing = smoothing  # доля старого значения в EMA
        self.bored_below = bored_below
        self.habituation = habituation
        self.recovery = recovery  # во сколько раз спадает усталость неактивных эмоций за тик
        self.stickiness = stickiness  # бонус текущей эмоции, чтобы не дёргалась каждый тик
        self.current: str | None = None
        self.min_hold = min_hold  # минимум тиков в одной эмоции...
        self.override = override  # ...если новая не сильнее в столько раз (резкий испуг пробьётся)
        self._held = 0
        self.scores = {k: 0.0 for k in reference_hz}
        self.fatigue = {k: 0.0 for k in reference_hz}

    def update(self, rates: dict[str, float]) -> Mood:
        a = self.smoothing
        for k, ref in self.ref.items():
            g = self.gains.get(k, 1.0)
            self.scores[k] = a * self.scores[k] + (1 - a) * g * rates.get(k, 0.0) / ref
        felt = {k: v * (1.0 - self.fatigue[k]) * (1.0 + self.stickiness * (k == self.current))
                for k, v in self.scores.items()}
        name, top = max(felt.items(), key=lambda kv: kv[1])
        cur = self.current
        if (cur and name != cur and self._held < self.min_hold and felt[cur] >= self.bored_below
                and top < felt[cur] * self.override):
            name, top = cur, felt[cur]
        self._held = self._held + 1 if name == cur else 0
        self.current = name if top >= self.bored_below else None
        for k in self.fatigue:
            if k == name and top >= self.bored_below:
                self.fatigue[k] = min(0.85, self.fatigue[k] + self.habituation)
            else:
                self.fatigue[k] *= self.recovery
        if top < self.bored_below:
            return Mood("bored", 0.0, felt)
        return Mood(name, 1.0 - math.exp(-1.5 * top), felt)

    def reset(self):
        self.scores = {k: 0.0 for k in self.ref}
        self.fatigue = {k: 0.0 for k in self.ref}
        self.current = None
        self._held = 0


class SleepCycle:
    """Когда муха засыпает и просыпается.

    Засыпает, если (а) мозг долго гудит сам по себе без входа — застрявшая
    реверберация, или (б) ночь и вокруг тихо. Будит сильный стимул или утро.
    """

    def __init__(
        self,
        reverb_active: int = 300,
        reverb_ticks: int = 15,
        quiet_drive_hz: float = 30.0,
        night_quiet_ticks: int = 20,
        wake_drive_hz: float = 250.0,
        min_sleep_ticks: int = 30,
    ):
        self.reverb_active = reverb_active
        self.reverb_ticks = reverb_ticks
        self.quiet_drive_hz = quiet_drive_hz
        self.night_quiet_ticks = night_quiet_ticks
        self.wake_drive_hz = wake_drive_hz
        self.min_sleep_ticks = min_sleep_ticks
        self.asleep = False
        self._reverb = 0
        self._quiet = 0
        self._slept = 0

    def observe_awake(self, drive: float, active: int, night: bool) -> bool:
        """Возвращает True, если пора засыпать."""
        quiet = drive < self.quiet_drive_hz
        self._quiet = self._quiet + 1 if quiet else 0
        self._reverb = self._reverb + 1 if (quiet and active > self.reverb_active) else 0
        if self._reverb >= self.reverb_ticks or (night and self._quiet >= self.night_quiet_ticks):
            self.asleep, self._slept, self._reverb, self._quiet = True, 0, 0, 0
            return True
        return False

    def observe_asleep(self, drive: float, night: bool) -> bool:
        """Возвращает True, если пора просыпаться."""
        self._slept += 1
        if drive >= self.wake_drive_hz or (not night and self._slept >= self.min_sleep_ticks):
            self.asleep = False
            return True
        return False
