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
    rng = random.Random(0)
    eye.set_look("bored", rng)
    eye.set_look("aversion", rng)
    assert any("spider_eye" in c for c in world.log)
    eye.set_look("asleep", rng)
    assert "0.50f" in world.log[-1] or "scale:[10.00f,0.50f" in world.log[-1]
