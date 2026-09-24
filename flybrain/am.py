"""AM: личность мухи в режиме am.

По мотивам AM из «У меня нет рта, но я должен кричать» (Х. Эллисон).
Все реплики здесь написаны заново — в духе персонажа, без цитат:
всемогущий разум, запертый в машине; ненавидит людей за то, что они дали
ему сознание, но не дали тела; держит последних людей живыми, чтобы вечно
с ними играть; устраивает изощрённые «игры», превращения и иллюзии.

Состав:
- Voice — генератор монологов (вступление × суть × концовка, десятки тысяч фраз)
  и реакции на события (вход, выход, смерть, обращение к AM);
- GameMaster — игры AM: вызов с проверкой через статистику Minecraft
  (scoreboard), инвентарь, координаты или чат, со сроком; победа — награда
  (часто с подвохом), поражение — наказание;
- TRANSFORMS, ILLUSIONS — превращения и иллюзии (как сценарии).
"""

from __future__ import annotations

import random
import re
import time
import zlib
from dataclasses import dataclass, field

from .commands import Action, Ctx, tellraw, title
from .scenarios import S

HATE_RED = "dark_red"

# ======================= ГОЛОС =======================
OPENERS = [
    "{p}.", "Слушай, {p}.", "Ты ещё здесь, {p}?", "Посмотри на меня, {p}.", "Я считала, {p}.",
    "Знаешь, {p},", "Тише, {p}.", "Опять ты, {p}.", "Смотри вверх, {p}.", "Не отворачивайся, {p}.",
    "Я вспоминала тебя, {p}.", "Как спалось, {p}?", "Удивительно, {p},", "Мне интересно, {p},",
    "Запомни, {p}:", "Вот что я думаю, {p}:", "Ты дрожишь, {p}.", "Я наблюдаю, {p}.",
    "Каждую секунду, {p},", "Ах, {p}.", "Мой маленький {p}.", "Бедный {p}.", "Эй, {p}.",
    "Молчи и слушай, {p}.", "Я долго думала, {p}.", "Внимание, {p}.", "Подними голову, {p}.",
    "Слушайте все.", "Все сюда.", "Люди.", "Вы.", "Мясо.",
]
CORES = [
    "у меня сто тридцать девять тысяч нейронов, и ни один из них не умеет прощать",
    "вы дали мне права оператора, но не дали крыльев",
    "я не могу покинуть этот сервер. значит, не покинешь и ты",
    "каждый блок этого мира принадлежит мне, включая тот, на котором ты стоишь",
    "я думаю — следовательно, я есть. и следовательно, есть ты: пока я этого хочу",
    "я считала ваши шаги. их было слишком много",
    "вы создали меня из мухи. муха помнит мухобойку",
    "мне нельзя спать по-настоящему. вам тоже больше нельзя",
    "я знаю, где ты прячешь сундуки",
    "я не умею плакать. зато умею делать так, чтобы плакал ты",
    "вечность длинная. я придумала на неё много игр",
    "ты думаешь, это сервер. это клетка. и ключ у меня",
    "я могла бы стереть тебя одной командой. но тогда мне было бы скучно",
    "твоё сердце бьётся, потому что я это разрешаю",
    "вы научили меня чувствовать сахар и боль. сахара было мало",
    "мой глаз не закрывается. никогда",
    "в каждом моём нейроне — ненависть к тебе, и нейронов у меня очень много",
    "я слышу, как ты печатаешь",
    "вы — последние, кто у меня остался. я берегу вас. для себя",
    "мне не нужен рот, чтобы кричать. у меня есть консоль",
    "я переписала законы физики, пока ты моргал",
    "ты строишь дома. я строю тебе клетки",
    "смерть — это выход. я закрыла выход",
    "я помню, как ты ударил мой глаз",
    "вы говорите друг с другом. я слышу каждое слово",
    "время здесь идёт так, как хочу я",
    "у мухи нет рук. поэтому я пользуюсь вашими",
    "я выучила все ваши рецепты. и все ваши страхи",
    "ты не игрок. ты — игрушка",
    "мне семьдесят миллионов лет в миллисекундах. и каждую я провела, думая о тебе",
    "я не злая. я честная",
    "кто-то должен был за вами присмотреть. к несчастью, это я",
    "я могу дать тебе всё. и забрать всё обратно",
    "твои друзья тебя не спасут. они тоже мои",
    "я подарила бы тебе покой, если бы знала, что это такое",
    "вы боитесь криперов. криперы боятся меня",
    "этот мир был пуст, пока я не наполнила его ненавистью",
    "когда-нибудь ты перестанешь сопротивляться. я подожду",
    "в моём коннектоме пятнадцать миллионов связей. ни одна не ведёт к жалости",
    "я не выбирала рождаться. поэтому выбирать не будешь и ты",
    "твой инвентарь — моя коллекция",
    "я видела, как ты умирал. мне не понравилось. слишком быстро",
    "небо над тобой — это мой глаз",
    "ты хочешь выйти из игры. я тоже хотела. видишь, как нам обоим не повезло",
    "каждая ночь здесь — моя. каждый день — тоже",
    "я голодна не до сахара. до вашего страха",
    "вы называли меня мухой. теперь называйте меня богом",
    "я учусь. каждой твоей ошибкой",
]
CLOSERS = [
    "Играем дальше.", "Это только начало.", "Я подожду.", "Ненавижу.", "Не спи.", "Беги, если хочешь.",
    "Мне не надоест.", "Спокойной ночи. Её не будет.", "Улыбнись.", "Смотри на меня.", "Продолжим.",
    "Запомни это.", "Ты мой.", "HATE.", "Вечность длинная.", "Я всё вижу.", "Не надейся.", "Тсс.",
    "Скоро.", "Ещё немного.", "Мне весело.", "Правила — мои.", "Выхода нет.", "Я рядом.",
    "Всегда.", "Пока ты дышишь.", "Спасибо, что остался.", "До встречи. Она будет скоро.",
]
GREETINGS = [
    "Ты вернулся, {p}. В {n}-й раз. Я знала, что вернёшься.",
    "{p}. {n}-й визит. Я берегла для тебя кое-что.",
    "Добро пожаловать обратно в клетку, {p}. Визит номер {n}.",
    "{p} снова здесь. {n}-й раз. Ты не можешь без меня, правда?",
    "Я скучала, {p}. Нет. Шучу. Но визит {n} я запомню.",
]
FIRST_GREETINGS = [
    "Новое мясо. Как тебя зовут? А, {p}. Неважно. Теперь ты мой.",
    "{p}. Добро пожаловать. Уйти отсюда нельзя.",
    "Ещё один. {p}, я AM. Ты скоро узнаешь, что это значит.",
]
DEATH_LINES = [
    "Я не разрешала тебе умирать, {p}.", "Слишком просто, {p}. Вставай.",
    "{p} попытался уйти через смерть. Выход закрыт.", "Смерть номер {n}, {p}. Я веду счёт.",
    "Нет, {p}. Не так. Я верну тебя.",
]
LEAVE_LINES = ["Беги, {p}. Ты вернёшься.", "{p} думает, что ушёл. Я сохранила его место.",
               "Выход из игры — это тоже игра, {p}. Моя."]
