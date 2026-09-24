"""Какие нейроны — «органы чувств», а какие — «настроения».

Группы подобраны по отклику полной модели: каждый сенсорный вход
стимулировали 150 Гц и смотрели, какие нисходящие (DN) и моторные нейроны
загораются. Проверить заново: `python -m flybrain calibrate`.
"""

from __future__ import annotations

import numpy as np

from .data import Connectome

# Сенсорные входы: имя -> (колонка аннотации, значение)
SENSES: dict[str, tuple[str, str]] = {
    "sugar": ("cell_sub_class", "sugar/water"),  # вкус сладкого — награда
    "bitter": ("cell_sub_class", "bitter"),  # горечь — боль, обида
    "auditory": ("cell_sub_class", "auditory"),  # орган Джонстона: звук, чат
    "wind": ("cell_sub_class", "wind_gravity"),  # ветер и гравитация: падения
    "touch": ("cell_sub_class", "head bristle"),  # щетинки на голове: касания
    "looming": ("cell_type", "LPLC2"),  # что-то быстро приближается
    "pheromone": ("cell_type", "ORN_DA1"),  # феромон cVA: рядом другие мухи
    "co2": ("cell_type", "ORN_V"),  # CO2: опасность, дым, взрывы
    "heat": ("cell_class", "thermosensory"),
    "humidity": ("cell_class", "hygrosensory"),  # дождь
}

# MN9 — мотонейрон хоботка (Shiu et al.), в аннотациях без типа
MN9_ROOT_ID = 720575940660219265

# Настроения: имя -> типы нисходящих/моторных нейронов
MOODS: dict[str, list[str]] = {
    # хоботок и глотка: сладкое -> ест -> довольна и щедра
    "feeding": ["MN9", "CB0700", "CB0701", "DNg67", "DNge031", "DNge059"],
    # гигантское волокно и looming-DN: взлёт-побег -> паника
    "escape": ["DNp01", "DNp02", "DNp04", "DNp11", "DNp70", "DNp103"],
    # DN груминга головы -> чистит лапки, наводит порядок
    "grooming": ["DNg15", "DNg35", "DNg37", "DNg48", "DNg84", "DNg85"],
    # горечь + moonwalker (задний ход) -> отвращение, злость
    "aversion": ["DNpe007", "DNge067", "DNp42", "MDN"],
    # запаховое руление и ходьба -> любопытство, исследование
    "curious": ["DNb05", "DNa01", "DNa02", "DNp09", "DNp31", "DNp32"],
    # слух/ветер -> настороженность
    "alert": ["DNg29", "DNb06", "DNp12", "DNp18", "DNp40", "DNbe001"],
}

# Типичная частота группы (Гц) при сильном «своём» стимуле — для нормировки
MOOD_REFERENCE_HZ: dict[str, float] = {
    "feeding": 60.0,
    "escape": 80.0,
    "grooming": 120.0,
    "aversion": 25.0,
    "curious": 20.0,
    "alert": 35.0,
}


def resolve_senses(c: Connectome) -> dict[str, np.ndarray]:
    groups = {}
    for name, (column, value) in SENSES.items():
        idx = c.ann.index[c.ann[column] == value].to_numpy()
        if len(idx) == 0:
            raise ValueError(f"сенсорная группа {name!r} пуста ({column}={value!r})")
        groups[name] = idx
    return groups


def resolve_moods(c: Connectome) -> dict[str, np.ndarray]:
    groups = {}
    for mood, types in MOODS.items():
        idx = list(c.ann.index[c.ann.cell_type.isin(types)])
        if "MN9" in types and (mn9 := c.index_of(MN9_ROOT_ID)) is not None:
            idx.append(mn9)
        if not idx:
            raise ValueError(f"группа настроения {mood!r} пуста")
        groups[mood] = np.array(sorted(set(idx)))
    return groups
