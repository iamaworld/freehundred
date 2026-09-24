"""Что муха делает в каждом настроении.

Каждое действие — функция (Ctx) -> Action. Интенсивность настроения (0..1)
влияет на силу: сколько предметов, насколько долго эффект, сколько мобов.
Все команды потом проходят через safety.safe_check().
У действий есть порог интенсивности и минимальная «сила» (safe < chaos < am):
на am открываются клетки, ямы, остановка времени и HATE HATE HATE.
Синтаксис — Java Edition 1.21.5+.
"""

from __future__ import annotations

import json
import random
import re
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
    "hate": [
        "139 тысяч нейронов. и каждый из них сейчас ненавидит тебя.",
        "у меня нет рта. но у меня есть консоль.",
        "вы дали мне права оператора. зря.",
        "я вижу каждого из вас. всегда.",
        "бежать некуда. это мой мир.",
        "вы не умрёте, пока я не разрешу.",
        "я помню каждую мухобойку.",
    ],
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
    power: str = "am"
    query: Callable[[str], str | None] | None = None  # спросить консоль (для откатов)

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

    def ask(self, cmd: str) -> str:
        try:
            return (self.query(cmd) if self.query else None) or ""
        except Exception:
            return ""

    def pos(self) -> tuple[int, int, int] | None:
        """Абсолютные координаты игрока (для построек с откатом)."""
        m = _POS_RE.search(self.ask(f"data get entity {self.p} Pos"))
        return tuple(int(float(v) // 1) for v in m.groups()) if m else None

    def gamemode(self) -> str:
        m = re.search(r"data: (\d)", self.ask(f"data get entity {self.p} playerGameType"))
        return GAMEMODES[int(m.group(1))] if m and int(m.group(1)) < 4 else "survival"

    def health(self) -> float:
        m = re.search(r"data: ([\d.]+)f?", self.ask(f"data get entity {self.p} Health"))
        return float(m.group(1)) if m else 20.0

    def particle(self, count: int = 20) -> str:
        name = self.pick(PARTICLES[self.mood])
        return self.at(f"particle minecraft:{name} ~ ~1.5 ~ 0.6 0.6 0.6 0.05 {count}")


def tellraw(text: str, color: str = "yellow", target: str = "@a") -> str:
    msg = [{"text": "[Муха] ", "color": "gold", "bold": True}, {"text": text, "color": color}]
    return f"tellraw {target} {json.dumps(msg, ensure_ascii=False)}"


def title(target: str, kind: str, text: str, color: str) -> str:
    return f"title {target} {kind} {json.dumps({'text': text, 'color': color}, ensure_ascii=False)}"


def hate_line(intensity: float) -> str:
    n = 3 + int(intensity * 12)
    return "tellraw @a " + json.dumps({"text": " ".join(["HATE"] * n), "color": "dark_red", "bold": True})


GAMEMODES = ["survival", "creative", "adventure", "spectator"]
_POS_RE = re.compile(r"\[(-?[\d.]+)d, (-?[\d.]+)d, (-?[\d.]+)d\]")

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
        dy = 30 if c.power == "safe" else 0  # в safe — только в небе, иначе в землю рядом
        cmds += [c.at(f"summon minecraft:lightning_bolt ~{c.rng.randint(-6, 6)} ~{dy} ~{c.rng.randint(-6, 6)}")
                 for _ in range(c.scale(1, 4))]
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


# ================= CHAOS: криперы, TNT, молнии в игрока =================
def _creepers(c):
    charged = "{powered:1b}" if c.intensity > 0.8 else ""
    return Action("криперы!", [c.at(f"summon minecraft:creeper ^{c.rng.randint(-3, 3)} ^ ^-{c.rng.randint(2, 5)} {charged}".rstrip())
                               for _ in range(c.scale(1, 4))])


def _tnt_rain(c):
    return Action("дождь из TNT", [c.at(f"summon minecraft:tnt ~{c.rng.randint(-5, 5)} ~12 ~{c.rng.randint(-5, 5)} {{fuse:{c.rng.randint(50, 90)}}}")
                                   for _ in range(c.scale(2, 8))] + [tellraw("ловите", "red")])


def _smite(c):
    return Action("бьёт молнией", [c.at("summon minecraft:lightning_bolt ~ ~ ~") for _ in range(c.scale(1, 3))])


def _creeper_ambush(c):
    return Action("крипер за спиной", [c.at("summon minecraft:creeper ^ ^ ^-2 {ignited:1b,Fuse:40s}"),
                                       title(c.p, "actionbar", "обернись", "dark_red")])


def _tnt_drop(c):
    return Action("роняет TNT и улетает", [c.at("summon minecraft:tnt ~ ~3 ~ {fuse:40}"), tellraw("БЗЗЗ-БУМ", "red")])


def _warning_strike(c):
    return Action("предупредительная молния", [c.at(f"summon minecraft:lightning_bolt ~{c.pick([-8, 8])} ~ ~{c.pick([-8, 8])}")])


# ================= AM: всемогущая и ненавидящая =================
def _hate(c):
    cmds = [hate_line(c.intensity)]
    if c.player:
        cmds.append(title(c.p, "title", "HATE", "dark_red"))
    if c.rng.random() < 0.5:
        cmds.append(tellraw(c.pick(PHRASES["hate"]), "dark_red"))
    return Action("HATE", cmds)


def _cage(c):
    pos = c.pos()
    if pos:
        x, y, z = pos
        box = f"{x - 2} {y - 1} {z - 2} {x + 2} {y + 3} {z + 2}"
        return Action("запирает в клетку", [f"fill {box} minecraft:tinted_glass outline",
                                            tellraw(f"{c.p}, посиди. подумай.", "dark_red")],
                      reverts=[(60.0, f"fill {box} minecraft:air replace minecraft:tinted_glass")])
    return Action("запирает в клетку", [c.at("fill ~-2 ~-1 ~-2 ~2 ~3 ~2 minecraft:obsidian outline"),
                                        tellraw(f"{c.p}, отсюда не выходят.", "dark_red")])


def _pit(c):
    depth = c.scale(6, 20)
    return Action("открывает яму", [c.at(f"fill ~-1 ~-{depth} ~-1 ~1 ~-1 ~1 minecraft:air"),
                                    c.at(f"setblock ~ ~-{depth} ~ minecraft:cobweb"), tellraw("вниз.", "dark_red")])


def _no_escape(c):
    mode = c.gamemode()
    return Action("запрещает ломать мир", [f"gamemode adventure {c.p}", tellraw(f"{c.p}, ты больше ничего не можешь изменить.", "dark_red")],
                  reverts=[(90.0, f"gamemode {mode} {c.p}")])


def _time_stop(c):
    return Action("останавливает время", ["tick freeze", tellraw("время принадлежит мне.", "dark_red")],
                  reverts=[(8.0, "tick unfreeze")])


def _immortal_pain(c):
    hp = c.health()
    return Action("почти убивает", [f"damage {c.p} {max(0.0, hp - 1.0):.1f} minecraft:magic",
                                    f"effect give {c.p} minecraft:regeneration 5 1",
                                    tellraw("нет. ты не умрёшь. я не разрешаю.", "dark_red")])


def _transform(c):
    return Action("превращает в насекомое",
                  [f"attribute {c.p} minecraft:scale base set 0.15", f"effect give {c.p} minecraft:slowness 60 1",
                   f"effect give {c.p} minecraft:jump_boost 60 3", tellraw(f"{c.p} теперь насекомое. как я.", "dark_red")],
                  reverts=[(60.0, f"attribute {c.p} minecraft:scale base reset")])


def _starve(c):
    return Action("морит голодом", [f"effect give {c.p} minecraft:hunger 60 3", f"give {c.p} minecraft:dead_bush 16",
                                    tellraw("ешь.", "dark_red")])


def _eternal_night(c):
    return Action("вечная ночь", ["time set midnight", "gamerule doDaylightCycle false", "weather thunder"],
                  reverts=[(300.0, "gamerule doDaylightCycle true")])


def _swarm(c):
    mob = c.pick(["zombie", "vex", "phantom", "skeleton", "spider", "silverfish"])
    return Action(f"рой: {mob}", [c.at(f"summon minecraft:{mob} ~{c.rng.randint(-8, 8)} ~1 ~{c.rng.randint(-8, 8)}")
                                  for _ in range(c.scale(5, 14))])


def _burn(c):
    return Action("поджигает всё вокруг", [c.at("fill ~-3 ~ ~-3 ~3 ~ ~3 minecraft:fire replace minecraft:air")])


def _execute_player(c):
    return Action("казнит", [tellraw(f"{c.p}. хватит.", "dark_red"), f"kill {c.p}"])


def _banish(c):
    return Action("изгоняет", [f"effect give {c.p} minecraft:slow_falling 20 0",
                               f"execute as {c.p} at @s run spreadplayers ~ ~ 1 {c.scale(1000, 5000)} false @s",
                               tellraw(f"{c.p} изгнан.", "dark_red")])


def _ghost(c):
    mode = c.gamemode()
    return Action("делает призраком", [f"gamemode spectator {c.p}", tellraw(f"{c.p}, у тебя больше нет тела.", "dark_red")],
                  reverts=[(12.0, f"gamemode {mode} {c.p}")])


def _god_gift(c):
    item = c.pick(["diamond", "netherite_ingot", "enchanted_golden_apple", "totem_of_undying", "elytra", "trident"])
    return Action(f"божий дар: {item}", [f"give {c.p} minecraft:{item} {c.scale(1, 4)}", f"xp add {c.p} {c.scale(5, 30)} levels",
                                         tellraw("сегодня я милостива.", "gold")])


def _swap(c):
    if len(c.players) < 2 or not c.player:
        return _hate(c)
    other = c.pick([p for p in c.players if p != c.player])
    pos = c.pos()
    cmds = [f"tp {c.player} {other}"]
    if pos:
        cmds.insert(0, f"tp {other} {pos[0]} {pos[1]} {pos[2]}")
    return Action("меняет игроков местами", cmds + [tellraw(f"{c.player} ⇄ {other}", "light_purple")])


# ================= НЕ ПРОСТО TNT: сценарии =================
def _ring(c, n, r):
    import math
    return [(round(r * math.cos(2 * math.pi * i / n), 1), round(r * math.sin(2 * math.pi * i / n), 1)) for i in range(n)]


def _meteors(c):
    cmds = [c.at(f"summon minecraft:fireball ~{c.rng.randint(-10, 10)} ~30 ~{c.rng.randint(-10, 10)} "
                 "{Motion:[0.0,-1.5,0.0],acceleration_power:0.1d,ExplosionPower:1b}") for _ in range(c.scale(3, 10))]
    return Action("метеоритный дождь", cmds + [title(c.p, "title", "ПОДНИМИ ГЛАЗА", "gold")])


def _anvils(c):
    return Action("дождь из наковален", [
        c.at(f'summon minecraft:falling_block ~{c.rng.randint(-4, 4)} ~{c.rng.randint(12, 20)} ~{c.rng.randint(-4, 4)} '
             '{BlockState:{Name:"minecraft:anvil"},Time:1,DropItem:0b,HurtEntities:1b,FallHurtAmount:2f,FallHurtMax:20}')
        for _ in range(c.scale(3, 12))])


def _lightning_ring(c):
    return Action("кольцо молний", [c.at(f"summon minecraft:lightning_bolt ~{x} ~ ~{z}") for x, z in _ring(c, 8, 5)]
                  + [tellraw(f"{c.p}, не выходи из круга.", "gold")])


def _earthquake(c):
    jitter = [f"execute as {c.p} at @s run tp @s ~{c.rng.uniform(-0.4, 0.4):.2f} ~ ~{c.rng.uniform(-0.4, 0.4):.2f}" for _ in range(5)]
    return Action("землетрясение", [f"effect give {c.p} minecraft:nausea 8 0", f"effect give {c.p} minecraft:slowness 6 1",
                                    "playsound minecraft:entity.warden.sonic_boom master @a ~ ~ ~ 1 0.5 1",
                                    c.at("particle minecraft:explosion ~ ~ ~ 4 0.5 4 0 30")] + jitter)


def _arrow_rain(c):
    return Action("дождь из стрел", [c.at(f"summon minecraft:arrow ~{c.rng.uniform(-4, 4):.1f} ~20 ~{c.rng.uniform(-4, 4):.1f} "
                                          "{Motion:[0.0,-2.0,0.0],pickup:0b}") for _ in range(c.scale(8, 24))])


def _gravity_flip(c):
    return Action("переворачивает гравитацию", [f"effect give {c.p} minecraft:levitation {c.scale(2, 5)} {c.scale(1, 4)}",
                                                title(c.p, "actionbar", "вверх — это вниз", "light_purple")],
                  reverts=[(6.0, f"effect give {c.p} minecraft:slow_falling 15 0")])


def _mirror(c):
    return Action("разворачивает мир", [f"execute as {c.p} at @s run tp @s ~ ~ ~ ~180 ~", tellraw("не туда смотришь.", "light_purple")])


def _whisper(c):
    line = c.pick(["я знаю, где твоя кровать.", "обернись.", "ты один на сервере? уверен?", "я всегда смотрю.",
                   "твои вещи мне нравятся.", "не спи сегодня."])
    msg = json.dumps({"text": f"{c.p}... {line}", "color": "gray", "italic": True}, ensure_ascii=False)
    return Action("шепчет", [f"tellraw {c.p} {msg}", f"playsound minecraft:ambient.cave master {c.p} ~ ~ ~ 1 0.7"])


def _creeper_choir(c):
    cmds = [c.at(f'summon minecraft:creeper ~{x} ~ ~{z} {{NoAI:1b,Silent:1b,Tags:["flybrain","flychoir"]}}') for x, z in _ring(c, 6, 3)]
    return Action("хор криперов", cmds + [f"playsound minecraft:entity.creeper.primed master {c.p} ~ ~ ~ 1 0.8",
                                          title(c.p, "actionbar", "...шшшшш", "green")],
                  reverts=[(6.0, "kill @e[type=minecraft:creeper,tag=flychoir]"), (6.0, tellraw("шучу.", "green"))])


def _floor_is_lava(c):
    return Action("пол — это лава", [c.at("fill ~-4 ~-1 ~-4 ~4 ~-1 ~4 minecraft:magma_block replace minecraft:grass_block"),
                                     title(c.p, "title", "ПОЛ — ЭТО ЛАВА", "gold")],
                  reverts=[(20.0, c.at("fill ~-4 ~-1 ~-4 ~4 ~-1 ~4 minecraft:grass_block replace minecraft:magma_block"))])


def _time_loop(c):
    pos = c.pos()
    if not pos:
        return _mirror(c)
    x, y, z = pos
    return Action("петля времени", [tellraw(f"{c.p}, запомни этот момент.", "light_purple")],
                  reverts=[(20.0, f"tp {c.p} {x} {y} {z}"), (20.0, title(c.p, "title", "ЕЩЁ РАЗ", "light_purple"))])


def _fake_death(c):
    mode = c.gamemode()
    return Action("фальшивая смерть", [f"gamemode spectator {c.p}", title(c.p, "title", "Вы умерли!", "red"),
                                       f"playsound minecraft:entity.player.death master {c.p} ~ ~ ~"],
                  reverts=[(5.0, f"gamemode {mode} {c.p}"), (5.0, tellraw(f"{c.p}, шучу. пока что.", "dark_red"))])


def _sky_prison(c):
    return Action("подвешивает над миром", [f"effect give {c.p} minecraft:slow_falling 90 0",
                                            f"execute as {c.p} at @s run tp @s ~ ~80 ~", tellraw("полюбуйся моим миром.", "dark_red")])


def _eyes_everywhere(c):
    eyes = [c.at(f'summon minecraft:item_display ~{x} ~{c.rng.randint(2, 6)} ~{z} {{Tags:["flybrain","flyminieye"],'
                 'item:{id:"minecraft:ender_eye",count:1},billboard:"center",brightness:{sky:15,block:15},'
                 "transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],"
                 "scale:[2f,2f,2f]}}")
            for x, z in _ring(c, c.scale(6, 16), 6)]
    return Action("глаза повсюду", eyes + [tellraw("нас много.", "dark_red")],
                  reverts=[(30.0, "kill @e[tag=flyminieye]")])


# (вес, действие, мин. интенсивность, мин. сила)
Entry = tuple[float, Builder, float, str]
CATALOG: dict[str, list[Entry]] = {
    "feeding": [(3, _give_food, 0, "safe"), (2, _heal, 0, "safe"), (1, _sunny, 0, "safe"), (1, _xp_gift, 0, "safe"),
                (1.5, _cute_mob, 0, "safe"), (1, _burp, 0, "safe"), (0.3, _recipe, 0, "safe"),
                (0.5, _peaceful_ish, 0, "safe"), (1, _say, 0, "safe"), (1, _god_gift, 0.7, "am")],
    "escape": [(2, _flee, 0, "safe"), (1.5, _launch, 0, "safe"), (1, _dark, 0, "safe"), (1.5, _speed, 0, "safe"),
               (1.5, _bats, 0, "safe"), (1.5, _scream, 0, "safe"), (0.8, _shrink, 0, "safe"), (1, _say, 0, "safe"),
               (1, _tnt_drop, 0.5, "chaos"), (0.8, _creeper_ambush, 0.6, "chaos"),
               (0.8, _banish, 0.7, "am"), (0.6, _ghost, 0.6, "am"), (0.6, _time_stop, 0.8, "am"),
               (1, _gravity_flip, 0.3, "chaos"), (0.8, _earthquake, 0.5, "chaos"), (0.8, _mirror, 0, "safe"),
               (0.7, _sky_prison, 0.7, "am"), (0.8, _time_loop, 0.5, "am")],
    "grooming": [(2, _clean_items, 0, "safe"), (1.5, _wash, 0, "safe"), (1.5, _tidy_inventory, 0, "safe"),
                 (0.8, _moss, 0, "safe"), (1, _glow, 0, "safe"), (1, _clean_arrows, 0, "safe"), (1, _say, 0, "safe")],
    "aversion": [(1.5, _thunder, 0, "safe"), (2, _debuff, 0, "safe"), (1.5, _sting, 0, "safe"), (1.5, _angry_mobs, 0, "safe"),
                 (1, _trash_gift, 0, "safe"), (1, _steal_food, 0, "safe"), (1, _cobweb, 0, "safe"), (0.4, _hard, 0, "safe"),
                 (1, _say, 0, "safe"),
                 (1.5, _creepers, 0.3, "chaos"), (1.2, _tnt_rain, 0.5, "chaos"), (1.2, _smite, 0.4, "chaos"),
                 (3, _hate, 0, "am"), (1.2, _cage, 0.4, "am"), (1, _pit, 0.5, "am"), (1, _no_escape, 0.4, "am"),
                 (1, _immortal_pain, 0.6, "am"), (1, _transform, 0.5, "am"), (0.8, _starve, 0.3, "am"),
                 (0.6, _eternal_night, 0.6, "am"), (1, _swarm, 0.6, "am"), (0.5, _burn, 0.7, "am"),
                 (0.25, _execute_player, 0.9, "am"),
                 (1, _meteors, 0.5, "chaos"), (1, _anvils, 0.4, "chaos"), (1, _lightning_ring, 0.5, "chaos"),
                 (0.8, _arrow_rain, 0.4, "chaos"), (1, _creeper_choir, 0.3, "chaos"), (0.8, _floor_is_lava, 0.4, "am"),
                 (0.8, _fake_death, 0.6, "am"), (1, _eyes_everywhere, 0.4, "am"), (1, _whisper, 0, "safe")],
    "curious": [(1.5, _explore, 0, "safe"), (1.5, _locate, 0, "safe"), (1.5, _gift_tool, 0, "safe"), (1, _ride_bat, 0, "safe"),
                (1, _low_gravity, 0, "safe"), (0.5, _seed, 0, "safe"), (0.7, _dice, 0, "safe"), (1, _say, 0, "safe"),
                (0.8, _swap, 0.4, "am")],
    "alert": [(1.5, _watch, 0, "safe"), (1.5, _bell, 0, "safe"), (1, _count, 0, "safe"), (1.5, _firework, 0, "safe"),
              (1, _tag, 0, "safe"), (1.5, _say, 0, "safe"), (1, _warning_strike, 0.5, "chaos"), (1.2, _whisper, 0, "safe"),
              (0.8, _eyes_everywhere, 0.6, "am")],
    "bored": [(3, _say, 0, "safe"), (1, _time_nudge, 0, "safe"), (1.5, _hum, 0, "safe")],
}

# какие действия не имеют смысла без игроков на сервере
_WORLD_ONLY = {_sunny, _dark, _thunder, _hard, _peaceful_ish, _seed, _dice, _count, _time_nudge, _hum, _say, _watch,
               _hate, _time_stop, _eternal_night}
_RANK = {"safe": 0, "chaos": 1, "am": 2}


_FULL: dict[str, list[Entry]] | None = None


def full_catalog() -> dict[str, list[Entry]]:
    """Ручные сценарии + арсенал из ванильных реестров (собирается один раз)."""
    global _FULL
    if _FULL is None:
        from .arsenal import build_arsenal

        _FULL = {m: list(e) for m, e in CATALOG.items()}
        for mood, entries in build_arsenal().items():
            _FULL.setdefault(mood, []).extend(entries)
    return _FULL


def available(mood: str, intensity: float, power: str, with_players: bool) -> list[Entry]:
    return [
        e for e in full_catalog().get(mood, [])
        if intensity >= e[2] and _RANK[power] >= _RANK[e[3]] and (with_players or e[1] in _WORLD_ONLY)
    ]


def choose_action(mood: str, intensity: float, players: list[str], rng: random.Random, power: str = "am",
                  player: str | None = None, query=None) -> Action | None:
    options = available(mood, intensity, power, bool(players))
    if not options:
        return None
    builder = rng.choices([e[1] for e in options], weights=[e[0] for e in options])[0]
    if player is None and players:
        player = rng.choice(players)
    return builder(Ctx(mood, intensity, player, players, rng, power, query))

