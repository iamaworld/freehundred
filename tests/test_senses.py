from flybrain.senses import LogTailer, Senses, parse_line


def stim(ev):
    return dict(ev.stimuli)


def test_chat_vanilla_and_paper_formats():
    for line in ("[12:00:01] [Server thread/INFO]: <Steve> привет", "[12:00:01 INFO]: <Steve> привет"):
        ev = parse_line(line)
        assert ev.kind == "chat" and ev.player == "Steve" and ev.text == "привет"
        assert "auditory" in stim(ev)


def test_chat_keywords():
    assert "sugar" in stim(parse_line("[12:00:01 INFO]: <Alex> держи торт"))
    rude = stim(parse_line("[12:00:01 INFO]: <Alex> тупая муха, где моя мухобойка"))
    assert "bitter" in rude and "looming" in rude and "touch" not in rude
    assert "touch" in stim(parse_line("[12:00:01 INFO]: <Alex> эй муха"))
    loud = stim(parse_line("[12:00:01 INFO]: <Alex> ЭЙ ТЫ!!!"))["auditory"]
    assert loud > stim(parse_line("[12:00:01 INFO]: <Alex> эй ты"))["auditory"]


def test_join_leave_advancement_death():
    assert parse_line("[12:00:01 INFO]: Notch joined the game").kind == "join"
    assert parse_line("[12:00:01 INFO]: Notch left the game").kind == "leave"
    adv = parse_line("[12:00:01 INFO]: Steve has made the advancement [Diamonds!]")
    assert adv.kind == "advancement" and adv.text == "Diamonds!" and "sugar" in stim(adv)
    boom = parse_line("[12:00:01 INFO]: Steve was blown up by Creeper")
    assert boom.kind == "death" and {"bitter", "auditory", "co2"} <= stim(boom).keys()
    fall = parse_line("[12:00:01 INFO]: Alex fell from a high place")
    assert "wind" in stim(fall)
    assert "heat" in stim(parse_line("[12:00:01 INFO]: Alex tried to swim in lava"))


def test_ignores_noise_and_own_rcon_echo():
    assert parse_line("[12:00:01 INFO]: Done (3.2s)! For help, type \"help\"") is None
    assert parse_line("[12:00:01 INFO]: [Rcon: Muha] Gave 3 [Cake] to Steve") is None
    assert parse_line("[12:00:01 INFO]: [Rcon] бзз") is None


def test_senses_accumulate_and_decay():
    s = Senses(half_life_s=1.0)
    s.add("sugar", 100)
    s.add("sugar", 150)
    assert s.rates()["sugar"] == 200  # потолок
    s.decay(1.0)
    assert abs(s.rates()["sugar"] - 100) < 1e-6
    s.decay(10.0)
    assert s.total() == 0


def test_log_tailer_reads_new_lines_and_survives_rotation(tmp_path):
    log = tmp_path / "latest.log"
    log.write_text("old line\n")
    t = LogTailer(log)
    assert t.poll() == []  # старое не читаем
    with open(log, "a") as f:
        f.write("one\ntwo\npart")
    assert t.poll() == ["one", "two"]
    with open(log, "a") as f:
        f.write("ial\n")
    assert t.poll() == ["partial"]
    log.unlink()
    log.write_text("fresh\n")  # ротация: новый файл
    assert t.poll() == ["fresh"]