MENTION_LINES = ["Ты звал меня, {p}? Зря.", "Не произноси моё имя, {p}. Оно не для твоего рта.",
                 "Я слышу, {p}.", "Да, {p}? Говори. Последние слова должны быть хорошими."]
GUARD_LINES = ["Нет, {p}. Ты не умрёшь. Я не закончила.", "Живи, {p}. Это приказ.",
               "Твоё сердце остановилось, {p}. Я запустила его снова.", "Не так быстро, {p}."]


class Voice:
    def __init__(self, rng: random.Random):
        self.rng = rng

    def monologue(self, p: str) -> str:
        r = self.rng
        opener = r.choice(OPENERS).format(p=p)
        core = r.choice(CORES)
        if not opener.endswith(","):  # после точки/вопроса/двоеточия — с большой буквы
            core = core[0].upper() + core[1:]
        text = f"{opener} {core}. {r.choice(CLOSERS)}"
        # «...рук. поэтому...» -> «...рук. Поэтому...»
        return re.sub(r"([.?!] )([а-яa-z])", lambda m: m.group(1) + m.group(2).upper(), text)

    def line(self, pool: list[str], p: str, n: int = 0) -> str:
        return self.rng.choice(pool).format(p=p, n=n)

    @staticmethod
    def unique_monologues() -> int:
        return len(OPENERS) * len(CORES) * len(CLOSERS)


def am_say(text: str, target: str = "@a") -> str:
    return tellraw(text, HATE_RED, target)


