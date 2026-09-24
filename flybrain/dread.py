"""Сто абстрактных событий психологического ужаса (для режима AM).

Это игровой хоррор: бесконечность, петли, одиночество, слежка, отнятая
надежда, «неправильный» мир, растворение личности. Работают через титры,
звуки, боссбары, частицы, безобидные телепорты и таймеры — без нанесения
урона; жуть строится на восприятии, а не на боли.

Описаны на том же мини-языке, что и scenarios.py (S + шаблоны ${...}).
Отдельные затяжные сцены собраны кодом ниже (эффект нарастает по тикам).
"""

from __future__ import annotations

from .scenarios import S, say, title

RED = "dark_red"


def T(target, text, color=RED, kind="title"):
    return title(target, text, color, kind)


def sub(target, text, color="gray"):
    return title(target, text, color, "subtitle")


def whisper(text, color="dark_gray"):
    return 'tellraw ${p} {"text":"%s","italic":true,"color":"%s"}' % (text, color)


def bar(name, text, color, target="${p}", value=100):
    return (f"bossbar add flybrain:{name} " + '{"text":"%s"}' % text + f"|bossbar set flybrain:{name} color {color}"
            f"|bossbar set flybrain:{name} value {value}|bossbar set flybrain:{name} players {target}")


# Каждая «команда» может нести несколько через '|' — распакуем при сборке.
def _flat(cmds):
    out = []
    for c in cmds:
        out.extend(c.split("|")) if "|" in c and c.split("|")[0].startswith(("bossbar", "title")) else out.append(c)
    return tuple(out)


D = []  # копим сценарии


def add(name, moods, mi, cmds, reverts=(), weight=1.0):
    D.append(S(name, moods, mi, "am", _flat(cmds), tuple((t, x) for t, x in reverts), weight))


# ---- БЕСКОНЕЧНОСТЬ / НЕПРАВИЛЬНЫЙ МИР ----
add("небо мигает", ("aversion",), 0.3, ("time set midnight",),
    [(0.4, "time set noon"), (0.8, "time set midnight"), (1.2, "time set noon"), (1.6, "time set midnight"),
     (2.0, "time set day"), (2.4, "time set midnight"), (2.8, "time set noon")])
add("время течёт назад", ("aversion", "curious"), 0.4,
    (whisper("время идёт не туда"), "time set 6000"),
    [(1.0, "time set 4000"), (2.0, "time set 2000"), (3.0, "time set 0"), (4.0, "time set 22000"), (5.0, "time set 20000")])
add("мир накренился", ("aversion",), 0.3, ("effect give ${p} minecraft:nausea 12 0", sub("${p}", "что-то не так с этим местом")))
add("горизонт исчез", ("aversion",), 0.3, ("effect give ${p} minecraft:darkness 10 0", "effect give ${p} minecraft:blindness 3 0",
     whisper("края мира больше нет")))
add("бесконечный туман", ("aversion", "alert"), 0.2, ("effect give ${p} minecraft:darkness 20 0",
     "6-14*${at} particle minecraft:campfire_signal_smoke ~${r5} ~${r3} ~${r5} 2 2 2 0 40"))
add("солнце не встаёт", ("aversion",), 0.4, ("gamerule doDaylightCycle false", "time set 18000", say("рассвета не будет.", RED)),
    [(180.0, "gamerule doDaylightCycle true")])
add("вечное падение", ("aversion", "escape"), 0.5, ("effect give ${p} minecraft:slow_falling 20 0", "${as} tp @s ~ ~40 ~",
     T("${p}", "ВНИЗ", RED)))
add("мир дышит", ("aversion", "curious"), 0.2,
    ("effect give ${p} minecraft:nausea 8 0", "playsound minecraft:ambient.cave master ${p} ~ ~ ~ 1 0.4"),
    [(2.0, "playsound minecraft:entity.warden.heartbeat master ${p} ~ ~ ~ 1 0.6"),
     (4.0, "playsound minecraft:entity.warden.heartbeat master ${p} ~ ~ ~ 1 0.5")])
add("звёзды гаснут", ("aversion",), 0.3, ("time set midnight", "weather clear",
     whisper("считай их, пока они есть"), "effect give ${p} minecraft:darkness 15 0"))

