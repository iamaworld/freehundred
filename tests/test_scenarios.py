import random

from flybrain.commands import Ctx, full_catalog
from flybrain.fakeworld import FakeWorld
from flybrain.safety import safe_check
from flybrain.scenarios import SCENARIOS, S, compile_scenario


def test_many_unique_scenarios():
    names = [s.name for s in SCENARIOS]
    assert len(names) >= 120 and len(set(names)) == len(names)


def test_every_scenario_renders_and_passes_its_power():
    world = FakeWorld(["Steve", "Alex"], seed=0, event_rate=0.0)
    powers = {e[1].__name__: e[3] for es in full_catalog().values() for e in es}
    rng = random.Random(0)
    for s in SCENARIOS:
        b = compile_scenario(s)
        power = powers["scenario:" + s.name]
        for intensity in (0.0, 1.0):
            a = b(Ctx(s.moods[0], intensity, "Steve", ["Steve", "Alex"], rng, power, world.command))
            for cmd in a.commands + [c for _, c in a.reverts]:
                assert "${" not in cmd, (s.name, cmd)
                assert safe_check(cmd, power) is None, (s.name, power, cmd, safe_check(cmd, power))


def test_template_features():
    world = FakeWorld(["Steve"], seed=0, event_rate=0.0)
    world.players["Steve"] = [10.5, 64.0, -3.2]
    s = S("t", ("bored",), 0, "am", ("2-2*say ${p} ${c:a,b}", "fill ${x-2} ${y+1} ${z} ${x} ${y} ${z+1} air"),
          ((5.0, "tp ${p} ${x} ${y} ${z}"),))
    a = compile_scenario(s)(Ctx("bored", 1.0, "Steve", ["Steve"], random.Random(1), "am", world.command))
    assert len([c for c in a.commands if c.startswith("say Steve ")]) == 2
    assert "fill 8 65 -4 10 64 -3 air" in a.commands
    assert a.reverts == [(5.0, "tp Steve 10 64 -4")]
