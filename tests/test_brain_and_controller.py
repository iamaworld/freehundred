import io
import random

import pytest

from flybrain.neurons import MOODS, SENSES

pytest.importorskip("brian2")


@pytest.fixture(scope="module")
def toy():
    from flybrain.brain import build_toy_brain

    return build_toy_brain(list(SENSES), list(MOODS), seed=0)


def test_toy_brain_silent_without_input_and_responds_to_stimulus(toy):
    toy.reset()
    st = toy.step({}, 50)
    assert st.active == 0 and all(v == 0 for v in st.rates.values())
    st = toy.step({"sugar": 150}, 100)
    assert st.rates["feeding"] > 0  # в игрушке sugar -> feeding
    toy.reset()
    assert toy.step({}, 50).active == 0  # сон гасит всё


def test_controller_acts_through_filter_and_reverts(toy):
    from flybrain.controller import Config, FlyController
    from flybrain.rcon import DryConsole

    console = DryConsole(players=["Steve"], out=io.StringIO())
    cfg = Config(act_base=1.0, min_action_gap_s=0, max_actions_per_min=100, spontaneous_prob=0)
    ctl = FlyController(toy, {k: 20.0 for k in MOODS}, console, config=cfg, rng=random.Random(0), out=io.StringIO())
    ctl.feel_line("[12:00:00 INFO]: Steve has made the advancement [Diamonds!]")
    for _ in range(5):
        ctl.tick()
    sent = [c for c in console.sent if not c.startswith(("bossbar", "list", "time query"))]
    assert sent, "муха должна что-то сделать"
    assert any(c.startswith("bossbar add flybrain:mood") for c in console.sent)
    # все отправленные команды прошли фильтр
    from flybrain.safety import safe_check

    assert all(safe_check(c) is None for c in console.sent)


def test_controller_blocks_forbidden_command(toy):
    from flybrain.controller import FlyController
    from flybrain.rcon import DryConsole

    console = DryConsole(out=io.StringIO())
    out = io.StringIO()
    ctl = FlyController(toy, {k: 20.0 for k in MOODS}, console, out=out)
    assert ctl.send("stop") is None
    assert "stop" not in console.sent
    assert "ФИЛЬТР" in out.getvalue()


def test_am_mode_chants_hate_and_remembers_offender(toy, tmp_path):
    from flybrain.controller import Config, FlyController
    from flybrain.rcon import DryConsole

    console = DryConsole(players=["Steve"], out=io.StringIO(), events=False)
    cfg = Config(power="am", act_base=0.0, act_gain=0.0, spontaneous_prob=0, hate_chant_gap_s=0)
    ctl = FlyController(toy, {k: 20.0 for k in MOODS}, console, config=cfg, rng=random.Random(0),
                        out=io.StringIO(), memory_path=tmp_path / "m.json")
    for _ in range(4):
        ctl.feel_line("[12:00:00 INFO]: <Steve> тупая муха, где мухобойка")
        ctl.tick()
    assert ctl.memory.get("Steve") < 0
    if ctl.mood.name == "aversion":
        assert any("HATE HATE HATE" in c for c in console.sent)
        assert ctl.label(ctl.mood) == "НЕНАВИСТЬ"
    ctl.shutdown()
    assert (tmp_path / "m.json").exists()
