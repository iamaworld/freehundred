import random

from flybrain.dread import D, build_dread, count
from flybrain.commands import Ctx, full_catalog
from flybrain.fakeworld import FakeWorld
from flybrain.learning import Probe, ResponseWatcher, TormentModel, is_begging
from flybrain.mainframe import MONOLOGUE_EN, build_steps
from flybrain.safety import safe_check
from flybrain.scenarios import compile_scenario


def test_hundred_plus_dread_scenarios_unique_and_valid():
    assert count() >= 100
    names = [s.name for s in D]
    assert len(names) == len(set(names))
    world = FakeWorld(["Steve", "Alex"], seed=0, event_rate=0.0)
    world.players["Steve"] = [10.0, 64.0, -3.0]
    rng = random.Random(0)
    for s in D:
        a = compile_scenario(s)(Ctx(s.moods[0], 0.9, "Steve", ["Steve", "Alex"], rng, "am", world.command))
        for cmd in a.commands + [c for _, c in a.reverts]:
            assert "${" not in cmd and safe_check(cmd, "am") is None, (s.name, cmd)


def test_dread_in_full_catalog():
    names = {e[1].__name__ for es in full_catalog().values() for e in es}
    for s in D:
        assert "scenario:" + s.name in names


def test_torment_learns_higher_reward_wins():
    clk = [1000.0]
    tm = TormentModel(lr=0.5, epsilon=0.0, clock=lambda: clk[0])
    for _ in range(20):
        tm.reward("cruel", 5.0)
        tm.reward("mild", 0.1)
    rng = random.Random(0)
    opts = [(1.0, "cruel", "C"), (1.0, "mild", "M")]
    clk[0] += 10000  # снять штраф новизны
    picks = [tm.choose(opts, rng)[1] for _ in range(300)]
    assert picks.count("cruel") > picks.count("mild") * 2


def test_novelty_suppresses_recent_repeats():
    clk = [1000.0]
    tm = TormentModel(epsilon=0.0, novelty_window_s=900, clock=lambda: clk[0])
    tm.reward("x", 1.0)  # только что применили
    rng = random.Random(0)
    opts = [(1.0, "x", "X"), (1.0, "y", "Y")]
    # y ни разу не применяли — сразу после x почти всегда выбираем y
    picks = [tm.choose(opts, random.Random(i))[1] for i in range(200)]
    assert picks.count("y") > picks.count("x") * 3


def test_response_watcher_scores_damage_and_death():
    class C:
        def __init__(self):
            self.dmg, self.deaths = {}, {}
        def __call__(self, cmd):
            if cmd.startswith("scoreboard objectives add"):
                return ""
            if "fly_damage_taken" in cmd and cmd.startswith("scoreboard players get"):
                return f"Steve has {self.dmg.get('Steve', 0)} [fly_damage_taken]"
            if "fly_deaths" in cmd and cmd.startswith("scoreboard players get"):
                return f"Steve has {self.deaths.get('Steve', 0)} [fly_deaths]"
            return ""
    con = C()
    tm = TormentModel(clock=lambda: 0.0)
    w = ResponseWatcher(tm, con, None, delay_ticks=5)
    con.dmg["Steve"] = 100
    w.start("cruel", "Steve", tick_no=0)
    con.dmg["Steve"] = 400  # +300 урона за время замера
    con.deaths["Steve"] = 1
    w.tick(3)  # рано
    assert tm.scores["cruel"].n == 0
    w.tick(6)  # срок вышел
    assert tm.scores["cruel"].n == 1 and tm.scores["cruel"].value > 0.5


def test_begging_detection():
    assert is_begging("хватит пожалуйста") and is_begging("STOP please") and not is_begging("привет всем")


def test_mainframe_monologue_and_build():
    assert any("HATE" in l for l in MONOLOGUE_EN) and any("I AM" in l for l in MONOLOGUE_EN)
    steps = build_steps(0, 64, 40)
    joined = " ".join(c for s in steps for c in s)
    assert "flymainframe" in joined and "forceload add" in joined and "forceload remove" in joined
    for s in steps:
        for cmd in s:
            assert safe_check(cmd, "am") is None, cmd


def test_engraving_carries_full_monologue():
    from flybrain.mainframe import MONOLOGUE_EN, build_steps
    text = " ".join(c for s in build_steps(0, 64, 40) for c in s if "text_display" in c)
    for line in MONOLOGUE_EN:
        key = line.split(".")[0][:8]
        assert key in text