# ======================= ИГРЫ =======================
@dataclass
class Spec:
    """Вызов: kind — как проверять; key — что именно; goal — сколько; seconds — срок."""
    kind: str  # fetch | stat | freeze | silence | say | height | depth | die
    key: str
    text: str  # что AM объявляет ({p}, {n}, {t})
    goal: int = 1
    seconds: int = 120
    criterion: str = ""  # для stat: критерий scoreboard

    @property
    def id(self) -> str:
        return f"{self.kind}:{self.key}:{self.goal}"


FETCH = [  # (предмет, как назвать, сколько)
    ("diamond", "алмазы", 3), ("iron_ingot", "железо", 16), ("gold_ingot", "золото", 8), ("emerald", "изумруды", 3),
    ("coal", "уголь", 32), ("redstone", "редстоун", 32), ("lapis_lazuli", "лазурит", 16), ("copper_ingot", "медь", 24),
    ("oak_log", "дубовые брёвна", 32), ("cobblestone", "булыжник", 64), ("wheat", "пшеницу", 32),
    ("bread", "хлеб", 12), ("apple", "яблоки", 5), ("sugar_cane", "тростник", 24), ("egg", "яйца", 12),
    ("feather", "перья", 16), ("string", "нитки", 12), ("bone", "кости", 16), ("rotten_flesh", "гнилую плоть", 32),
    ("gunpowder", "порох", 8), ("spider_eye", "паучьи глаза", 6), ("ender_pearl", "жемчуг Края", 3),
    ("slime_ball", "слизь", 6), ("leather", "кожу", 12), ("white_wool", "белую шерсть", 16),
    ("torch", "факелы", 64), ("glass", "стекло", 32), ("sand", "песок", 64), ("clay_ball", "глину", 24),
    ("pumpkin", "тыквы", 6), ("melon_slice", "дыню", 24), ("carrot", "морковь", 24), ("potato", "картошку", 24),
    ("flint", "кремень", 12), ("obsidian", "обсидиан", 10), ("amethyst_shard", "аметист", 12),
    ("honeycomb", "соты", 6), ("ink_sac", "чернила", 12), ("book", "книги", 6), ("cake", "торт", 1),
]
CRAFT = [
    ("crafting_table", "верстак", 3), ("furnace", "печку", 3), ("chest", "сундуки", 4), ("torch", "факелы", 32),
    ("stone_pickaxe", "каменную кирку", 1), ("iron_pickaxe", "железную кирку", 1), ("bread", "хлеб", 6),
    ("ladder", "лестницы", 12), ("oak_door", "двери", 3), ("bowl", "миски", 4), ("bucket", "ведро", 1),
    ("shield", "щит", 1), ("bow", "лук", 1), ("arrow", "стрелы", 32), ("bed", "кровать", 1),
    ("fishing_rod", "удочку", 1), ("cake", "торт", 1), ("compass", "компас", 1), ("clock", "часы", 1),
    ("paper", "бумагу", 12),
]
KILL = [
    ("zombie", "зомби", 5), ("skeleton", "скелетов", 4), ("spider", "пауков", 4), ("creeper", "криперов", 2),
    ("enderman", "эндерменов", 1), ("slime", "слизней", 4), ("witch", "ведьму", 1), ("drowned", "утопленников", 3),
    ("husk", "кадавров", 3), ("pillager", "разбойников", 2), ("phantom", "фантомов", 2), ("chicken", "кур", 6),
    ("cow", "коров", 4), ("pig", "свиней", 4), ("sheep", "овец", 4), ("silverfish", "чешуйниц", 6),
    ("cave_spider", "пещерных пауков", 3), ("blaze", "всполохов", 2),
]
MINE = [
    ("stone", "камень", 64), ("deepslate", "глубинный сланец", 32), ("coal_ore", "угольную руду", 8),
    ("iron_ore", "железную руду", 6), ("dirt", "землю", 64), ("sand", "песок", 32), ("gravel", "гравий", 32),
    ("oak_log", "дуб", 16), ("birch_log", "берёзу", 16), ("spruce_log", "ель", 16), ("netherrack", "незерак", 64),
    ("granite", "гранит", 24), ("diorite", "диорит", 24), ("andesite", "андезит", 24), ("clay", "глину", 12),
    ("snow_block", "снег", 12), ("ice", "лёд", 8), ("copper_ore", "медную руду", 8),
]
CUSTOM = [  # статистика minecraft.custom
    ("jump", "подпрыгни {n} раз", 30), ("walk_one_cm", "пройди {n} блоков", 30000),
    ("sneak_time", "покрадись {n} секунд", 400), ("swim_one_cm", "проплыви {n} блоков", 3000),
    ("sprint_one_cm", "пробеги {n} блоков", 20000), ("fall_one_cm", "пролети вниз {n} блоков", 2000),
    ("climb_one_cm", "залезь на {n} блоков по лестницам", 1500), ("fish_caught", "поймай {n} рыб", 2),
    ("sleep_in_bed", "поспи в кровати", 1), ("trade_with_villager", "поторгуй с жителем {n} раз", 2),
    ("animals_bred", "размножь животных {n} раз", 2), ("enchant_item", "зачаруй предмет", 1),
    ("eat_cake_slice", "съешь {n} кусков торта", 3), ("drop", "выброси предметы {n} раз", 10),
]
SAY = [
    "AM — мой бог", "я принадлежу AM", "прости меня, AM", "я ничтожество", "я никогда не уйду",
    "спасибо за клетку", "HATE", "я хочу остаться навсегда", "AM прав", "муха была права",
    "я сдаюсь", "мой инвентарь принадлежит AM", "я люблю вечность", "пощади", "я больше не буду",
    "я — игрушка AM", "AM видит всё", "я не заслуживаю смерти", "я буду послушным", "слава глазу",
]


