import io
import random

from flybrain import am
from flybrain.commands import Ctx, full_catalog
from flybrain.fakeworld import FakeWorld
from flybrain.memory import PlayerMemory
from flybrain.safety import safe_check


class Console:
    """Консоль-заглушка: отвечает на проверки игр как Minecraft."""

    def __init__(self):
        self.sent, self.items, self.score, self.pos = [], {}, {}, [0.0, 64.0, 0.0]

    def __call__(self, cmd):
        self.sent.append(cmd)
        if cmd.startswith("clear ") and cmd.endswith(" 0"):
            n = self.items.get(cmd.split()[2].split(":")[1], 0)
            return f"Found {n} matching item(s) on player Steve" if n else "No items were found on player Steve"
        if cmd.startswith("scoreboard players get"):
            obj = cmd.split()[-1]
            return f"Steve has {self.score[obj]} [{obj}]" if obj in self.score else f"Can't get value of {obj} for Steve; none is set"
        if cmd.startswith("data get entity Steve Pos"):
            return "Steve has the following entity data: [%sd, %sd, %sd]" % tuple(self.pos)
        if cmd.startswith("data get entity Steve Health"):
            return "Steve has the following entity data: 20.0f"
        return ""


def gm_with(clock):
    con = Console()
    results = []
    gm = am.GameMaster(con, random.Random(0), am.Voice(random.Random(0)), clock=lambda: clock[0])
    gm.on_result = lambda p, won: results.append(won)
    return gm, con, results


def spec(kind_key):
    return next(s for s in am.SPECS if s.key == kind_key)


def test_many_unique_events():
    st = am.stats()
    assert st["games"] >= 2000 and st["monologues"] > 10000 and st["transforms"] >= 20 and st["illusions"] >= 20


def test_fetch_game_won_and_tribute_taken():
    t = [0.0]
    gm, con, res = gm_with(t)
    gm.offer("Steve", 0.8, spec("diamond"), am.punishments()[0])
    gm.tick()
    assert res == []
    con.items["diamond"] = 5
    gm.tick()
    assert res == [True] and "clear Steve minecraft:diamond 3" in con.sent and not gm.games


def test_stat_game_counts_from_baseline():
    t = [0.0]
    gm, con, res = gm_with(t)
    s = spec("kill_zombie")
    obj = gm._objective(s)
    con.score[obj] = 10  # до игры уже 10 убийств — не считаются
    gm.offer("Steve", 0.8, s, am.punishments()[0])
    assert any(c.startswith(f"scoreboard objectives add {obj} minecraft.killed:minecraft.zombie") for c in con.sent)
    con.score[obj] = 13
    gm.tick()
    assert res == []
    con.score[obj] = 15
    gm.tick()
    assert res == [True]


def test_timeout_punishes():
    t = [0.0]
    gm, con, res = gm_with(t)
    gm.offer("Steve", 0.8, spec("iron_ingot"), am.punishments()[0])
    t[0] = 1000
    gm.tick()
    assert res == [False] and any("ПРОИГРЫШ" in c for c in con.sent)


def test_freeze_silence_say_die():
    t = [0.0]
    gm, con, res = gm_with(t)
    gm.offer("Steve", 0.5, spec("freeze_20"), am.punishments()[0])
    con.pos[0] = 5.0
    gm.tick()
    assert res == [False]  # пошевелился
    gm.offer("Steve", 0.5, spec("silence_30"), am.punishments()[0])
    t[0] = 100
    gm.tick()
    assert res[-1] is True  # промолчал до конца
    gm.offer("Steve", 0.5, spec("say_0"), am.punishments()[0])
    gm.on_chat("Steve", "ну ладно, AM — мой бог")
    assert res[-1] is True
    gm.offer("Steve", 0.5, spec("die"), am.punishments()[0])
    gm.on_death("Steve")
    assert res[-1] is True


def test_monologue_is_capitalised_and_varied():
    v = am.Voice(random.Random(1))
    lines = {v.monologue("Steve") for _ in range(50)}
    assert len(lines) > 40
    assert all(". " not in l or not any(l[i + 2].islower() for i in range(len(l) - 2) if l[i:i + 2] == ". ") for l in lines)


def test_am_scenarios_render_and_pass_filter():
    world = FakeWorld(["Steve", "Alex"], seed=0, event_rate=0.0)
    rng = random.Random(0)
    names = {e[1].__name__ for es in full_catalog().values() for e in es}
    from flybrain.scenarios import compile_scenario

    for s in am.TRANSFORMS + am.ILLUSIONS:
        assert "scenario:" + s.name in names, s.name
        a = compile_scenario(s)(Ctx(s.moods[0], 1.0, "Steve", ["Steve", "Alex"], rng, "am", world.command))
        for cmd in a.commands + [c for _, c in a.reverts]:
            assert "${" not in cmd and safe_check(cmd, "am") is None, (s.name, cmd)


def test_memory_meta_and_old_format(tmp_path):
    p = tmp_path / "m.json"
    p.write_text('{"Steve": -0.5}')  # старый формат
    m = PlayerMemory(p)
    assert m.get("Steve") == -0.5
    assert m.count("Steve", "visits") == 1 and m.count("Steve", "visits") == 2
    m.save()
    m2 = PlayerMemory(p)
    assert m2.get("Steve") == -0.5 and m2.counter("Steve", "visits") == 2


def test_controller_am_persona_greets_and_guards():
    from flybrain.brain import build_toy_brain
    from flybrain.controller import Config, FlyController
    from flybrain.neurons import MOODS, SENSES
    from flybrain.rcon import DryConsole

    console = DryConsole(players=["Steve"], out=io.StringIO(), events=False)
    ctl = FlyController(build_toy_brain(list(SENSES), list(MOODS)), {k: 20.0 for k in MOODS}, console,
                        config=Config(power="am"), rng=random.Random(0), out=io.StringIO())
    ctl.feel_line("[12:00:00 INFO]: Steve joined the game")
    assert any("[AM]" in c and "Steve" in c for c in console.sent)
    ctl.feel_line("[12:00:00 INFO]: Steve fell from a high place")
    assert ctl.memory.counter("Steve", "deaths") == 1
