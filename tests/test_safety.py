import random

import pytest

from flybrain.commands import CATALOG, Ctx, _RANK, choose_action, full_catalog
from flybrain.safety import safe_check

# никогда, ни при какой силе: сервер остаётся у владельца
NEVER = [
    "stop", "/stop", "minecraft:stop", "op Steve", "deop Steve", "ban Steve", "ban-ip 1.2.3.4", "pardon Steve",
    "whitelist off", "reload", "save-off", "datapack disable vanilla", "execute as @a run stop",
    "execute at Steve run execute as @a run op @s", "luckperms user Steve permission set *", "essentials:god Steve",
    "bukkit:reload", "", "say hi\nstop",
]


@pytest.mark.parametrize("power", ["safe", "chaos", "am"])
@pytest.mark.parametrize("cmd", NEVER)
def test_never_allowed(cmd, power):
    assert safe_check(cmd, power) is not None


AM_ONLY = [
    "kill @a", "kill Steve", "gamemode adventure Steve", "tick freeze", "kick Steve",
    "fill ~-50 ~-50 ~-50 ~50 ~50 ~50 minecraft:air", "clone ~ ~ ~ ~1 ~1 ~1 ~5 ~5 ~5", "worldborder set 10",
    "summon minecraft:wither", "give Steve minecraft:command_block", "damage Steve 100",
    "tp Steve 0 -100 0", "clear Steve", "execute at Steve run fill ~-3 ~ ~-3 ~3 ~ ~3 minecraft:lava",
]


@pytest.mark.parametrize("cmd", AM_ONLY)
def test_am_can_almost_anything(cmd):
    assert safe_check(cmd, "am") is None
    assert safe_check(cmd, "chaos") is not None


CHAOS = [
    "summon minecraft:creeper ~ ~ ~ {powered:1b}", "execute at Steve run summon minecraft:tnt ~2 ~12 ~ {fuse:60}",
    "execute at Steve run summon minecraft:lightning_bolt ~ ~ ~", "summon minecraft:lightning_bolt",
    "give Steve minecraft:tnt 32", "execute at Steve run setblock ~ ~ ~ minecraft:tnt",
    "execute at Steve run fill ~ ~ ~ ~3 ~3 ~3 minecraft:fire", "damage Steve 10",
]


@pytest.mark.parametrize("cmd", CHAOS)
def test_chaos_allows_creepers_tnt_lightning(cmd):
    assert safe_check(cmd, "chaos") is None
    assert safe_check(cmd, "safe") is not None


@pytest.mark.parametrize(
    "cmd",
    [
        "kill @a", "kill @e", "kill Steve", "kill @e[type=player]", "kill @e[type=minecraft:bat]",
        "damage @a 2", "damage Steve 100", "clear Steve", "clear @a minecraft:dirt 4",
        "fill ~-10 ~-10 ~-10 ~10 ~10 ~10 minecraft:air", "fill 0 0 0 1 1 1 minecraft:stone",
        "fill ~ ~ ~ ~1 ~1 ~1 minecraft:lava", "fill ~ ~ ~ ~1 ~ ~ minecraft:stone destroy", "setblock 10 64 10 minecraft:stone",
        "summon minecraft:wither", "summon minecraft:lightning_bolt ~ ~ ~", "give Steve minecraft:command_block",
        "give Steve minecraft:cake 999", "effect give Steve minecraft:poison 10 200", "gamerule keepInventory false",
        "attribute Steve minecraft:max_health base set 1", "attribute Steve minecraft:scale base set 50",
        "tp Steve ~ ~-500 ~", "spreadplayers ~ ~ 1 100000 false Steve", "data merge entity Steve {Health:0}",
        "difficulty peaceful", "xp add Steve 1000 levels", "gamemode creative Steve",
    ],
)
def test_safe_blocks(cmd):
    assert safe_check(cmd, "safe") is not None


@pytest.mark.parametrize(
    "cmd",
    [
        "say бзз", "weather thunder", "give Steve minecraft:cake 3", "execute at Steve run kill @e[type=minecraft:item,distance=..24]",
        "kill @e[tag=flybody]", "damage Steve 3 minecraft:sting", "clear Steve minecraft:dirt 16",
        "execute at Steve run summon minecraft:lightning_bolt ~3 ~30 ~-2", "attribute Steve minecraft:scale base set 0.4",
        'tellraw @a [{"text":"[Муха] ","color":"gold"},{"text":"привет всем","color":"green"}]',
        'data merge entity @e[tag=flyeye,limit=1] {item:{id:"minecraft:spider_eye",count:1}}',
        "execute at Steve run tp @e[tag=flyeye,limit=1] ~3.1 ~6.0 ~-2.2", "data get entity Steve SelectedItem.id",
        "scoreboard players set Голод flybrain 40", "tp Steve Alex", "/weather clear",
    ],
)
def test_safe_allows(cmd):
    assert safe_check(cmd, "safe") is None, safe_check(cmd, "safe")


@pytest.mark.parametrize("power", ["safe", "chaos", "am"])
def test_whole_catalog_passes_filter(power):
    rng = random.Random(0)
    for mood, options in full_catalog().items():
        for _, build, _, min_power in options:
            if _RANK[power] < _RANK[min_power]:
                continue
            for intensity in (0.0, 0.5, 1.0):
                for player in ("Steve", None):
                    players = ["Steve", "Alex"] if player else []
                    action = build(Ctx(mood, intensity, player, players, rng, power))
                    for cmd in action.commands + [c for _, c in action.reverts]:
                        assert safe_check(cmd, power) is None, (power, mood, action.name, cmd, safe_check(cmd, power))


def test_no_players_only_world_actions():
    rng = random.Random(1)
    for power in ("safe", "am"):
        for mood in CATALOG:
            for _ in range(30):
                a = choose_action(mood, 0.9, [], rng, power)
                if a:
                    assert all("@r" not in c for c in a.commands), (mood, a)


def test_power_gates_actions():
    from flybrain.commands import available

    def names(power):
        return {e[1].__name__.lstrip("_") for e in available("aversion", 1.0, power, True)}

    safe, am = names("safe"), names("am")
    assert "hate" not in safe and "creepers" not in safe and "cage" not in safe
    assert {"hate", "creepers", "cage", "scenario:HATE в небе"} <= am
    assert len(am) > len(names("chaos")) > len(safe)


def test_arsenal_is_huge():
    from flybrain.arsenal import build_arsenal, stats

    st = stats(build_arsenal())
    assert st["total"] >= 500
    assert st["by_power"]["safe"] > 0 and st["by_power"]["chaos"] > 0 and st["by_power"]["am"] > 0