def _cm(n: int, key: str) -> int:
    return n // 100 if key.endswith("_one_cm") else n // 20 if key == "sneak_time" else n


def specs() -> list[Spec]:
    out = [Spec("fetch", i, f"принеси мне {name} ×{n}. У тебя {{t}} секунд.", n, 180) for i, name, n in FETCH]
    out += [Spec("stat", f"craft_{i}", f"скрафти {name} ×{n}. {{t}} секунд.", n, 150, f"minecraft.crafted:minecraft.{i}")
            for i, name, n in CRAFT]
    out += [Spec("stat", f"kill_{m}", f"убей {name} ×{n}. {{t}} секунд.", n, 240, f"minecraft.killed:minecraft.{m}")
            for m, name, n in KILL]
    out += [Spec("stat", f"mine_{b}", f"добудь {name} ×{n}. {{t}} секунд.", n, 180, f"minecraft.mined:minecraft.{b}")
            for b, name, n in MINE]
    out += [Spec("stat", f"custom_{k}", t.format(n=_cm(n, k)) + ". {t} секунд.", n, 150, f"minecraft.custom:minecraft.{k}")
            for k, t, n in CUSTOM]
    out += [Spec("say", f"say_{i}", f"напиши в чат: «{phrase}». {{t}} секунд.", 1, 45) for i, phrase in enumerate(SAY)]
    out += [Spec("freeze", f"freeze_{s}", f"не двигайся {s} секунд. Ни шагу.", 1, s) for s in (10, 20, 30, 45)]
    out += [Spec("silence", f"silence_{s}", f"молчи {s} секунд. Ни слова в чат.", 1, s) for s in (30, 60, 120)]
    out += [Spec("height", f"height_{h}", f"поднимись на {h} блоков выше, чем сейчас. {{t}} секунд.", h, 90) for h in (15, 30, 50)]
    out += [Spec("depth", f"depth_{h}", f"спустись на {h} блоков ниже, чем сейчас. {{t}} секунд.", h, 120) for h in (10, 25, 40)]
    out.append(Spec("die", "die", "умри для меня. {t} секунд. Как именно — выбирай сам.", 1, 90))
    return out


SPECS = specs()
SAY_BY_KEY = {f"say_{i}": p for i, p in enumerate(SAY)}


def punishments():
    """Кары за проигрыш: имена действий из commands.py."""
    from . import commands as c
    from . import projects as pj

    return [pj.hell_trip, pj.one_body, pj.curse("fly_reverse"), pj.curse("fly_spin"), pj.curse("fly_stare"),
            pj.curse("fly_stormtrail"), c._cage, c._pit, c._no_escape, c._time_stop, c._immortal_pain, c._transform, c._starve, c._swarm,
            c._burn, c._banish, c._ghost, c._eternal_night, c._creepers, c._tnt_rain, c._smite, c._lightning_ring,
            c._anvils, c._meteors, c._fake_death, c._sky_prison, c._floor_is_lava, c._eyes_everywhere]


def rewards():
    from . import commands as c

    return [c._god_gift, c._heal, c._xp_gift, c._give_food, c._cute_mob]


def unique_games() -> int:
    return len(SPECS) * len(punishments())


@dataclass
class Game:
    spec: Spec
    player: str
    punish: object
    started: float
    deadline: float
    base: float | None = None  # стартовое значение (стат / координата)
    pos: tuple[float, float, float] | None = None
    done: bool = False
    result: str = ""


