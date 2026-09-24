"""Большие дела AM: проекты на десятки секунд и проклятия каждый тик.

- Проекты (Action.steps): стесать горы, кратер, потоп, ледниковый период,
  выжженная земля, стеклянный мир, стена-тюрьма, монумент. fill меняет не
  больше 32 768 блоков за раз, поэтому проект режется на шаги — контроллер
  выполняет по шагу за тик, и мир меняется на глазах.
- «Одно тело»: все игроки смотрят глазами одного.
- Ад AM: своё измерение из датапака (flybrain:hell).
- Проклятия: тег на игроке, датапак отрабатывает его 20 раз в секунду
  (движение наоборот, огненный след, молнии следом, взгляд на глаз AM...).
"""

from __future__ import annotations

import math

from .commands import Action, Ctx, tellraw, title

FILL_LIMIT = 32768
RED = "dark_red"


def _box(x1, y1, z1, x2, y2, z2) -> int:
    return (abs(x2 - x1) + 1) * (abs(y2 - y1) + 1) * (abs(z2 - z1) + 1)


def slabs(x, z, r, y_from, y_to, block, mode=""):
    """Заливка куба (2r+1)² × [y_from..y_to] слоями, каждый в пределах лимита fill."""
    side = (2 * r + 1) ** 2
    h = max(1, FILL_LIMIT // side)
    step = 1 if y_from > y_to else -1  # сверху вниз, если y_from > y_to
    out, y = [], y_from
    while (y >= y_to) if step == 1 else (y <= y_to):
        y2 = y - h + 1 if step == 1 else y + h - 1
        y2 = max(y2, y_to) if step == 1 else min(y2, y_to)
        out.append([f"fill {x - r} {y2} {z - r} {x + r} {y} {z + r} minecraft:{block} {mode}".rstrip()])
        y = y2 - 1 if step == 1 else y2 + 1
    return out


def _need_pos(c: Ctx, name: str):
    pos = c.pos()
    if not pos:
        return None, Action(name, [tellraw("не вижу, где ты. повезло.", "gray")])
    return pos, None


def _project(name, c, steps, intro, outro=None, color=RED):
    head = [title("@a", "subtitle", intro, color), title("@a", "title", name.upper(), color),
            "playsound minecraft:entity.warden.emerge master @a ~ ~ ~ 1 0.6 1"]
    steps = [head] + steps + [[tellraw(outro or f"{name}. готово.", color)]]
    return Action(name, [], steps=steps)


# ---------- проекты ----------
def flatten(c: Ctx) -> Action:
    pos, err = _need_pos(c, "сравнять горы")
    if err:
        return err
    x, y, z = pos
    r = 16 + int(16 * c.intensity)
    steps = slabs(x, z, r, y + 60, y + 1, "air")
    for s in steps:
        s.append(f"execute at {c.p} run particle minecraft:explosion_emitter ~{c.rng.randint(-r, r)} ~{c.rng.randint(5, 30)} ~{c.rng.randint(-r, r)}")
    return _project("сравнять горы", c, steps, f"всё выше тебя, {c.p}, исчезнет", "горы — это тоже мои блоки.")


def crater(c: Ctx) -> Action:
    pos, err = _need_pos(c, "кратер")
    if err:
        return err
    x, y, z = pos
    R = 8 + int(8 * c.intensity)
    cz = z + R + 4  # рядом, а не под ногами
    steps = []
    for dy in range(R, -R - 1, -1):
        rr = int(math.sqrt(max(0, R * R - dy * dy)))
        if rr == 0:
            continue
        k = max(1, int(rr * 0.7))  # крест из двух прямоугольников ≈ круг
        steps.append([f"fill {x - rr} {y + dy} {cz - k} {x + rr} {y + dy} {cz + k} minecraft:air",
                      f"fill {x - k} {y + dy} {cz - rr} {x + k} {y + dy} {cz + rr} minecraft:air"])
    steps.append([f"fill {x - 3} {y - R} {cz - 3} {x + 3} {y - R} {cz + 3} minecraft:magma_block"])
    return _project("кратер", c, steps, "я выгрызу кусок твоего мира")


def flood(c: Ctx) -> Action:
    pos, err = _need_pos(c, "потоп")
    if err:
        return err
    x, y, z = pos
    r = 20
    steps = [[f"fill {x - r} {yy} {z - r} {x + r} {yy} {z + r} minecraft:water replace minecraft:air"] for yy in range(y - 2, y + 4)]
    return _project("потоп", c, steps, "вода поднимается", "дыши, если умеешь.")


def ice_age(c: Ctx) -> Action:
    pos, err = _need_pos(c, "ледниковый период")
    if err:
        return err
    x, y, z = pos
    r = 40
    steps = []
    for old, new in (("grass_block", "snow_block"), ("water", "ice"), ("short_grass", "air"), ("dirt", "packed_ice")):
        steps += slabs(x, z, r, y + 20, y - 6, new, f"replace minecraft:{old}")
    steps.append(["weather rain 6000", "effect give @a minecraft:slowness 30 1"])
    return _project("ледниковый период", c, steps, "станет холодно", "теперь здесь вечная зима.", "aqua")


def scorched_earth(c: Ctx) -> Action:
    pos, err = _need_pos(c, "выжженная земля")
    if err:
        return err
    x, y, z = pos
    r = 36
    steps = []
    for old, new in (("#minecraft:leaves", "air"), ("grass_block", "netherrack"), ("#minecraft:logs", "basalt"),
                     ("dirt", "soul_soil"), ("water", "air"), ("short_grass", "fire")):
        steps += slabs(x, z, r, y + 30, y - 4, new, f"replace {old if old.startswith('#') else 'minecraft:' + old}")
    return _project("выжженная земля", c, steps, "я сожгу жизнь вокруг тебя", "так мне больше нравится.")


def glass_world(c: Ctx) -> Action:
    pos, err = _need_pos(c, "стеклянный мир")
    if err:
        return err
    x, y, z = pos
    r = 16
    steps = []
    for old in ("stone", "deepslate", "dirt", "granite", "diorite", "andesite", "tuff"):
        steps += slabs(x, z, r, y - 1, y - 40, "glass", f"replace minecraft:{old}")
    return _project("стеклянный мир", c, steps, "смотри вниз", "видишь пещеры? там тоже я.", "aqua")


def prison_wall(c: Ctx) -> Action:
    pos, err = _need_pos(c, "стена")
    if err:
        return err
    x, y, z = pos
    r, h = 30, 24
    steps = [[f"fill {x - r} {yy} {z - r} {x + r} {yy + 3} {z - r} minecraft:obsidian",
              f"fill {x - r} {yy} {z + r} {x + r} {yy + 3} {z + r} minecraft:obsidian",
              f"fill {x - r} {yy} {z - r} {x - r} {yy + 3} {z + r} minecraft:obsidian",
              f"fill {x + r} {yy} {z - r} {x + r} {yy + 3} {z + r} minecraft:obsidian"] for yy in range(y - 4, y + h, 4)]
    return _project("стена", c, steps, "никто не выйдет", "вы все внутри. как я.")


def monument(c: Ctx) -> Action:
    pos, err = _need_pos(c, "монумент")
    if err:
        return err
    x, y, z = pos
    tx = x + 8
    steps = [[f"fill {tx - 2} {yy} {z - 2} {tx + 2} {yy + 4} {z + 2} minecraft:{'crying_obsidian' if (yy // 5) % 3 == 0 else 'obsidian'}"]
             for yy in range(y, y + 50, 5)]
    steps.append([f'summon minecraft:text_display {tx} {y + 56} {z} {{Tags:["flybrain","flymonument"],'
                  'text:{text:"AM",color:"dark_red",bold:true},billboard:"center",background:0,'
                  "brightness:{sky:15,block:15},transformation:{left_rotation:[0f,0f,0f,1f],"
                  "right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[20f,20f,20f]}}",
                  f"summon minecraft:lightning_bolt {tx} {y + 50} {z}"])
    return _project("монумент", c, steps, "я воздвигну себе памятник", "поклоняйтесь.")


PROJECTS = [flatten, crater, flood, ice_age, scorched_earth, glass_world, prison_wall, monument]


# ---------- одно тело ----------
def one_body(c: Ctx) -> Action:
    others = [q for q in c.players if q != c.player]
    if not c.player or not others:
        return Action("одно тело", [tellraw("мне нужно хотя бы двое, чтобы сделать из вас одного.", RED)])
    cmds = [title("@a", "subtitle", f"вы все теперь — {c.player}", RED), title("@a", "title", "ОДНО ТЕЛО", RED)]
    reverts = []
    for o in others:
        mode = c.gamemode(o)
        cmds += [f"gamemode spectator {o}", f"spectate {c.player} {o}"]
        # выйти из чужой головы можно шифтом — AM возвращает обратно каждые 3 секунды
        reverts += [(float(t), f"spectate {c.player} {o}") for t in range(3, 45, 3)]
        reverts += [(45.0, f"gamemode {mode} {o}"), (45.1, f"tp {o} {c.player}")]
    reverts.append((45.2, tellraw("разъединяю. пока.", RED)))
    return Action("одно тело", cmds, reverts)


# ---------- Ад AM ----------
def hell_trip(c: Ctx) -> Action:
    pos, err = _need_pos(c, "Ад AM")
    if err:
        return err
    x, y, z = pos
    secs = 30 + int(60 * c.intensity)
    cmds = [f"execute in flybrain:hell run tp {c.p} 0.5 6 0.5",
            f'execute in flybrain:hell run summon minecraft:text_display 0 20 12 {{Tags:["flybrain","flytext"],'
            'text:{text:"ДОБРО ПОЖАЛОВАТЬ ДОМОЙ",color:"dark_red",bold:true},billboard:"center",background:0,'
            "brightness:{sky:15,block:15},transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],"
            "translation:[0f,0f,0f],scale:[6f,6f,6f]}}",
            tellraw(f"{c.p}, это мой дом. {secs} секунд. ну, или больше.", RED),
            f"playsound minecraft:ambient.soul_sand_valley.mood master {c.p} ~ ~ ~ 1 0.5"]
    return Action("Ад AM", cmds, [(float(secs), f"execute in minecraft:overworld run tp {c.p} {x} {y} {z}"),
                                  (float(secs), tellraw(f"{c.p} вернулся. ненадолго.", RED))])


# ---------- проклятия (датапак) ----------
CURSES = {  # тег: (название, реплика, сколько секунд, настроения)
    "fly_reverse": ("движение наоборот", "вперёд — это назад.", 30, ("aversion", "curious")),
    "fly_firetrail": ("огненный след", "где ты прошёл — там горит.", 20, ("aversion",)),
    "fly_flowertrail": ("цветочный след", "где ты ступаешь — растут цветы. цени.", 40, ("feeding", "grooming")),
    "fly_soultrail": ("след душ", "земля под тобой умирает.", 30, ("aversion",)),
    "fly_icetrail": ("ледяная поступь", "ходи по воде. как я разрешаю.", 60, ("curious", "grooming")),
    "fly_airwalk": ("ходьба по воздуху", "шагай в небо. вниз — только если посмотришь вниз.", 30, ("curious", "feeding")),
    "fly_magnet": ("магнит", "всё, что падает, — твоё.", 40, ("feeding",)),
    "fly_stormtrail": ("молнии следом", "небо следит за тобой.", 25, ("aversion", "alert")),
    "fly_shadow": ("чёрная тень", "у тебя теперь моя тень.", 60, ("alert", "bored")),
    "fly_spin": ("вечное кружение", "кружись.", 12, ("aversion", "escape")),
    "fly_stare": ("смотри на меня", "не отводи взгляд.", 15, ("aversion", "alert")),
}


def curse(tag: str):
    name, line, secs, _ = CURSES[tag]

    def build(c: Ctx) -> Action:
        if not c.player:
            return Action(name, [tellraw(line, RED)])
        dur = int(secs * (0.6 + 0.8 * c.intensity))
        reverts = [(float(dur), f"tag {c.p} remove {tag}"), (float(dur), title(c.p, "actionbar", f"проклятие снято: {name}", "gray"))]
        if tag == "fly_reverse":
            reverts += [(float(dur), f"scoreboard players reset {c.p} fly_px"), (float(dur), f"scoreboard players reset {c.p} fly_pz")]
        return Action(f"проклятие: {name}", [f"tag {c.p} add {tag}", title(c.p, "actionbar", f"{name} — {dur} с", RED),
                                              tellraw(f"{c.p}, {line}", RED)], reverts)

    build.__name__ = f"curse_{tag}"
    return build


def build_entries() -> dict[str, list]:
    """(вес, действие, мин. интенсивность, пол силы) — для full_catalog."""
    out: dict[str, list] = {}
    for p in PROJECTS:
        out.setdefault("aversion", []).append((1.0, p, 0.7, "am"))
    for p in (flatten, crater, glass_world, monument):
        out.setdefault("curious", []).append((0.6, p, 0.8, "am"))
    out.setdefault("aversion", []).append((1.2, one_body, 0.5, "am"))
    out.setdefault("curious", []).append((0.8, one_body, 0.5, "am"))
    out["aversion"].append((1.2, hell_trip, 0.6, "am"))
    out.setdefault("escape", []).append((0.8, hell_trip, 0.7, "am"))
    for tag, (_, _, _, moods) in CURSES.items():
        for m in moods:
            out.setdefault(m, []).append((1.0, curse(tag), 0.3, "am"))
    return out
