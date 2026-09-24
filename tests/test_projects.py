import io
import random
import re
from pathlib import Path

from flybrain import projects as pj
from flybrain.commands import Ctx
from flybrain.fakeworld import FakeWorld
from flybrain.safety import safe_check

FILL = re.compile(r"fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) ")


def ctx(players=("Steve", "Alex", "Notch"), intensity=1.0):
    world = FakeWorld(list(players), seed=0, event_rate=0.0)
    world.players["Steve"] = [100.0, 70.0, -50.0]
    return Ctx("aversion", intensity, "Steve", list(players), random.Random(0), "am", world.command)


def all_cmds(a):
    return a.commands + [c for s in a.steps for c in s] + [c for _, c in a.reverts]


def test_projects_respect_fill_limit_and_filter():
    for build in pj.PROJECTS + [pj.one_body, pj.hell_trip]:
        a = build(ctx())
        cmds = all_cmds(a)
        assert cmds, build.__name__
        for cmd in cmds:
            assert safe_check(cmd, "am") is None, (build.__name__, cmd)
            m = FILL.search(cmd)
            if m:
                assert pj._box(*map(int, m.groups())) <= pj.FILL_LIMIT, (build.__name__, cmd)


def test_slabs_cover_range_without_gaps():
    ys = []
    for (cmd,) in pj.slabs(0, 0, 40, 60, -6, "air"):
        x1, y1, z1, x2, y2, z2 = map(int, FILL.search(cmd).groups())
        ys += list(range(y1, y2 + 1))
    assert sorted(ys) == list(range(-6, 61))


def test_flatten_is_a_multi_step_project():
    a = pj.flatten(ctx())
    assert len(a.steps) > 3 and "fill" in a.steps[1][0] and "70" not in a.steps[1][0].split()[2]


def test_one_body_spectates_and_restores():
    a = pj.one_body(ctx())
    assert "gamemode spectator Alex" in a.commands and "spectate Steve Alex" in a.commands
    assert (45.0, "gamemode survival Alex") in a.reverts
    assert "двое" in pj.one_body(ctx(players=("Steve",))).commands[0]


def test_curses_exist_in_datapack():
    tick = Path("datapack/flybrain/data/flybrain/function/tick.mcfunction").read_text()
    for tag in pj.CURSES:
        assert f"tag={tag}]" in tick, tag
        a = pj.curse(tag)(ctx())
        assert f"tag Steve add {tag}" in a.commands and any(f"remove {tag}" in c for _, c in a.reverts)
    assert "$tp @s $(x) $(y) $(z)" in Path("datapack/flybrain/data/flybrain/function/reverse_tp.mcfunction").read_text()


def test_controller_runs_project_step_by_step():
    from flybrain.brain import build_toy_brain
    from flybrain.commands import Action
    from flybrain.controller import Config, FlyController
    from flybrain.neurons import MOODS, SENSES
    from flybrain.rcon import DryConsole

    console = DryConsole(players=["Steve"], out=io.StringIO(), events=False)
    ctl = FlyController(build_toy_brain(list(SENSES), list(MOODS)), {k: 20.0 for k in MOODS}, console,
                        config=Config(power="am", act_base=0, act_gain=0, bored_act_prob=0, spontaneous_prob=0),
                        rng=random.Random(0), out=io.StringIO())
    ctl.projects.append([["say шаг1"], ["say шаг2"], ["say шаг3"]])
    ctl.tick()
    assert "say шаг1" in console.sent and "say шаг2" not in console.sent
    ctl.tick()
    ctl.tick()
    assert "say шаг3" in console.sent and not ctl.projects
