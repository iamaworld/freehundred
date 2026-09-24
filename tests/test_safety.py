import random

import pytest

from flybrain.commands import CATALOG, Ctx, choose_action
from flybrain.safety import safe_check


@pytest.mark.parametrize(
    "cmd",
    [
        "stop", "/stop", "minecraft:stop", "op Steve", "deop Steve", "ban Steve", "ban-ip 1.2.3.4",
        "kick Steve", "whitelist off", "reload", "save-off", "gamemode creative Steve", "tick freeze",
        "worldborder set 1", "clone ~ ~ ~ ~1 ~1 ~1 ~5 ~5 ~5", "item replace entity Steve armor.head with air",
        "execute as @a run stop", "execute at Steve run execute as @a run op @s",
        "kill @a", "kill @e", "kill Steve", "kill @e[type=player]", "kill @e[type=minecraft:bat]", "execute as @a at @s run kill @s",
        "damage @a 2", "damage Steve 100",
        "clear Steve", "clear @a minecraft:dirt 4",
        "fill ~-10 ~-10 ~-10 ~10 ~10 ~10 minecraft:air", "fill 0 0 0 1 1 1 minecraft:stone",
        "fill ~ ~ ~ ~1 ~1 ~1 minecraft:lava", "fill ~ ~ ~ ~1 ~ ~ minecraft:stone destroy",
        "setblock ~ ~ ~ minecraft:tnt", "setblock 10 64 10 minecraft:stone",
        "summon minecraft:wither", "summon creeper ~ ~ ~", "summon tnt", "summon minecraft:lightning_bolt ~ ~ ~",
        "summon minecraft:lightning_bolt",
        "give Steve minecraft:command_block", "give Steve tnt 1", "give Steve minecraft:cake 999",
        "effect give Steve minecraft:instant_damage 1 10", "effect give Steve minecraft:poison 10 200",
        "gamerule doFireTick true", "gamerule keepInventory false", "gamerule mobGriefing true",
        "attribute Steve minecraft:max_health base set 1", "attribute Steve minecraft:scale base set 50",
        "tp Steve 0 -100 0", "tp Steve ~ ~-500 ~", "spreadplayers ~ ~ 1 100000 false Steve",
        "data merge entity Steve {Health:0}", "difficulty peaceful", "xp add Steve 1000 levels",
        "luckperms user Steve permission set *", "essentials:god Steve", "",
        "say hi\nstop",
    ],
)
def test_blocked(cmd):
    assert safe_check(cmd) is not None


@pytest.mark.parametrize(
    "cmd",
    [
        "say бзз", "weather thunder", "time set night", "give Steve minecraft:cake 3",
        "effect give Steve minecraft:speed 10 2", "execute at Steve run kill @e[type=minecraft:item,distance=..24]",
        "kill @e[type=minecraft:bat,tag=flyride]", "damage Steve 3 minecraft:sting",
        "clear Steve minecraft:dirt 16", "execute at Steve run fill ~-2 ~-1 ~-2 ~2 ~-1 ~2 minecraft:moss_block replace minecraft:grass_block",
        "execute at Steve run setblock ~ ~ ~ minecraft:cobweb keep", "execute at Steve run summon minecraft:lightning_bolt ~3 ~30 ~-2",
        'execute at Steve run summon minecraft:bat ~ ~1 ~ {Tags:["flybrain"]}', "attribute Steve minecraft:scale base set 0.4",
        "execute as Steve at @s run spreadplayers ~ ~ 1 50 false @s", "execute as Steve at @s run tp @s ~ ~20 ~",
        'tellraw @a [{"text":"[Муха] ","color":"gold"},{"text":"привет всем","color":"green"}]',
        "bossbar set flybrain:mood value 50", "gamerule doDaylightCycle false", "difficulty hard", "seed",
        "tp Steve Alex", "/weather clear",
    ],
)
def test_allowed(cmd):
    assert safe_check(cmd) is None, safe_check(cmd)


def test_whole_catalog_passes_filter():
    rng = random.Random(0)
    for mood, options in CATALOG.items():
        for _, build in options:
            for intensity in (0.0, 0.5, 1.0):
                for player in ("Steve", None):
                    action = build(Ctx(mood, intensity, player, [player] if player else [], rng))
                    for cmd in action.commands + [c for _, c in action.reverts]:
                        assert safe_check(cmd) is None, (mood, action.name, cmd, safe_check(cmd))


def test_no_players_only_world_actions():
    rng = random.Random(1)
    for mood in CATALOG:
        for _ in range(30):
            a = choose_action(mood, 0.7, [], rng)
            if a:
                assert all("@r" not in c for c in a.commands), (mood, a)
