"""Арсенал: сотни команд из полных ванильных реестров (Java 1.21.x).

Ручные сценарии из commands.py (клетка, яма, HATE...) — «характер» мухи.
Арсенал — её словарь: каждый эффект, моб, частица, звук, чары, атрибут,
структура, биом, геймрул, предмет и блок, привязанные к настроениям.

Минимальная сила (safe/chaos/am) для каждого действия вычисляется
автоматически: пробная команда прогоняется через safety — так каталог
никогда не разойдётся с фильтром.
"""

from __future__ import annotations

import random
import re
from collections import Counter
from typing import Callable

from .commands import Action, Ctx, tellraw, title
from .safety import safe_check

# ---------------- реестры ----------------
GOOD_EFFECTS = ["speed", "haste", "strength", "instant_health", "jump_boost", "regeneration", "resistance",
                "fire_resistance", "water_breathing", "invisibility", "night_vision", "health_boost", "absorption",
                "saturation", "luck", "slow_falling", "conduit_power", "dolphins_grace", "hero_of_the_village"]
BAD_EFFECTS = ["slowness", "mining_fatigue", "instant_damage", "nausea", "blindness", "hunger", "weakness", "poison",
               "wither", "unluck", "bad_omen", "darkness", "trial_omen", "raid_omen", "wind_charged", "weaving",
               "oozing", "infested"]
ODD_EFFECTS = ["glowing", "levitation"]

PASSIVE_MOBS = ["allay", "armadillo", "axolotl", "camel", "cat", "chicken", "cow", "donkey", "fox", "frog",
                "glow_squid", "horse", "mooshroom", "mule", "ocelot", "parrot", "pig", "rabbit", "sheep", "sniffer",
                "snow_golem", "strider", "turtle", "villager", "wandering_trader", "bee", "dolphin", "goat",
                "iron_golem", "llama", "panda", "polar_bear", "wolf", "tadpole", "cod", "salmon", "tropical_fish",
                "pufferfish", "squid", "skeleton_horse", "zombie_horse", "trader_llama"]
FLYING_MOBS = ["bat", "phantom", "vex", "allay", "bee", "parrot", "ghast", "blaze", "breeze"]
HOSTILE_MOBS = ["blaze", "bogged", "breeze", "cave_spider", "creeper", "drowned", "elder_guardian", "endermite",
                "enderman", "evoker", "ghast", "guardian", "hoglin", "husk", "magma_cube", "phantom", "piglin",
                "piglin_brute", "pillager", "ravager", "shulker", "silverfish", "skeleton", "slime", "spider",
                "stray", "vex", "vindicator", "witch", "wither_skeleton", "zoglin", "zombie", "zombie_villager",
                "zombified_piglin", "illusioner", "creaking"]
BOSSES = ["wither", "warden", "ender_dragon"]

