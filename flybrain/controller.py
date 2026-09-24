"""Главный цикл: чувства -> мозг -> настроение -> команды в консоль."""

from __future__ import annotations

import heapq
import os
import random
import re
import sys
import time
from dataclasses import dataclass, fields

from .body import FlyEye
from .commands import MOOD_COLOR, choose_action, hate_line, tellraw
from .memory import PlayerMemory
from .mood import MOOD_RU, Mood, MoodEngine, SleepCycle
from .safety import POWERS, safe_check
from .senses import LogTailer, Senses, parse_line


@dataclass
class Config:
    power: str = "am"  # safe | chaos | am — см. safety.py
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
    sidebar: bool = True  # табло «Мозг мухи» справа
    body: bool = True  # огромный глаз в небе
    body_every_ticks: int = 2
    eye_scale: float = 10.0
    hunger_period_s: float = 900.0  # за сколько муха проголодается с нуля
    hate_chant_gap_s: float = 6.0  # HATE HATE HATE не чаще раза в N секунд (am)
    hate_gain: float = 1.8  # в режиме am горький путь -> ненависть усилен

    @classmethod
    def from_env(cls, prefix: str = "FLY_") -> "Config":
        kw = {}
        for f in fields(cls):
            val = os.environ.get(prefix + f.name.upper())
            if val is not None:
                kw[f.name] = val.lower() in ("1", "true", "yes") if f.type in (bool, "bool") else type(f.default)(val)
        cfg = cls(**kw)
        if cfg.power not in POWERS:
            raise ValueError(f"FLY_POWER должен быть одним из {POWERS}")
        return cfg


# обратная связь: муха чувствует последствия своих действий
FEEDBACK = [
    (re.compile(r"weather (rain|thunder)"), "humidity", 60.0),
    (re.compile(r"weather thunder|lightning_bolt|minecraft:tnt|creeper"), "auditory", 80.0),
    (re.compile(r"summon minecraft:(bat|phantom|vex|bee|creeper)"), "looming", 50.0),
    (re.compile(r"give .*minecraft:(cake|honey|cookie|sugar|sweet)"), "sugar", 40.0),
    (re.compile(r"minecraft:fire|lightning_bolt"), "heat", 60.0),
]
# кого выбирать целью в каком настроении
TARGET_PREFERENCE = {"feeding": "friend", "grooming": "friend", "aversion": "enemy", "escape": "enemy"}
_PLAYERS_RE = re.compile(r"online:\s*(.*)$")
_TIME_RE = re.compile(r"The time is (\d+)")
_WHO_AM_I = re.compile(r"(муха|fly).*(кто я|who am i|любишь меня|ненавидишь меня)", re.I)


