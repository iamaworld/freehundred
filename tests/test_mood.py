from flybrain.mood import MoodEngine, SleepCycle


def test_mood_picks_strongest_normalised_group():
    m = MoodEngine({"feeding": 60, "escape": 80}, smoothing=0.0)
    mood = m.update({"feeding": 30, "escape": 70})
    assert mood.name == "escape" and 0 < mood.intensity < 1
    assert m.update({}).name == "bored"


def test_sleep_on_reverberation_and_wake_on_stimulus():
    s = SleepCycle(reverb_active=100, reverb_ticks=3, wake_drive_hz=200, min_sleep_ticks=5)
    assert not s.observe_awake(drive=0, active=500, night=False)
    assert not s.observe_awake(drive=0, active=500, night=False)
    assert s.observe_awake(drive=0, active=500, night=False)
    assert s.asleep
    assert not s.observe_asleep(drive=50, night=True)
    assert s.observe_asleep(drive=300, night=True)
    assert not s.asleep


def test_sleep_at_quiet_night_and_wake_in_morning():
    s = SleepCycle(night_quiet_ticks=2, min_sleep_ticks=2)
    s.observe_awake(0, 0, night=True)
    assert s.observe_awake(0, 0, night=True)
    assert not s.observe_asleep(0, night=True)
    assert not s.observe_asleep(0, night=True)
    assert s.observe_asleep(0, night=False)