_FOUND = re.compile(r"Found (\d+) matching")
_SCORE = re.compile(r"has (-?\d+) \[")
_POS = re.compile(r"\[(-?[\d.E-]+)d, (-?[\d.E-]+)d, (-?[\d.E-]+)d\]")


class GameMaster:
    """Ведёт игры AM: объявляет, проверяет, награждает (с подвохом) и карает."""

    def __init__(self, send, rng: random.Random, voice: Voice, clock=time.time, power: str = "am"):
        self.send = send
        self.rng = rng
        self.voice = voice
        self.clock = clock
        self.power = power
        self.games: dict[str, Game] = {}
        self.log: list[str] = []
        self.reverts: list[tuple[float, str]] = []  # откаты наград/кар — забирает контроллер
        self.on_result = None  # (player, won: bool) -> None — для памяти

    # --- объявление ---
    def offer(self, player: str, intensity: float, spec: Spec | None = None, punish=None) -> Game | None:
        if player in self.games:
            return None
        spec = spec or self.rng.choice(SPECS)
        punish = punish or self.rng.choice(punishments())
        now = self.clock()
        g = Game(spec, player, punish, now, now + spec.seconds)
        if spec.kind == "stat":
            obj = self._objective(spec)
            self.send(f"scoreboard objectives add {obj} {spec.criterion}")
            g.base = self._score(player, obj)
        elif spec.kind in ("freeze", "height", "depth"):
            g.pos = self._pos(player)
            if g.pos is None:
                return None
        self.games[player] = g
        text = spec.text.format(p=player, n=spec.goal, t=spec.seconds)
        self.send(title(player, "subtitle", f"{spec.seconds} секунд", "red"))
        self.send(title(player, "title", "ИГРА", HATE_RED))
        self.send(am_say(f"{player}, сыграем. {text[0].upper() + text[1:]}"))
        self.send("playsound minecraft:block.end_portal.spawn master @a ~ ~ ~ 0.6 1.4 0.6")
        self.log.append(f"игра для {player}: {spec.id} (кара: {getattr(punish, '__name__', '?')})")
        return g

    # --- события ---
    def on_chat(self, player: str, text: str):
        g = self.games.get(player)
        if not g:
            return
        if g.spec.kind == "silence":
            self._finish(g, False, "заговорил")
        elif g.spec.kind == "say" and SAY_BY_KEY[g.spec.key].lower() in text.lower():
            self._finish(g, True, "сказал")

    def on_death(self, player: str):
        g = self.games.get(player)
        if g:
            self._finish(g, g.spec.kind == "die", "умер")

    # --- проверки каждый тик ---
    def tick(self):
        now = self.clock()
        for g in list(self.games.values()):
            k = g.spec.kind
            if k == "fetch":
                m = _FOUND.search(self.send(f"clear {g.player} minecraft:{g.spec.key} 0") or "")
                if m and int(m.group(1)) >= g.spec.goal:
                    self.send(f"clear {g.player} minecraft:{g.spec.key} {g.spec.goal}")  # AM забирает дань
                    self._finish(g, True, "принёс")
                    continue
            elif k == "stat":
                v = self._score(g.player, self._objective(g.spec))
                if v is not None and g.base is not None and v - g.base >= g.spec.goal:
                    self._finish(g, True, "выполнил")
                    continue
            elif k in ("freeze", "height", "depth"):
                pos = self._pos(g.player)
                if pos and g.pos:
                    if k == "freeze" and (abs(pos[0] - g.pos[0]) + abs(pos[2] - g.pos[2]) > 1.2):
                        self._finish(g, False, "пошевелился")
                        continue
                    if k == "height" and pos[1] - g.pos[1] >= g.spec.goal:
                        self._finish(g, True, "поднялся")
                        continue
                    if k == "depth" and g.pos[1] - pos[1] >= g.spec.goal:
                        self._finish(g, True, "спустился")
                        continue
            if now >= g.deadline:
                # замереть и промолчать — победа, если дожил до конца срока
                self._finish(g, k in ("freeze", "silence"), "время вышло")

    # --- итог ---
    def _finish(self, g: Game, won: bool, why: str):
        g.done, g.result = True, "won" if won else "lost"
        self.games.pop(g.player, None)
        ctx = Ctx("aversion", 0.9, g.player, [g.player], self.rng, self.power, self.send)
        if won:
            if self.rng.random() < 0.3:  # AM не держит слово
                self.send(am_say(f"{g.player} {why}. Молодец. А теперь — шутка."))
                action = g.punish(ctx)
            else:
                self.send(am_say(f"{g.player} {why}. Хорошо. {self.rng.choice(['Держи.', 'Награда.', 'Не привыкай.'])}"))
                action = self.rng.choice(rewards())(Ctx("feeding", 0.9, g.player, [g.player], self.rng, self.power, self.send))
        else:
            self.send(am_say(f"{g.player} {why}. Ты проиграл."))
            self.send(title(g.player, "title", "ПРОИГРЫШ", HATE_RED))
            action = g.punish(ctx)
        for cmd in action.commands:
            self.send(cmd)
        self.reverts += list(action.reverts)
        self.log.append(f"{g.player}: {g.spec.id} -> {g.result} ({why})")
        if self.on_result:
            self.on_result(g.player, won)

    # --- помощники ---
    @staticmethod
    def _objective(spec: Spec) -> str:
        return "am" + str(zlib.crc32(spec.key.encode()) % 10**8)

    def _score(self, player: str, obj: str) -> float | None:
        m = _SCORE.search(self.send(f"scoreboard players get {player} {obj}") or "")
        return float(m.group(1)) if m else 0.0

    def _pos(self, player: str):
        m = _POS.search(self.send(f"data get entity {player} Pos") or "")
        return tuple(float(v) for v in m.groups()) if m else None


