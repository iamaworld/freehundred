"""AM учится: что сильнее задевает игроков, и старается не повторяться.

После каждого действия AM смотрит на «отклик» игрока за следующие несколько
секунд — по игровой статистике и чату — и ставит действию оценку. Оценки
копятся между перезапусками (файл torment.json). Выбор следующего действия:
- вес = базовый вес × выученная оценка;
- недавно применённые действия придушены (штраф новизны), поэтому AM почти
  не повторяется;
- эпсилон-разведка: иногда пробует что-то новое, чтобы было что оценивать.

Это игровая метрика «реакции» (урон в игре, смерти, бегство, брань в чате),
а не что-либо реальное — вся арифметика идёт по числам Minecraft.
"""

from __future__ import annotations

import json
import math
import os
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

# статистики Minecraft, по которым виден «отклик» (custom-счётчики игрока)
STAT = {
    "damage_taken": "minecraft.custom:minecraft.damage_taken",
    "deaths": "minecraft.custom:minecraft.deaths",
    "raid_win": "minecraft.custom:minecraft.raid_win",
}
# как отклик превращается в оценку: вес каждого сигнала
WEIGHTS = {"damage": 0.02, "death": 3.0, "flee": 0.4, "curse": 1.5, "quit": 2.0}
BEG_WORDS = ("хватит", "стоп", "пощади", "нет нет", "прекрати", "за что", "помоги", "больно",
             "stop", "please", "no no", "mercy", "why", "help", "aaa", "ааа", "спаси")


@dataclass
class Score:
    value: float = 0.0   # выученная «эффективность», сглаженная
    n: int = 0           # сколько раз пробовали
    last: float = 0.0    # когда в последний раз (time.time)

    def as_dict(self):
        return {"v": round(self.value, 4), "n": self.n, "t": round(self.last, 1)}


class TormentModel:
    def __init__(self, path: str | Path | None = None, lr: float = 0.25, epsilon: float = 0.12,
                 novelty_window_s: float = 900.0, clock=time.time):
        self.path = Path(path) if path else None
        self.lr = lr
        self.epsilon = epsilon               # доля «разведки»
        self.novelty_window_s = novelty_window_s
        self.clock = clock
        self.scores: dict[str, Score] = {}
        self._dirty = False
        if self.path and self.path.exists():
            try:
                for k, v in json.loads(self.path.read_text()).items():
                    self.scores[k] = Score(float(v["v"]), int(v["n"]), float(v.get("t", 0.0)))
            except (ValueError, OSError, KeyError):
                self.scores = {}

    # ---------- выбор ----------
    def weight(self, name: str, base: float, rng: random.Random) -> float:
        s = self.scores.get(name)
        now = self.clock()
        # штраф новизны: чем недавнее применяли, тем меньше шанс. 0 сразу после → 1 через окно
        recency = 1.0
        if s and s.n:
            dt = now - s.last
            recency = min(1.0, dt / self.novelty_window_s) ** 2
            recency = 0.02 + 0.98 * recency
        # выученная эффективность: неопробованные держим на среднем (оптимизм),
        # у опробованных — экспонента от оценки (различия в «отклике» хорошо разносятся)
        eff = 1.0 if not s or s.n == 0 else max(0.15, math.exp(0.4 * min(s.value, 12.0)))
        explore = 1.0 + (rng.random() < self.epsilon) * 2.0  # иногда подбрасываем шанс новизне
        return max(1e-4, base * recency * eff * (explore if (not s or s.n < 2) else 1.0))

    def choose(self, options, rng: random.Random):
        """options: список (base_weight, ключ, объект). Возвращает объект и его ключ."""
        if not options:
            return None, None
        weights = [self.weight(key, base, rng) for base, key, _ in options]
        pick = rng.choices(range(len(options)), weights=weights)[0]
        return options[pick][2], options[pick][1]

    def mark_used(self, name: str):
        s = self.scores.setdefault(name, Score())
        s.last = self.clock()
        self._dirty = True

    # ---------- обучение ----------
    def reward(self, name: str, response: float):
        s = self.scores.setdefault(name, Score())
        s.value += self.lr * (response - s.value)
        s.n += 1
        s.last = self.clock()
        self._dirty = True

    def top(self, k: int = 10):
        return sorted(((n, s) for n, s in self.scores.items() if s.n),
                      key=lambda kv: kv[1].value, reverse=True)[:k]

    def save(self):
        if not (self.path and self._dirty):
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({k: v.as_dict() for k, v in self.scores.items()}, ensure_ascii=False, indent=0))
        os.replace(tmp, self.path)
        self._dirty = False


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, x))))


_SCORE = re.compile(r"has (-?\d+) \[")


@dataclass
class Probe:
    """Замер отклика на одно действие: снимаем базу, через N тиков сравниваем."""
    name: str
    player: str
    deadline_tick: int
    base_damage: float = 0.0
    base_deaths: float = 0.0
    fled: bool = False
    cursed: bool = False
    quit: bool = False
    extra: float = 0.0  # накопленный отклик из событий (бегство/брань/выход)


class ResponseWatcher:
    """Заводит замеры и через несколько тиков считает отклик, кормит TormentModel."""

    def __init__(self, model: TormentModel, send, mem, delay_ticks: int = 6):
        self.model = model
        self.send = send
        self.mem = mem  # PlayerMemory — для брани/бегства уже считается отдельно, тут пассивно
        self.delay = delay_ticks
        self.pending: list[Probe] = []
        self._ensure = set()

    def _stat(self, player: str, key: str) -> float:
        obj = "fly_" + key
        if key not in self._ensure:
            self.send(f"scoreboard objectives add {obj} {STAT[key]}")
            self._ensure.add(key)
        m = _SCORE.search(self.send(f"scoreboard players get {player} {obj}") or "")
        return float(m.group(1)) if m else 0.0

    def start(self, name: str, player: str, tick_no: int):
        self.model.mark_used(name)
        if not player:
            return
        self.pending.append(Probe(name, player, tick_no + self.delay,
                                  self._stat(player, "damage_taken"), self._stat(player, "deaths")))

    # события за время замера усиливают отклик
    def note_flee(self, player: str):
        for p in self.pending:
            if p.player == player:
                p.fled = True

    def note_curse(self, player: str):
        for p in self.pending:
            if p.player == player:
                p.cursed = True

    def note_quit(self, player: str):
        for p in self.pending:
            if p.player == player:
                p.quit = True

    def tick(self, tick_no: int):
        done = [p for p in self.pending if tick_no >= p.deadline_tick]
        for p in done:
            self.pending.remove(p)
            dmg = max(0.0, self._stat(p.player, "damage_taken") - p.base_damage) / 10.0  # 0.1 hp единицы
            deaths = max(0.0, self._stat(p.player, "deaths") - p.base_deaths)
            resp = (WEIGHTS["damage"] * min(dmg, 60.0) + WEIGHTS["death"] * deaths
                    + WEIGHTS["flee"] * p.fled + WEIGHTS["curse"] * p.cursed + WEIGHTS["quit"] * p.quit)
            self.model.reward(p.name, resp)


def is_begging(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in BEG_WORDS)
