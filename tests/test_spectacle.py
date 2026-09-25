import random

from flybrain import spectacle as sp
from flybrain.commands import Ctx, full_catalog
from flybrain.fakeworld import FakeWorld
from flybrain.safety import safe_check
from flybrain.scenarios import compile_scenario


def test_spectacle_unique_and_valid():
    assert sp.count() >= 40
    names = [s.name for s in sp.S3]
    assert len(names) == len(set(names))
    world = FakeWorld(["Steve", "Alex"], seed=0, event_rate=0.0)
    world.players["Steve"] = [10.0, 64.0, -3.0]
    rng = random.Random(2)
    for s in sp.S3:
        a = compile_scenario(s)(Ctx(s.moods[0], 0.9, "Steve", ["Steve", "Alex"], rng, "am", world.command))
        for cmd in a.commands + [c for _, c in a.reverts]:
            assert "${" not in cmd and safe_check(cmd, "am") is None, (s.name, cmd)


def test_spectacle_in_catalog():
    names = {e[1].__name__ for es in full_catalog().values() for e in es}
    for s in sp.S3:
        assert "scenario:" + s.name in names


def test_spectacle_events_are_multi_step():
    # каждая сцена — не однострочник: несколько команд или отложенные шаги
    for s in sp.S3:
        assert len(s.cmds) + len(s.reverts) >= 2, s.name
