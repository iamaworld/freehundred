import io
import random

from flybrain.body import FlyEye
from flybrain.fakeworld import FakeWorld
from flybrain.memory import PlayerMemory


def test_memory_learns_conditions_and_persists(tmp_path):
    path = tmp_path / "memory.json"
    m = PlayerMemory(path)
    for _ in range(5):
        m.learn("Alex", sugar_hz=200)
        m.learn("Steve", bitter_hz=200)
    assert m.get("Alex") > 0.3 > -0.3 > m.get("Steve")
    assert dict(m.conditioned("Alex"))["sugar"] > 0
    assert "bitter" in dict(m.conditioned("Steve"))
    rng = random.Random(0)
    enemies = [m.pick(["Alex", "Steve"], "enemy", rng) for _ in range(200)]
    assert enemies.count("Steve") > 150
    m.save()
    assert PlayerMemory(path).get("Alex") == m.get("Alex")


def test_eye_spawns_moves_and_feels_hits_and_food():
    world = FakeWorld(["Steve", "Alex"], seed=3, event_rate=0.0)
    eye = FlyEye(world.command)
    rng = random.Random(0)
    rep = eye.sense(["Steve", "Alex"])
    assert "пересоздаю" in rep.notes[0] and world.eye and world.hitbox
    eye.sense(["Steve", "Alex"])  # запоминает исходные таймстемпы
    eye.move("Steve", "curious", rng)
    # Alex бьёт глаз
    world.gametime += 20
    world.attack = ("Alex", world.gametime)
    rep = eye.sense(["Steve", "Alex"])
    assert ("Alex", 0.0, 250.0) in rep.learn and dict(rep.stimuli)["bitter"] > 0
    # Steve кормит сахаром с руки
    world.items["Steve"] = "sugar"
    world.gametime += 20
    world.interaction = ("Steve", world.gametime)
    rep = eye.sense(["Steve", "Alex"])
    assert ("Steve", 250.0, 0.0) in rep.learn and world.items["Steve"] is None
    # подбежал к глазу — looming
    eye.pos = (100.0, 70.0, 100.0)
    eye.sense(["Steve"])
    world.players["Steve"] = [96.0, 64.0, 100.0]
    rep = eye.sense(["Steve"])
    assert dict(rep.stimuli).get("looming", 0) > 0


def test_eye_look_changes_with_mood():
    world = FakeWorld(["Steve"], seed=1, event_rate=0.0)
    eye = FlyEye(world.command)
    eye.spawn("Steve")
    summons = [c for c in world.log if "summon minecraft:block_display" in c]
    assert len(summons) >= 20 and world.eye  # монстр из ~20 частей
    rng = random.Random(0)
    eye.set_look("bored", rng)
    eye.set_look("aversion", rng)
    assert any("flyeye_iris0" in c and "red_concrete" in c for c in world.log)  # радужка краснеет
    eye.set_look("asleep", rng)
    assert any("flyeye_lidu" in c for c in world.log[-12:])  # веки закрываются
    eye.move("Steve", "curious", rng)
    assert any("tp @e[tag=flyeyepart]" in c and "facing entity Steve eyes" in c for c in world.log)


def test_eye_model_geometry():
    from flybrain import eye_model as em

    parts = em.build(2.5, "aversion")
    roles = [p.role for p in parts]
    assert len(roles) == len(set(roles)) >= 20
    assert "red_concrete" in {p.block for p in parts}
    closed = em.lids(2.5, 0.0)
    assert closed[0].translation[1] <= 0.01 and closed[1].translation[1] + closed[1].scale[1] >= -0.01  # щель закрыта
