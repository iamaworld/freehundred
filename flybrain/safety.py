"""Фильтр команд: что муха может, а что — нет. Три уровня силы (FLY_POWER):

- ``am`` (по умолчанию) — почти всемогущая, как AM из «У меня нет рта, но я
  должен кричать»: убивает, строит клетки, останавливает время, жжёт мир.
  Нельзя только то, что отнимает сервер у владельца: выключить его, выдать
  себе/другим оп, банить, трогать вайтлист, отключать сохранения, перезагружать
  датапаки. И никаких плагинных команд.
- ``chaos`` — криперы, TNT, молнии куда угодно, но с лимитами (объём fill,
  урон, никаких визеров и gamemode).
- ``safe`` — детский режим: ничего не взрывается, всё обратимо.
"""

from __future__ import annotations

import re

POWERS = ("safe", "chaos", "am")

# нельзя ни при какой силе: это власть над самим сервером
ALWAYS_BLOCKED = {
    "stop", "restart", "reload", "op", "deop", "ban", "ban-ip", "pardon", "pardon-ip",
    "whitelist", "save-off", "publish", "debug", "jfr", "perf", "setidletimeout", "transfer",
    "datapack",
}

# безобидное ядро (safe/chaos разрешают только его)
ALLOWED = {
    "advancement", "attribute", "bossbar", "clear", "damage", "data", "difficulty", "effect",
    "enchant", "execute", "experience", "xp", "fill", "gamerule", "give", "help", "kill", "list",
    "locate", "loot", "me", "msg", "tell", "w", "particle", "playsound", "random", "recipe",
    "ride", "rotate", "save-all", "say", "scoreboard", "seed", "setblock", "spawnpoint",
    "spectate", "spreadplayers", "stopsound", "summon", "tag", "team", "teammsg", "tm",
    "teleport", "tp", "tellraw", "time", "title", "trigger", "weather",
}
# остальные ванильные команды — только для am
AM_ONLY = {
    "kick", "gamemode", "defaultgamemode", "clone", "fillbiome", "place", "forceload", "worldborder",
    "setworldspawn", "item", "tick", "function", "schedule", "return", "test", "save-on", "dialog",
    "waypoint",
}
VANILLA = ALLOWED | AM_ONLY

FORBIDDEN_ENTITIES = {
    "safe": {
        "wither", "ender_dragon", "tnt", "tnt_minecart", "end_crystal", "creeper", "ghast", "fireball",
        "small_fireball", "dragon_fireball", "wither_skull", "warden", "ravager", "command_block_minecart",
        "falling_block",
    },
    "chaos": {"wither", "ender_dragon", "warden", "command_block_minecart", "end_crystal"},
}
_BLOCKS_BASE = {
    "bedrock", "barrier", "command_block", "chain_command_block", "repeating_command_block",
    "structure_block", "structure_void", "jigsaw", "end_portal", "end_portal_frame", "end_gateway",
    "light", "reinforced_deepslate",
}
FORBIDDEN_BLOCKS = {
    "safe": _BLOCKS_BASE | {"tnt", "lava", "fire", "soul_fire", "nether_portal"},
    "chaos": _BLOCKS_BASE | {"lava"},
}
_ITEMS_BASE = {"command_block_minecart", "debug_stick", "knowledge_book", "spawner", "trial_spawner", "dragon_egg"}
FORBIDDEN_ITEMS = {
    "safe": FORBIDDEN_BLOCKS["safe"] | _ITEMS_BASE | {
        "lava_bucket", "end_crystal", "tnt_minecart", "flint_and_steel", "fire_charge", "wither_skeleton_skull",
    } | {e + "_spawn_egg" for e in FORBIDDEN_ENTITIES["safe"]},
    "chaos": FORBIDDEN_BLOCKS["chaos"] | _ITEMS_BASE | {"lava_bucket", "end_crystal", "wither_skeleton_skull"}
    | {e + "_spawn_egg" for e in FORBIDDEN_ENTITIES["chaos"]},
}
FORBIDDEN_EFFECTS = {"instant_damage", "wither"}
ALLOWED_GAMERULES = {
    "doDaylightCycle", "doWeatherCycle", "doInsomnia", "doPatrolSpawning", "doTraderSpawning",
    "playersSleepingPercentage", "sendCommandFeedback", "showDeathMessages", "fallDamage",
    "announceAdvancements",
}
ALLOWED_ATTRIBUTES = {"scale", "gravity", "jump_strength", "movement_speed", "step_height", "safe_fall_distance"}

