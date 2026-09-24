"""Геометрия монструозного глаза из block_display (чистая математика).

Все части стоят в одной точке (центр глаза) и отличаются только своей
трансформацией, поэтому одна команда ``tp ... facing entity <игрок>``
разворачивает весь глаз к игроку как единое тело. Локальная +Z — «вперёд»
(туда смотрит зрачок); FLIP разворачивает модель, если в игре окажется
наоборот.

Части (R — радиус глаза в блоках):
- склера: 4 повёрнутых куба из светлых «органических» блоков → округлый шар;
- радужка: два квадрата под 45° → восьмиугольный диск, цвет = настроение;
- зрачок: вертикальная щель, ширина = настроение (ненависть — ниточка);
- блик и 6 кровеносных сосудов на белке;
- два века из багровой плоти — моргают/щурятся/закрываются (интерполяция);
- 5 щупалец снизу, покачиваются.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Vec = tuple[float, float, float]
Quat = tuple[float, float, float, float]  # x, y, z, w (как в NBT Minecraft)

IDENTITY: Quat = (0.0, 0.0, 0.0, 1.0)

# радужка по настроению: (блок, ширина зрачка в долях R, раскрытие век)
MOOD_STYLE = {
    "feeding": ("lime_concrete", 0.30, 0.95),
    "escape": ("white_concrete", 0.75, 1.35),
    "grooming": ("light_blue_concrete", 0.25, 0.55),
    "aversion": ("red_concrete", 0.07, 1.0),
    "curious": ("purple_concrete", 0.45, 1.15),
    "alert": ("yellow_concrete", 0.12, 1.35),
    "bored": ("gray_concrete", 0.30, 0.40),
    "asleep": ("gray_concrete", 0.30, 0.0),
}


def axis_angle(axis: Vec, degrees: float) -> Quat:
    a = math.radians(degrees) / 2
    n = math.sqrt(sum(c * c for c in axis)) or 1.0
    s = math.sin(a)
    return (axis[0] / n * s, axis[1] / n * s, axis[2] / n * s, math.cos(a))


def rotate(q: Quat, v: Vec) -> Vec:
    x, y, z, w = q
    # v' = q v q*
    ix = w * v[0] + y * v[2] - z * v[1]
    iy = w * v[1] + z * v[0] - x * v[2]
    iz = w * v[2] + x * v[1] - y * v[0]
    iw = -x * v[0] - y * v[1] - z * v[2]
    return (ix * w + iw * -x + iy * -z - iz * -y,
            iy * w + iw * -y + iz * -x - ix * -z,
            iz * w + iw * -z + ix * -y - iy * -x)


@dataclass
class Part:
    role: str  # уникальный тег части: flyeye_<role>
    block: str
    translation: Vec
    scale: Vec
    rotation: Quat = IDENTITY
    glow: bool = False

    def transformation(self, flip: bool = False) -> str:
        t, q = self.translation, self.rotation
        if flip:  # разворот на 180° вокруг Y: (x, z) -> (-x, -z)
            t = (-t[0], t[1], -t[2])
            q = _mul(axis_angle((0, 1, 0), 180), q)
        f = lambda v: ",".join(f"{c:.3f}f" for c in v)  # noqa: E731
        return (f"{{left_rotation:[{f(q)}],right_rotation:[0f,0f,0f,1f],"
                f"translation:[{f(t)}],scale:[{f(self.scale)}]}}")


def _mul(a: Quat, b: Quat) -> Quat:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def centered(role: str, block: str, center: Vec, size: Vec, q: Quat = IDENTITY, glow: bool = False) -> Part:
    """Куб-модель блока [0,1]^3, отмасштабированный и повёрнутый вокруг своего центра."""
    half = rotate(q, (size[0] / 2, size[1] / 2, size[2] / 2))
    return Part(role, block, (center[0] - half[0], center[1] - half[1], center[2] - half[2]), size, q, glow)


def hanging(role: str, block: str, anchor: Vec, size: Vec, q: Quat = IDENTITY) -> Part:
    """Брусок, подвешенный за середину верхней грани (для качания щупалец)."""
    top = rotate(q, (size[0] / 2, size[1], size[2] / 2))
    return Part(role, block, (anchor[0] - top[0], anchor[1] - top[1], anchor[2] - top[2]), size, q)


def sclera(R: float) -> list[Part]:
    a = 1.64 * R
    return [
        centered("sclera0", "mushroom_stem", (0, 0, 0), (a, a, a)),
        centered("sclera1", "white_concrete", (0, 0, 0), (a, a, a), axis_angle((0, 0, 1), 45)),
        centered("sclera2", "mushroom_stem", (0, 0, -0.35 * R), (a, a, a), axis_angle((0, 1, 0), 45)),
        centered("sclera3", "white_concrete", (0, 0, -0.35 * R), (a, a, a), axis_angle((1, 0, 0), 45)),
    ]


FRONT = 0.82  # передняя грань склеры в долях R


def iris(R: float, block: str) -> list[Part]:
    d = 1.1 * R
    z = (FRONT + 0.01) * R
    return [centered("iris0", block, (0, 0, z), (d, d, 0.05), glow=True),
            centered("iris1", block, (0, 0, z), (d, d, 0.05), axis_angle((0, 0, 1), 45), glow=True)]


def pupil(R: float, width: float) -> Part:
    return centered("pupil", "black_concrete", (0, 0, (FRONT + 0.03) * R), (max(0.04, width) * R, 0.9 * R, 0.05))


def glint(R: float) -> Part:
    return centered("glint", "white_concrete", (-0.22 * R, 0.25 * R, (FRONT + 0.05) * R), (0.14 * R, 0.14 * R, 0.03),
                    glow=True)


def veins(R: float) -> list[Part]:
    out = []
    for i, deg in enumerate((20, 75, 140, 200, 255, 320)):
        th = math.radians(deg)
        c = (0.68 * R * math.cos(th), 0.68 * R * math.sin(th), (FRONT + 0.005) * R)
        out.append(centered(f"vein{i}", "redstone_block", c, (0.3 * R, 0.05 * R, 0.03), axis_angle((0, 0, 1), deg)))
    return out


def lids(R: float, openness: float) -> list[Part]:
    """openness: 0 — закрыт, 1 — обычно, до 1.4 — распахнут."""
    gap = 0.55 * R * max(0.0, min(1.45, openness))  # половина видимой щели
    top = 0.95 * R
    h = max(0.02, top - gap)
    z = (FRONT + 0.08) * R
    return [centered("lidu", "crimson_hyphae", (0, gap + h / 2, z), (1.8 * R, h, 0.2 * R)),
            centered("lidl", "crimson_hyphae", (0, -gap - h / 2, z), (1.8 * R, h, 0.2 * R))]


TENTACLES = [(-0.45, 0.1), (0.4, 0.25), (0.0, -0.35), (-0.25, -0.3), (0.3, -0.2)]  # (x, z) в долях R


def tentacles(R: float, sway: list[tuple[float, float]] | None = None) -> list[Part]:
    """sway: для каждого щупальца (угол вокруг X, угол вокруг Z) в градусах."""
    out = []
    for i, (x, z) in enumerate(TENTACLES):
        ax, az = sway[i] if sway else (0.0, 0.0)
        q = _mul(axis_angle((1, 0, 0), ax), axis_angle((0, 0, 1), az))
        length = (1.4 + 0.3 * (i % 3)) * R
        block = "crimson_hyphae" if i % 2 else "warped_hyphae"
        out.append(hanging(f"tent{i}", block, (x * R, -0.7 * R, z * R), (0.16 * R, length, 0.16 * R), q))
    return out


def build(R: float, mood: str = "bored") -> list[Part]:
    block, width, openness = MOOD_STYLE.get(mood, MOOD_STYLE["bored"])
    return sclera(R) + iris(R, block) + [pupil(R, width), glint(R)] + veins(R) + lids(R, openness) + tentacles(R)