PARTICLES = {
    "feeding": ["heart", "happy_villager", "note", "composter", "dripping_honey", "falling_honey", "totem_of_undying",
                "cherry_leaves", "egg_crack", "spore_blossom_air"],
    "escape": ["cloud", "poof", "smoke", "large_smoke", "explosion", "gust", "small_gust", "sweep_attack", "firework",
               "campfire_cosy_smoke"],
    "grooming": ["bubble", "bubble_pop", "splash", "falling_water", "dripping_water", "rain", "wax_off", "scrape",
                 "white_smoke", "snowflake", "item_snowball", "current_down", "underwater", "fishing"],
    "aversion": ["angry_villager", "witch", "damage_indicator", "flame", "soul_fire_flame", "lava", "dripping_lava",
                 "sculk_soul", "soul", "squid_ink", "crimson_spore", "dragon_breath", "infested", "item_slime", "spit",
                 "sneeze", "ominous_spawning", "raid_omen", "trial_omen"],
    "curious": ["end_rod", "enchant", "glow", "portal", "reverse_portal", "nautilus", "electric_spark",
                "trial_spawner_detection", "enchanted_hit", "glow_squid_ink", "dolphin", "mycelium", "warped_spore"],
    "alert": ["crit", "wax_on", "small_flame", "sculk_charge_pop", "firework", "flash"],
    "bored": ["ash", "white_ash", "mycelium", "falling_dust"],
}
SOUNDS = {
    "feeding": ["entity.cat.purr", "entity.player.levelup", "ui.toast.challenge_complete", "entity.villager.yes",
                "entity.allay.ambient_with_item", "entity.dolphin.play", "block.beacon.activate", "item.totem.use",
                "entity.axolotl.splash", "music_disc.cat", "block.note_block.chime", "block.note_block.harp",
                "block.note_block.flute", "block.note_block.xylophone", "block.note_block.pling"],
    "escape": ["entity.ghast.scream", "entity.enderman.scream", "entity.phantom.swoop", "entity.fox.scream",
               "entity.goat.screaming.ambient", "entity.firework_rocket.launch", "entity.warden.sonic_boom",
               "block.glass.break", "entity.generic.explode", "entity.creeper.primed"],
    "grooming": ["entity.axolotl.splash", "block.bubble_column.upwards_ambient", "entity.generic.splash",
                 "block.brush.generic", "item.bucket.empty", "block.note_block.bell"],
    "aversion": ["entity.warden.roar", "entity.warden.heartbeat", "entity.wither.spawn", "entity.ender_dragon.growl",
                 "entity.elder_guardian.curse", "block.sculk_shrieker.shriek", "entity.evoker.prepare_summon",
                 "event.raid.horn", "music_disc.11", "music_disc.13", "entity.bee.loop_aggressive",
                 "entity.zombie.ambient", "entity.witch.celebrate", "block.anvil.land", "block.respawn_anchor.deplete",
                 "entity.lightning_bolt.thunder", "entity.parrot.imitate.creeper", "block.note_block.didgeridoo",
                 "block.note_block.bass"],
    "curious": ["block.portal.trigger", "block.end_portal.spawn", "entity.ender_eye.death", "block.chest.open",
                "block.note_block.bit", "block.note_block.banjo", "block.note_block.cow_bell",
                "block.note_block.iron_xylophone", "music_disc.pigstep", "block.amethyst_block.chime"],
    "alert": ["block.bell.use", "block.note_block.snare", "block.note_block.hat", "block.note_block.basedrum",
              "entity.skeleton.ambient", "ambient.cave", "block.beacon.deactivate", "entity.item.pickup",
              "block.note_block.guitar", "block.trial_spawner.detect_player"],
    "bored": ["entity.bee.loop", "block.note_block.bass", "entity.bat.ambient"],
}
ENCHANTS = ["protection", "fire_protection", "feather_falling", "blast_protection", "projectile_protection",
            "respiration", "aqua_affinity", "thorns", "depth_strider", "frost_walker", "soul_speed", "swift_sneak",
            "sharpness", "smite", "bane_of_arthropods", "knockback", "fire_aspect", "looting", "sweeping_edge",
            "efficiency", "silk_touch", "unbreaking", "fortune", "power", "punch", "flame", "infinity",
            "luck_of_the_sea", "lure", "loyalty", "impaling", "riptide", "channeling", "multishot", "quick_charge",
            "piercing", "mending", "density", "breach", "wind_burst"]
