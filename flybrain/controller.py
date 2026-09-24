"""Главный цикл: чувства -> мозг -> настроение -> команды в консоль."""

from __future__ import annotations

import heapq
import os
import random
import re
import sys
import time
from dataclasses import dataclass, fields

from .commands import MOOD_COLOR, choose_action, tellraw
from .mood import Mood, MoodEngine, SleepCycle
from .safety import safe_check
from .senses import LogTailer, Senses, parse_line


@dataclass
class Config:
    sim_ms: float = 100.0  # сколько мушиного времени считать за тик
    tick_s: float = 1.0  # минимальная длина тика в реальном времени
    act_base: float = 0.05  # шанс действия за тик при нулевой интенсивности
    act_gain: float = 0.5  # + интенсивность * act_gain
    min_action_gap_s: float = 4.0
    max_actions_per_min: int = 8
    bored_act_prob: float = 0.03
    spontaneous_prob: float = 0.08  # шанс «случайной мысли» за тик
    poll_every_ticks: int = 10  # как часто спрашивать list / time
    stim_half_life_s: float = 3.0
    bossbar: bool = True

    @classmethod
    def from_env(cls, prefix: str = "FLY_") -> "Config":
        kw = {}
        for f in fields(cls):
            val = os.environ.get(prefix + f.name.upper())
            if val is not None:
                kw[f.name] = val.lower() in ("1", "true", "yes") if f.type in (bool, "bool") else type(f.default)(val)
        return cls(**kw)


# обратная связь: муха чувствует последствия своих действий
FEEDBACK = [
    (re.compile(r"weather (rain|thunder)"), "humidity", 60.0),
    (re.compile(r"weather thunder|lightning_bolt"), "auditory", 80.0),
    (re.compile(r"summon minecraft:(bat|phantom|vex|bee)"), "looming", 50.0),
    (re.compile(r"give .*minecraft:(cake|honey|cookie|sugar|sweet)"), "sugar", 40.0),
]
_PLAYERS_RE = re.compile(r"online:\s*(.*)$")
_TIME_RE = re.compile(r"The time is (\d+)")