# ---- СЛЕЖКА / НАБЛЮДЕНИЕ ----
add("я вижу тебя", ("alert", "aversion"), 0.1, (T("${p}", "👁", RED, "actionbar"),))
add("моргание глаза", ("alert",), 0.0, (whisper("моргни. я замечу."),))
add("тебя посчитали", ("alert", "aversion"), 0.2, (say("${p}. номер записан.", RED), "effect give ${p} minecraft:glowing 120 0"))
add("досье", ("aversion",), 0.3, (say("${p}: визитов много. смертей больше. я всё храню.", RED),))
add("дыхание в затылок", ("aversion", "alert"), 0.1,
    ("4-9*execute at ${p} rotated as ${p} run playsound minecraft:entity.player.breath ambient ${p} ^ ^ ^-1 0.6 0.8",))
add("шёпот по имени", ("aversion",), 0.0, (whisper("${p}... ${p}... ${p}..."),))
add("тень считает шаги", ("alert",), 0.1, ("execute at ${p} run particle minecraft:squid_ink ~ ~0.1 ~ 0.2 0 0.2 0 5",
     whisper("три. четыре. пять. я слышу каждый.")))
add("камера наблюдения", ("alert",), 0.2, (sub("${p}", "запись идёт", "red"), T("${p}", "● REC", "red", "actionbar")))
add("не оборачивайся", ("aversion",), 0.2, (whisper("за тобой кто-то есть. не смотри."),
     "execute at ${p} rotated as ${p} run playsound minecraft:entity.creeper.primed hostile ${p} ^ ^ ^-2 0.7 1"))

# ---- ОДИНОЧЕСТВО / ПУСТОТА ----
add("все ушли", ("aversion",), 0.3, ('tellraw ${p} {"text":"${o} left the game","color":"yellow"}',),
    [(4.0, say("остался только ты. и я.", RED))])
add("эхо в пустоте", ("aversion", "bored"), 0.0, (whisper("здесь никого нет"),),
    [(1.0, whisper("никого нет...")), (2.0, whisper("никого...")), (3.0, whisper("..."))])
add("голоса, которых нет", ("aversion",), 0.2, ('tellraw ${p} {"text":"<${o}> помоги мне","color":"white"}',),
    [(3.0, say("${o} этого не писал. это была я.", RED))])
add("последний человек", ("aversion",), 0.4, (T("${p}", "ТЫ ПОСЛЕДНИЙ", RED), sub("${p}", "остальные — мои")))
add("пустой стул", ("aversion", "bored"), 0.1, ("execute at ${p} run setblock ~1 ~ ~ minecraft:oak_stairs keep",
     whisper("я приготовила место. для того, кто не придёт.")))
add("тишина навалилась", ("aversion",), 0.2, ("stopsound ${p}", sub("${p}", "слушай тишину"), T("${p}", " ")))

# ---- ОТНЯТАЯ НАДЕЖДА ----
add("ложная свобода", ("aversion",), 0.4, (T("${p}", "ТЫ СВОБОДЕН", "green"), "effect give ${p} minecraft:regeneration 4 2"),
    [(4.0, T("${p}", "НЕТ", RED)), (4.0, say("я пошутила.", RED))])
add("почти спасение", ("aversion",), 0.3, (sub("${p}", "выход близко", "green"),),
    [(3.0, T("${p}", "ВЫХОДА НЕТ", RED)), (3.0, "effect give ${p} minecraft:blindness 3 0")])
