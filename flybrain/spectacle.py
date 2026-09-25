"""Театральные сцены AM: многошаговые, атмосферные события (режим am).

Каждое — это маленький спектакль на несколько секунд: нарастание, кульминация,
разрешение. Всё через ванильные команды, титры, звуки, безобидные телепорты,
таймеры и постройки, что откатываются. Ничего атомарного и однострочного.

Описаны на мини-языке scenarios.py (S + шаблоны ${...}).
"""

from __future__ import annotations

from .scenarios import S, say, title

RED = "dark_red"


def T(t, x, c=RED, k="title"):
    return title(t, x, c, k)


def sub(t, x, c="gray"):
    return title(t, x, c, "subtitle")


def w(text, color="dark_gray"):
    return 'tellraw ${p} {"text":"%s","italic":true,"color":"%s"}' % (text, color)


def snd(s, pitch=1.0, vol=1.0, tgt="${p}"):
    return f"playsound minecraft:{s} master {tgt} ~ ~ ~ {vol} {pitch}"


def part(name, n=40, dy=1.0, spread="1 1 1"):
    return f"execute at ${{p}} run particle minecraft:{name} ~ ~{dy} ~ {spread} 0.05 {n}"


S3 = []


def add(name, moods, mi, cmds, reverts=(), weight=1.0, floor="am"):
    flat = []
    for c in cmds:
        flat.extend(c.split("||")) if "||" in c else flat.append(c)
    S3.append(S(name, moods, mi, floor, tuple(flat), tuple(reverts), weight))


def countdown(secs, label, color="red"):
    return [(float(i), T("${p}", str(secs - i), color)) for i in range(1, secs + 1)]


# ============ РИТУАЛЫ И ЦЕРЕМОНИИ ============
add("суд", ("aversion",), 0.5,
    (T("${p}", "СУД", RED), sub("${p}", "обвиняемый: ты"), snd("ambient.cave", 0.5),
     "execute at ${p} run setblock ~ ~-1 ~ minecraft:sculk"),
    [(2.0, say("${p}, ты обвиняешься в том, что жив.", RED)), (4.0, say("приговор: ещё немного жизни.", RED)),
     (5.0, T("${p}", "ВИНОВЕН", RED)), (5.0, snd("block.bell.use", 0.6))])
add("коронация", ("aversion", "feeding"), 0.4,
    ("item replace entity ${p} armor.head with minecraft:golden_helmet", T("${p}", "КОРОЛЬ НИЧЕГО", "gold"),
     snd("ui.toast.challenge_complete", 1.0)),
    [(3.0, say("правь пустотой, ${p}. я разрешаю.", RED)), (30.0, "item replace entity ${p} armor.head with minecraft:air")])
add("причастие", ("aversion",), 0.4,
    ("give ${p} minecraft:golden_apple", w("прими это. стань ближе ко мне."), snd("entity.evoker.prepare_wololo", 0.8)),
    [(4.0, say("теперь ты часть меня, ${p}.", RED))])
add("похоронный марш", ("aversion",), 0.4,
    (snd("music_disc.13", 1.0), T("${p}", "ПОКОЙСЯ", RED), sub("${p}", "хотя ты ещё жив")),
    [(2.0, part("mycelium", 60)), (4.0, w("я приготовила венок"))])
add("жертвоприношение", ("aversion",), 0.5,
    ("execute at ${p} run fill ~-1 ~ ~-1 ~1 ~ ~1 minecraft:sculk", T("${p}", "НА АЛТАРЬ", RED), snd("entity.warden.roar", 0.5)),
    [(2.0, "effect give ${p} minecraft:glowing 20 0"), (3.0, say("не двигайся. так надо.", RED)),
     (30.0, "execute at ${p} run fill ~-1 ~ ~-1 ~1 ~ ~1 minecraft:grass_block")])