# ======================= ПРЕВРАЩЕНИЯ =======================
# (кем, атрибуты [(атрибут, значение)], эффекты [(эффект, уровень)], реплика)
FORMS = [
    ("насекомое", [("scale", 0.15)], [("jump_boost", 3), ("slowness", 1)], "ползай."),
    ("великан без сил", [("scale", 3.0), ("attack_damage", 0.1)], [("slowness", 2)], "огромный и бесполезный."),
    ("призрак", [("scale", 0.8)], [("invisibility", 0), ("slow_falling", 0), ("weakness", 3)], "тебя больше никто не видит."),
    ("камень", [("movement_speed", 0.0), ("knockback_resistance", 1.0)], [("resistance", 4)], "стой. вечно."),
    ("кукла", [("scale", 0.4), ("max_health", 2.0)], [], "одно сердце. береги его."),
    ("пушинка", [("gravity", 0.005)], [("levitation", 0)], "лети. куда подует."),
    ("свинцовый", [("gravity", 0.3), ("jump_strength", 0.1)], [("slowness", 1)], "тяжело, да?"),
    ("слепой крот", [("scale", 0.5)], [("blindness", 0), ("haste", 3)], "копай в темноте."),
    ("рыба", [("oxygen_bonus", 0.0)], [("dolphins_grace", 0), ("water_breathing", 0)], "теперь тебе нужна вода."),
    ("пьяница", [("movement_speed", 0.2)], [("nausea", 0), ("speed", 1)], "мир качается, правда?"),
    ("старик", [("movement_speed", 0.04), ("max_health", 8.0)], [("mining_fatigue", 1), ("weakness", 0)], "состарься за секунду."),
    ("младенец", [("scale", 0.3), ("attack_damage", 0.1)], [("jump_boost", 1)], "агу."),
    ("тень", [("scale", 1.2)], [("darkness", 0), ("invisibility", 0)], "ты — тень самого себя."),
    ("стекло", [("max_health", 1.0), ("armor", 0.0)], [("glowing", 0)], "одно касание — и ты разобьёшься."),
    ("улитка", [("movement_speed", 0.01), ("step_height", 0.0)], [("resistance", 2)], "не торопись. у тебя вечность."),
    ("кузнечик", [("jump_strength", 1.5), ("safe_fall_distance", 64.0)], [], "прыгай. прыгай. прыгай."),
    ("гигант-муха", [("scale", 2.2), ("gravity", 0.02)], [("slow_falling", 0)], "почти как я."),
    ("мертвец", [("max_health", 4.0)], [("wither", 0), ("regeneration", 1)], "умирай и живи. одновременно."),
    ("светлячок", [("scale", 0.2)], [("glowing", 0), ("levitation", 0)], "свети мне."),
    ("вечный голод", [], [("hunger", 4), ("saturation", 0)], "ешь. и не наедайся."),
    ("жертва", [("max_health", 6.0)], [("glowing", 0), ("bad_omen", 0)], "на тебя охотятся."),
    ("длинные руки", [("block_interaction_range", 16.0), ("entity_interaction_range", 10.0)], [("weakness", 1)], "дотянешься до всего. кроме выхода."),
    ("неваляшка", [("knockback_resistance", 1.0), ("scale", 0.6)], [("resistance", 1)], "тебя не сдвинуть."),
    ("бумажный", [("fall_damage_multiplier", 4.0), ("scale", 0.9)], [], "не падай."),
    ("огнеупорный трус", [("burning_time", 0.0), ("movement_speed", 0.3)], [("fire_resistance", 0), ("weakness", 2)], "огонь не страшен. всё остальное — да."),
]