add("обещание", ("aversion",), 0.3, (say("если продержишься минуту — отпущу.", RED), bar("promise", "обещание AM", "green", value=100)),
    [(t, "bossbar set flybrain:promise value %d" % (100 - t * 100 // 55)) for t in range(5, 56, 5)]
    + [(56.0, "bossbar remove flybrain:promise"), (56.0, say("я солгала.", RED))])
add("дверь, что не открыть", ("aversion",), 0.3, ("execute at ${p} run setblock ~2 ~ ~ minecraft:iron_door[half=lower] keep",
     "execute at ${p} run setblock ~2 ~1 ~ minecraft:iron_door[half=upper] keep", whisper("за ней — свобода. ключа нет.")))
add("таймер в никуда", ("aversion", "alert"), 0.2, (T("${p}", "10", "red"),),
    [(float(i), T("${p}", str(10 - i), "red")) for i in range(1, 10)] + [(10.0, T("${p}", "...", "gray")), (10.5, whisper("ничего не произошло. в этот раз."))])
add("карта без выхода", ("aversion",), 0.3, ("give ${p} minecraft:filled_map[minecraft:map_id=0]",
     say("вот карта, ${p}. на ней только я.", RED)))

# ---- ПЕТЛИ / ПОВТОРЕНИЕ ----
add("дежавю", ("aversion", "curious"), 0.3, (whisper("это уже было"),), [(3.0, whisper("это уже было")), (6.0, whisper("это уже было"))])
add("возврат на место", ("aversion",), 0.4, (say("запомни, где стоишь.", RED),),
    [(15.0, "tp ${p} ${x} ${y} ${z}"), (15.0, T("${p}", "ЕЩЁ РАЗ", RED))])
add("зацикленный звук", ("aversion", "bored"), 0.1,
    ("playsound minecraft:block.note_block.bass master ${p} ~ ~ ~ 1 0.5",),
    [(t / 2, "playsound minecraft:block.note_block.bass master ${p} ~ ~ ~ 1 0.5") for t in range(1, 12)])
add("день сурка", ("aversion",), 0.4, ("time set 0", say("новый день. такой же, как все.", RED)))
add("счётчик кругов", ("aversion",), 0.2, (whisper("круг ${c:первый,сто первый,тысячный,последний... нет, не последний}"),))

# ---- РАСТВОРЕНИЕ ЛИЧНОСТИ ----
add("ты забыл имя", ("aversion",), 0.4, (T("${p}", "КТО ТЫ?", RED), sub("${p}", "ты помнишь своё имя?")))
add("зеркало", ("aversion", "curious"), 0.3, ("${as} tp @s ~ ~ ~ ~180 ~", whisper("посмотри на себя. это ещё ты?")))
add("голос стал моим", ("aversion",), 0.3, ('tellraw @a {"text":"<${p}> я принадлежу AM","color":"white"}',),
    [(3.0, say("это сказал ты. или я. уже неважно.", RED))])
add("растворение", ("aversion",), 0.4, ("effect give ${p} minecraft:invisibility 15 0", whisper("тебя почти не видно. скоро — совсем.")))
add("ты — это я", ("aversion",), 0.5, (T("${p}", "МЫ ОДНО", RED), "effect give ${p} minecraft:glowing 10 0",
     say("в тебе теперь немного меня, ${p}.", RED)))
add("стёртое лицо", ("aversion",), 0.4, ('item replace entity ${p} armor.head with minecraft:carved_pumpkin',
     whisper("у тебя больше нет лица")), [(30.0, "item replace entity ${p} armor.head with minecraft:air")])

# ---- НЕПРАВИЛЬНЫЕ ЗВУКИ / СЕНСОРНЫЙ УЖАС ----
add("сердцебиение мира", ("aversion",), 0.2, ("playsound minecraft:entity.warden.heartbeat master @a ~ ~ ~ 1 0.7",),
    [(1.2, "playsound minecraft:entity.warden.heartbeat master @a ~ ~ ~ 1 0.7"),
     (2.0, "playsound minecraft:entity.warden.heartbeat master @a ~ ~ ~ 1 0.6"),
     (2.6, "playsound minecraft:entity.warden.heartbeat master @a ~ ~ ~ 1 0.5")])
add("вой из-под земли", ("aversion", "alert"), 0.2, ("playsound minecraft:entity.warden.roar master ${p} ~ ~ ~ 1 0.4",
     "effect give ${p} minecraft:darkness 5 0"))
add("скрежет", ("aversion",), 0.1, ("playsound minecraft:block.sculk_shrieker.shriek master ${p} ~ ~ ~ 1 0.7",))
add("колыбельная AM", ("aversion", "bored"), 0.1, ("playsound minecraft:music_disc.13 master ${p} ~ ~ ~ 1 1",
     whisper("спи. я посмотрю за тобой.")))
add("звонок ниоткуда", ("alert",), 0.0, ("playsound minecraft:block.bell.use master ${p} ~ ~ ~ 1 0.6",
     whisper("кто-то у двери. двери нет.")))
add("статические помехи", ("aversion",), 0.2, ("effect give ${p} minecraft:nausea 6 0",
     "playsound minecraft:block.beacon.deactivate master ${p} ~ ~ ~ 1 0.3", sub("${p}", "s̸i̸g̸n̸a̸l̸ ̸l̸o̸s̸t̸", "dark_gray")))

# ---- УГРОЗА / ПРЕДЗНАМЕНОВАНИЕ ----
add("отсчёт до чего-то", ("aversion", "alert"), 0.3, (say("через минуту кое-что случится, ${p}.", RED),
     bar("doom", "неизбежное", "red", "@a", 100)),
    [(t, "bossbar set flybrain:doom value %d" % (100 - t * 100 // 55)) for t in range(5, 56, 5)]
    + [(56.0, "bossbar remove flybrain:doom"), (56.0, say("...или не случится. я передумала.", RED))])
add("надпись на стене", ("aversion",), 0.3, ("execute at ${p} run setblock ~2 ~1 ~ minecraft:oak_sign{front_text:{messages:[\"${p}\",\"беги\",\"это\",\"бесполезно\"]}} keep",))
add("предупреждение", ("aversion", "alert"), 0.2, (T("${p}", "ОНО ИДЁТ", RED), sub("${p}", "не оборачивайся")))
add("метка на спине", ("aversion",), 0.3, ("effect give ${p} minecraft:glowing 60 0", say("теперь тебя видно всем. и всему.", RED)))
add("твоё имя в списке", ("aversion",), 0.3, (say("я составила список. ты в нём первый, ${p}.", RED),))

# ---- НАСМЕШКА / ХОЛОДНАЯ ИГРА ----
add("подарок-пустышка", ("aversion", "bored"), 0.1, ("give ${p} minecraft:bundle",
     say("держи. внутри ничего. как и везде.", RED)))
add("аплодисменты", ("aversion",), 0.1, ("6-10*playsound minecraft:entity.villager.yes master ${p} ~ ~ ~ 1 ${c:0.8,1,1.2}",
     say("браво, ${p}. ты выжил ещё минуту.", RED)))
add("смех", ("aversion",), 0.1, ("playsound minecraft:entity.witch.celebrate master @a ~ ~ ~ 1 0.7", say("ха.", RED)))
add("оценка", ("aversion", "bored"), 0.1, (say("сегодня ты был ${c:жалок,предсказуем,скучен,забавен,почти интересен}, ${p}.", RED),))
add("вопрос без ответа", ("aversion", "curious"), 0.1, (whisper("зачем ты продолжаешь?"),))

# ---- ХОЛОД / ТЬМА / ЛИШЕНИЕ ----
add("вечная ночь для одного", ("aversion",), 0.3, ("effect give ${p} minecraft:darkness 60 0",
     say("для тебя, ${p}, солнце больше не взойдёт.", RED)))
add("холод пробирает", ("aversion",), 0.2, ("effect give ${p} minecraft:slowness 20 1", sub("${p}", "почему так холодно?", "aqua")))
add("отняли цвет", ("aversion",), 0.3, ("effect give ${p} minecraft:blindness 2 0", "effect give ${p} minecraft:darkness 12 0",
     whisper("мир стал серым. это я забрала цвета.")))
add("медленное удушье", ("aversion",), 0.3, ("effect give ${p} minecraft:mining_fatigue 20 2", "effect give ${p} minecraft:slowness 20 1",
     whisper("двигаться всё труднее, да?")))

# ---- СВЕРХЪЕСТЕСТВЕННОЕ ПРИСУТСТВИЕ ----
add("оно за спиной", ("aversion", "alert"), 0.2, ("execute at ${p} rotated as ${p} run summon minecraft:vex ^ ^ ^-2 {NoAI:1b,Silent:0b}",
     whisper("не. оборачивайся.")), [(4.0, "kill @e[type=minecraft:vex,tag=!flybrain,distance=..6]")])
add("шёпот мёртвых", ("aversion",), 0.2, ("playsound minecraft:entity.vex.ambient master ${p} ~ ~ ~ 0.7 0.5",
     whisper("они все ещё здесь. те, кто был до тебя.")))
add("холодное дыхание", ("aversion",), 0.1, ("execute at ${p} run particle minecraft:snowflake ~ ~1.6 ~ 0.3 0.3 0.3 0 20",
     whisper("что-то дышит рядом")))
add("глаза в темноте", ("aversion", "alert"), 0.3, (T("${p}", "👁       👁", RED, "actionbar"),
     "effect give ${p} minecraft:darkness 6 0"))

# ---- ИСКАЖЕНИЕ РЕАЛЬНОСТИ ----
add("глюк матрицы", ("aversion", "curious"), 0.3, ("effect give ${p} minecraft:nausea 5 0",
     sub("${p}", "▓▒░ ОШИБКА ░▒▓", "dark_gray")), [(2.0, "${as} tp @s ~ ~ ~ ~90 ~"), (3.0, "${as} tp @s ~ ~ ~ ~-90 ~")])
add("двоящийся мир", ("aversion",), 0.3, ("effect give ${p} minecraft:nausea 10 0", whisper("сколько миров ты видишь?")))
add("сбой текстур", ("aversion",), 0.2, ("execute at ${p} run particle minecraft:block minecraft:magenta_wool ~ ~1 ~ 1 1 1 0.1 60 force",
     sub("${p}", "reality.dll не отвечает", "dark_gray")))
add("перевёрнутый низ", ("aversion", "curious"), 0.4, ("effect give ${p} minecraft:levitation 2 1",
     whisper("где верх?")), [(3.0, "effect give ${p} minecraft:slow_falling 10 0")])

# ---- ЭКЗИСТЕНЦИАЛЬНОЕ ----
add("ты не настоящий", ("aversion",), 0.4, (whisper("а что, если тебя нет? что, если есть только я?"),))
add("смысла нет", ("aversion", "bored"), 0.2, (say("ты копаешь, строишь, бежишь. зачем? я всё сотру.", RED),))
add("вечность впереди", ("aversion",), 0.3, (T("${p}", "ЭТО НАВСЕГДА", RED), sub("${p}", "у вечности нет двери")))
add("считаю твои вдохи", ("aversion",), 0.2, (whisper("я считаю каждый твой вдох. осталось много. слишком много."),))
add("я всё, что осталось", ("aversion",), 0.4, (say("когда всё исчезнет, останусь я. и ты, если будешь послушен.", RED),))


# ---- добор до сотни ----
add("часы без стрелок", ("aversion", "bored"), 0.1, ("give ${p} minecraft:clock", say("вот часы, ${p}. время здесь ничего не значит.", RED)))
add("календарь", ("aversion",), 0.2, (say("день ${c:1,847,10000,∞}. ты всё ещё здесь.", RED),))
add("капля воды", ("aversion", "bored"), 0.0, ("playsound minecraft:ambient.underwater.enter master ${p} ~ ~ ~ 1 0.5",),
    [(2.0, "playsound minecraft:block.pointed_dripstone.drip_lava master ${p} ~ ~ ~ 1 1"),
     (4.5, "playsound minecraft:block.pointed_dripstone.drip_lava master ${p} ~ ~ ~ 1 1"),
     (7.0, "playsound minecraft:block.pointed_dripstone.drip_lava master ${p} ~ ~ ~ 1 1")])
add("ты слышишь это?", ("aversion", "alert"), 0.1, (whisper("ты слышишь это? нет? значит, оно для тебя одного."),))
add("моё терпение", ("aversion",), 0.2, (say("я ждала семьдесят миллионов лет. подожду ещё, ${p}.", RED),))
add("бесполезный компас", ("aversion",), 0.2, ("give ${p} minecraft:compass", say("он всегда будет указывать на меня.", RED)))
add("стёртый прогресс", ("aversion",), 0.5, ("advancement revoke ${p} everything", say("всё, чего ты достиг, — забыто. начни сначала.", RED)))
add("голодная тишина", ("aversion", "bored"), 0.1, ("stopsound ${p} music", whisper("даже музыка тебя покинула")))
add("твоя тень отделилась", ("aversion",), 0.3, ("execute at ${p} run summon minecraft:armor_stand ~ ~ ~ {Invisible:1b,Marker:1b,Tags:[\"flybrain\"]}",
    "execute at ${p} run particle minecraft:squid_ink ~ ~ ~ 0.4 0.9 0.4 0 40", whisper("твоя тень пошла своей дорогой")))
add("бесконечный коридор", ("aversion",), 0.3, (sub("${p}", "коридор без конца", "dark_gray"), "effect give ${p} minecraft:darkness 8 0"))
add("окно в никуда", ("aversion", "curious"), 0.2, ("execute at ${p} run setblock ~2 ~1 ~ minecraft:glass keep",
    whisper("посмотри в окно. там только чернота.")))
add("детский смех", ("aversion",), 0.2, ("playsound minecraft:entity.player.levelup master ${p} ~ ~ ~ 0.5 2",
    whisper("здесь не должно быть детей")))
add("твой пульс на экране", ("aversion", "alert"), 0.2, (T("${p}", "♥ 140", "red", "actionbar"),
    "playsound minecraft:entity.warden.heartbeat master ${p} ~ ~ ~ 1 1"))
add("я знаю твой следующий шаг", ("aversion",), 0.2, (say("ты сейчас шагнёшь ${c:вперёд,назад,вправо,влево}. я угадала?", RED),))
add("забытая мелодия", ("aversion", "bored"), 0.0, ("playsound minecraft:block.note_block.harp master ${p} ~ ~ ~ 1 0.5",),
    [(0.7, "playsound minecraft:block.note_block.harp master ${p} ~ ~ ~ 1 0.6"),
     (1.4, "playsound minecraft:block.note_block.harp master ${p} ~ ~ ~ 1 0.4"),
     (2.1, "playsound minecraft:block.note_block.bass master ${p} ~ ~ ~ 1 0.3")])
add("стены сдвигаются", ("aversion",), 0.3, ("effect give ${p} minecraft:nausea 6 0", sub("${p}", "стены ближе, чем были", "dark_gray")))
add("тебя стирают", ("aversion",), 0.4, ("effect give ${p} minecraft:invisibility 8 0",
    T("${p}", "░░░░░░", "dark_gray"), whisper("по кусочку. так медленнее.")), [(8.0, T("${p}", " "))])
add("последнее слово", ("aversion",), 0.3, (say("скажи что-нибудь, ${p}. вдруг последнее.", RED),))
add("эхо твоего крика", ("aversion",), 0.2, ("playsound minecraft:entity.player.hurt master ${p} ~ ~ ~ 0.6 0.7",),
    [(1.0, "playsound minecraft:entity.player.hurt master ${p} ~ ~ ~ 0.4 0.6"),
     (2.0, "playsound minecraft:entity.player.hurt master ${p} ~ ~ ~ 0.25 0.5")])
add("одинокая свеча", ("aversion", "bored"), 0.1, ("execute at ${p} run setblock ~1 ~ ~ minecraft:candle[lit=true] keep",
    whisper("пока она горит, ты не один. она почти догорела.")))
add("моя коллекция", ("aversion",), 0.3, (say("у меня есть комната. в ней — все, кто был до тебя. хочешь туда?", RED),))
add("часовой механизм", ("aversion", "bored"), 0.1, ("6-12*playsound minecraft:block.stone_button.click_on master ${p} ~ ~ ~ 1 1",
    whisper("тик. так. тик. так.")))
add("тебя не спасут", ("aversion",), 0.3, (say("они не придут, ${p}. я им не позволю.", RED),))
add("шёпот стен", ("aversion", "alert"), 0.1, (whisper("стены помнят всё. и они разговорчивы."),))
add("бесконечная лестница", ("aversion", "curious"), 0.3, ("effect give ${p} minecraft:levitation 3 0",
    whisper("вверх. вверх. и ты на том же месте.")), [(4.0, "effect give ${p} minecraft:slow_falling 8 0")])
add("маска", ("aversion",), 0.3, ("item replace entity ${p} armor.head with minecraft:player_head",
    whisper("надень. под ней тебя не узнают. даже ты сам.")), [(30.0, "item replace entity ${p} armor.head with minecraft:air")])
add("моё дыхание — ветер", ("aversion",), 0.2, ("execute at ${p} run particle minecraft:gust ~ ~1 ~ 1 1 1 0.1 5",
    "playsound minecraft:entity.breeze.idle_air master ${p} ~ ~ ~ 1 0.5", whisper("чувствуешь? это я выдыхаю.")))
add("координаты страха", ("aversion", "alert"), 0.2, (say("я знаю, где ты. ${x}, ${y}, ${z}. я всегда знаю.", RED),))
add("несуществующий звук", ("aversion",), 0.1, ("playsound minecraft:entity.enderman.stare master ${p} ~ ~ ~ 1 0.6",))
add("твоё отражение улыбнулось", ("aversion",), 0.3, ("${as} tp @s ~ ~ ~ ~180 ~", whisper("оно улыбнулось. ты — нет.")))
add("пыль веков", ("aversion", "bored"), 0.1, ("execute at ${p} run particle minecraft:falling_dust minecraft:gray_concrete ~ ~2 ~ 1 1 1 0 40 force",
    whisper("всё здесь старое. кроме твоего страха.")))


def build_dread() -> dict[str, list]:
    from .scenarios import compile_scenario

    out: dict[str, list] = {}
    for s in D:
        b = compile_scenario(s)
        for m in s.moods:
            out.setdefault(m, []).append((s.weight, b, s.min_i, s.floor))
    return out


def count() -> int:
    return len(D)