CURSES = ["binding_curse", "vanishing_curse"]
# (атрибут, «весёлое» значение, «злое» значение)
ATTRIBUTES = [("scale", 2.5, 0.2), ("gravity", 0.02, 0.3), ("jump_strength", 1.5, 0.1), ("movement_speed", 0.25, 0.03),
              ("step_height", 3.0, 0.0), ("safe_fall_distance", 40.0, 0.0), ("max_health", 40.0, 4.0),
              ("attack_damage", 10.0, 0.1), ("attack_speed", 20.0, 0.5), ("armor", 20.0, 0.0),
              ("knockback_resistance", 1.0, 0.0), ("luck", 10.0, -10.0), ("block_interaction_range", 12.0, 1.0),
              ("entity_interaction_range", 8.0, 0.5), ("block_break_speed", 4.0, 0.1),
              ("fall_damage_multiplier", 0.0, 4.0), ("oxygen_bonus", 10.0, 0.0),
              ("water_movement_efficiency", 1.0, 0.0), ("burning_time", 0.0, 10.0), ("sneaking_speed", 1.0, 0.1),
              ("mining_efficiency", 50.0, 0.0), ("submerged_mining_speed", 1.0, 0.0),
              ("explosion_knockback_resistance", 1.0, 0.0), ("movement_efficiency", 1.0, 0.0)]
STRUCTURES = ["village_plains", "village_desert", "village_savanna", "village_snowy", "village_taiga",
              "pillager_outpost", "mansion", "jungle_pyramid", "desert_pyramid", "igloo", "shipwreck",
              "shipwreck_beached", "swamp_hut", "stronghold", "monument", "ocean_ruin_cold", "ocean_ruin_warm",
              "buried_treasure", "mineshaft", "mineshaft_mesa", "ruined_portal", "ancient_city", "trail_ruins",
              "trial_chambers"]
BIOMES = ["plains", "sunflower_plains", "snowy_plains", "ice_spikes", "desert", "swamp", "mangrove_swamp", "forest",
          "flower_forest", "birch_forest", "dark_forest", "pale_garden", "taiga", "snowy_taiga", "savanna", "jungle",
          "bamboo_jungle", "badlands", "eroded_badlands", "meadow", "cherry_grove", "grove", "snowy_slopes",
          "frozen_peaks", "jagged_peaks", "stony_peaks", "river", "frozen_river", "beach", "mushroom_fields",
          "ocean", "deep_dark", "dripstone_caves", "lush_caves", "nether_wastes", "warped_forest", "crimson_forest",
          "soul_sand_valley", "basalt_deltas", "the_end", "end_highlands", "the_void"]
GAMERULES = [("doMobSpawning", "false", "true"), ("doFireTick", "true", "false"), ("mobGriefing", "true", "true"),
             ("keepInventory", "false", "false"), ("naturalRegeneration", "false", "true"),
             ("fallDamage", "false", "true"), ("fireDamage", "false", "true"), ("drowningDamage", "false", "true"),
             ("freezeDamage", "false", "true"), ("doImmediateRespawn", "true", "false"),
             ("doDaylightCycle", "false", "true"), ("doWeatherCycle", "false", "true"),
             ("doInsomnia", "true", "true"), ("randomTickSpeed", "300", "3"), ("playersSleepingPercentage", "101", "100"),
             ("doPatrolSpawning", "true", "true"), ("doTraderSpawning", "true", "true")]
FOOD = ["cake", "honey_bottle", "cookie", "sweet_berries", "glow_berries", "melon_slice", "bread", "pumpkin_pie",
        "apple", "sugar", "golden_apple", "golden_carrot", "enchanted_golden_apple", "cooked_beef", "cooked_porkchop",
        "cooked_chicken", "cooked_mutton", "cooked_rabbit", "cooked_cod", "cooked_salmon", "baked_potato",
        "mushroom_stew", "rabbit_stew", "beetroot_soup", "carrot", "beetroot", "chorus_fruit", "dried_kelp",
        "honeycomb", "sugar_cane"]