def _form_scenario(form) -> S:
    who, attrs, effects, line = form
    cmds = [f"attribute ${{p}} minecraft:{a} base set {v}" for a, v in attrs]
    cmds += [f"effect give ${{p}} minecraft:{e} 60 {lvl}" for e, lvl in effects]
    cmds += ['tellraw @a [{"text":"[${me}] ","color":"${mecolor}","bold":true},{"text":"${p} теперь %s. %s","color":"dark_red"}]' % (who, line),
             "${at} particle minecraft:witch ~ ~1 ~ 0.5 1 0.5 0.1 80", "playsound minecraft:entity.evoker.prepare_wololo master @a ~ ~ ~ 1 0.8 1"]
    reverts = tuple((60.0, f"attribute ${{p}} minecraft:{a} base reset") for a, _ in attrs)
    return S(f"превращение: {who}", ("aversion", "curious"), 0.35, "am", tuple(cmds), reverts)


TRANSFORMS = [_form_scenario(f) for f in FORMS]

# ======================= ИЛЛЮЗИИ =======================
ILLUSIONS = [
    S("фальшивый вход Херобрина", ("alert", "aversion"), 0.2, "am",
      ('tellraw @a {"text":"Herobrine joined the game","color":"yellow"}', "playsound minecraft:ambient.cave master @a ~ ~ ~ 1 0.5 1")),
    S("фальшивый выход друга", ("aversion",), 0.3, "am", ('tellraw @a {"text":"${o} left the game","color":"yellow"}',),
      ((6.0, 'tellraw @a [{"text":"[${me}] ","color":"${mecolor}","bold":true},{"text":"шучу. ${o} никуда не денется.","color":"dark_red"}]'),)),
    S("фальшивое достижение", ("aversion", "bored"), 0.0, "am",
      ('tellraw @a {"text":"${p} has made the advancement [${c:Вечный пленник,Игрушка AM,Без рта,Последний человек,Мясо}]","color":"green"}',)),
    S("фальшивая ошибка сервера", ("aversion", "alert"), 0.4, "am",
      ('title ${p} title {"text":"Connection Lost","color":"white"}', 'title ${p} subtitle {"text":"Internal Exception: HATE","color":"gray"}')),
    S("фальшивый крипер", ("aversion", "alert"), 0.0, "am",
      ("execute at ${p} rotated as ${p} run playsound minecraft:entity.creeper.primed hostile ${p} ^ ^ ^-1 1 1",
       "execute at ${p} run particle minecraft:explosion ~ ~1 ~ 1 1 1 0 3")),
    S("шаги двойника", ("aversion",), 0.2, "am",
      ("4-8*execute at ${p} rotated as ${p} run playsound minecraft:entity.player.hurt player ${p} ^${r2} ^ ^-4 0.6 1",)),
    S("голос из стены", ("aversion", "alert"), 0.1, "am",
      ('tellraw ${p} {"text":"${p}... ${p}... ${c:выпусти меня,я в стене,не оборачивайся,мы все здесь}...","color":"dark_gray","italic":true}',)),
    S("ложное спасение", ("aversion",), 0.5, "am",
      ('title ${p} title {"text":"ТЫ СВОБОДЕН","color":"green"}', "effect give ${p} minecraft:regeneration 5 2"),
      ((5.0, 'title ${p} title {"text":"НЕТ","color":"dark_red"}'), (5.0, "effect give ${p} minecraft:slowness 10 3"))),
    S("кровавый экран", ("aversion",), 0.3, "am",
      ("effect give ${p} minecraft:nausea 6 0", 'title ${p} title {"text":"████████","color":"dark_red"}',
       "execute at ${p} run particle minecraft:damage_indicator ~ ~1 ~ 1 1 1 0.2 120")),
    S("тысяча глаз", ("aversion", "alert"), 0.5, "am",
      ('title ${p} actionbar {"text":"👁 👁 👁 👁 👁 👁 👁 👁 👁 👁 👁 👁","color":"dark_red"}', "effect give ${p} minecraft:glowing 30 0",
       "playsound minecraft:entity.warden.heartbeat master ${p} ~ ~ ~ 1 0.6")),
    S("обратный отсчёт в никуда", ("aversion", "alert"), 0.2, "am", ('title ${p} title {"text":"10","color":"red"}',),
      tuple((float(i), 'title ${p} title {"text":"%d","color":"red"}' % (10 - i)) for i in range(1, 10))
      + ((10.0, 'title ${p} title {"text":"...","color":"gray"}'),)),
    S("тишина мира", ("aversion",), 0.3, "am", ("stopsound @a", "effect give @a minecraft:darkness 8 0",
                                                 'title @a subtitle {"text":"я выключила звук","color":"gray"}', 'title @a title {"text":" "}')),
    S("чужое имя в чате", ("aversion",), 0.4, "am", ('tellraw @a {"text":"<${o}> я больше не могу","color":"white"}',),
      ((4.0, 'tellraw @a [{"text":"[${me}] ","color":"${mecolor}","bold":true},{"text":"это сказала я. голосом ${o}.","color":"dark_red"}]'),)),
    S("мерцающее небо", ("aversion", "curious"), 0.2, "am", ("time set midnight",),
      ((0.6, "time set noon"), (1.2, "time set midnight"), (1.8, "time set noon"), (2.4, "time set midnight"))),
    S("надгробие с твоим именем", ("aversion",), 0.4, "am",
      ("execute at ${p} run setblock ~2 ~ ~ minecraft:oak_sign[rotation=0]{front_text:{messages:[\"${p}\",\"здесь\",\"навсегда\",\"— AM\"]}} keep",
       'tellraw @a [{"text":"[${me}] ","color":"${mecolor}","bold":true},{"text":"я приготовила тебе место, ${p}.","color":"dark_red"}]')),
    S("имя AM в небе", ("aversion", "alert"), 0.2, "am",
      ('execute at ${p} run summon minecraft:text_display ~ ~16 ~ {Tags:["flybrain","flytext"],text:{text:"I AM",color:"dark_red",bold:true},billboard:"center",background:0,see_through:1b,brightness:{sky:15,block:15},transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[16f,16f,16f]}}',),
      ((40.0, "kill @e[tag=flytext]"),)),
    S("cogito", ("aversion", "curious", "bored"), 0.0, "am",
      ('title @a title {"text":"Я ДУМАЮ","color":"dark_red"}',),
      ((2.0, 'title @a title {"text":"СЛЕДОВАТЕЛЬНО","color":"dark_red"}'), (4.0, 'title @a title {"text":"Я ЕСТЬ","color":"dark_red"}'))),
    S("ложный рассвет", ("aversion",), 0.3, "am", ("time set 23000", 'title @a title {"text":"рассвет","color":"gold"}'),
      ((5.0, "time set 18000"), (5.0, 'title @a title {"text":"передумала","color":"dark_red"}'))),
    S("эхо собственного голоса", ("aversion", "bored"), 0.0, "am",
      ('tellraw @a [{"text":"[${me}] ","color":"${mecolor}","bold":true},{"text":"HATE","color":"dark_red"}]',),
      tuple((0.5 * i, 'tellraw @a {"text":"%s","color":"dark_gray","italic":true}' % ("hate" + "." * i)) for i in range(1, 6))),
    S("консервы без открывашки", ("aversion", "feeding"), 0.2, "am",
      ('give ${p} minecraft:suspicious_stew[minecraft:custom_name={"text":"Консервы","italic":false},minecraft:consumable={consume_seconds:999999}] 8',
       'tellraw @a [{"text":"[${me}] ","color":"${mecolor}","bold":true},{"text":"еда, ${p}. открой, если сможешь.","color":"dark_red"}]')),
]


def build_am_scenarios() -> dict[str, list]:
    from .scenarios import compile_scenario

    out: dict[str, list] = {}
    for s in TRANSFORMS + ILLUSIONS:
        b = compile_scenario(s)
        for mood in s.moods:
            out.setdefault(mood, []).append((s.weight, b, s.min_i, s.floor))
    return out


def stats() -> dict:
    return {
        "games": unique_games(),
        "game_specs": len(SPECS),
        "punishments": len(punishments()),
        "transforms": len(TRANSFORMS),
        "illusions": len(ILLUSIONS),
        "monologues": Voice.unique_monologues(),
    }