LIMITS = {
    #        fill  damage give spread xp  offset
    "safe": (125, 6.0, 64, 200, 30, 60),
    "chaos": (1000, 12.0, 64, 500, 30, 100),
}
_BODY_TAG = re.compile(r"tag=fly[a-z0-9_]*")


class Rejected(ValueError):
    pass


def _id(token: str) -> str:
    """minecraft:cake{...}[...] -> cake"""
    token = re.split(r"[\[{]", token, maxsplit=1)[0]
    return token.split(":", 1)[-1].lower()


def _is_broad(selector: str) -> bool:
    """@a / @e без фильтра типа — «по всем»."""
    s = selector.lower()
    if s.startswith("@a"):
        return True
    return s.startswith("@e") and "type=" not in s


def _rel(tokens: list[str], power: str = "safe") -> list[float]:
    """Координаты только относительные (~ или ^) и недалеко."""
    max_off = LIMITS[power][5]
    out = []
    for t in tokens:
        if not t or t[0] not in "~^":
            raise Rejected(f"абсолютная координата {t!r}")
        v = float(t[1:]) if len(t) > 1 else 0.0
        if abs(v) > max_off:
            raise Rejected(f"слишком далеко: {t}")
        out.append(v)
    return out


def _split_args(rest: str) -> list[str]:
    """Режет по пробелам, не разрывая {...} [...] и строки в кавычках."""
    out, cur, depth, quote = [], [], 0, None
    for ch in rest:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        if ch == " " and depth == 0:
            if cur:
                out.append("".join(cur))
                cur = []
            continue
        cur.append(ch)
    if cur:
        out.append("".join(cur))
    return out


def check_command(cmd: str, power: str = "am") -> None:
    """Бросает Rejected, если муха так делать не должна."""
    if power not in POWERS:
        raise ValueError(f"неизвестная сила {power!r}, нужна одна из {POWERS}")
    cmd = cmd.strip()
    if cmd.startswith("/"):
        cmd = cmd[1:]
    if not cmd or "\n" in cmd or "\r" in cmd:
        raise Rejected("пустая или многострочная команда")
    if len(cmd) > 1400:
        raise Rejected("слишком длинная команда")
    args = _split_args(cmd)
    root = args[0].lower()
    if ":" in root:
        ns, root = root.split(":", 1)
        if ns != "minecraft":
            raise Rejected(f"плагинная команда {args[0]!r}")
    if root in ALWAYS_BLOCKED:
        raise Rejected(f"/{root} — власть над сервером остаётся у владельца")
    if root not in VANILLA:
        raise Rejected(f"/{root} неизвестна мухе")
    if root == "execute":
        _execute(args[1:], power)
        return
    if power == "am":
        return
    if root not in ALLOWED:
        raise Rejected(f"/{root} доступна только при FLY_POWER=am")
    check = _CHECKS.get(root)
    if check:
        check(args[1:], power)


def is_allowed(cmd: str, power: str = "am") -> bool:
    try:
        check_command(cmd, power)
        return True
    except Rejected:
        return False


def _execute(a, power):
    if "run" in a:
        check_command(" ".join(a[a.index("run") + 1 :]), power)


def _kill(a, power):
    if not a:
        raise Rejected("kill без цели убьёт исполнителя")
    target = a[0].lower()
    if not target.startswith("@e") or not re.search(
        r"type=(minecraft:)?(item|experience_orb|arrow)\b|tag=fly[a-z]*\b", target
    ):
        raise Rejected("убивать можно только предметы, стрелы и мух-питомцев (игроков — только при am)")


def _damage(a, power):
    if len(a) < 2 or _is_broad(a[0]):
        raise Rejected("damage: нужна одна цель")
    if float(a[1]) > LIMITS[power][1]:
        raise Rejected("damage: слишком больно")


def _clear(a, power):
    if len(a) < 2:
        raise Rejected("clear: нужно указать предмет, а не весь инвентарь")
    if _is_broad(a[0]) or a[1].startswith("#") or a[1] == "*":
        raise Rejected("clear: слишком широко")
    if len(a) > 2 and int(a[2]) > LIMITS[power][2]:
        raise Rejected("clear: слишком много")


def _fill(a, power):
    if len(a) < 7:
        raise Rejected("fill: мало аргументов")
    x1, y1, z1, x2, y2, z2 = _rel(a[:6], power)
    vol = (abs(x2 - x1) + 1) * (abs(y2 - y1) + 1) * (abs(z2 - z1) + 1)
    if vol > LIMITS[power][0]:
        raise Rejected(f"fill: объём {vol:.0f} > {LIMITS[power][0]}")
    if _id(a[6]) in FORBIDDEN_BLOCKS[power]:
        raise Rejected(f"fill: блок {a[6]} запрещён")
    if len(a) > 7 and a[7] == "destroy" and power == "safe":
        raise Rejected("fill destroy запрещён")


