"""Что муха делает в каждом настроении.

Каждое действие — функция (Ctx) -> Action. Интенсивность настроения (0..1)
влияет на силу: сколько предметов, насколько долго эффект, сколько мобов.
Все команды потом проходят через safety.safe_check().
Синтаксис — Java Edition 1.21.4+.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Callable

FOODS = ["cake", "honey_bottle", "cookie", "sweet_berries", "melon_slice", "bread", "pumpkin_pie", "apple", "sugar"]
RARE_FOODS = ["golden_apple", "golden_carrot", "enchanted_golden_apple"]
GIFTS = ["compass", "spyglass", "map", "firework_rocket", "flower_pot", "honeycomb", "glow_berries", "bell"]
TRASH = ["rotten_flesh", "poisonous_potato", "spider_eye", "dead_bush", "pufferfish"]
CUTE_MOBS = ["cat", "axolotl", "allay", "rabbit", "fox", "bee", "parrot", "frog", "sniffer", "armadillo"]
ANGRY_MOBS = ["silverfish", "zombie", "vex", "bee", "endermite", "slime", "phantom"]
PARTICLES = {
    "feeding": ["heart", "happy_villager", "note"],
    "escape": ["cloud", "poof", "smoke"],
    "grooming": ["bubble", "splash", "bubble_pop", "falling_water"],
    "aversion": ["angry_villager", "smoke", "witch"],
    "curious": ["end_rod", "enchant", "glow"],
    "alert": ["crit", "electric_spark", "wax_on"],
    "bored": ["ash", "white_ash", "mycelium"],
}
PHRASES = {
    "feeding": ["ням-ням", "сладенько!", "хоботок доволен", "ещё сахарку бы", "вкуснятина, делюсь!"],
    "escape": ["ААА!!", "ЧТО-ТО ЛЕТИТ!", "спасайся кто может", "бзззз-зз-з!!!", "гигантское волокно сработало"],
    "grooming": ["*чистит лапки*", "*трёт глазки*", "порядок должен быть", "уборка, бзз"],
    "aversion": ["ФУ.", "горько!", "вы меня бесите", "БЗЗЗ!!!", "сейчас кто-то получит"],
    "curious": ["а что там?", "чую что-то...", "полетели смотреть", "интересненько"],
    "alert": ["тихо!", "кто здесь?", "слышу вас", "усики на макушке"],
    "bored": ["бзз", "скучно", "...", "*летает кругами*", "потираю лапки"],
}
MOOD_COLOR = {
    "feeding": "green",
    "escape": "red",
    "grooming": "blue",
    "aversion": "red",
    "curious": "purple",
    "alert": "yellow",
    "bored": "white",
    "asleep": "white",
}


@dataclass
class Action:
    name: str
    commands: list[str]
    reverts: list[tuple[float, str]] = field(default_factory=list)  # (через сколько секунд, команда)


@dataclass
class Ctx:
    mood: str
    intensity: float
    player: str | None
    players: list[str]
    rng: random.Random

    @property
    def p(self) -> str:
        return self.player or "@r"

    def pick(self, items):
        return self.rng.choice(items)

    def scale(self, lo: int, hi: int) -> int:
        """Число от lo до hi по интенсивности, с шумом."""
        x = self.intensity + self.rng.uniform(-0.15, 0.15)
        return max(lo, min(hi, round(lo + (hi - lo) * x)))

    def at(self, cmd: str) -> str:
        return f"execute at {self.p} run {cmd}"

    def particle(self, count: int = 20) -> str:
        name = self.pick(PARTICLES[self.mood])
        return self.at(f"particle minecraft:{name} ~ ~1.5 ~ 0.6 0.6 0.6 0.05 {count}")


def tellraw(text: str, color: str = "yellow", target: str = "@a") -> str:
    msg = [{"text": "[Муха] ", "color": "gold", "bold": True}, {"text": text, "color": color}]
    return f"tellraw {target} {json.dumps(msg, ensure_ascii=False)}"


def title(target: str, kind: str, text: str, color: str) -> str:
    return f"title {target} {kind} {json.dumps({'text': text, 'color': color}, ensure_ascii=False)}"


Builder = Callable[[Ctx], Action]


def _say(c: Ctx) -> Action:
    cmds = [tellraw(c.pick(PHRASES[c.mood]), MOOD_COLOR[c.mood])]
    if c.player:
        cmds.append(c.particle())
    return Action("say", cmds)


# ---------- СЫТОСТЬ: щедрая и добрая ----------
def _give_food(c):
    food = c.pick(RARE_FOODS) if c.intensity > 0.8 and c.rng.random() < 0.3 else c.pick(FOODS)
    return Action("угощает", [f"give {c.p} minecraft:{food} {c.scale(1, 16)}", c.particle(30)])


def _heal(c):
    eff = c.pick(["regeneration", "saturation", "luck", "hero_of_the_village", "absorption", "health_boost"])
    return Action("лечит", [f"effect give {c.p} minecraft:{eff} {c.scale(5, 60)} {c.scale(0, 2)}", c.particle()])


def _sunny(c):
    return Action("солнышко", ["weather clear", "time set day" if c.rng.random() < 0.5 else "time add 1000"])


def _xp_gift(c):
    return Action("опыт", [f"xp add {c.p} {c.scale(1, 10)} levels", f"playsound minecraft:entity.player.levelup master {c.p}"])


def _cute_mob(c):
    mob = c.pick(CUTE_MOBS)
    cmds = [c.at(f"summon minecraft:{mob} ~ ~1 ~ {{Tags:[\"flybrain\"]}}") for _ in range(c.scale(1, 3))]
    return Action(f"дарит {mob}", cmds + [c.particle(40)])


def _burp(c):
    return Action("отрыжка", ["playsound minecraft:entity.player.burp master @a ~ ~ ~ 1 1.5 1", tellraw("*буэ*")])


def _recipe(c):
    return Action("учит рецептам", [f"recipe give {c.p} *", tellraw(f"{c.p}, держи все рецепты, мне не жалко", "green")])


def _peaceful_ish(c):
    return Action("добреет", ["difficulty easy", tellraw("пусть будет полегче", "green")])


# ---------- ПАНИКА: хаотичная ----------
def _flee(c):
    return Action(
        "уносит игрока",
        [
            f"effect give {c.p} minecraft:slow_falling 15 0",
            f"execute as {c.p} at @s run spreadplayers ~ ~ 1 {c.scale(10, 80)} false @s",
            title(c.p, "title", "УЛЕТАЕМ!!", "red"),
        ],
    )


def _launch(c):
    h = c.scale(5, 30)
    return Action(
        "подбрасывает",
        [f"effect give {c.p} minecraft:slow_falling 20 0", f"execute as {c.p} at @s run tp @s ~ ~{h} ~", c.particle(40)],
    )


def _dark(c):
    return Action("всё выключает", ["time set night", "weather thunder", "effect give @a minecraft:darkness 5 0"])


def _speed(c):
    return Action("бегите!", [f"effect give {c.p} minecraft:speed {c.scale(5, 30)} {c.scale(1, 3)}",
                              f"effect give {c.p} minecraft:jump_boost {c.scale(5, 30)} 1"])


def _bats(c):
    return Action("стая летучих мышей", [c.at("summon minecraft:bat ~ ~2 ~ {Tags:[\"flybrain\"]}") for _ in range(c.scale(2, 8))])


def _scream(c):
    snd = c.pick(["entity.phantom.swoop", "entity.ghast.scream", "ambient.cave", "entity.enderman.scream"])
    return Action("крик", [f"playsound minecraft:{snd} master @a ~ ~ ~ 1 1.3 1", tellraw(c.pick(PHRASES["escape"]), "red")])


def _shrink(c):
    size = round(0.3 + 0.4 * (1 - c.intensity), 2)
    return Action(
        "уменьшает до размера мухи",
        [f"attribute {c.p} minecraft:scale base set {size}", tellraw(f"{c.p}, теперь ты тоже муха", "red")],
        reverts=[(30.0, f"attribute {c.p} minecraft:scale base reset")],
    )


# ---------- ЧИСТОПЛОТНОСТЬ: наводит порядок ----------
def _clean_items(c):
    return Action("подметает", [c.at("kill @e[type=minecraft:item,distance=..24]"), c.particle(40)])


def _wash(c):
    return Action("моет всех", ["weather rain", f"effect give {c.p} minecraft:water_breathing 60 0", c.particle(60)])


def _tidy_inventory(c):
    junk = c.pick(["dirt", "cobblestone", "gravel", "rotten_flesh", "netherrack", "cobbled_deepslate"])
    return Action("выкидывает мусор", [f"clear {c.p} minecraft:{junk} {c.scale(4, 64)}", tellraw(f"зачем тебе {junk}?", "aqua")])


def _moss(c):
    return Action("стелет мох", [c.at("fill ~-2 ~-1 ~-2 ~2 ~-1 ~2 minecraft:moss_block replace minecraft:grass_block")])


def _glow(c):
    return Action("полирует", [f"effect give {c.p} minecraft:night_vision {c.scale(20, 120)} 0",
                               f"effect give {c.p} minecraft:glowing 10 0"])


def _clean_arrows(c):
    return Action("собирает стрелы", [c.at("kill @e[type=minecraft:arrow,distance=..32]"),
                                      c.at("kill @e[type=minecraft:experience_orb,distance=..16]")])


# ---------- ЗЛОСТЬ: вредничает ----------
def _thunder(c):
    cmds = ["weather thunder"]
    if c.player:
        cmds += [c.at(f"summon minecraft:lightning_bolt ~{c.rng.randint(-6, 6)} ~30 ~{c.rng.randint(-6, 6)}") for _ in range(c.scale(1, 4))]
    return Action("гром и молнии", cmds)


def _debuff(c):
    eff = c.pick(["poison", "slowness", "mining_fatigue", "nausea", "hunger", "weakness", "levitation", "blindness"])
    dur = c.scale(3, 20) if eff != "levitation" else c.scale(2, 5)
    return Action(f"насылает {eff}", [f"effect give {c.p} minecraft:{eff} {dur} {c.scale(0, 2)}", c.particle()])


def _sting(c):
    return Action("кусает", [f"damage {c.p} {c.scale(1, 6)} minecraft:sting", tellraw(f"*кусь {c.p}*", "red")])


def _angry_mobs(c):
    mob = c.pick(ANGRY_MOBS)
    return Action(f"зовёт {mob}", [c.at(f"summon minecraft:{mob} ~{c.rng.randint(-4, 4)} ~ ~{c.rng.randint(-4, 4)}") for _ in range(c.scale(1, 4))])


def _trash_gift(c):
    return Action("дарит гадость", [f"give {c.p} minecraft:{c.pick(TRASH)} {c.scale(1, 16)}", tellraw("на, жри", "red")])


def _steal_food(c):
    food = c.pick(FOODS)
    return Action("отбирает еду", [f"clear {c.p} minecraft:{food} {c.scale(1, 16)}", tellraw(f"{food} теперь мой", "red")])


def _cobweb(c):
    return Action("опутывает паутиной", [c.at("setblock ~ ~ ~ minecraft:cobweb keep"), c.at("setblock ~ ~1 ~ minecraft:cobweb keep")])


def _hard(c):
    return Action("усложняет жизнь", ["difficulty hard", tellraw("теперь будет больно", "dark_red")])


# ---------- ЛЮБОПЫТСТВО: исследует ----------
def _explore(c):
    return Action(
        "тащит на экскурсию",
        [f"effect give {c.p} minecraft:slow_falling 15 0",
         f"execute as {c.p} at @s run spreadplayers ~ ~ 1 {c.scale(30, 200)} false @s",
         tellraw(f"{c.p}, смотри, что я нашла!", "light_purple")],
    )


def _locate(c):
    s = c.pick(["village_plains", "ruined_portal", "shipwreck", "mineshaft", "pillager_outpost", "trail_ruins", "trial_chambers"])
    return Action(f"ищет {s}", [c.at(f"locate structure minecraft:{s}")])


def _gift_tool(c):
    return Action("дарит находку", [f"give {c.p} minecraft:{c.pick(GIFTS)} {c.scale(1, 4)}"])


def _ride_bat(c):
    return Action(
        "сажает на летучую мышь",
        [c.at("summon minecraft:bat ~ ~1 ~ {Tags:[\"flybrain\",\"flyride\"]}"),
         f"ride {c.p} mount @e[type=minecraft:bat,tag=flyride,limit=1,sort=nearest]"],
        reverts=[(20.0, f"ride {c.p} dismount"), (21.0, "kill @e[type=minecraft:bat,tag=flyride]")],
    )


def _low_gravity(c):
    g = round(0.01 + 0.04 * (1 - c.intensity), 3)  # обычная 0.08
    return Action(
        "выключает гравитацию",
        [f"attribute {c.p} minecraft:gravity base set {g}",
         f"attribute {c.p} minecraft:jump_strength base set 1.2"],
        reverts=[(30.0, f"attribute {c.p} minecraft:gravity base reset"), (30.0, f"attribute {c.p} minecraft:jump_strength base reset")],
    )


def _seed(c):
    return Action("читает сид мира", ["seed"])


def _dice(c):
    return Action("бросает кубик", ["random roll 1..20"])


# ---------- ТРЕВОГА: следит ----------
def _watch(c):
    return Action("всех подсвечивает", ["effect give @a minecraft:glowing 10 0", tellraw("я вас всех вижу", "yellow")])


def _bell(c):
    return Action("звонит", ["playsound minecraft:block.bell.use master @a ~ ~ ~ 1 1 1", title(c.p, "actionbar", "муха насторожилась", "yellow")])


def _count(c):
    return Action("пересчитывает", ["list"])


def _firework(c):
    return Action("сигнальная ракета", [c.at("summon minecraft:firework_rocket ~ ~2 ~ {LifeTime:20}")])


def _tag(c):
    return Action("метит подозреваемого", [f"tag {c.p} add fly_suspect", tellraw(f"{c.p} под подозрением", "gold")],
                  reverts=[(60.0, f"tag {c.p} remove fly_suspect")])


# ---------- СКУКА ----------
def _time_nudge(c):
    return Action("подкручивает время", [f"time add {c.rng.randint(100, 2000)}"])


def _hum(c):
    return Action("жужжит", [f"playsound minecraft:entity.bee.loop master @a ~ ~ ~ 0.6 {c.rng.choice(['0.8', '1', '1.2'])} 0.6"])


CATALOG: dict[str, list[tuple[float, Builder]]] = {
    "feeding": [(3, _give_food), (2, _heal), (1, _sunny), (1, _xp_gift), (1.5, _cute_mob), (1, _burp), (0.3, _recipe),
                (0.5, _peaceful_ish), (1, _say)],
    "escape": [(2, _flee), (1.5, _launch), (1, _dark), (1.5, _speed), (1.5, _bats), (1.5, _scream), (0.8, _shrink), (1, _say)],
    "grooming": [(2, _clean_items), (1.5, _wash), (1.5, _tidy_inventory), (0.8, _moss), (1, _glow), (1, _clean_arrows), (1, _say)],
    "aversion": [(1.5, _thunder), (2, _debuff), (1.5, _sting), (1.5, _angry_mobs), (1, _trash_gift), (1, _steal_food),
                 (1, _cobweb), (0.4, _hard), (1, _say)],
    "curious": [(1.5, _explore), (1.5, _locate), (1.5, _gift_tool), (1, _ride_bat), (1, _low_gravity), (0.5, _seed),
                (0.7, _dice), (1, _say)],
    "alert": [(1.5, _watch), (1.5, _bell), (1, _count), (1.5, _firework), (1, _tag), (1.5, _say)],
    "bored": [(3, _say), (1, _time_nudge), (1.5, _hum)],
}

# какие действия не имеют смысла без игроков на сервере
_WORLD_ONLY = {_sunny, _dark, _thunder, _hard, _peaceful_ish, _seed, _dice, _count, _time_nudge, _hum, _say, _watch}


def choose_action(mood: str, intensity: float, players: list[str], rng: random.Random) -> Action | None:
    options = CATALOG.get(mood)
    if not options:
        return None
    if not players:
        options = [(w, b) for w, b in options if b in _WORLD_ONLY]
        if not options:
            return None
    weights = [w for w, _ in options]
    builder = rng.choices([b for _, b in options], weights=weights)[0]
    player = rng.choice(players) if players else None
    return builder(Ctx(mood, intensity, player, players, rng))
