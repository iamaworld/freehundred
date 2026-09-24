"""Фильтр команд: что муха может, а что — нет.

Логика «всё, кроме того, что ломает сервер или мир насовсем»:
- разрешены только ванильные команды из ALLOWED (плагинные — нет);
- из них вырезано всё про сервер, права и баны (BLOCKED);
- у опасных, но весёлых команд есть лимиты (объём fill, урон, мобы...).
Каждая команда, которую пишет муха, проходит через check_command().
"""

from __future__ import annotations

import re

BLOCKED = {
    # сервер и права
    "stop", "restart", "reload", "op", "deop", "ban", "ban-ip", "pardon", "pardon-ip",
    "kick", "whitelist", "save-off", "publish", "debug", "jfr", "perf", "setidletimeout",
    "transfer", "datapack", "function", "schedule", "return", "test", "tick",
    "defaultgamemode", "gamemode",
    # мир навсегда
    "clone", "fillbiome", "place", "forceload", "worldborder", "setworldspawn", "item",
}

ALLOWED = {
    "advancement", "attribute", "bossbar", "clear", "damage", "data", "difficulty", "effect",
    "enchant", "execute", "experience", "xp", "fill", "gamerule", "give", "help", "kill", "list",
    "locate", "loot", "me", "msg", "tell", "w", "particle", "playsound", "random", "recipe",
    "ride", "rotate", "save-all", "say", "scoreboard", "seed", "setblock", "spawnpoint",
    "spectate", "spreadplayers", "stopsound", "summon", "tag", "team", "teammsg", "tm",
    "teleport", "tp", "tellraw", "time", "title", "trigger", "weather",
}

FORBIDDEN_ENTITIES = {
    "wither", "ender_dragon", "tnt", "tnt_minecart", "end_crystal", "creeper", "ghast", "fireball",
    "small_fireball", "dragon_fireball", "wither_skull", "warden", "ravager", "command_block_minecart",
    "falling_block", "block_display",
}
FORBIDDEN_BLOCKS = {
    "tnt", "lava", "fire", "soul_fire", "bedrock", "barrier", "command_block", "chain_command_block",
    "repeating_command_block", "structure_block", "structure_void", "jigsaw", "end_portal",
    "end_portal_frame", "nether_portal", "end_gateway", "light", "reinforced_deepslate",
}
FORBIDDEN_ITEMS = FORBIDDEN_BLOCKS | {
    "command_block_minecart", "debug_stick", "knowledge_book", "lava_bucket", "end_crystal",
    "tnt_minecart", "flint_and_steel", "fire_charge", "spawner", "trial_spawner",
    "wither_skeleton_skull", "dragon_egg",
} | {e + "_spawn_egg" for e in FORBIDDEN_ENTITIES}
FORBIDDEN_EFFECTS = {"instant_damage", "wither"}
ALLOWED_GAMERULES = {
    "doDaylightCycle", "doWeatherCycle", "doInsomnia", "doPatrolSpawning", "doTraderSpawning",
    "playersSleepingPercentage", "sendCommandFeedback", "showDeathMessages", "fallDamage",
    "announceAdvancements",
}
ALLOWED_ATTRIBUTES = {"scale", "gravity", "jump_strength", "movement_speed", "step_height", "safe_fall_distance"}

MAX_FILL_VOLUME = 125
MAX_DAMAGE = 6.0
MAX_GIVE = 64
MAX_SPREAD = 200
MAX_XP_LEVELS = 30
MAX_ABS_COORD_OFFSET = 60  # насколько далеко от игрока можно что-то делать


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


def _rel(tokens: list[str]) -> list[float]:
    """Координаты только относительные (~ или ^) и недалеко."""
    out = []
    for t in tokens:
        if not t or t[0] not in "~^":
            raise Rejected(f"абсолютная координата {t!r}")
        v = float(t[1:]) if len(t) > 1 else 0.0
        if abs(v) > MAX_ABS_COORD_OFFSET:
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


def check_command(cmd: str) -> None:
    """Бросает Rejected, если муха так делать не должна."""
    cmd = cmd.strip()
    if cmd.startswith("/"):
        cmd = cmd[1:]
    if not cmd or "\n" in cmd or "\r" in cmd:
        raise Rejected("пустая или многострочная команда")
    if len(cmd) > 1000:
        raise Rejected("слишком длинная команда")
    args = _split_args(cmd)
    root = args[0].lower()
    if ":" in root:
        ns, root = root.split(":", 1)
        if ns != "minecraft":
            raise Rejected(f"плагинная команда {args[0]!r}")
    if root in BLOCKED:
        raise Rejected(f"/{root} в чёрном списке")
    if root not in ALLOWED:
        raise Rejected(f"/{root} неизвестна мухе")
    _CHECKS.get(root, lambda a, c: None)(args[1:], cmd)


def is_allowed(cmd: str) -> bool:
    try:
        check_command(cmd)
        return True
    except Rejected:
        return False


def _execute(a, cmd):
    if "run" in a:
        check_command(" ".join(a[a.index("run") + 1 :]))


def _kill(a, cmd):
    if not a:
        raise Rejected("kill без цели убьёт исполнителя")
    target = a[0].lower()
    if not target.startswith("@e") or not re.search(r"type=(minecraft:)?(item|experience_orb|arrow)\b|tag=fly(brain|ride)\b", target):
        raise Rejected("убивать можно только предметы, стрелы и мух-питомцев")


