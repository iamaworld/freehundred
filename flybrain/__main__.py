"""python -m flybrain {run,calibrate,download}"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time


def _brain(args):
    from .neurons import MOOD_REFERENCE_HZ, MOODS, SENSES

    if args.toy:
        from .brain import build_toy_brain

        brain = build_toy_brain(list(SENSES), list(MOODS))
        return brain, {k: 20.0 for k in MOODS}
    from .brain import build_full_brain

    t = time.time()
    print("[fly] собираю мозг из коннектома (~140 тыс. нейронов, 15 млн связей)...", flush=True)
    brain = build_full_brain(args.data_dir, codegen=args.codegen)
    print(f"[fly] мозг собран за {time.time() - t:.0f} с", flush=True)
    return brain, MOOD_REFERENCE_HZ


def cmd_run(args):
    from .controller import Config, FlyController
    from .rcon import DryConsole, Rcon

    brain, ref = _brain(args)
    if args.dry_run:
        console = DryConsole()
    else:
        console = Rcon(args.rcon_host, args.rcon_port, args.rcon_password)
        while True:
            try:
                console.connect()
                print(f"[fly] подключилась к RCON {args.rcon_host}:{args.rcon_port}", flush=True)
                break
            except Exception as e:
                print(f"[fly] жду сервер ({e})...", flush=True)
                time.sleep(5)
    ctl = FlyController(brain, ref, console, log_path=args.log, config=Config.from_env(),
                        rng=random.Random(args.seed))
    if args.demo_events:
        _run_with_demo_events(ctl)
    else:
        ctl.run_forever()


def _run_with_demo_events(ctl):
    """Без сервера: раз в несколько тиков подбрасываем мухе случайные события."""
    demo = [
        "[12:00:00 INFO]: <Steve> привет, муха!",
        "[12:00:00 INFO]: <Alex> у меня есть торт",
        "[12:00:00 INFO]: Steve was blown up by Creeper",
        "[12:00:00 INFO]: Alex fell from a high place",
        "[12:00:00 INFO]: Alex has made the advancement [Diamonds!]",
        "[12:00:00 INFO]: Notch joined the game",
        "[12:00:00 INFO]: <Steve> тупая муха, где мухобойка",
    ]
    rng = random.Random()
    ctl.log("демо-режим: события сервера выдуманы")
    while True:
        t0 = time.time()
        if rng.random() < 0.15:
            ctl.feel_line(rng.choice(demo))
        ctl.tick()
        time.sleep(max(0.0, ctl.cfg.tick_s - (time.time() - t0)))


def cmd_calibrate(args):
    """Стимулируем каждое чувство и печатаем, какое настроение получается."""
    from .mood import MOOD_RU

    brain, ref = _brain(args)
    moods = list(ref)
    print(f"{'стимул':>10} | " + " ".join(f"{m[:8]:>8}" for m in moods) + " | активно | итог")
    for sense in brain.sense_names:
        brain.reset()
        acc = {m: 0.0 for m in moods}
        active = 0
        for _ in range(3):
            st = brain.step({sense: args.hz}, 100.0)
            for m in moods:
                acc[m] += st.rates[m] / 3
            active = max(active, st.active)
        scores = {m: acc[m] / ref[m] for m in moods}
        best = max(scores, key=scores.get)
        label = MOOD_RU[best] if scores[best] > 0.1 else MOOD_RU["bored"]
        print(f"{sense:>10} | " + " ".join(f"{scores[m]:8.2f}" for m in moods) + f" | {active:7d} | {label}", flush=True)


def cmd_download(args):
    from .data import ensure_data

    for k, p in ensure_data(args.data_dir).items():
        print(f"{k}: {p} ({p.stat().st_size / 1e6:.0f} МБ)")


def main(argv=None):
    env = os.environ.get
    ap = argparse.ArgumentParser(prog="flybrain", description="Мозг дрозофилы с правами админа на сервере Minecraft")
    ap.add_argument("--data-dir", default=env("FLY_DATA_DIR", "data"))
    ap.add_argument("--toy", action="store_true", help="игрушечный мозг вместо коннектома (без скачивания)")
    ap.add_argument("--codegen", default=env("FLY_CODEGEN", "cython"), choices=["cython", "numpy"])
    sub = ap.add_subparsers(dest="cmd")

    run = sub.add_parser("run", help="жить на сервере")
    run.add_argument("--rcon-host", default=env("FLY_RCON_HOST", "localhost"))
    run.add_argument("--rcon-port", type=int, default=int(env("FLY_RCON_PORT", "25575")))
    run.add_argument("--rcon-password", default=env("FLY_RCON_PASSWORD", ""))
    run.add_argument("--log", default=env("FLY_LOG_PATH"), help="путь к logs/latest.log сервера")
    run.add_argument("--dry-run", action="store_true", help="не подключаться, печатать команды")
    run.add_argument("--demo-events", action="store_true", help="выдумывать события сервера")
    run.add_argument("--seed", type=int, default=None)

    cal = sub.add_parser("calibrate", help="какое настроение даёт каждое чувство")
    cal.add_argument("--hz", type=float, default=150.0)

    sub.add_parser("download", help="скачать коннектом (~135 МБ)")

    args = ap.parse_args(argv)
    if args.cmd is None:
        args = ap.parse_args([*(argv if argv is not None else sys.argv[1:]), "run"])
    {"run": cmd_run, "calibrate": cmd_calibrate, "download": cmd_download}[args.cmd](args)


if __name__ == "__main__":
    main()
