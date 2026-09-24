"""Загрузка коннектома FlyWire (снимок v783) и аннотаций типов нейронов.

Источники:
- связи и список нейронов — модель Shiu et al. 2024 (Nature),
  https://github.com/philshiu/Drosophila_brain_model
- типы клеток — Schlegel et al. 2024 (Nature),
  https://github.com/flyconnectome/flywire_annotations
"""

from __future__ import annotations

import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

_SHIU = "https://raw.githubusercontent.com/philshiu/Drosophila_brain_model/main"
_ANN = "https://raw.githubusercontent.com/flyconnectome/flywire_annotations/main/supplemental_files"

DATA_FILES = {
    "completeness": ("Completeness_783.csv", f"{_SHIU}/Completeness_783.csv"),
    "connectivity": ("Connectivity_783.parquet", f"{_SHIU}/Connectivity_783.parquet"),
    "annotations": ("neuron_annotations.tsv", f"{_ANN}/Supplemental_file1_neuron_annotations.tsv"),
}

ANN_COLUMNS = ["root_id", "super_class", "cell_class", "cell_sub_class", "cell_type", "side"]
SENSORY_SUPER_CLASSES = ("sensory", "sensory_ascending")


def ensure_data(data_dir: str | Path) -> dict[str, Path]:
    """Скачивает недостающие файлы (~135 МБ) и возвращает пути к ним."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, (name, url) in DATA_FILES.items():
        path = data_dir / name
        if not path.exists():
            print(f"[data] качаю {name} ...", file=sys.stderr, flush=True)
            tmp = path.with_suffix(path.suffix + ".part")
            urllib.request.urlretrieve(url, tmp)
            tmp.rename(path)
        paths[key] = path
    return paths


@dataclass
class Connectome:
    n: int
    pre: np.ndarray  # индексы пресинаптических нейронов
    post: np.ndarray  # индексы постсинаптических нейронов
    weight: np.ndarray  # число синапсов со знаком (+ возбуждающий, - тормозной)
    root_ids: np.ndarray  # FlyWire ID по индексу нейрона
    ann: pd.DataFrame  # аннотации, индекс = индекс нейрона в модели

    def index_of(self, root_id: int) -> int | None:
        hits = np.flatnonzero(self.root_ids == root_id)
        return int(hits[0]) if len(hits) else None

    def sensory_mask(self) -> np.ndarray:
        mask = np.zeros(self.n, dtype=bool)
        mask[self.ann.index[self.ann.super_class.isin(SENSORY_SUPER_CLASSES)]] = True
        return mask


def load_connectome(data_dir: str | Path, prune_recurrent: bool = True) -> Connectome:
    paths = ensure_data(data_dir)
    comp = pd.read_csv(paths["completeness"], index_col=0)
    conn = pd.read_parquet(
        paths["connectivity"],
        columns=["Presynaptic_Index", "Postsynaptic_Index", "Excitatory x Connectivity"],
    )
    ann = pd.read_csv(paths["annotations"], sep="\t", usecols=ANN_COLUMNS, low_memory=False)
    ann = ann.drop_duplicates("root_id")
    ann["i"] = comp.index.get_indexer(ann.root_id)
    ann = ann[ann.i >= 0].set_index("i").sort_index()

    c = Connectome(
        n=len(comp),
        pre=conn["Presynaptic_Index"].to_numpy(np.int32),
        post=conn["Postsynaptic_Index"].to_numpy(np.int32),
        weight=conn["Excitatory x Connectivity"].to_numpy(np.int32),
        root_ids=comp.index.to_numpy(np.int64),
        ann=ann,
    )
    return prune(c) if prune_recurrent else c


def prune(c: Connectome) -> Connectome:
    """Убирает связи, которые в точечной LIF-модели дают вечный «припадок».

    - KC→KC: аксо-аксональные синапсы клеток Кеньона (~300 тыс. связей).
      В грибовидных телах они не разгоняют активность, а в модели
      замыкаются в кольцо и держат ~3000 клеток включёнными навсегда.
    - всё, что входит в сенсорные нейроны (ORN→ORN и т.п.): рецепторы
      должны отражать мир, а не друг друга.
    - возбуждающие химические выходы локальных нейронов антеннальной доли
      (eLN, напр. lLN1_bc): у мухи они работают в основном через
      электрические синапсы, а в модели кольцо eLN↔PN держит ~1000
      нейронов после любого запаха.
    """
    kc = np.zeros(c.n, dtype=bool)
    kc[c.ann.index[c.ann.cell_class == "Kenyon_Cell"]] = True
    eln = np.zeros(c.n, dtype=bool)
    eln[c.ann.index[c.ann.cell_class == "ALLN"]] = True
    drop = (kc[c.pre] & kc[c.post]) | c.sensory_mask()[c.post] | (eln[c.pre] & (c.weight > 0))
    keep = ~drop
    return Connectome(c.n, c.pre[keep], c.post[keep], c.weight[keep], c.root_ids, c.ann)
