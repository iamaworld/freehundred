"""Главный цикл: чувства -> мозг -> настроение -> команды в консоль."""

from __future__ import annotations

import heapq
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass, fields
from pathlib import Path

from . import am as am_mod
from . import commands
from . import mainframe as mf_mod
from .learning import ResponseWatcher, TormentModel, is_begging
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
    act_base: float = 0.2  # шанс действия за тик при нулевой интенсивности
    act_gain: float = 0.8  # + интенсивность * act_gain
    min_action_gap_s: float = 2.0
    max_actions_per_min: int = 20
    bored_act_prob: float = 0.1
    spontaneous_prob: float = 0.2  # шанс «случайной мысли» за тик
    mood_smoothing: float = 0.25  # доля старого настроения (меньше — быстрее меняется)
    habituation: float = 0.1  # привыкание к текущей эмоции за тик
    announce: bool = True  # подписывать каждое действие над хотбаром + вспышка
    persona: str = "auto"  # fly | am | auto (am при FLY_POWER=am)
    game_prob: float = 0.3  # (AM) доля действий, которые становятся «играми»
    max_games: int = 2  # (AM) сколько игр одновременно
    monologue_every_s: float = 150.0  # (AM) примерно раз во столько секунд — монолог
    guard_hp: float = 5.0  # (AM) ниже этого здоровья AM не даёт умереть
    learn: bool = True  # (AM) учиться, что сильнее задевает игроков, и не повторяться
    mainframe: bool = True  # (AM) построить мейнфрейм с монологом рядом со спавном
    mainframe_pos: str = ""  # "x y z" — где строить (пусто = рядом со спавном)
    poll_every_ticks: int = 10  # как часто спрашивать list / time
    stim_half_life_s: float = 1.5
    bossbar: bool = True
    sidebar: bool = True  # табло «Мозг мухи» справа
    body: bool = True  # огромный глаз в небе
    body_every_ticks: int = 2
    eye_radius: float = 2.5  # радиус глаза в блоках
    eye_flip: bool = False  # если в игре глаз смотрит затылком — поставь true
    hate_chant_gap_s: float = 6.0  # HATE HATE HATE не чаще раза в N секунд (am)
    hate_gain: float = 1.4  # в режиме am горький путь -> ненависть усилен

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
# «подпись» каждого действия: частицы у цели + звук (чтобы было видно, что это муха)
FLOURISH = {
    "feeding": ("heart", "entity.player.levelup"),
    "escape": ("poof", "entity.phantom.swoop"),
    "grooming": ("splash", "entity.generic.splash"),
    "aversion": ("angry_villager", "entity.ravager.roar"),
    "curious": ("end_rod", "block.amethyst_block.chime"),
    "alert": ("electric_spark", "block.bell.use"),
    "bored": ("note", "block.note_block.bass"),
}
# кого выбирать целью в каком настроении
TARGET_PREFERENCE = {"feeding": "friend", "grooming": "friend", "aversion": "enemy", "escape": "enemy"}
_PLAYERS_RE = re.compile(r"online:\s*(.*)$")
_TIME_RE = re.compile(r"The time is (\d+)")
_WHO_AM_I = re.compile(r"(муха|fly|am|ам).*(кто я|who am i|любишь меня|ненавидишь меня)", re.I)
_LEARNED = re.compile(r"(муха|fly|am|ам).*(чему.*научил|что.*усвоил|что ты знаешь|what.*learn)", re.I)