def _setblock(a, power):
    if len(a) < 4:
        raise Rejected("setblock: мало аргументов")
    _rel(a[:3], power)
    if _id(a[3]) in FORBIDDEN_BLOCKS[power]:
        raise Rejected(f"setblock: блок {a[3]} запрещён")
    if len(a) > 4 and a[4] == "destroy" and power == "safe":
        raise Rejected("setblock destroy запрещён")


def _summon(a, power):
    if not a:
        raise Rejected("summon: кого?")
    ent = _id(a[0])
    if ent in FORBIDDEN_ENTITIES[power]:
        raise Rejected(f"summon: {ent} запрещён")
    dy = _rel(a[1:4], power)[1] if len(a) >= 4 else 0.0
    if power == "safe" and ent == "lightning_bolt" and dy < 20:
        raise Rejected("в safe молния только высоко в небе (иначе пожар)")


def _give(a, power):
    if len(a) < 2:
        raise Rejected("give: мало аргументов")
    if _id(a[1]) in FORBIDDEN_ITEMS[power]:
        raise Rejected(f"give: {a[1]} запрещён")
    if len(a) > 2 and int(a[2]) > LIMITS[power][2]:
        raise Rejected("give: слишком много")


def _effect(a, power):
    if a and a[0] == "give" and len(a) >= 3 and _id(a[2]) in FORBIDDEN_EFFECTS and power == "safe":
        raise Rejected(f"effect: {a[2]} запрещён")
    if a and a[0] == "give" and len(a) >= 5 and int(a[4]) > 4:
        raise Rejected("effect: слишком сильно")


def _gamerule(a, power):
    if not a or a[0] not in ALLOWED_GAMERULES:
        raise Rejected(f"gamerule {a[0] if a else ''} запрещено")


def _attribute(a, power):
    if len(a) < 2 or _id(a[1]) not in ALLOWED_ATTRIBUTES:
        raise Rejected("attribute: только размер/гравитация/прыжок/скорость")
    if len(a) >= 5 and a[2] == "base" and a[3] == "set":
        if not 0.01 <= float(a[4]) <= 4.0:
            raise Rejected("attribute: значение вне 0.01..4")


def _teleport(a, power):
    coords = [t for t in a if t[:1] in "~^" or re.fullmatch(r"-?\d+(\.\d+)?", t)]
    if coords:
        _rel(coords[:3], power)


def _spreadplayers(a, power):
    if len(a) < 5:
        raise Rejected("spreadplayers: мало аргументов")
    _rel(a[:2], power)
    if float(a[3]) > LIMITS[power][3]:
        raise Rejected("spreadplayers: слишком далеко")


def _xp(a, power):
    cap = LIMITS[power][4]
    if len(a) >= 3 and a[0] in ("add", "set") and abs(int(a[2])) > cap * 100:
        raise Rejected("xp: слишком много")
    if len(a) >= 4 and a[3] == "levels" and abs(int(a[2])) > cap:
        raise Rejected("xp: слишком много уровней")


def _data(a, power):
    if a and a[0] == "get":
        return
    # своё тело (глаз) муха может менять всегда
    if len(a) >= 3 and a[0] in ("merge", "modify") and a[1] == "entity" and _BODY_TAG.search(a[2]):
        return
    raise Rejected("data: только чтение (и своё тело)")


def _loot(a, power):
    if not a or a[0] != "give":
        raise Rejected("loot: только give")


def _difficulty(a, power):
    if a and a[0] == "peaceful":
        raise Rejected("peaceful удалит всех мобов")


_CHECKS = {
    "kill": _kill,
    "damage": _damage,
    "clear": _clear,
    "fill": _fill,
    "setblock": _setblock,
    "summon": _summon,
    "give": _give,
    "effect": _effect,
    "gamerule": _gamerule,
    "attribute": _attribute,
    "teleport": _teleport,
    "tp": _teleport,
    "spreadplayers": _spreadplayers,
    "experience": _xp,
    "xp": _xp,
    "data": _data,
    "loot": _loot,
    "difficulty": _difficulty,
}


def safe_check(cmd: str, power: str = "am") -> str | None:
    """None если ок, иначе причина отказа. Ошибки разбора — тоже отказ."""
    try:
        check_command(cmd, power)
        return None
    except Rejected as e:
        return str(e)
    except (ValueError, IndexError) as e:
        return f"не разобрал команду: {e}"