TREASURE = ["diamond", "emerald", "gold_ingot", "iron_ingot", "netherite_ingot", "lapis_lazuli", "amethyst_shard",
            "totem_of_undying", "elytra", "trident", "mace", "heart_of_the_sea", "nether_star", "shulker_shell",
            "experience_bottle", "name_tag", "saddle", "diamond_sword", "diamond_pickaxe", "diamond_axe",
            "netherite_sword", "netherite_pickaxe", "bow", "crossbow", "shield", "diamond_helmet",
            "diamond_chestplate", "diamond_leggings", "diamond_boots", "turtle_helmet", "ender_pearl",
            "firework_rocket", "golden_horse_armor", "wolf_armor", "goat_horn", "music_disc_pigstep", "music_disc_cat",
            "recovery_compass", "echo_shard", "sniffer_egg"]
CURIOS = ["compass", "clock", "spyglass", "map", "brush", "bundle", "lead", "bell", "painting", "armor_stand",
          "flower_pot", "glow_ink_sac", "ink_sac", "feather", "string", "slime_ball", "egg", "snowball",
          "ender_eye", "writable_book", "candle", "lantern", "soul_lantern", "firework_star", "bone_meal",
          "armadillo_scute", "wind_charge", "fire_charge", "tnt", "lava_bucket", "water_bucket", "axolotl_bucket",
          "powder_snow_bucket", "spawner", "dragon_head", "creeper_head"]
JUNK = ["rotten_flesh", "poisonous_potato", "spider_eye", "fermented_spider_eye", "dead_bush", "pufferfish", "bone",
        "stick", "dirt", "gravel", "cobblestone", "netherrack", "wheat_seeds", "kelp", "clay_ball", "flint",
        "poppy", "pale_moss_carpet", "cobweb", "suspicious_stew"]
PRETTY_BLOCKS = ["poppy", "dandelion", "cornflower", "blue_orchid", "allium", "azure_bluet", "oxeye_daisy",
                 "lily_of_the_valley", "torchflower", "pink_petals", "sunflower", "rose_bush", "moss_carpet",
                 "flowering_azalea", "glowstone", "sea_lantern", "shroomlight", "amethyst_block", "honey_block",
                 "gold_block", "diamond_block", "emerald_block", "cherry_leaves", "hay_block", "cake"]
TRAP_BLOCKS = ["cobweb", "powder_snow", "soul_sand", "magma_block", "sweet_berry_bush", "pointed_dripstone", "cactus",
               "slime_block", "honey_block", "ice", "blue_ice", "scaffolding", "sculk_sensor", "sculk_shrieker",
               "fire", "soul_fire", "lava", "water", "tnt", "wither_rose"]
DOOM_BLOCKS = ["obsidian", "crying_obsidian", "bedrock", "barrier", "sculk", "netherrack", "end_stone", "soul_soil",
               "blackstone", "gilded_blackstone", "reinforced_deepslate", "tinted_glass", "red_stained_glass",
               "black_concrete", "bone_block", "respawn_anchor"]

_ORDER = ["safe", "chaos", "am"]

# ---------------- построители ----------------
Entry = tuple[float, Callable[[Ctx], Action], float, str]


def _act(name: str, fn, reverts=None):
    def build(c: Ctx) -> Action:
        cmds = fn(c)
        rv = [(d, cmd(c) if callable(cmd) else cmd) for d, cmd in (reverts(c) if callable(reverts) else reverts or [])]
        return Action(name, cmds, rv)

    build.__name__ = "arsenal:" + name
    return build


def _category(out: dict, category: str, moods, items, make, min_intensity: float = 0.0, weight: float = 4.0,
              floor: str = "safe"):
    """Раскладывает семейство действий по настроениям; вес на семейство, а не на штуку.
    floor — минимальная сила по смыслу (фильтр может потребовать и больше)."""
    moods = [moods] if isinstance(moods, str) else moods
    per = weight / max(1, len(items))
    for item in items:
        name, fn, *rv = make(item)
        builder = _act(name, fn, rv[0] if rv else None)
        builder.category = category
        builder.floor = floor
        for mood in moods:
            out.setdefault(mood, []).append((per, builder, min_intensity, None))