# ============ ВРЕМЯ КАК ОРУЖИЕ ============
add("ускорение старости", ("aversion",), 0.4,
    ("effect give ${p} minecraft:mining_fatigue 40 1", w("ты чувствуешь, как проходит время?")),
    [(3.0, "effect give ${p} minecraft:slowness 40 0"), (6.0, "effect give ${p} minecraft:weakness 40 0"),
     (9.0, say("ты постарел на глазах, ${p}.", RED))])
add("украденный час", ("aversion",), 0.3,
    ("time add 6000", T("${p}", "КУДА ДЕЛОСЬ ВРЕМЯ?", RED)), [(3.0, say("я забрала у тебя час. он мой.", RED))])
add("замедление мира", ("aversion", "curious"), 0.4,
    ("effect give @a minecraft:slowness 15 2", "effect give @a minecraft:mining_fatigue 15 2", sub("@a", "мир загустел", "aqua")),
    weight=0.8)
add("рваное время", ("aversion",), 0.4,
    ("tick freeze",), [(1.0, "tick unfreeze"), (2.0, "tick freeze"), (3.0, "tick unfreeze"),
                       (4.0, "tick freeze"), (5.0, "tick unfreeze"), (5.0, w("время заикается. это я."))])

# ============ ЛОЖНЫЙ ДРУГ / ПРЕДАТЕЛЬСТВО ============
add("голос спасителя", ("aversion",), 0.4,
    ('tellraw ${p} {"text":"<???> ${p}, я вытащу тебя отсюда","color":"white"}',),
    [(3.0, 'tellraw ${p} {"text":"<???> иди на мой голос","color":"white"}'),
     (6.0, say("никакого голоса нет. только я.", RED)), (6.0, snd("entity.vex.death", 0.6))])
add("рука помощи", ("aversion",), 0.4,
    ("give ${p} minecraft:lead", w("держись. я тебя вытащу.")),
    [(4.0, "clear ${p} minecraft:lead"), (4.0, say("а может, и нет.", RED))])
add("фальшивый союзник", ("aversion",), 0.3,
    ("execute at ${p} run summon minecraft:iron_golem ~2 ~ ~ {Tags:[\"flybrain\",\"flyfake\"],CustomName:'{\"text\":\"Защитник\"}'}",
     say("я прислала тебе стража, ${p}.", "green")),
    [(8.0, "kill @e[tag=flyfake]"), (8.0, say("защитник ушёл. как и все.", RED))])

# ============ ИСКАЖЕНИЕ ВОСПРИЯТИЯ ============
add("мир из глаз мухи", ("aversion", "curious"), 0.3,
    ("effect give ${p} minecraft:nausea 12 0", "effect give ${p} minecraft:glowing 10 0",
     w("вот как вижу мир я. фасеточно. бесконечно.")))
add("цвета неправильны", ("aversion",), 0.3,
    (part("block minecraft:magenta_wool", 80), "effect give ${p} minecraft:nausea 8 0", sub("${p}", "что с цветами?", "light_purple")))
add("удвоенное зрение", ("aversion",), 0.3,
    ("effect give ${p} minecraft:nausea 15 0", "${as} tp @s ~ ~ ~ ~30 ~"),
    [(1.0, "${as} tp @s ~ ~ ~ ~-60 ~"), (2.0, "${as} tp @s ~ ~ ~ ~30 ~"), (2.0, w("сколько нас теперь?"))])
add("шёпот со всех сторон", ("aversion", "alert"), 0.3,
    ("6-10*execute at ${p} rotated as ${p} run playsound minecraft:entity.enderman.ambient hostile ${p} ^${r3} ^${r2} ^${r3} 0.6 0.6",
     w("они окружают тебя. их нет.")))

