"""Мозг мухи: LIF-модель всего коннектома на Brian2.

Базовая модель — Shiu et al. 2024 (параметры те же). Для непрерывной
жизни (а не секундных опытов) добавлено две вещи:
- адаптация: нейрон, который часто стреляет, устаёт (w_a);
- глобальное торможение: если во всём мозге слишком много спайков,
  центральные нейроны притормаживаются (аналог APL и прочих больших
  тормозных нейронов, которых точечная модель не воспроизводит).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class BrainParams:
    v_0: float = -52.0  # мВ, потенциал покоя
    v_rst: float = -52.0  # мВ, сброс после спайка
    v_th: float = -45.0  # мВ, порог
    t_mbr: float = 20.0  # мс, мембранная постоянная
    tau: float = 5.0  # мс, затухание синаптического тока
    t_rfc: float = 2.2  # мс, рефрактерность
    t_dly: float = 1.8  # мс, синаптическая задержка
    w_syn: float = 0.275  # мВ на один синапс
    f_poi: float = 250.0  # вес пуассоновского входа в единицах w_syn
    # добавлено для «вечной» жизни
    adapt_b: float = 1.0  # мВ, прирост усталости за спайк
    adapt_tau: float = 200.0  # мс
    inh_k: float = 0.2  # мВ торможения на единицу превышения активности
    inh_a0: float = 1200.0  # порог глобальной активности (спайков в окне 20 мс)
    dt: float = 0.1  # мс, шаг интегрирования


@dataclass
class BrainState:
    rates: dict[str, float]  # средняя частота групп настроений, Гц
    active: int  # сколько нейронов выстрелило за шаг
    drive: float  # суммарный сенсорный вход, Гц
    extra: dict = field(default_factory=dict)


class Brain:
    def __init__(
        self,
        n: int,
        pre: np.ndarray,
        post: np.ndarray,
        weight: np.ndarray,
        senses: dict[str, np.ndarray],
        outputs: dict[str, np.ndarray],
        uninhibited: np.ndarray | None = None,
        params: BrainParams | None = None,
        codegen: str = "cython",
        seed: int | None = None,
    ):
        # импорт здесь: brian2 тяжёлый, а остальной пакет без него живёт
        import brian2 as b2
        from brian2 import Hz, NeuronGroup, PoissonGroup, Synapses, mV, ms

        self._b2 = b2
        p = self.params = params or BrainParams()
        b2.prefs.codegen.target = codegen
        b2.prefs.logging.console_log_level = "ERROR"
        b2.defaultclock.dt = p.dt * ms
        if seed is not None:
            b2.seed(seed)

        ns = {
            "v_0": p.v_0 * mV,
            "v_rst": p.v_rst * mV,
            "v_th": p.v_th * mV,
            "t_mbr": p.t_mbr * ms,
            "tau": p.tau * ms,
            "tau_a": p.adapt_tau * ms,
            "b_a": p.adapt_b * mV,
            "k_inh": p.inh_k * mV,
            "A0": p.inh_a0,
        }
        eqs = """
        dv/dt = (v_0 - v + g - w_a - inh_gain*k_inh*clip(A_glob - A0, 0, 1e9)) / t_mbr : volt (unless refractory)
        dg/dt = -g / tau : volt (unless refractory)
        dw_a/dt = -w_a / tau_a : volt
        A_glob : 1 (linked)
        inh_gain : 1
        awake : 1
        n_spk : integer
        """
        self.n = n
        neu = NeuronGroup(
            n,
            eqs,
            method="euler",
            threshold="v > v_th and awake > 0.5",
            reset="v = v_rst; g = 0*mV; w_a += b_a; n_spk += 1",
            refractory=p.t_rfc * ms,
            namespace=ns,
        )
        neu.v = p.v_0 * mV
        neu.inh_gain = 1.0
        neu.awake = 1.0
        if uninhibited is not None and len(uninhibited):
            neu.inh_gain[np.asarray(uninhibited)] = 0.0

        # «счётчик активности» всего мозга: каждый спайк +1, затухает за 20 мс
        pool = NeuronGroup(1, "dA/dt = -A / (20*ms) : 1", method="exact")
        neu.A_glob = b2.linked_var(pool, "A", index=np.zeros(n, dtype=int))
        to_pool = Synapses(neu, pool, on_pre="A_post += 1")
        to_pool.connect(i=np.arange(n), j=0)

        syn = Synapses(neu, neu, "w : volt", on_pre="g += w", delay=p.t_dly * ms)
        syn.connect(i=np.asarray(pre), j=np.asarray(post))
        syn.w = np.asarray(weight, dtype=float) * p.w_syn * mV

        # пуассоновские «рецепторы»: по одному на каждый сенсорный нейрон группы
        self.sense_names = list(senses)
        self._sense_slices = {}
        targets, start = [], 0
        for name in self.sense_names:
            idx = np.asarray(senses[name])
            self._sense_slices[name] = slice(start, start + len(idx))
            targets.append(idx)
            start += len(idx)
        targets = np.concatenate(targets) if targets else np.zeros(0, dtype=int)
        self._stim = PoissonGroup(max(len(targets), 1), rates=0 * Hz)
        stim_syn = Synapses(
            self._stim, neu, on_pre="v += w_in", namespace={"w_in": p.w_syn * p.f_poi * mV}
        )
        if len(targets):
            stim_syn.connect(i=np.arange(len(targets)), j=targets)

        self.outputs = {k: np.asarray(v) for k, v in outputs.items()}
        self._neu, self._pool = neu, pool
        self._net = b2.Network(neu, pool, to_pool, syn, self._stim, stim_syn)
        self._n_stim = len(targets)

    def step(self, stim_hz: dict[str, float], duration_ms: float = 100.0) -> BrainState:
        """Прогнать мозг `duration_ms` с заданной частотой на сенсорных группах."""
        from brian2 import Hz, ms

        rates = np.zeros(max(self._n_stim, 1))
        drive = 0.0
        for name, hz in stim_hz.items():
            sl = self._sense_slices.get(name)
            if sl is not None and hz > 0:
                rates[sl] = hz
                drive += hz
        self._stim.rates = rates * Hz
        self._neu.n_spk = 0
        self._net.run(duration_ms * ms, namespace={})

        spikes = np.asarray(self._neu.n_spk[:])
        per_s = 1000.0 / duration_ms
        out = {k: float(spikes[idx].mean() * per_s) if len(idx) else 0.0 for k, idx in self.outputs.items()}
        return BrainState(rates=out, active=int((spikes > 0).sum()), drive=drive)

    def reset(self):
        """Сон: гасим всю текущую активность (связи не трогаем)."""
        from brian2 import ms, mV

        p = self.params
        self._stim.rates = 0 * self._stim.rates
        # спайки, уже летящие по синапсам, не должны разжечь кольцо заново:
        # 5 мс никто не стреляет, очередь задержек пустеет
        self._neu.awake = 0.0
        self._neu.v = p.v_0 * mV
        self._neu.g = 0 * mV
        self._net.run(5 * ms, namespace={})
        self._neu.awake = 1.0
        self._neu.v = p.v_0 * mV
        self._neu.g = 0 * mV
        self._neu.w_a = 0 * mV
        self._pool.A = 0


def build_full_brain(data_dir, codegen: str = "cython", params: BrainParams | None = None) -> Brain:
    from .data import load_connectome
    from .neurons import resolve_moods, resolve_senses

    c = load_connectome(data_dir)
    return Brain(
        c.n,
        c.pre,
        c.post,
        c.weight,
        senses=resolve_senses(c),
        outputs=resolve_moods(c),
        uninhibited=np.flatnonzero(c.sensory_mask()),
        params=params,
        codegen=codegen,
    )


def build_toy_brain(senses: list[str], moods: list[str], seed: int = 0, codegen: str = "numpy") -> Brain:
    """Маленький игрушечный мозг без скачивания данных: каждый орган чувств
    ведёт (через слой интернейронов) в свою группу настроения, плюс шум связей.
    Для тестов и `--toy`."""
    rng = np.random.default_rng(seed)
    per = 10
    s_groups, m_groups, pre, post, w = {}, {}, [], [], []
    n = 0
    for k, sense in enumerate(senses):
        s = np.arange(n, n + per)
        h = np.arange(n + per, n + 2 * per)
        n += 2 * per
        s_groups[sense] = s
        mood = moods[k % len(moods)]
        if mood not in m_groups:
            m_groups[mood] = np.arange(n, n + per)
            n += per
        m = m_groups[mood]
        for a_, b_ in ((s, h), (h, m)):
            for i in a_:
                for j in rng.choice(b_, size=4, replace=False):
                    pre.append(i), post.append(j), w.append(30)
    # немного случайной перекрёстной связности
    for _ in range(n * 3):
        pre.append(int(rng.integers(n))), post.append(int(rng.integers(n))), w.append(int(rng.integers(-3, 4)))
    uninhibited = np.concatenate(list(s_groups.values()))
    params = BrainParams(inh_a0=1e6)
    return Brain(n, np.array(pre), np.array(post), np.array(w), s_groups, m_groups, uninhibited, params, codegen, seed)