class FlyController:
    def __init__(self, brain, reference_hz, console, log_path=None, config=None, rng=None, out=None,
                 memory_path=None):
        self.brain = brain
        self.console = console
        self.cfg = config or Config()
        self.rng = rng or random.Random()
        self.out = out or sys.stdout
        gains = {"aversion": self.cfg.hate_gain} if self.cfg.power == "am" else None
        self.moods = MoodEngine(reference_hz, gains=gains)
        self.sleep = SleepCycle()
        self.senses = Senses(self.cfg.stim_half_life_s)
        self.memory = PlayerMemory(memory_path)
        self.tailer = LogTailer(log_path) if log_path else None
        self.eye = FlyEye(self.send, self.cfg.eye_scale) if self.cfg.body else None
        self.players: list[str] = []
        self.focus: str | None = None
        self.hunger = 0.3
        self.night = False
        self.mood = None
        self.tick_no = 0
        self._last_action = -1e9
        self._last_hate = -1e9
        self._recent: list[float] = []
        self._reverts: list[tuple[float, int, str]] = []
        self._shown_mood = None
        self._shown_sidebar: dict[str, int] = {}
        self._last_tick = None

    # ---------- ввод ----------
    def feel(self, stimuli, player: str | None = None, learn: bool = True):
        for sense, hz in stimuli:
            self.senses.add(sense, hz)
        if player and learn:
            d = dict(stimuli)
            self.memory.learn(player, d.get("sugar", 0.0), d.get("bitter", 0.0))

    def feel_line(self, line: str):
        ev = parse_line(line)
        if not ev:
            return
        if ev.kind == "join" and ev.player not in self.players:
            self.players.append(ev.player)
        if ev.kind == "leave" and ev.player in self.players:
            self.players.remove(ev.player)
        # смерть — горько мухе, но жертва не виновата; виноват убийца-игрок
        self.feel(ev.stimuli, ev.player, learn=ev.kind == "chat")
        if ev.kind == "death" and ev.other in self.players:
            self.memory.learn(ev.other, 0.0, 200.0)
            self.focus = ev.other
        elif ev.kind in ("chat", "join"):
            self.focus = ev.player
        # условный рефлекс: сам вид игрока уже сладок или горек
        if ev.kind in ("chat", "join"):
            self.feel(self.memory.conditioned(ev.player), learn=False)
        self.log(f"чувствует {ev.kind} от {ev.player}: " + ", ".join(f"{s}+{hz:.0f}" for s, hz in ev.stimuli)
                 + f" | отношение {self.memory.get(ev.player):+.2f}")
        if ev.kind == "chat" and _WHO_AM_I.search(ev.text):
            self.send(tellraw(f"{ev.player}: {self.memory.describe(ev.player)}", "gold"))

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
        if self.focus not in self.players:
            self.focus = self.rng.choice(self.players) if self.players else None

    def spontaneous(self):
        if self.rng.random() < self.cfg.spontaneous_prob:
            sense = self.rng.choice(self.brain.sense_names)
            self.senses.add(sense, self.rng.uniform(40, 120))

    def body_tick(self):
        if not (self.eye and self.players):
            return
        rep = self.eye.sense(self.players)
        self.feel(rep.stimuli, learn=False)
        for player, sugar, bitter in rep.learn:
            self.memory.learn(player, sugar, bitter)
            self.focus = player
        for p in rep.near:  # глаз видит знакомых — условный рефлекс, послабее
            self.feel(self.memory.conditioned(p, gain=40.0), learn=False)
        for note in rep.notes:
            self.log(f"глаз: {note}")
        mood = self.mood.name if self.mood else "bored"
        if self.focus:
            self.eye.move(self.focus, mood, self.rng)
        self.eye.set_look(mood, self.rng)

    def update_hunger(self, dt: float):
        """Голод растёт со временем, сахар его гасит. Голодная муха сильнее
        чувствует сладкое и слабее — горькое (так и у настоящих дрозофил)."""
        sugar = self.senses.level.get("sugar", 0.0)
        self.hunger = min(1.0, max(0.0, self.hunger + dt / self.cfg.hunger_period_s - sugar * dt / 4000.0))
        if self.hunger > 0.8 and self.rng.random() < 0.01:
            self.send(tellraw("ГОЛОДНО. покормите глаз сахаром (ПКМ с сахаром в руке)", "gold"))

    def brain_input(self) -> dict[str, float]:
        rates = self.senses.rates()
        if "sugar" in rates:
            rates["sugar"] *= 1.0 + self.hunger
        if "bitter" in rates:
            rates["bitter"] *= 1.0 - 0.5 * self.hunger
        return rates

    # ---------- вывод ----------
    def send(self, cmd: str) -> str | None:
        why = safe_check(cmd, self.cfg.power)
        if why:
            self.log(f"ФИЛЬТР не пропустил /{cmd}: {why}")
            return None
        try:
            return self.console.command(cmd)
        except Exception as e:
            self.log(f"консоль недоступна: {e}")
            return None

    def label(self, mood: Mood) -> str:
        if mood.name == "aversion" and self.cfg.power == "am":
            return "НЕНАВИСТЬ"
        return mood.label

    def maybe_act(self, now: float):
        m = self.mood
        if self.cfg.power == "am" and m.name == "aversion" and now - self._last_hate >= self.cfg.hate_chant_gap_s:
            if self.rng.random() < 0.3 + 0.7 * m.intensity:
                self._last_hate = now
                self.send(hate_line(m.intensity))
        self._recent = [t for t in self._recent if now - t < 60]
        if now - self._last_action < self.cfg.min_action_gap_s or len(self._recent) >= self.cfg.max_actions_per_min:
            return
        p = self.cfg.bored_act_prob if m.name == "bored" else self.cfg.act_base + self.cfg.act_gain * m.intensity
        if self.rng.random() >= p:
            return
        target = self.memory.pick(self.players, TARGET_PREFERENCE.get(m.name, ""), self.rng)
        if TARGET_PREFERENCE.get(m.name) is None and self.focus in self.players:
            target = self.focus
        action = choose_action(m.name, m.intensity, self.players, self.rng, self.cfg.power, target, self.send)
        if not action:
            return
        self._last_action = now
        self._recent.append(now)
        self.log(f"{self.label(m)} ({m.intensity:.2f}) -> {action.name}" + (f" [{target}]" if target else ""))
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

    def run_reverts(self, now: float, force: bool = False):
        while self._reverts and (force or self._reverts[0][0] <= now):
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
            self.send(f'bossbar set flybrain:mood name {{"text":"Муха: {self.label(self.mood)}"}}')
            self.send(f"bossbar set flybrain:mood color {MOOD_COLOR.get(name, 'white')}")
        if value != shown_value:
            self.send(f"bossbar set flybrain:mood value {value}")
        self._shown_mood = (name, value)

    def show_sidebar(self):
        """Табло справа: сила каждого настроения и голод, 0..100."""
        if not self.cfg.sidebar or not self.mood or self.tick_no % 3:
            return
        if not self._shown_sidebar:
            self.send('scoreboard objectives add flybrain dummy {"text":"Мозг мухи","color":"gold"}')
            self.send("scoreboard objectives setdisplay sidebar flybrain")
        rows = {MOOD_RU[k].capitalize(): int(min(1.0, v) * 100) for k, v in self.moods.scores.items()}
        if self.cfg.power == "am":
            rows["Ненависть"] = rows.pop(MOOD_RU["aversion"].capitalize())
        rows["Голод"] = int(self.hunger * 100)
        for name, val in rows.items():
            if self._shown_sidebar.get(name) != val:
                self.send(f"scoreboard players set {name} flybrain {val}")
                self._shown_sidebar[name] = val

    # ---------- тик ----------
    def tick(self):
        now = time.time()
        dt = self.cfg.tick_s if self._last_tick is None else now - self._last_tick
        self._last_tick = now
        self.tick_no += 1
        if hasattr(self.console, "tick"):
            self.console.tick()  # фейковый мир живёт
        if self.tailer:
            for line in self.tailer.poll():
                self.feel_line(line)
        if self.tick_no % self.cfg.poll_every_ticks == 1:
            self.poll_world()
        self.run_reverts(now)
        if self.tick_no % self.cfg.body_every_ticks == 0:
            self.body_tick()
        self.update_hunger(dt)
        self.memory.forget(dt)
        if self.tick_no % 30 == 0:
            self.memory.save()

        if self.sleep.asleep:
            if self.sleep.observe_asleep(self.senses.total(), self.night):
                self.log("проснулась!")
                self.moods.reset()
                self.send(tellraw("*глаз открылся*", "gray"))
            else:
                self.mood = Mood("asleep", 0.0, {})
                self.show_mood()
                self.senses.decay(dt)
                return

        self.spontaneous()
        state = self.brain.step(self.brain_input(), self.cfg.sim_ms)
        self.mood = self.moods.update(state.rates)
        scores = " ".join(f"{k[:4]}={v:.2f}" for k, v in self.mood.scores.items())
        self.log(f"вход={state.drive:.0f}Гц активно={state.active} голод={self.hunger:.2f} | "
                 f"{self.label(self.mood)} {self.mood.intensity:.2f} | {scores}")
        self.show_mood()
        self.show_sidebar()
        self.maybe_act(now)

        if self.sleep.observe_awake(state.drive, state.active, self.night):
            self.log("засыпает (сброс состояния мозга)")
            self.brain.reset()
            self.send(tellraw("Zzz... (глаз закрылся)", "gray"))
        self.senses.decay(dt)

    def shutdown(self):
        """Откатить временные эффекты и сохранить память."""
        self.run_reverts(time.time(), force=True)
        self.memory.save()

    def run_forever(self):
        self.log(f"муха проснулась и слушает сервер (сила: {self.cfg.power})")
        try:
            while True:
                t0 = time.time()
                self.tick()
                time.sleep(max(0.0, self.cfg.tick_s - (time.time() - t0)))
        finally:
            self.shutdown()

    def log(self, msg: str):
        print(f"[fly {self.tick_no:5d}] {msg}", file=self.out, flush=True)