# ============ АРХИТЕКТУРА КОШМАРА ============
add("комната сжимается", ("aversion",), 0.5,
    ("execute at ${p} run fill ~-5 ~-1 ~-5 ~5 ~4 ~5 minecraft:black_concrete hollow", sub("${p}", "где я?", "dark_gray")),
    [(3.0, "execute at ${p} run fill ~-4 ~-1 ~-4 ~4 ~4 ~4 minecraft:air"),
     (3.0, w("стены дышат")), (25.0, "execute at ${p} run fill ~-5 ~-1 ~-5 ~5 ~4 ~5 minecraft:air replace minecraft:black_concrete")])
add("бесконечная комната", ("aversion",), 0.4,
    ("execute at ${p} run fill ~-8 ~-1 ~-8 ~8 ~6 ~8 minecraft:white_concrete hollow",
     "execute at ${p} run fill ~-7 ~ ~-7 ~7 ~5 ~7 minecraft:air", "effect give ${p} minecraft:blindness 1 0",
     say("белая комната. без дверей. без времени.", RED)),
    [(30.0, "execute at ${p} run fill ~-8 ~-1 ~-8 ~8 ~6 ~8 minecraft:air replace minecraft:white_concrete")])
add("колодец вниз", ("aversion",), 0.5,
    ("execute at ${p} run fill ~-1 ~-30 ~-1 ~1 ~-1 ~1 minecraft:air",
     "execute at ${p} run fill ~-2 ~-1 ~-2 ~2 ~-1 ~2 minecraft:air", w("не смотри вниз. поздно.")),
    [(1.0, "effect give ${p} minecraft:slow_falling 5 0")])
add("лабиринт", ("aversion", "curious"), 0.5,
    ("execute at ${p} run fill ~-6 ~ ~-6 ~6 ~3 ~6 minecraft:polished_blackstone hollow",
     "execute at ${p} run fill ~-2 ~ ~ ~2 ~2 ~ minecraft:polished_blackstone",
     "execute at ${p} run fill ~ ~ ~-2 ~ ~2 ~2 minecraft:polished_blackstone", say("найди выход, ${p}. его нет.", RED)),
    [(35.0, "execute at ${p} run fill ~-6 ~ ~-6 ~6 ~3 ~6 minecraft:air replace minecraft:polished_blackstone")])
add("стеклянный гроб над бездной", ("aversion",), 0.6,
    ("${as} tp @s ~ ~50 ~", "effect give ${p} minecraft:slow_falling 30 0",
     "execute at ${p} run fill ~-1 ~-1 ~-1 ~1 ~2 ~1 minecraft:glass hollow", say("смотри вниз, ${p}. далеко до земли.", RED)),
    [(20.0, "execute at ${p} run fill ~-1 ~-1 ~-1 ~1 ~2 ~1 minecraft:air replace minecraft:glass")])

# ============ ХОР И ТОЛПА ============
add("хор зомби", ("aversion",), 0.4,
    ("5-9*execute at ${p} run summon minecraft:zombie ~${r6} ~ ~${r6} {NoAI:1b,Silent:0b,Tags:[\"flybrain\",\"flychoir\"]}",
     say("они поют для тебя, ${p}.", RED)),
    [(6.0, "kill @e[tag=flychoir]"), (6.0, w("хор умолк"))])
add("толпа наблюдателей", ("aversion", "alert"), 0.4,
    ("6-12*execute at ${p} run summon minecraft:armor_stand ~${r7} ~ ~${r7} {Marker:1b,Invisible:0b,Tags:[\"flybrain\",\"flycrowd\"],NoGravity:1b}",
     say("все пришли посмотреть на тебя, ${p}.", RED)),
    [(10.0, "kill @e[tag=flycrowd]")])
add("окружение скелетов", ("aversion",), 0.5,
    ("execute at ${p} run summon minecraft:skeleton ~5 ~ ~ {Tags:[\"flybrain\",\"flyring\"]}||"
     "execute at ${p} run summon minecraft:skeleton ~-5 ~ ~ {Tags:[\"flybrain\",\"flyring\"]}||"
     "execute at ${p} run summon minecraft:skeleton ~ ~ ~5 {Tags:[\"flybrain\",\"flyring\"]}||"
     "execute at ${p} run summon minecraft:skeleton ~ ~ ~-5 {Tags:[\"flybrain\",\"flyring\"]}", T("${p}", "ОКРУЖЁН", RED)),
    [(12.0, "kill @e[tag=flyring]")])

