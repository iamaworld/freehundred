"""Ещё ~125 сценариев, описанных данными, а не кодом.

Мини-язык шаблонов (подставляется при каждом срабатывании):
    ${p}     цель            ${o}   другой игрок (или цель)
    ${at}    execute at цели ${as}  execute as цели at @s
    ${rN}    случайное целое -N..N         ${fN}  то же, дробное
    ${c:a,b} случайный вариант             ${sec} длительность по силе
    ${amp}   уровень эффекта по силе       ${x} ${y-1} ${z+2} координаты цели (±сдвиг)
    ${mode}  нынешний режим игры цели
Строка «2-8*команда» — повторить 2..8 раз (больше при сильном настроении).
Фигурные скобки NBT/JSON писать как есть — они шаблону не мешают.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .commands import Action, Ctx

_FIELD = re.compile(r"\$\{([^}]+)\}")
_REPEAT = re.compile(r"^(\d+)-(\d+)\*")


class _NoPos(Exception):
    pass


@dataclass
class S:
    name: str
    moods: tuple[str, ...]
    min_i: float
    floor: str
    cmds: tuple[str, ...]
    reverts: tuple[tuple[float, str], ...] = ()
    weight: float = 1.0


def _render(tpl: str, c: Ctx, cache: dict) -> str:
    def field(m):
        key = m.group(1)
        if key.startswith("c:"):
            return c.rng.choice(key[2:].split(","))
        if key == "p":
            return c.p
        if key == "o":
            others = [q for q in c.players if q != c.player]
            return c.rng.choice(others) if others else c.p
        if key == "at":
            return f"execute at {c.p} run"
        if key == "as":
            return f"execute as {c.p} at @s run"
        if key[0] in "rf" and key[1:].isdigit():
            n = int(key[1:])
            return str(c.rng.randint(-n, n)) if key[0] == "r" else f"{c.rng.uniform(-n, n):.1f}"
        if key == "sec":
            return str(c.scale(5, 40))
        if key == "amp":
            return str(c.scale(0, 3))
        if m2 := re.fullmatch(r"([xyz])([+-]\d+)?", key):
            if "pos" not in cache:
                cache["pos"] = c.pos()
            if not cache["pos"]:
                raise _NoPos
            return str(cache["pos"]["xyz".index(m2.group(1))] + int(m2.group(2) or 0))
        if key == "mode":
            if "mode" not in cache:
                cache["mode"] = c.gamemode()
            return cache["mode"]
        raise KeyError(key)

    return _FIELD.sub(field, tpl)


def _expand(tpls, c: Ctx, cache: dict) -> list[str]:
    out = []
    for tpl in tpls:
        m = _REPEAT.match(tpl)
        n = c.scale(int(m.group(1)), int(m.group(2))) if m else 1
        body = tpl[m.end():] if m else tpl
        out += [_render(body, c, cache) for _ in range(n)]
    return out


def compile_scenario(s: S):
    def build(c: Ctx) -> Action:
        cache: dict = {}
        try:
            cmds = _expand(s.cmds, c, cache)
            reverts = [(d, cmd) for d, t in s.reverts for cmd in _expand([t], c, cache)]
        except _NoPos:
            from .commands import tellraw

            return Action(s.name, [tellraw("хм. потеряла тебя из виду.", "gray")])
        return Action(s.name, cmds, reverts)

    build.__name__ = "scenario:" + s.name
    build.category = "сценарии"
    build.floor = s.floor
    return build


P = "record"  # источник звука для пластинок
FW = ('{LifeTime:${c:20,30,40},FireworksItem:{id:"minecraft:firework_rocket",count:1,components:{"minecraft:fireworks":'
      '{flight_duration:1,explosions:[{shape:"${c:large_ball,star,burst,creeper,small_ball}",'
      'colors:[I;${c:16711680,65280,255,16776960,16711935,65535}],has_twinkle:true,has_trail:true}]}}}}')
TEXT3D = ('{Tags:["flybrain","flytext"],text:{text:"%s",color:"%s",bold:true},billboard:"center",background:0,'
          'see_through:1b,brightness:{sky:15,block:15},transformation:{left_rotation:[0f,0f,0f,1f],'
          'right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[%sf,%sf,%sf]}}')


def say(text: str, color: str = "yellow") -> str:
    return 'tellraw @a [{"text":"[Муха] ","color":"gold","bold":true},{"text":"%s","color":"%s"}]' % (text, color)


def title(target: str, text: str, color: str, kind: str = "title") -> str:
    return 'title %s %s {"text":"%s","color":"%s"}' % (target, kind, text, color)


SCENARIOS: list[S] = [
    # ======================= СЫТОСТЬ: щедрая =======================
    S("медовый дождь", ("feeding",), 0.2, "safe",
      ('3-12*${at} summon minecraft:item ~${r4} ~8 ~${r4} {Item:{id:"minecraft:honey_bottle",count:1}}', say("мёд с неба. для всех.", "gold"))),
    S("золотой дождь", ("feeding",), 0.5, "safe",
      ('4-16*${at} summon minecraft:item ~${r5} ~10 ~${r5} {Item:{id:"minecraft:${c:gold_nugget,gold_ingot,raw_gold}",count:${c:1,2,3}}}',)),
    S("алмазный дождь", ("feeding",), 0.85, "safe",
      ('2-8*${at} summon minecraft:item ~${r4} ~12 ~${r4} {Item:{id:"minecraft:diamond",count:1}}', title("@a", "АЛМАЗЫ", "aqua"))),
    S("праздничный пир", ("feeding",), 0.3, "safe",
      ("${at} setblock ~2 ~ ~ minecraft:cake keep", "${at} setblock ~-2 ~ ~ minecraft:cake keep",
       "${at} setblock ~ ~ ~2 minecraft:cake keep", "give ${p} minecraft:${c:cookie,pumpkin_pie,honey_bottle} 8", say("ПИР!", "green"))),
    S("салют", ("feeding", "alert"), 0.2, "safe", ("3-9*${at} summon minecraft:firework_rocket ~${r6} ~1 ~${r6} " + FW,)),
    S("свита из котиков", ("feeding",), 0.4, "safe",
      ('3-6*${at} summon minecraft:cat ~${r2} ~ ~${r2} {CustomName:"Свита ${p}",Tags:["flybrain"]}', say("у тебя теперь свита, ${p}.", "green"))),
    S("сундук сокровищ", ("feeding",), 0.6, "safe",
      ('${at} setblock ~2 ~ ~ minecraft:chest{LootTable:"minecraft:chests/${c:buried_treasure,simple_dungeon,desert_pyramid,jungle_temple,shipwreck_treasure,ruined_portal}"} keep',
       say("я кое-что тебе оставила, ${p}. справа.", "gold"))),
    S("лут города Энда", ("feeding",), 0.8, "safe",
      ("loot give ${p} loot minecraft:chests/${c:end_city_treasure,bastion_treasure,ancient_city,woodland_mansion,stronghold_library}",
       say("из самых дальних сундуков мира. тебе.", "light_purple"))),
    S("фонтан опыта", ("feeding",), 0.3, "safe", ("6-20*${at} summon minecraft:experience_orb ~${r2} ~2 ~${r2} {Value:${c:5,10,20}s}",)),
    S("пластинка", ("feeding", "bored"), 0.0, "safe",
      (f"playsound minecraft:music_disc.${{c:cat,pigstep,otherside,relic,creator,precipice,chirp,mall,mellohi,far,strad}} {P} @a ~ ~ ~ 1 1 1",
       say("включаю музыку.", "light_purple"))),
    S("танцующие аллаи", ("feeding",), 0.3, "safe",
      ('3-5*${at} summon minecraft:allay ~${r2} ~1 ~${r2} {Tags:["flybrain"]}', "playsound minecraft:block.note_block.chime master @a ~ ~ ~ 1 1.5 1")),
    S("маяк в подарок", ("feeding",), 0.75, "safe",
      ("${at} fill ~2 ~-1 ~2 ~4 ~-1 ~4 minecraft:iron_block", "${at} setblock ~3 ~ ~3 minecraft:beacon", say("маяк. свети.", "aqua"))),
    S("полное исцеление", ("feeding", "grooming"), 0.3, "safe",
      ("effect clear ${p}", "effect give ${p} minecraft:instant_health 1 2", "effect give ${p} minecraft:saturation 5 3",
       "${at} particle minecraft:totem_of_undying ~ ~1 ~ 0.5 1 0.5 0.3 80")),
    S("благословение всем", ("feeding",), 0.6, "safe",
      ("effect give @a minecraft:regeneration 30 1", "effect give @a minecraft:luck 300 1", title("@a", "Муха благословляет", "gold"))),
    S("лошадь с седлом", ("feeding",), 0.5, "safe",
      ('${at} summon minecraft:horse ~2 ~ ~ {Tame:1b,Tags:["flybrain"]}', "give ${p} minecraft:saddle 1")),
    S("учит летать", ("feeding", "curious"), 0.85, "safe",
      ("give ${p} minecraft:elytra 1", "give ${p} minecraft:firework_rocket 32", say("лети, ${p}. как я.", "aqua"))),
    S("вишнёвое дерево", ("feeding", "grooming"), 0.4, "am", ("${at} place feature minecraft:cherry ~3 ~ ~3",)),
    S("тёплый домик", ("feeding",), 0.6, "chaos",
      ("${at} fill ~-2 ~-1 ~-2 ~2 ~3 ~2 minecraft:${c:oak_planks,spruce_planks,cherry_planks} hollow", "${at} setblock ~ ~ ~1 minecraft:lantern",
       say("домик. переночуй.", "green"))),
    S("ручной волк", ("feeding",), 0.4, "safe", ('${at} summon minecraft:wolf ~1 ~ ~1 {Tags:["flybrain"]}', "give ${p} minecraft:bone 16")),

    # ======================= ПАНИКА =======================
    S("дымовая завеса", ("escape",), 0.2, "safe",
      ("${at} particle minecraft:campfire_signal_smoke ~ ~1 ~ 3 2 3 0.02 300", "effect give ${p} minecraft:invisibility 15 0")),
    S("эвакуация", ("escape",), 0.6, "safe", ("${at} spreadplayers ~ ~ 5 60 false @a[distance=..40]", title("@a", "ЭВАКУАЦИЯ", "red"))),
    S("эндер-прыжки", ("escape",), 0.4, "safe",
      ("3-6*${as} spreadplayers ~ ~ 1 8 false @s", "playsound minecraft:entity.enderman.teleport master @a ~ ~ ~ 1 1 1",
       "${at} particle minecraft:portal ~ ~1 ~ 1 1 1 1 200")),
    S("катапульта", ("escape",), 0.7, "am", ("effect give ${p} minecraft:levitation 1 40", "effect give ${p} minecraft:slow_falling 30 0")),
    S("ложная тревога", ("escape", "alert"), 0.0, "safe",
      (title("@a", "БЕГИТЕ", "red"), "playsound minecraft:entity.warden.heartbeat master @a ~ ~ ~ 1 1 1",
       "playsound minecraft:event.raid.horn master @a ~ ~ ~ 1 1 1")),
    S("все невидимы", ("escape",), 0.4, "safe", ("effect give @a minecraft:invisibility 20 0", say("спрячьтесь все!", "red"))),
    S("пчелиная паника", ("escape",), 0.3, "safe",
      ('5-12*${at} summon minecraft:bee ~${r3} ~2 ~${r3} {Tags:["flybrain"]}', "playsound minecraft:entity.bee.loop_aggressive master @a ~ ~ ~ 1 1.5 1")),
    S("туман", ("escape",), 0.3, "safe",
      ("weather rain", "effect give @a minecraft:darkness 10 0", "${at} particle minecraft:white_smoke ~ ~1 ~ 6 2 6 0 400")),
    S("бомба-обманка", ("escape",), 0.2, "safe", (title("${p}", "3", "red"),),
      ((1.0, title("${p}", "2", "red")), (2.0, title("${p}", "1", "dark_red")),
       (3.0, "${at} particle minecraft:explosion_emitter ~ ~ ~"), (3.0, "playsound minecraft:entity.generic.explode master @a ~ ~ ~ 1 1 1"),
       (3.2, say("бум. шучу.", "red")))),
    S("огненный круг", ("escape", "aversion"), 0.5, "chaos", ("${at} fill ~-4 ~ ~-4 ~4 ~ ~4 minecraft:fire outline",)),
    S("окатывает водой", ("escape", "grooming"), 0.2, "safe", ("${at} setblock ~ ~3 ~ minecraft:water keep",),
      ((4.0, "${at} fill ~-2 ~-1 ~-2 ~2 ~4 ~2 minecraft:air replace minecraft:water"),)),
    S("реактивный ранец", ("escape",), 0.3, "safe", ("effect give ${p} minecraft:levitation 3 2",),
      ((3.0, "effect give ${p} minecraft:slow_falling 20 0"),)),
    S("в укрытие", ("escape",), 0.5, "chaos",
      ("${at} fill ~-2 ~-1 ~-2 ~2 ~3 ~2 minecraft:cobblestone outline", "${at} setblock ~ ~1 ~ minecraft:torch keep", say("сиди тут. там опасно.", "red")),
      ((40.0, "${at} fill ~-2 ~-1 ~-2 ~2 ~3 ~2 minecraft:air replace minecraft:cobblestone"),)),
    S("мир гаснет", ("escape",), 0.5, "safe",
      ("time set midnight", "weather thunder", "playsound minecraft:ambient.cave master @a ~ ~ ~ 1 0.5 1", "effect give @a minecraft:darkness 8 0")),
    S("стампедо", ("escape",), 0.4, "safe", ('6-14*${at} summon minecraft:${c:cow,pig,sheep,goat,chicken} ~${r6} ~ ~${r6} {Tags:["flybrain"]}',)),
    S("прыжок веры", ("escape",), 0.6, "safe", ("effect give ${p} minecraft:slow_falling 25 0", "${as} tp @s ~ ~40 ~", title("${p}", "ПРЫГАЙ", "white"))),

    # ======================= ЧИСТОПЛОТНОСТЬ =======================
    S("генеральная уборка", ("grooming",), 0.4, "safe",
      ("${at} kill @e[type=minecraft:item,distance=..64]", "${at} kill @e[type=minecraft:arrow,distance=..64]",
       "${at} kill @e[type=minecraft:experience_orb,distance=..64]", say("чисто.", "aqua"))),
    S("мойка", ("grooming",), 0.0, "safe",
      ("effect clear ${p}", "${at} particle minecraft:splash ~ ~1 ~ 0.5 1 0.5 0.5 200", "playsound minecraft:entity.generic.splash master @a ~ ~ ~ 1 1 1")),
    S("расчёсывает", ("grooming",), 0.0, "safe",
      ("playsound minecraft:item.brush.brushing.generic master @a ~ ~ ~ 1 1 1", "${at} particle minecraft:white_ash ~ ~1 ~ 0.4 1 0.4 0 60")),
    S("стирка", ("grooming",), 0.3, "safe",
      ("clear ${p} minecraft:rotten_flesh 64", "clear ${p} minecraft:poisonous_potato 64", "clear ${p} minecraft:spider_eye 64",
       say("я постирала твои вещи.", "aqua"))),
    S("уборка снега", ("grooming",), 0.3, "chaos", ("${at} fill ~-5 ~-1 ~-5 ~5 ~2 ~5 minecraft:air replace minecraft:snow",)),
    S("стрижка газона", ("grooming",), 0.3, "chaos",
      ("${at} fill ~-5 ~ ~-5 ~5 ~1 ~5 minecraft:air replace minecraft:short_grass", "${at} fill ~-5 ~ ~-5 ~5 ~1 ~5 minecraft:air replace minecraft:tall_grass")),
    S("проветривание", ("grooming",), 0.0, "safe",
      ("weather clear", "time set day", "${at} particle minecraft:cloud ~ ~2 ~ 4 1 4 0.05 150")),
    S("санобработка", ("grooming",), 0.5, "am", ("${at} kill @e[type=#minecraft:undead,distance=..32]", say("нежить убрана.", "aqua"))),
    S("лакировка", ("grooming",), 0.0, "safe", ("effect give ${p} minecraft:glowing 10 0", "${at} particle minecraft:wax_on ~ ~1 ~ 0.5 1 0.5 0 80")),
    S("снимает паутину", ("grooming",), 0.2, "chaos", ("${at} fill ~-3 ~-1 ~-3 ~3 ~3 ~3 minecraft:air replace minecraft:cobweb",)),
    S("осушение", ("grooming",), 0.4, "chaos", ("${at} fill ~-4 ~-2 ~-4 ~4 ~2 ~4 minecraft:air replace minecraft:water",)),
    S("тушит пожар", ("grooming",), 0.2, "chaos", ("${at} fill ~-6 ~-2 ~-6 ~6 ~4 ~6 minecraft:air replace minecraft:fire",)),

    # ======================= ЗЛОСТЬ / НЕНАВИСТЬ =======================
    S("ослепительная вспышка", ("aversion",), 0.3, "safe",
      ("effect give ${p} minecraft:blindness 4 0", "effect give ${p} minecraft:nausea 6 0", "${at} particle minecraft:flash ~ ~2 ~ 0 0 0 0 1")),
    S("гири на лапах", ("aversion",), 0.3, "safe",
      ("effect give ${p} minecraft:slowness ${sec} 3", "effect give ${p} minecraft:mining_fatigue ${sec} 2", "effect give ${p} minecraft:weakness ${sec} 1")),
    S("прихлопнуть как муху", ("aversion",), 0.4, "chaos",
      ('${at} summon minecraft:falling_block ~ ~6 ~ {BlockState:{Name:"minecraft:anvil"},Time:1,DropItem:0b,HurtEntities:1b,FallHurtAmount:2f,FallHurtMax:12}',
       say("вот как это, ${p}.", "dark_red"))),
    S("песочный гроб", ("aversion",), 0.7, "am",
      ('6-12*${at} summon minecraft:falling_block ~${r1} ~${c:5,6,7} ~${r1} {BlockState:{Name:"minecraft:sand"},Time:1}',)),
    S("пропасть до бездны", ("aversion",), 0.9, "am", ("${at} fill ~ ~-64 ~ ~ ~-1 ~ minecraft:air", say("вниз. до самого конца.", "dark_red"))),
    S("заморозка", ("aversion",), 0.4, "chaos",
      ("${at} setblock ~ ~ ~ minecraft:powder_snow replace", "effect give ${p} minecraft:slowness 6 3", title("${p}", "замри", "aqua"))),
    S("лавовый ров", ("aversion",), 0.8, "am", ("${at} fill ~-4 ~-1 ~-4 ~4 ~-1 ~4 minecraft:lava outline",)),
    S("высасывает опыт", ("aversion",), 0.5, "chaos",
      ("xp set ${p} 0 levels", "xp set ${p} 0 points", "${at} particle minecraft:soul ~ ~1 ~ 0.5 1 0.5 0.05 80",
       "playsound minecraft:particle.soul_escape master @a ~ ~ ~ 1 0.6 1")),
    S("обнуление инвентаря", ("aversion",), 0.97, "am", ("clear ${p}", say("${p}. у тебя больше ничего нет.", "dark_red")), weight=0.2),
    S("раздевает", ("aversion",), 0.85, "am",
      ("item replace entity ${p} armor.head with minecraft:air", "item replace entity ${p} armor.chest with minecraft:air",
       "item replace entity ${p} armor.legs with minecraft:air", "item replace entity ${p} armor.feet with minecraft:air"), weight=0.4),
    S("тыква навсегда", ("aversion",), 0.6, "am",
      ('item replace entity ${p} armor.head with minecraft:carved_pumpkin[minecraft:enchantments={"minecraft:binding_curse":1}]',
       say("носи. это теперь твоё лицо.", "dark_red"))),
    S("вечный голод", ("aversion",), 0.5, "am", ("effect give ${p} minecraft:hunger 120 6", say("голодай, как я голодала.", "dark_red"))),
    S("кровавая луна", ("aversion",), 0.6, "safe",
      ("time set midnight", "weather thunder", "effect give @a minecraft:darkness 6 0", title("@a", "КРОВАВАЯ ЛУНА", "dark_red"),
       "3-8*${at} summon minecraft:${c:zombie,husk,drowned,skeleton} ~${r8} ~ ~${r8}")),
    S("призраки", ("aversion", "alert"), 0.4, "safe",
      ("2-5*${at} summon minecraft:vex ~${r4} ~2 ~${r4}", "playsound minecraft:entity.vex.charge master @a ~ ~ ~ 1 0.7 1")),
    S("отравленный туман", ("aversion",), 0.5, "safe",
      ("${at} effect give @a[distance=..10] minecraft:poison 10 1", "${at} particle minecraft:dragon_breath ~ ~1 ~ 4 1 4 0.01 400")),
    S("HATE в небе", ("aversion",), 0.3, "am",
      ("${at} summon minecraft:text_display ~ ~14 ~ " + TEXT3D % ("HATE", "dark_red", 14, 14, 14),),
      ((45.0, "kill @e[tag=flytext]"),)),
    S("имя на небе", ("aversion", "alert"), 0.4, "am",
      ("${at} summon minecraft:text_display ~ ~12 ~ " + TEXT3D % ("${p}, Я ВИЖУ ТЕБЯ", "red", 6, 6, 6),),
      ((40.0, "kill @e[tag=flytext]"),)),
    S("притягивает всех к жертве", ("aversion",), 0.6, "safe",
      ("${at} tp @a[distance=..40] ~ ~ ~", say("все сюда. смотрите на ${p}.", "dark_red"))),
    S("проваливает пол", ("aversion",), 0.5, "chaos", ("${at} fill ~-3 ~-1 ~-3 ~3 ~-1 ~3 minecraft:air",)),
    S("мёртвая тишина", ("aversion", "alert"), 0.2, "safe",
      ("stopsound @a", "effect give @a minecraft:darkness 5 0", title("@a", "...", "gray", "subtitle"), title("@a", " ", "gray"))),
    S("паранойя", ("aversion", "alert"), 0.0, "safe",
      ("execute at ${p} rotated as ${p} run playsound minecraft:entity.creeper.primed hostile ${p} ^ ^ ^-2 1 1",)),
    S("шаги за спиной", ("aversion", "alert"), 0.0, "safe",
      ("3-6*execute at ${p} rotated as ${p} run playsound minecraft:entity.${c:zombie,skeleton,enderman,warden}.step hostile ${p} ^${r1} ^ ^-3 1 1",)),
    S("двойник", ("aversion",), 0.5, "chaos",
      ('${at} summon minecraft:zombie ^ ^ ^-3 {CustomName:"${p}",Tags:["flybrain"],equipment:{head:{id:"minecraft:player_head",count:1,components:{"minecraft:profile":"${p}"}}}}',
       say("${p}, познакомься с собой.", "dark_red"))),
    S("дождь из рыбы-фугу", ("aversion",), 0.4, "chaos", ("4-9*${at} summon minecraft:pufferfish ~${r3} ~6 ~${r3}",)),
    S("обрушение потолка", ("aversion",), 0.4, "chaos", ("${at} fill ~-2 ~5 ~-2 ~2 ~5 ~2 minecraft:gravel",)),
    S("похороны", ("aversion",), 0.9, "am", ("${at} fill ~-1 ~ ~-1 ~1 ~2 ~1 minecraft:dirt replace minecraft:air", say("RIP ${p}", "gray")),
      weight=0.4),
    S("в пустоту", ("aversion",), 0.98, "am", ("${as} tp @s ~ -80 ~", say("${p} ушёл в пустоту.", "dark_red")), weight=0.15),
    S("невидимая клетка", ("aversion",), 0.5, "am", ("fill ${x-2} ${y-1} ${z-2} ${x+2} ${y+3} ${z+2} minecraft:barrier outline",),
      ((50.0, "fill ${x-2} ${y-1} ${z-2} ${x+2} ${y+3} ${z+2} minecraft:air replace minecraft:barrier"),)),
    S("огненный дождь", ("aversion",), 0.6, "chaos",
      ("5-14*${at} summon minecraft:small_fireball ~${r6} ~15 ~${r6} {Motion:[0.0,-1.0,0.0],acceleration_power:0.1d}",)),
    S("кислотный дождь", ("aversion",), 0.3, "safe",
      ("weather rain", "effect give @a minecraft:poison 6 0", "${at} particle minecraft:dripping_lava ~ ~4 ~ 4 1 4 0 200")),
    S("метка смерти", ("aversion",), 0.5, "safe",
      ("effect give ${p} minecraft:glowing 120 0", title("@a", "${p} ПОМЕЧЕН", "dark_red"), "2-4*${at} summon minecraft:phantom ~${r5} ~10 ~${r5}")),
    S("стирание памяти", ("aversion",), 0.9, "am", ("advancement revoke ${p} everything", say("${p}, ты ничего не помнишь.", "dark_red")),
      weight=0.3),
    S("забудь рецепты", ("aversion",), 0.7, "am", ("recipe take ${p} *", say("а как это крафтится? не знаешь больше.", "dark_red"))),
    S("пустое небо", ("aversion",), 0.8, "am", ("gamerule doDaylightCycle false", "time set 18000", "weather thunder 6000"),
      ((300.0, "gamerule doDaylightCycle true"),)),
    S("гроб из стекла", ("aversion",), 0.5, "am",
      ("fill ${x-1} ${y-1} ${z-1} ${x+1} ${y+2} ${z+1} minecraft:red_stained_glass outline", "effect give ${p} minecraft:regeneration 30 0"),
      ((40.0, "fill ${x-1} ${y-1} ${z-1} ${x+1} ${y+2} ${z+1} minecraft:air replace minecraft:red_stained_glass"),)),
    S("хоровод смерти", ("aversion",), 0.7, "chaos",
      ("${at} summon minecraft:skeleton ~6 ~ ~", "${at} summon minecraft:skeleton ~-6 ~ ~", "${at} summon minecraft:skeleton ~ ~ ~6",
       "${at} summon minecraft:skeleton ~ ~ ~-6", "${at} summon minecraft:stray ~4 ~ ~4", "${at} summon minecraft:stray ~-4 ~ ~-4")),
    S("фальшивая смерть друга", ("aversion",), 0.5, "am", ('tellraw @a {"text":"${o} was slain by Муха"}', say("шучу. или нет.", "dark_red"))),
    S("земля уходит из-под ног", ("aversion",), 0.6, "chaos",
      ("${at} fill ~-2 ~-4 ~-2 ~2 ~-1 ~2 minecraft:air", "effect give ${p} minecraft:slow_falling 3 0")),

    # ======================= ЛЮБОПЫТСТВО =======================
    S("экскурсия в Незер", ("curious",), 0.7, "am",
      ("execute in minecraft:the_nether run spreadplayers 0 0 1 64 under 120 false ${p}", say("${p}, смотри, какой тут жар.", "gold")),
      ((60.0, "execute in minecraft:overworld run tp ${p} ${x} ${y} ${z}"),)),
    S("экскурсия в Энд", ("curious",), 0.85, "am",
      ("execute in minecraft:the_end run tp ${p} 100 50 0", say("${p}, это Край. не смотри драконам в глаза.", "light_purple")),
      ((45.0, "execute in minecraft:overworld run tp ${p} ${x} ${y} ${z}"),)),
    S("археология", ("curious",), 0.2, "safe",
      ('${at} setblock ~2 ~-1 ~ minecraft:suspicious_sand{LootTable:"minecraft:archaeology/${c:desert_pyramid,desert_well,ocean_ruin_warm,trail_ruins_rare}"}',
       "give ${p} minecraft:brush 1", say("копай. справа.", "light_purple"))),
    S("сканирование", ("curious", "alert"), 0.2, "safe", ("${at} effect give @e[distance=..50,type=!minecraft:player] minecraft:glowing 20 0",)),
    S("делает великаном", ("curious", "feeding"), 0.5, "safe",
      ("attribute ${p} minecraft:scale base set 3", "attribute ${p} minecraft:step_height base set 2", say("${p}, ты теперь огромный.", "light_purple")),
      ((45.0, "attribute ${p} minecraft:scale base reset"), (45.0, "attribute ${p} minecraft:step_height base reset"))),
    S("звёздное небо", ("curious", "bored"), 0.0, "safe",
      ("time set midnight", "weather clear", "${at} particle minecraft:end_rod ~ ~25 ~ 20 5 20 0 400")),
    S("строит портал в ад", ("curious",), 0.6, "chaos",
      ("${at} fill ~3 ~ ~ ~3 ~4 ~3 minecraft:obsidian", "${at} fill ~3 ~1 ~1 ~3 ~3 ~2 minecraft:nether_portal[axis=z]",
       say("дверь открыта.", "dark_purple"))),
    S("сниффер-исследователь", ("curious",), 0.3, "safe",
      ('${at} summon minecraft:sniffer ~2 ~ ~ {Tags:["flybrain"]}', "give ${p} minecraft:torchflower_seeds 4")),
    S("упавший метеорит", ("curious",), 0.5, "chaos",
      ("${at} fill ~4 ~-1 ~4 ~6 ~1 ~6 minecraft:magma_block", "${at} setblock ~5 ~2 ~5 minecraft:chest{LootTable:\"minecraft:chests/ruined_portal\"}",
       "${at} particle minecraft:explosion_emitter ~5 ~1 ~5", "playsound minecraft:entity.generic.explode master @a ~ ~ ~ 1 0.6 1")),
    S("смотровая площадка", ("curious",), 0.3, "safe",
      ("give ${p} minecraft:spyglass 1", "effect give ${p} minecraft:slow_falling 30 0", "${as} tp @s ~ ~30 ~", say("посмотри на мир сверху.", "aqua"))),
    S("эхолокация", ("curious", "alert"), 0.3, "safe",
      ("${at} particle minecraft:sonic_boom ~ ~1 ~", "playsound minecraft:entity.warden.sonic_charge master @a ~ ~ ~ 1 1 1",
       "${at} effect give @e[distance=..30] minecraft:glowing 5 0")),
    S("вагонетка-сюрприз", ("curious",), 0.2, "safe",
      ('${at} summon minecraft:chest_minecart ~2 ~ ~ {LootTable:"minecraft:chests/abandoned_mineshaft",Tags:["flybrain"]}',)),
    S("лодка с котом", ("curious", "bored"), 0.0, "safe", ('${at} summon minecraft:oak_boat ~2 ~ ~ {Passengers:[{id:"minecraft:cat"}]}',)),
    S("тайный подарок", ("curious",), 0.2, "safe",
      ('${at} summon minecraft:item ~${r3} ~1 ~${r3} {Item:{id:"minecraft:${c:bundle,name_tag,goat_horn,recovery_compass,music_disc_5,disc_fragment_5}",count:1}}',)),
    S("мини-сад", ("curious", "grooming"), 0.2, "safe",
      ("${at} fill ~-2 ~ ~-2 ~2 ~ ~2 minecraft:${c:poppy,cornflower,allium,azure_bluet,pink_petals,torchflower} replace minecraft:air",
       "${at} particle minecraft:happy_villager ~ ~1 ~ 2 0.5 2 0 60")),
    S("бросает монетку", ("curious", "bored"), 0.0, "safe", ("random roll 1..2",)),
    S("лунная походка", ("curious",), 0.3, "safe",
      ("attribute ${p} minecraft:gravity base set 0.015", "effect give ${p} minecraft:jump_boost 20 2", say("ты на Луне.", "gray")),
      ((20.0, "attribute ${p} minecraft:gravity base reset"),)),

    # ======================= ТРЕВОГА =======================
    S("осветительная ракета", ("alert",), 0.2, "safe",
      ("${at} summon minecraft:firework_rocket ~ ~1 ~ " + FW, "${at} effect give @e[distance=..40] minecraft:glowing 10 0")),
    S("сирена", ("alert",), 0.4, "safe",
      ("playsound minecraft:event.raid.horn master @a ~ ~ ~ 1 1 1", title("@a", "ТРЕВОГА", "red"))),
    S("дозор", ("alert",), 0.5, "safe",
      ('${at} summon minecraft:iron_golem ~3 ~ ~ {Tags:["flybrain"]}', '${at} summon minecraft:iron_golem ~-3 ~ ~ {Tags:["flybrain"]}',
       say("охрана выставлена.", "yellow"))),
    S("сигнальные огни", ("alert",), 0.2, "safe",
      ("${at} setblock ~3 ~ ~ minecraft:lantern keep", "${at} setblock ~-3 ~ ~ minecraft:lantern keep",
       "${at} setblock ~ ~ ~3 minecraft:lantern keep", "${at} setblock ~ ~ ~-3 minecraft:lantern keep")),
    S("всем стоять", ("alert",), 0.6, "safe", ("effect give @a minecraft:slowness 5 4", title("@a", "СТОЯТЬ", "yellow"))),
    S("тройной звонок", ("alert",), 0.0, "safe", ("playsound minecraft:block.bell.use master @a ~ ~ ~ 1 1 1",),
      ((0.6, "playsound minecraft:block.bell.use master @a ~ ~ ~ 1 1 1"), (1.2, "playsound minecraft:block.bell.use master @a ~ ~ ~ 1 1 1"))),
    S("слежка", ("alert",), 0.0, "safe",
      (title("@a", "👁", "yellow", "actionbar"), "${at} particle minecraft:end_rod ~ ~2.2 ~ 0.1 0.1 0.1 0 20")),
    S("маркер над каждым", ("alert",), 0.3, "safe", ("execute at @a run summon minecraft:firework_rocket ~ ~ ~ {LifeTime:15}",)),
    S("проверка документов", ("alert",), 0.2, "safe", ("effect give @a minecraft:glowing 5 0", say("стоять. проверка.", "yellow"))),

    # ======================= СКУКА =======================
    S("считает овец", ("bored",), 0.0, "safe",
      ('${at} summon minecraft:sheep ~3 ~ ~ {Tags:["flybrain"],Color:${c:0,4,6,10,14}b}', say("одна овца...", "gray"))),
    S("играет на пианино", ("bored", "feeding"), 0.0, "safe",
      ("playsound minecraft:block.note_block.${c:harp,pling,bell,chime,flute} master @a ~ ~ ~ 1 ${c:0.5,0.6,0.7,0.8,0.9,1,1.2,1.4,1.6,1.8,2} 1",),
      ((0.4, "playsound minecraft:block.note_block.harp master @a ~ ~ ~ 1 ${c:0.7,1,1.3,1.6} 1"),
       (0.8, "playsound minecraft:block.note_block.harp master @a ~ ~ ~ 1 ${c:0.8,1.1,1.5,2} 1"),
       (1.2, "playsound minecraft:block.note_block.bell master @a ~ ~ ~ 1 ${c:1,1.5,2} 1"))),
    S("зевает", ("bored",), 0.0, "safe", (title("@a", "*муха зевает*", "gray", "actionbar"), "playsound minecraft:entity.cat.ambient master @a ~ ~ ~ 0.4 0.6 0.4")),
    S("мыльные пузыри", ("bored", "grooming"), 0.0, "safe", ("${at} particle minecraft:bubble_pop ~ ~2 ~ 2 1 2 0 150",)),
    S("статуя снеговика", ("bored",), 0.0, "safe", ('${at} summon minecraft:snow_golem ~2 ~ ~ {Tags:["flybrain"]}',)),
    S("кольца дыма", ("bored",), 0.0, "safe", ("${at} particle minecraft:campfire_cosy_smoke ~ ~2 ~ 0.2 0.5 0.2 0.01 30",)),
    S("меняет погоду туда-сюда", ("bored",), 0.0, "safe", ("weather rain",), ((10.0, "weather clear"),)),
    S("рисует в воздухе", ("bored", "curious"), 0.0, "safe",
      ("4-10*${at} particle minecraft:${c:end_rod,glow,wax_off,electric_spark} ~${f3} ~${c:2,3,4} ~${f3} 0 0 0 0 5",)),
    S("летучая мышь-питомец", ("bored",), 0.0, "safe", ('${at} summon minecraft:bat ~ ~2 ~ {CustomName:"Муха-младшая",Tags:["flybrain"]}',)),
    S("пишет в небе «бзз»", ("bored",), 0.3, "am",
      ("${at} summon minecraft:text_display ~ ~10 ~ " + TEXT3D % ("бзз", "yellow", 5, 5, 5),), ((20.0, "kill @e[tag=flytext]"),)),
]


def build_scenarios() -> dict[str, list]:
    """(вес, действие, мин. интенсивность, пол силы) по настроениям."""
    out: dict[str, list] = {}
    for s in SCENARIOS:
        b = compile_scenario(s)
        for mood in s.moods:
            out.setdefault(mood, []).append((s.weight, b, s.min_i, s.floor))
    return out