def _damage(a, cmd):
    if len(a) < 2 or _is_broad(a[0]):
        raise Rejected("damage: нужна одна цель")
    if float(a[1]) > MAX_DAMAGE:
        raise Rejected("damage: слишком больно")


def _clear(a, cmd):
    if len(a) < 2:
        raise Rejected("clear: нужно указать предмет, а не весь инвентарь")
    if _is_broad(a[0]) or a[1].startswith("#") or a[1] == "*":
        raise Rejected("clear: слишком широко")
    if len(a) > 2 and int(a[2]) > MAX_GIVE:
        raise Rejected("clear: слишком много")


def _fill(a, cmd):
    if len(a) < 7:
        raise Rejected("fill: мало аргументов")
    x1, y1, z1, x2, y2, z2 = _rel(a[:6])
    vol = (abs(x2 - x1) + 1) * (abs(y2 - y1) + 1) * (abs(z2 - z1) + 1)
    if vol > MAX_FILL_VOLUME:
        raise Rejected(f"fill: объём {vol:.0f} > {MAX_FILL_VOLUME}")
    if _id(a[6]) in FORBIDDEN_BLOCKS:
        raise Rejected(f"fill: блок {a[6]} запрещён")
    if len(a) > 7 and a[7] == "destroy":
        raise Rejected("fill destroy запрещён")


def _setblock(a, cmd):
    if len(a) < 4:
        raise Rejected("setblock: мало аргументов")
    _rel(a[:3])
    if _id(a[3]) in FORBIDDEN_BLOCKS:
        raise Rejected(f"setblock: блок {a[3]} запрещён")
    if len(a) > 4 and a[4] == "destroy":
        raise Rejected("setblock destroy запрещён")


def _summon(a, cmd):
    if not a:
        raise Rejected("summon: кого?")
    ent = _id(a[0])
    if ent in FORBIDDEN_ENTITIES:
        raise Rejected(f"summon: {ent} запрещён")
    if len(a) >= 4:
        _, dy, _ = _rel(a[1:4])
        if ent == "lightning_bolt" and dy < 20:
            raise Rejected("молния только высоко в небе (иначе пожар)")
    elif ent == "lightning_bolt":
        raise Rejected("молния только высоко в небе (иначе пожар)")


def _give(a, cmd):
    if len(a) < 2:
        raise Rejected("give: мало аргументов")
    if _id(a[1]) in FORBIDDEN_ITEMS:
        raise Rejected(f"give: {a[1]} запрещён")
    if len(a) > 2 and int(a[2]) > MAX_GIVE:
        raise Rejected("give: слишком много")


def _effect(a, cmd):
    if a and a[0] == "give" and len(a) >= 3 and _id(a[2]) in FORBIDDEN_EFFECTS:
        raise Rejected(f"effect: {a[2]} запрещён")
    if a and a[0] == "give" and len(a) >= 5 and int(a[4]) > 4:
        raise Rejected("effect: слишком сильно")


def _gamerule(a, cmd):
    if not a or a[0] not in ALLOWED_GAMERULES:
        raise Rejected(f"gamerule {a[0] if a else ''} запрещено")


def _attribute(a, cmd):
    if len(a) < 2 or _id(a[1]) not in ALLOWED_ATTRIBUTES:
        raise Rejected("attribute: только размер/гравитация/прыжок/скорость")
    if len(a) >= 5 and a[2] == "base" and a[3] == "set":
        if not 0.01 <= float(a[4]) <= 4.0:
            raise Rejected("attribute: значение вне 0.01..4")


def _teleport(a, cmd):
    coords = [t for t in a if t[:1] in "~^" or re.fullmatch(r"-?\d+(\.\d+)?", t)]
    if coords:
        _rel(coords[:3])


def _spreadplayers(a, cmd):
    if len(a) < 5:
        raise Rejected("spreadplayers: мало аргументов")
    _rel(a[:2])
    if float(a[3]) > MAX_SPREAD:
        raise Rejected("spreadplayers: слишком далеко")


def _xp(a, cmd):
    if len(a) >= 3 and a[0] in ("add", "set") and abs(int(a[2])) > MAX_XP_LEVELS * 100:
        raise Rejected("xp: слишком много")
    if len(a) >= 4 and a[3] == "levels" and abs(int(a[2])) > MAX_XP_LEVELS:
        raise Rejected("xp: слишком много уровней")


def _data(a, cmd):
    if not a or a[0] != "get":
        raise Rejected("data: только чтение")


def _loot(a, cmd):
    if not a or a[0] != "give":
        raise Rejected("loot: только give")


def _difficulty(a, cmd):
    if a and a[0] == "peaceful":
        raise Rejected("peaceful удалит всех мобов")


_CHECKS = {
    "execute": _execute,
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


def safe_check(cmd: str) -> str | None:
    """None если ок, иначе причина отказа. Ошибки разбора — тоже отказ."""
    try:
        check_command(cmd)
        return None
    except Rejected as e:
        return str(e)
    except (ValueError, IndexError) as e:
        return f"не разобрал команду: {e}"
