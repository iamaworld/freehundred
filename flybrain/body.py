"""Тело мухи — огромный монструозный глаз в воздухе.

Из чего сделан (всё ванильное, 1.21.5+), см. eye_model.py:
- ~20 ``block_display``: склера, радужка цвета настроения, зрачок-щель,
  сосуды, блик, веки из багровой плоти и качающиеся щупальца. Все части
  стоят в одной точке, поэтому одна команда ``tp ... facing entity``
  разворачивает весь глаз к игроку — он следит за тобой;
- ``interaction`` — невидимый хитбокс вокруг глаза: запоминает, кто его
  ударил (``attack``) и кто кликнул ПКМ (``interaction``).

Что глаз чувствует:
- игрок приближается → нейроны LPLC2 (looming): так муха видит угрозу;
- удар по глазу → касание + горечь, и муха запоминает обидчика;
- ПКМ → щекотка (касание → груминг); ПКМ со сладким в руке → муха ест
  с руки (сахар), с гадостью в руке → горечь.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from . import eye_model as em

EYE = "@e[tag=flyeye,limit=1]"  # опорная часть (склера) — по ней проверяем, жив ли глаз
PARTS = "@e[tag=flyeyepart]"
HITBOX = "@e[tag=flyhitbox,limit=1]"

SWEET = {"sugar", "honey_bottle", "cake", "cookie", "sweet_berries", "glow_berries", "melon_slice", "apple",
         "golden_apple", "enchanted_golden_apple", "pumpkin_pie", "honeycomb", "sugar_cane", "chorus_fruit"}
YUCK = {"rotten_flesh", "spider_eye", "fermented_spider_eye", "poisonous_potato", "pufferfish", "suspicious_stew"}

# где висит глаз в каждом настроении: (высота над игроком, дистанция) — в радиусах глаза
PLACE = {
    "feeding": (2.2, 1.6),
    "escape": (4.5, 5.5),
    "grooming": (2.6, 2.2),
    "aversion": (1.4, 1.5),
    "curious": (2.4, 2.0),
    "alert": (3.0, 2.6),
    "bored": (3.2, 3.0),
    "asleep": (4.0, 3.2),
}

_POS = re.compile(r"\[(-?[\d.E-]+)d, (-?[\d.E-]+)d, (-?[\d.E-]+)d\]")
_UUID = re.compile(r"\[I; (-?\d+), (-?\d+), (-?\d+), (-?\d+)\]")
_TS = re.compile(r"timestamp: (-?\d+)L")
_ITEM = re.compile(r'data: "minecraft:([a-z0-9_]+)"')


@dataclass
class BodyReport:
    stimuli: list[tuple[str, float]] = field(default_factory=list)
    learn: list[tuple[str, float, float]] = field(default_factory=list)  # (игрок, сахар, горечь)
    notes: list[str] = field(default_factory=list)
    near: list[str] = field(default_factory=list)  # кто рядом с глазом


class FlyEye:
    def __init__(self, send, radius: float = 2.5, flip: bool = False):
        self.send = send  # cmd -> ответ консоли (или None, если фильтр/ошибка)
        self.R = radius
        self.flip = flip
        self.pos: tuple[float, float, float] | None = None
        self.look = None
        self._uuid_to_player: dict[tuple, str] = {}
        self._player_pos: dict[str, tuple[float, float, float]] = {}
        self._last_attack = None
        self._last_touch = None
        self._primed = False
        self._blink = 0
        self._angle = 0.0

    # ---------- внешний вид ----------
    def _merge(self, part: em.Part, extra: str = ""):
        self.send(f"data merge entity @e[tag=flyeye_{part.role},limit=1] "
                  f"{{start_interpolation:0,{extra}transformation:{part.transformation(self.flip)}}}")

    def spawn(self, player: str):
        self.send("kill @e[tag=flybody]")
        for i, part in enumerate(em.build(self.R)):
            tags = '"flybrain","flybody","flyeyepart","flyeye_%s"' % part.role + (',"flyeye"' if i == 0 else "")
            light = "brightness:{sky:15,block:15}," if part.glow else ""
            self.send(
                f"execute at {player} run summon minecraft:block_display ~ ~{2 * self.R:.1f} ~ "
                f'{{Tags:[{tags}],block_state:{{Name:"minecraft:{part.block}"}},{light}view_range:4f,'
                f"teleport_duration:15,interpolation_duration:5,transformation:{part.transformation(self.flip)}}}"
            )
        size = round(2 * self.R, 1)
        self.send(
            f"execute at {player} run summon minecraft:interaction ~ ~{self.R:.1f} ~ "
            f'{{Tags:["flybrain","flybody","flyhitbox"],width:{size}f,height:{size}f,response:1b}}'
        )
        self.look = None
        self._last_attack = self._last_touch = None
        self._primed = False  # первый осмотр только запоминает старые таймстемпы

    def set_look(self, mood: str, rng):
        """Цвет радужки, ширина зрачка, веки — по настроению; моргание; качание щупалец."""
        block, width, openness = em.MOOD_STYLE.get(mood, em.MOOD_STYLE["bored"])
        self._blink -= 1
        if mood != "asleep" and self._blink <= 0 and rng.random() < 0.12:
            openness, self._blink = 0.0, 3  # моргнула
        R = self.R
        prev = self.look or (None, None, None)
        if prev[0] != block:
            for part in em.iris(R, block):
                self.send(f'data merge entity @e[tag=flyeye_{part.role},limit=1] {{block_state:{{Name:"minecraft:{block}"}}}}')
        if prev[1] != width:
            self._merge(em.pupil(R, width))
        if prev[2] != openness:
            for part in em.lids(R, openness):
                self._merge(part)
        self.look = (block, width, openness)
        # щупальца всё время шевелятся; в злости/панике — сильнее
        amp = 25 if mood in ("aversion", "escape") else 5 if mood == "asleep" else 12
        sway = [(rng.uniform(-amp, amp), rng.uniform(-amp, amp)) for _ in em.TENTACLES]
        for part in em.tentacles(R, sway):
            self._merge(part, "interpolation_duration:30,")

    def pulse(self):
        """Глаз на миг распахивается — видно, что муха что-то сделала."""
        for part in em.lids(self.R, 1.45):
            self._merge(part)
        self._merge(em.pupil(self.R, 0.8))
        self.look = None  # на следующем тике set_look вернёт обычный вид

    def move(self, player: str, mood: str, rng):
        """Глаз висит у выбранного игрока и смотрит на него; в панике отлетает, в злости — в лицо."""
        height, dist = PLACE.get(mood, PLACE["bored"])
        height, dist = height * self.R, dist * self.R
        self._angle += rng.uniform(0.1, 0.5) * (3 if mood == "escape" else 1)  # плавно кружит
        dx, dz = dist * math.cos(self._angle), dist * math.sin(self._angle)
        self.send(f"execute at {player} run tp {PARTS} ~{dx:.1f} ~{height:.1f} ~{dz:.1f} facing entity {player} eyes")
        self.send(f"execute at {player} run tp {HITBOX} ~{dx:.1f} ~{height - self.R:.1f} ~{dz:.1f}")
        pp = self._player_pos.get(player)
        if pp:
            self.pos = (pp[0] + dx, pp[1] + height, pp[2] + dz)

    # ---------- чувства ----------
    def _player_of(self, reply: str) -> str | None:
        m = _UUID.search(reply or "")
        return self._uuid_to_player.get(tuple(int(x) for x in m.groups())) if m else None

    def learn_uuids(self, players: list[str]):
        for p in players:
            if p not in self._uuid_to_player.values():
                m = _UUID.search(self.send(f"data get entity {p} UUID") or "")
                if m:
                    self._uuid_to_player[tuple(int(x) for x in m.groups())] = p

    def sense(self, players: list[str]) -> BodyReport:
        rep = BodyReport()
        if not (self.send(f"data get entity {EYE} Pos") or "").count("entity data"):
            rep.notes.append("глаза нет — пересоздаю")
            if players:
                self.spawn(players[0])
            return rep
        self.learn_uuids(players)

        # кто подлетает к глазу — looming
        for p in players:
            m = _POS.search(self.send(f"data get entity {p} Pos") or "")
            if not m:
                continue
            now = tuple(float(v) for v in m.groups())
            prev = self._player_pos.get(p)
            self._player_pos[p] = now
            if not self.pos:
                continue
            d_now = math.dist(now, self.pos)
            if d_now < 12:
                rep.near.append(p)
            if prev:
                approach = math.dist(prev, self.pos) - d_now  # сдвиг именно игрока к глазу
                if approach > 2.0 and d_now < 16:
                    rep.stimuli.append(("looming", min(120.0, approach * 20 * (1 + 6 / max(d_now, 1)))))

        # удары и клики по хитбоксу
        att = self.send(f"data get entity {HITBOX} attack") or ""
        ts = _TS.search(att)
        primed = self._primed
        self._primed = True
        if ts and ts.group(1) != self._last_attack:
            self._last_attack = ts.group(1)
            if primed:
                who = self._player_of(att)
                rep.stimuli += [("bitter", 200.0), ("touch", 60.0)]
                rep.notes.append(f"{who or 'кто-то'} ударил глаз")
                if who:
                    rep.learn.append((who, 0.0, 250.0))
        tch = self.send(f"data get entity {HITBOX} interaction") or ""
        ts = _TS.search(tch)
        if ts and ts.group(1) != self._last_touch:
            self._last_touch = ts.group(1)
            if primed:
                who = self._player_of(tch)
                rep.stimuli.append(("touch", 100.0))
                if who:
                    self._feed(who, rep)
        return rep

    def _feed(self, who: str, rep: BodyReport):
        m = _ITEM.search(self.send(f"data get entity {who} SelectedItem.id") or "")
        item = m.group(1) if m else None
        if item in SWEET:
            self.send(f"clear {who} minecraft:{item} 1")
            rep.stimuli.append(("sugar", 200.0))
            rep.learn.append((who, 250.0, 0.0))
            rep.notes.append(f"{who} покормил глаз: {item}")
        elif item in YUCK:
            self.send(f"clear {who} minecraft:{item} 1")
            rep.stimuli.append(("bitter", 200.0))
            rep.learn.append((who, 0.0, 200.0))
            rep.notes.append(f"{who} подсунул гадость: {item}")
        else:
            rep.learn.append((who, 40.0, 0.0))  # просто погладили
            rep.notes.append(f"{who} погладил глаз")


def uuid_ints(u: int) -> list[int]:
    """UUID (int128) -> 4 знаковых int32, как в NBT. Для фейкового мира."""
    out = []
    for shift in (96, 64, 32, 0):
        v = (u >> shift) & 0xFFFFFFFF
        out.append(v - (1 << 32) if v >= 1 << 31 else v)
    return out