def _min_power(builder) -> str | None:
    rng = random.Random(0)
    for power in ("safe", "chaos", "am"):
        a = builder(Ctx("aversion", 1.0, "Steve", ["Steve", "Alex"], rng, power))
        cmds = a.commands + [c for _, c in a.reverts]
        if all(safe_check(c, power) is None for c in cmds):
            return power
    return None  # не пройдёт даже при am — выбрасываем


def build_arsenal() -> dict[str, list[Entry]]:
    A: dict[str, list] = {}
    near = lambda c, cmd: c.at(cmd)  # noqa: E731

    # эффекты
    _category(A, "эффекты", ["feeding", "grooming"], GOOD_EFFECTS,
              lambda e: (f"дарит {e}", lambda c: [f"effect give {c.p} minecraft:{e} {c.scale(10, 120)} {c.scale(0, 3)}"]))
    _category(A, "эффекты", ["feeding"], GOOD_EFFECTS,
              lambda e: (f"{e} всем", lambda c: [f"effect give @a minecraft:{e} {c.scale(10, 60)} {c.scale(0, 2)}"]), 0.6, 1.5)
    _category(A, "эффекты", "aversion", BAD_EFFECTS,
              lambda e: (f"насылает {e}", lambda c: [f"effect give {c.p} minecraft:{e} {c.scale(3, 30)} {c.scale(0, 3)}"]))
    _category(A, "эффекты", "aversion", BAD_EFFECTS,
              lambda e: (f"{e} на всех", lambda c: [f"effect give @a minecraft:{e} {c.scale(3, 20)} {c.scale(0, 2)}"]), 0.7, 1.5)
    _category(A, "эффекты", ["escape", "curious"], ODD_EFFECTS,
              lambda e: (f"{e}", lambda c: [f"effect give {c.p} minecraft:{e} {c.scale(2, 10)} {c.scale(0, 2)}"]), 0, 1)

    # мобы
    _category(A, "мобы", ["feeding", "curious"], PASSIVE_MOBS,
              lambda m: (f"дарит {m}", lambda c: [near(c, f'summon minecraft:{m} ~ ~1 ~ {{Tags:["flybrain"]}}')
                                                  for _ in range(c.scale(1, 3))]))
    _category(A, "мобы", "escape", FLYING_MOBS,
              lambda m: (f"стая: {m}", lambda c: [near(c, f"summon minecraft:{m} ~{c.rng.randint(-3, 3)} ~3 ~{c.rng.randint(-3, 3)}")
                                                  for _ in range(c.scale(2, 6))]), 0.3)
    _category(A, "мобы", "aversion", HOSTILE_MOBS,
              lambda m: (f"натравливает {m}", lambda c: [near(c, f"summon minecraft:{m} ~{c.rng.randint(-5, 5)} ~ ~{c.rng.randint(-5, 5)}")
                                                         for _ in range(c.scale(1, 5))]), 0.3, 4.0, "chaos")
    _category(A, "мобы", "aversion", BOSSES,
              lambda m: (f"призывает босса: {m}", lambda c: [tellraw(f"{m.upper()}. для тебя, {c.p}.", "dark_red"),
                                                             near(c, f"summon minecraft:{m} ~8 ~2 ~8")]), 0.95, 0.4)
    _category(A, "мобы", "curious", PASSIVE_MOBS + HOSTILE_MOBS,
              lambda m: (f"сажает верхом на {m}", lambda c: [near(c, f'summon minecraft:{m} ~ ~ ~ {{Tags:["flybrain","flyride"]}}'),
                                                             f"ride {c.p} mount @e[tag=flyride,limit=1,sort=nearest]"],
                         lambda c: [(25.0, f"ride {c.p} dismount")]), 0.4, 1.5)

    # частицы и звуки
    for mood, parts in PARTICLES.items():
        _category(A, "частицы", mood, parts,
                  lambda p: (f"частицы {p}", lambda c: [near(c, f"particle minecraft:{p} ~ ~1.5 ~ 1 1 1 0.05 {c.scale(20, 200)}")]), 0, 1.5)
    for mood, sounds in SOUNDS.items():
        _category(A, "звуки", mood, sounds,
                  lambda s: (f"звук {s}", lambda c: [f"playsound minecraft:{s} master @a ~ ~ ~ 1 {c.rng.choice(['0.5', '1', '1.5'])} 1"]), 0, 1.5)

    # чары
    _category(A, "чары", "feeding", ENCHANTS,
              lambda e: (f"зачаровывает: {e}", lambda c: [f"enchant {c.p} minecraft:{e}", tellraw(f"{c.p}, {e}. носи.", "light_purple")]), 0.3, 2)
    _category(A, "чары", "aversion", CURSES,
              lambda e: (f"проклинает: {e}", lambda c: [f"enchant {c.p} minecraft:{e}", tellraw(f"{c.p} проклят.", "dark_red")]), 0.5, 1)

    # атрибуты — с откатом
    _category(A, "атрибуты", ["curious", "feeding"], ATTRIBUTES,
              lambda a: (f"меняет {a[0]} ↑", lambda c: [f"attribute {c.p} minecraft:{a[0]} base set {a[1]}"],
                         lambda c: [(60.0, f"attribute {c.p} minecraft:{a[0]} base reset")]), 0.3, 3)
    _category(A, "атрибуты", ["aversion", "escape"], ATTRIBUTES,
              lambda a: (f"меняет {a[0]} ↓", lambda c: [f"attribute {c.p} minecraft:{a[0]} base set {a[2]}"],
                         lambda c: [(60.0, f"attribute {c.p} minecraft:{a[0]} base reset")]), 0.4, 3)

    # структуры и биомы
    _category(A, "структуры", "curious", STRUCTURES,
              lambda s: (f"ищет {s}", lambda c: [near(c, f"locate structure minecraft:{s}")]), 0, 2)
    _category(A, "структуры", ["curious", "escape"], STRUCTURES,
              lambda s: (f"телепортирует к {s}", lambda c: _tp_to_structure(c, s)), 0.6, 1.5, "am")
    _category(A, "биомы", ["curious", "aversion"], BIOMES,
              lambda b: (f"перекрашивает мир в {b}", lambda c: [near(c, f"fillbiome ~-12 ~-8 ~-12 ~12 ~16 ~12 minecraft:{b}")]), 0.5, 1.5)

    # геймрулы — с откатом
    _category(A, "геймрулы", ["aversion", "alert"], GAMERULES,
              lambda g: (f"правило {g[0]}={g[1]}", lambda c: [f"gamerule {g[0]} {g[1]}", tellraw(f"новое правило: {g[0]} = {g[1]}", "dark_red")],
                         [(180.0, f"gamerule {g[0]} {g[2]}")]), 0.6, 1.5)

    # время и погода
    times = ["day", "noon", "night", "midnight", "0", "6000", "13000", "18000", "23000"]
    _category(A, "время", ["alert", "bored", "curious"], times, lambda t: (f"время {t}", lambda c: [f"time set {t}"]), 0, 1)
    weathers = ["clear", "rain", "thunder"]
    _category(A, "погода", ["grooming", "aversion", "feeding"], weathers,
              lambda w: (f"погода {w}", lambda c: [f"weather {w} {c.scale(60, 900)}"]), 0, 1)

    # предметы
    _category(A, "еда", "feeding", FOOD, lambda i: (f"дарит {i}", lambda c: [f"give {c.p} minecraft:{i} {c.scale(1, 16)}"]))
    _category(A, "сокровища", "feeding", TREASURE,
              lambda i: (f"божий дар: {i}", lambda c: [f"give {c.p} minecraft:{i} {c.scale(1, 3)}"]), 0.7, 2)
    _category(A, "находки", "curious", CURIOS, lambda i: (f"находка: {i}", lambda c: [f"give {c.p} minecraft:{i} {c.scale(1, 4)}"]))
    _category(A, "мусор", "aversion", JUNK, lambda i: (f"швыряет {i}", lambda c: [f"give {c.p} minecraft:{i} {c.scale(8, 64)}"]), 0, 2)
    _category(A, "отбирает", "aversion", FOOD + TREASURE,
              lambda i: (f"отбирает {i}", lambda c: [f"clear {c.p} minecraft:{i} {c.scale(1, 64)}"]), 0.4, 2, "chaos")

    # блоки: узоры вокруг игрока
    patterns = {
        "клумбу": ("~-2 ~ ~-2 ~2 ~ ~2", "replace minecraft:air"),
        "пол": ("~-2 ~-1 ~-2 ~2 ~-1 ~2", ""),
        "кольцо": ("~-3 ~ ~-3 ~3 ~1 ~3", "outline"),
        "башню": ("~ ~-1 ~ ~ ~-1 ~", ""),
    }
    for pname, (box, mode) in patterns.items():
        _category(A, "постройки", ["feeding", "grooming"], PRETTY_BLOCKS,
                  lambda b, box=box, mode=mode, pname=pname: (f"строит {pname} из {b}", lambda c: [near(c, f"fill {box} minecraft:{b} {mode}".rstrip())]), 0, 1.2)
        _category(A, "ловушки", "aversion", TRAP_BLOCKS,
                  lambda b, box=box, mode=mode, pname=pname: (f"ловушка: {pname} из {b}", lambda c: [near(c, f"fill {box} minecraft:{b} {mode}".rstrip())]), 0.3, 1.2, "chaos")
    _category(A, "гробницы", "aversion", DOOM_BLOCKS,
              lambda b: (f"замуровывает в {b}", lambda c: [near(c, f"fill ~-2 ~-1 ~-2 ~2 ~3 ~2 minecraft:{b} outline"),
                                                             title(c.p, "title", "ТЫ ЗДЕСЬ НАВСЕГДА", "dark_red")],
                         lambda c: [(45.0, near(c, f"fill ~-2 ~-1 ~-2 ~2 ~3 ~2 minecraft:air replace minecraft:{b}"))]), 0.6, 2)
    _category(A, "гробницы", "aversion", DOOM_BLOCKS,
              lambda b: (f"пожирает землю: {b}", lambda c: [near(c, f"fill ~-6 ~-3 ~-6 ~6 ~-1 ~6 minecraft:{b}")]), 0.7, 1)

    # проставляем силу по фильтру, выкидываем то, что не пройдёт никогда
    result: dict[str, list[Entry]] = {}
    for mood, entries in A.items():
        for w, b, mi, _ in entries:
            if (power := _min_power(b)) is not None:
                power = max(power, b.floor, key=_ORDER.index)
                result.setdefault(mood, []).append((w, b, mi, power))
    return result


_LOCATED = re.compile(r"at \[(-?\d+), (~|-?\d+), (-?\d+)\]")


def _tp_to_structure(c: Ctx, s: str) -> list[str]:
    m = _LOCATED.search(c.ask(c.at(f"locate structure minecraft:{s}")))
    if not m:
        return [tellraw(f"{s} не нашла. повезло тебе.", "light_purple")]
    x, _, z = m.groups()
    return [f"effect give {c.p} minecraft:slow_falling 40 0", f"tp {c.p} {x} 200 {z}",
            tellraw(f"{c.p} отправлен к {s}", "light_purple")]


def stats(arsenal: dict[str, list[Entry]]) -> dict:
    """Сколько уникальных действий: всего, по силе, по категориям."""
    uniq = {}
    for entries in arsenal.values():
        for _, b, _, power in entries:
            uniq[b.__name__] = (power, getattr(b, "category", "?"))
    return {
        "total": len(uniq),
        "by_power": Counter(p for p, _ in uniq.values()),
        "by_category": Counter(cat for _, cat in uniq.values()),
    }