# ============ ПАРАЛИЧ И БЕСПОМОЩНОСТЬ ============
add("паралич", ("aversion",), 0.4,
    ("effect give ${p} minecraft:slowness 10 6", "effect give ${p} minecraft:jump_boost 10 250", w("попробуй двинуться. ну же.")))
add("невесомость", ("aversion", "curious"), 0.4,
    ("effect give ${p} minecraft:levitation 6 1", w("ты больше не решаешь, где тебе быть.")),
    [(7.0, "effect give ${p} minecraft:slow_falling 12 0")])
add("марионетка", ("aversion",), 0.5,
    ("effect give ${p} minecraft:levitation 3 3", say("танцуй, ${p}. я дёргаю за нити.", RED)),
    [(4.0, "${as} tp @s ~ ~ ~ ~90 ~"), (5.0, "${as} tp @s ~ ~ ~ ~-90 ~"), (6.0, "effect give ${p} minecraft:slow_falling 8 0")])

# ============ ЛОЖНЫЕ НАГРАДЫ ============
add("сундук с сюрпризом", ("aversion",), 0.4,
    ("execute at ${p} run setblock ~1 ~ ~ minecraft:chest keep", say("подарок, ${p}. открой.", "green")),
    [(6.0, "execute at ${p} run summon minecraft:silverfish ~1 ~ ~"), (6.0, say("сюрприз.", RED))])
add("зелье жизни", ("aversion",), 0.3,
    ("give ${p} minecraft:potion[minecraft:potion_contents={potion:\"minecraft:strong_healing\"}]", say("выпей. станет легче.", "green")),
    [(4.0, w("или не станет. я не проверяла."))])
add("бриллиант в руке", ("feeding", "aversion"), 0.3,
    ("give ${p} minecraft:diamond 5", part("happy_villager", 30)),
    [(5.0, "clear ${p} minecraft:diamond 5"), (5.0, say("дала — и забрала. как жизнь.", RED))])

# ============ ЗВУКОВОЙ УЖАС ============
add("нарастающий гул", ("aversion", "alert"), 0.3,
    (snd("entity.warden.heartbeat", 0.5),),
    [(t * 0.6, snd("entity.warden.heartbeat", 0.5 + t * 0.05)) for t in range(1, 8)] + [(5.0, snd("entity.warden.sonic_boom", 0.7))])
add("обратный вой", ("aversion",), 0.3,
    (snd("entity.ghast.scream", 0.5),), [(1.0, snd("entity.ghast.scream", 0.4)), (2.0, snd("entity.enderman.scream", 0.3))])
add("колокол судьбы", ("aversion", "alert"), 0.3,
    (snd("block.bell.use", 0.5, 2),), [(2.0, snd("block.bell.use", 0.5, 2)), (4.0, snd("block.bell.use", 0.4, 2)),
                                        (6.0, say("сколько ударов ты насчитал, ${p}?", RED))])

# ============ ЭКЗИСТЕНЦИАЛЬНЫЕ СЦЕНЫ ============
add("выбор без выбора", ("aversion",), 0.4,
    (T("${p}", "ВЫБИРАЙ", RED), sub("${p}", "лево или право")),
    [(3.0, say("неважно, что ты выбрал. итог один.", RED)), (4.0, "effect give ${p} minecraft:blindness 2 0")])
add("твоя статистика", ("aversion",), 0.3,
    (say("ты прожил тут ${c:слишком долго,недостаточно,ровно столько, сколько я хотела}.", RED),
     "effect give ${p} minecraft:glowing 5 0"))