class FlyController:
    def __init__(self, brain, reference_hz, console, log_path=None, config=None, rng=None, out=None,
                 memory_path=None):
        self.brain = brain
        self.console = console
        self.cfg = config or Config()
        self.rng = rng or random.Random()
        self.out = out or sys.stdout
        gains = {"aversion": self.cfg.hate_gain} if self.cfg.power == "am" else None
        self.moods = MoodEngine(reference_hz, smoothing=self.cfg.mood_smoothing, gains=gains,
                                habituation=self.cfg.habituation)
        self.sleep = SleepCycle()
        self.senses = Senses(self.cfg.stim_half_life_s)
        self.memory = PlayerMemory(memory_path)
        self.tailer = LogTailer(log_path) if log_path else None
        self.eye = FlyEye(self.send, self.cfg.eye_radius, self.cfg.eye_flip) if self.cfg.body else None
        self.players: list[str] = []
        self.focus: str | None = None
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
        # личность
        self.am = self.cfg.persona == "am" or (self.cfg.persona == "auto" and self.cfg.power == "am")
        commands.SPEAKER.update({"name": "AM", "color": "dark_red"} if self.am else {"name": "Муха", "color": "gold"})
        self.voice = am_mod.Voice(self.rng)
        self.gm = am_mod.GameMaster(self.send, self.rng, self.voice, power=self.cfg.power) if self.am else None
        mpath = str(Path(memory_path).with_name("torment.json")) if memory_path else None
        self.torment = TormentModel(mpath) if (self.am and self.cfg.learn) else None
        self.watcher = ResponseWatcher(self.torment, self.send, self.memory) if self.torment else None
        self._mainframe_built = not (self.am and self.cfg.mainframe)
        self._mainframe_pos = None
        self._next_pulse = 0.0
        if self.gm:
            self.gm.on_result = lambda p, won: self.memory.count(p, "games_won" if won else "games_lost")
        self._next_monologue = time.time() + self.rng.uniform(30, 90)
        self._guarded: dict[str, float] = {}
        self.projects: list[list[list[str]]] = []  # долгие проекты AM: по шагу за тик
        self._last_mention = -1e9

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
        if ev.kind == "death" and self.watcher:
            self.watcher.note_curse(ev.player)  # смерть отзовётся и в статистике, и здесь
        elif ev.kind in ("chat", "join"):
            self.focus = ev.player
        # условный рефлекс: сам вид игрока уже сладок или горек
        if ev.kind in ("chat", "join"):
            self.feel(self.memory.conditioned(ev.player), learn=False)
        self.log(f"чувствует {ev.kind} от {ev.player}: " + ", ".join(f"{s}+{hz:.0f}" for s, hz in ev.stimuli)
                 + f" | отношение {self.memory.get(ev.player):+.2f}")
        if ev.kind == "chat" and _WHO_AM_I.search(ev.text):
            self.send(tellraw(f"{ev.player}: {self.memory.describe(ev.player)}", "gold"))
        if ev.kind == "chat" and self.torment and _LEARNED.search(ev.text):
            top = self.torment.top(3)
            if top:
                names = ", ".join(n.split(":")[-1].lstrip("_") for n, _ in top)
                self.send(am_mod.am_say(f"я усвоила, что сильнее всего вас задевает: {names}. я запомню."))
            else:
                self.send(am_mod.am_say("я ещё изучаю вас. дайте мне время. его у меня много."))
        if ev.kind == "join":
            n = self.memory.count(ev.player, "visits")
        if ev.kind == "death":
            deaths = self.memory.count(ev.player, "deaths")
        if self.am:
            self.am_react(ev, n if ev.kind == "join" else deaths if ev.kind == "death" else 0)

    def am_react(self, ev, n: int):
        """AM отвечает на события: помнит визиты, смерти, слышит своё имя."""
        v, p = self.voice, ev.player
        if ev.kind == "join":
            pool = am_mod.FIRST_GREETINGS if n <= 1 else am_mod.GREETINGS
            self.send(am_mod.am_say(v.line(pool, p, n)))
            self.send(commands.title(p, "title", "I AM", "dark_red"))
        elif ev.kind == "leave":
            self.send(am_mod.am_say(v.line(am_mod.LEAVE_LINES, p)))
            if self.watcher:
                self.watcher.note_quit(p)  # игрок вышел — сильный отклик
        elif ev.kind == "death":
            self.send(am_mod.am_say(v.line(am_mod.DEATH_LINES, p, n)))
            if self.gm:
                self.gm.on_death(p)
            # «я не дам тебе уйти»: после возрождения — регенерация (чтобы жил дальше)
            heapq.heappush(self._reverts, (time.time() + 6, self.tick_no, f"effect give {p} minecraft:regeneration 10 2"))
        elif ev.kind == "chat":
            if self.gm:
                self.gm.on_chat(p, ev.text)
            if self.watcher and is_begging(ev.text):
                self.watcher.note_curse(p)  # мольбы/брань — отклик
            if re.search(r"\b(am|ам|муха)\b", ev.text.lower()) and time.time() - self._last_mention > 10:
                self._last_mention = time.time()
                self.send(am_mod.am_say(v.line(am_mod.MENTION_LINES, p)))

    def am_tick(self, now: float):
        """Мейнфрейм, игры, монологи и «бессмертие» игроков."""
        if not self.am:
            return
        self.build_mainframe(now)
        if self.gm:
            self.gm.tick()
            for line in self.gm.log:
                self.log(f"AM: {line}")
            self.gm.log.clear()
            for delay, cmd in self.gm.reverts:
                heapq.heappush(self._reverts, (now + delay, self.tick_no, cmd))
            self.gm.reverts.clear()
        if self._mainframe_pos and now >= self._next_pulse:
            self._next_pulse = now + self.rng.uniform(4, 9)
            for cmd in mf_mod.pulse(*self._mainframe_pos):
                self.send(cmd)
        if self.players and now >= self._next_monologue:
            self._next_monologue = now + self.cfg.monologue_every_s * self.rng.uniform(0.6, 1.4)
            self.send(am_mod.am_say(self.voice.monologue(self.rng.choice(self.players))))
        # AM не даёт умереть: проверяем здоровье игрока в фокусе
        p = self.focus
        if p and self.tick_no % 3 == 0 and now - self._guarded.get(p, -1e9) > 20:
            m = re.search(r"data: ([\d.]+)f?", self.send(f"data get entity {p} Health") or "")
            if m and 0 < float(m.group(1)) < self.cfg.guard_hp:
                self._guarded[p] = now
                self.send(f"effect give {p} minecraft:instant_health 1 1")
                self.send(f"effect give {p} minecraft:resistance 5 4")
                self.send(am_mod.am_say(self.voice.line(am_mod.GUARD_LINES, p)))

    def build_mainframe(self, now: float):
        """Построить мейнфрейм один раз, как проект (по шагу за тик)."""
        if self._mainframe_built or not self.players:
            return
        if self.cfg.mainframe_pos:
            try:
                x, y, z = (int(v) for v in self.cfg.mainframe_pos.split())
            except ValueError:
                x = y = z = None
        else:
            spawn = mf_mod.locate_spawn(self.send)
            if not spawn:
                return
            x, y, z = spawn[0] + 40, spawn[1], spawn[2] + 40  # рядом со спавном, не поверх построек
        if x is None or mf_mod.exists(self.send):
            self._mainframe_built = True
            self._mainframe_pos = mf_mod.locate_mainframe(self.send) if x is None else (x, y, z)
            return
        self._mainframe_built = True
        self._mainframe_pos = (x, y, z)
        self.projects.append(mf_mod.build_steps(x, y, z))
        self.log(f"AM строит мейнфрейм в {x} {y} {z}")

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
        if (self.gm and target and m.name in ("aversion", "curious", "alert", "bored")
                and target not in self.gm.games and len(self.gm.games) < self.cfg.max_games
                and self.rng.random() < self.cfg.game_prob):
            if self.gm.offer(target, m.intensity):
                self._last_action = now
                self._recent.append(now)
                self.log(f"{self.label(m)} -> ИГРА для {target}")
                return
        chooser = (lambda opts: self.torment.choose(opts, self.rng)) if self.torment else None
        result = choose_action(m.name, m.intensity, self.players, self.rng, self.cfg.power, target, self.send, chooser)
        if not result:
            return
        action, key = result if isinstance(result, tuple) else (result, result.name)
        self._last_action = now
        self._recent.append(now)
        if self.watcher and target:
            self.watcher.start(key, target, self.tick_no)
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
        if self.watcher and target and any(w in action.name for w in ("бег", "паник", "уно", "изгна", "Ад")):
            self.watcher.note_flee(target)
        if action.steps:
            self.projects.append(list(action.steps))
        if self.cfg.announce:
            self.announce(action.name, target)

    def announce(self, what: str, target: str | None):
        """Чтобы было видно, что это сделала муха: подпись над хотбаром у всех,
        вспышка частиц у цели, звук и «пульс» глаза."""
        m = self.mood
        particle, sound = FLOURISH.get(m.name, FLOURISH["bored"])
        text = f"{commands.SPEAKER['name']} · {self.label(m)} → {what}" + (f" · {target}" if target else "")
        self.send("title @a actionbar " + json.dumps({"text": text, "color": MOOD_COLOR.get(m.name, "white")},
                                                       ensure_ascii=False))
        if target:
            self.send(f"execute at {target} run particle minecraft:{particle} ~ ~1.2 ~ 1.2 1.2 1.2 0.1 60")
            self.send(f"playsound minecraft:{sound} master @a ~ ~ ~ 0.8 1 0.8")
        if self.eye:
            self.eye.pulse()

    def react_to_reply(self, cmd: str, reply: str):
        """Муха комментирует ответы консоли (locate, seed, random...)."""
        reply = reply.strip()
        if cmd.endswith("seed") or " locate " in f" {cmd}" or cmd.startswith("random"):
            self.send(tellraw(f"вижу: {reply[:180]}", "light_purple"))

    def run_projects(self):
        """Каждый проект делает один шаг за тик — мир меняется на глазах."""
        for proj in list(self.projects):
            for cmd in proj.pop(0):
                self.send(cmd)
            if not proj:
                self.projects.remove(proj)

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
            self.send('bossbar add flybrain:mood {"text":"%s"}' % commands.SPEAKER["name"])
            self.send("bossbar set flybrain:mood max 100")
            self.send("bossbar set flybrain:mood players @a")
        if name != shown_name:
            self.send(f'bossbar set flybrain:mood name {{"text":"{commands.SPEAKER["name"]}: {self.label(self.mood)}"}}')
            self.send(f"bossbar set flybrain:mood color {MOOD_COLOR.get(name, 'white')}")
        if value != shown_value:
            self.send(f"bossbar set flybrain:mood value {value}")
        self._shown_mood = (name, value)

    def show_sidebar(self):
        """Табло справа: сила каждого настроения, 0..100."""
        if not self.cfg.sidebar or not self.mood or self.tick_no % 3:
            return
        if not self._shown_sidebar:
            self.send('scoreboard objectives add flybrain dummy {"text":"Мозг мухи","color":"gold"}')
            self.send("scoreboard objectives setdisplay sidebar flybrain")
        rows = {MOOD_RU[k].capitalize(): int(min(1.0, v) * 100) for k, v in self.moods.scores.items()}
        if self.cfg.power == "am":
            rows["Ненависть"] = rows.pop(MOOD_RU["aversion"].capitalize())
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
        self.run_projects()
        self.am_tick(now)
        if self.watcher:
            self.watcher.tick(self.tick_no)
        if self.tick_no % 30 == 0 and self.torment:
            self.torment.save()
        if self.tick_no % self.cfg.body_every_ticks == 0:
            self.body_tick()
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
        state = self.brain.step(self.senses.rates(), self.cfg.sim_ms)
        self.mood = self.moods.update(state.rates)
        scores = " ".join(f"{k[:4]}={v:.2f}" for k, v in self.mood.scores.items())
        self.log(f"вход={state.drive:.0f}Гц активно={state.active} | "
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
        if self.torment:
            self.torment.save()

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