class FlyController:
    def __init__(self, brain, reference_hz, console, log_path=None, config=None, rng=None, out=None):
        self.brain = brain
        self.console = console
        self.cfg = config or Config()
        self.rng = rng or random.Random()
        self.out = out or sys.stdout
        self.moods = MoodEngine(reference_hz)
        self.sleep = SleepCycle()
        self.senses = Senses(self.cfg.stim_half_life_s)
        self.tailer = LogTailer(log_path) if log_path else None
        self.players: list[str] = []
        self.night = False
        self.mood = None
        self.tick_no = 0
        self._last_action = -1e9
        self._recent: list[float] = []
        self._reverts: list[tuple[float, int, str]] = []
        self._shown_mood = None
        self._last_tick = None

    # ---------- ввод ----------
    def feel_line(self, line: str):
        ev = parse_line(line)
        if not ev:
            return
        if ev.kind == "join" and ev.player not in self.players:
            self.players.append(ev.player)
        if ev.kind == "leave" and ev.player in self.players:
            self.players.remove(ev.player)
        for sense, hz in ev.stimuli:
            self.senses.add(sense, hz)
        self.log(f"чувствует {ev.kind} от {ev.player}: " + ", ".join(f"{s}+{hz:.0f}" for s, hz in ev.stimuli))

    def poll_world(self):
        try:
            m = _PLAYERS_RE.search(self.console.command("list") or "")
            if m:
                self.players = [p.strip() for p in m.group(1).split(",") if p.strip()]
                if self._shown_mood is not None and self.cfg.bossbar:
                    self.send("bossbar set flybrain:mood players @a")
            t = _TIME_RE.search(self.console.command("time query daytime") or "")
            if t:
                night = 13000 <= int(t.group(1)) < 23000
                if night != self.night:
                    self.senses.add("heat", 60.0)  # рассвет/закат: смена температуры
                self.night = night
        except Exception as e:  # сервер мог перезапуститься — не падаем
            self.log(f"не смог опросить сервер: {e}")

    def spontaneous(self):
        if self.rng.random() < self.cfg.spontaneous_prob:
            sense = self.rng.choice(self.brain.sense_names)
            self.senses.add(sense, self.rng.uniform(40, 120))

    # ---------- вывод ----------
    def send(self, cmd: str) -> str | None:
        why = safe_check(cmd)
        if why:
            self.log(f"ФИЛЬТР не пропустил /{cmd}: {why}")
            return None
        try:
            return self.console.command(cmd)
        except Exception as e:
            self.log(f"консоль недоступна: {e}")
            return None

    def maybe_act(self, now: float):
        m = self.mood
        self._recent = [t for t in self._recent if now - t < 60]
        if now - self._last_action < self.cfg.min_action_gap_s or len(self._recent) >= self.cfg.max_actions_per_min:
            return
        p = self.cfg.bored_act_prob if m.name == "bored" else self.cfg.act_base + self.cfg.act_gain * m.intensity
        if self.rng.random() >= p:
            return
        action = choose_action(m.name, m.intensity, self.players, self.rng)
        if not action:
            return
        self._last_action = now
        self._recent.append(now)
        self.log(f"{m.label} ({m.intensity:.2f}) -> {action.name}")
        for cmd in action.commands:
            reply = self.send(cmd)
            if reply:
                self.react_to_reply(cmd, reply)
            for rx, sense, hz in FEEDBACK:
                if rx.search(cmd):
                    self.senses.add(sense, hz)
        for delay, cmd in action.reverts:
            heapq.heappush(self._reverts, (now + delay, self.tick_no, cmd))

    def react_to_reply(self, cmd: str, reply: str):
        """Муха комментирует ответы консоли (locate, seed, random...)."""
        reply = reply.strip()
        if cmd.endswith("seed") or " locate " in f" {cmd}" or cmd.startswith("random"):
            self.send(tellraw(f"вижу: {reply[:180]}", "light_purple"))

    def run_reverts(self, now: float):
        while self._reverts and self._reverts[0][0] <= now:
            _, _, cmd = heapq.heappop(self._reverts)
            self.send(cmd)

    def show_mood(self):
        """Боссбар над экраном у всех игроков: настроение и его сила."""
        if not self.cfg.bossbar or not self.mood:
            return
        name, value = self.mood.name, int(round(self.mood.intensity * 10)) * 10
        shown_name, shown_value = self._shown_mood or (None, None)
        if self._shown_mood is None:
            self.send('bossbar add flybrain:mood {"text":"Муха"}')
            self.send("bossbar set flybrain:mood max 100")
            self.send("bossbar set flybrain:mood players @a")
        if name != shown_name:
            self.send(f'bossbar set flybrain:mood name {{"text":"Муха: {self.mood.label}"}}')
            self.send(f"bossbar set flybrain:mood color {MOOD_COLOR.get(name, 'white')}")
        if value != shown_value:
            self.send(f"bossbar set flybrain:mood value {value}")
        self._shown_mood = (name, value)

    # ---------- тик ----------
    def tick(self):
        now = time.time()
        dt = self.cfg.tick_s if self._last_tick is None else now - self._last_tick
        self._last_tick = now
        self.tick_no += 1
        if self.tailer:
            for line in self.tailer.poll():
                self.feel_line(line)
        if self.tick_no % self.cfg.poll_every_ticks == 1:
            self.poll_world()
        self.run_reverts(now)

        if self.sleep.asleep:
            if self.sleep.observe_asleep(self.senses.total(), self.night):
                self.log("проснулась!")
                self.moods.reset()
                self.send(tellraw("*проснулась* бзз?", "gray"))
            else:
                self.mood = Mood("asleep", 0.0, {})
                self.show_mood()
                self.senses.decay(dt)
                return

        self.spontaneous()
        state = self.brain.step(self.senses.rates(), self.cfg.sim_ms)
        self.mood = self.moods.update(state.rates)
        scores = " ".join(f"{k[:4]}={v:.2f}" for k, v in self.mood.scores.items())
        self.log(f"вход={state.drive:.0f}Гц активно={state.active} | {self.mood.label} {self.mood.intensity:.2f} | {scores}")
        self.show_mood()
        self.maybe_act(now)

        if self.sleep.observe_awake(state.drive, state.active, self.night):
            self.log("засыпает (сброс состояния мозга)")
            self.brain.reset()
            self.send(tellraw("Zzz...", "gray"))
        self.senses.decay(dt)

    def run_forever(self):
        self.log("муха проснулась и слушает сервер")
        while True:
            t0 = time.time()
            self.tick()
            time.sleep(max(0.0, self.cfg.tick_s - (time.time() - t0)))

    def log(self, msg: str):
        print(f"[fly {self.tick_no:5d}] {msg}", file=self.out, flush=True)