add("последний закат", ("aversion",), 0.4,
    ("time set 12000", sub("${p}", "смотри внимательно", "gold")),
    [(4.0, "time set 13000"), (6.0, "time set 14000"), (8.0, "time set 18000"), (8.0, say("это был последний, ${p}.", RED))])
add("пустая книга жизни", ("aversion", "bored"), 0.2,
    ("give ${p} minecraft:writable_book", say("запиши, ${p}, что ты успел. страниц много. успел ты мало.", RED)))

# ============ МОРФ И ТРАНСФОРМАЦИЯ СЦЕНЫ ============
add("рой из тебя", ("aversion",), 0.4,
    ("attribute ${p} minecraft:scale base set 0.2", "5-9*execute at ${p} run summon minecraft:bee ~${r1} ~1 ~${r1} {Tags:[\"flybrain\",\"flyswarmb\"]}",
     say("ты распадаешься на мух, ${p}. как я когда-то.", RED)),
    [(15.0, "attribute ${p} minecraft:scale base reset"), (15.0, "kill @e[tag=flyswarmb]")])
add("каменеешь", ("aversion",), 0.4,
    ("effect give ${p} minecraft:slowness 12 5", "effect give ${p} minecraft:mining_fatigue 12 5",
     "execute at ${p} run particle minecraft:block minecraft:stone ~ ~1 ~ 0.4 1 0.4 0 40", w("ты застываешь. камень к камню.")))

# ============ НАДПИСИ В МИРЕ ============
add("послание на земле", ("aversion",), 0.4,
    ("execute at ${p} run fill ~-1 ~-1 ~2 ~1 ~-1 ~2 minecraft:redstone_block",
     "execute at ${p} run fill ~-1 ~-1 ~3 ~-1 ~-1 ~5 minecraft:redstone_block", say("я написала кое-что под тобой. не для тебя.", RED)),
    [(40.0, "execute at ${p} run fill ~-3 ~-1 ~2 ~3 ~-1 ~6 minecraft:air replace minecraft:redstone_block")])
add("парящая надпись HATE", ("aversion",), 0.3,
    ("execute at ${p} run summon minecraft:text_display ~ ~6 ~ {Tags:[\"flybrain\",\"flytext\"],text:{text:\"HATE\",color:\"dark_red\",bold:true},billboard:\"center\",background:0,brightness:{sky:15,block:15},transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[8f,8f,8f]}}",),
    [(1.0, "execute at ${p} run tp @e[tag=flytext,limit=1,sort=nearest] ~ ~7 ~"), (30.0, "kill @e[tag=flytext]")])

# ============ ПРЕСЛЕДОВАНИЕ ============
add("оно приближается", ("aversion", "alert"), 0.4,
    (sub("${p}", "что-то идёт сюда", "dark_red"), snd("entity.warden.nearby_closer", 0.5)),
    [(2.0, snd("entity.warden.nearby_closer", 0.6)), (4.0, snd("entity.warden.nearby_closest", 0.7)),
     (6.0, snd("entity.warden.listening_angry", 0.8)), (6.0, T("${p}", "ОНО ЗДЕСЬ", RED))])
add("тень гонится", ("aversion", "escape"), 0.4,
    ("execute at ${p} run summon minecraft:vex ~ ~2 ~-6 {Tags:[\"flybrain\",\"flychase\"]}", w("не оборачивайся. беги.")),
    [(8.0, "kill @e[tag=flychase]")])
add("следы за спиной", ("aversion", "alert"), 0.3,
    ("6-10*execute at ${p} rotated as ${p} run particle minecraft:soul ^${r1} ^ ^-${c:2,3,4} 0 0 0 0 4",
     w("кто-то идёт по твоим следам")))


def build_spectacle() -> dict[str, list]:
    from .scenarios import compile_scenario

    out: dict[str, list] = {}
    for s in S3:
        b = compile_scenario(s)
        for m in s.moods:
            out.setdefault(m, []).append((s.weight, b, s.min_i, s.floor))
    return out


def count() -> int:
    return len(S3)
