#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a closed wavy water body OBJ for the water_pool scene."""

from __future__ import print_function

import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "models" / "water_surface.obj"


def height(x, z):
    return (
        0.04 * math.sin(2.4 * x + 0.8 * z)
        + 0.025 * math.sin(3.7 * z - 1.1 * x)
        + 0.015 * math.sin(5.1 * x + 4.2 * z)
    )


def main():
    # Pool water volume: x in [-1.6, 1.6], z in [-1.0, 1.0], bottom y=0.05, top ~0.55+wave
    x0, x1 = -1.55, 1.55
    z0, z1 = -0.95, 0.95
    y_bot = 0.08
    y_top = 0.52
    nx, nz = 48, 32

    verts = []
    faces = []

    def add_v(x, y, z):
        verts.append((x, y, z))
        return len(verts)  # 1-based later

    # Top grid (wavy), outward normal up → CCW when viewed from above
    top = [[0] * (nz + 1) for _ in range(nx + 1)]
    for i in range(nx + 1):
        for j in range(nz + 1):
            u = float(i) / nx
            v = float(j) / nz
            x = x0 + (x1 - x0) * u
            z = z0 + (z1 - z0) * v
            y = y_top + height(x, z)
            top[i][j] = add_v(x, y, z)

    for i in range(nx):
        for j in range(nz):
            a, b = top[i][j], top[i + 1][j]
            c, d = top[i + 1][j + 1], top[i][j + 1]
            faces.append((a, b, c))
            faces.append((a, c, d))

    # Bottom (outward down → CW from above = CCW from below)
    bot = [[0] * (nz + 1) for _ in range(nx + 1)]
    for i in range(nx + 1):
        for j in range(nz + 1):
            u = float(i) / nx
            v = float(j) / nz
            x = x0 + (x1 - x0) * u
            z = z0 + (z1 - z0) * v
            bot[i][j] = add_v(x, y_bot, z)

    for i in range(nx):
        for j in range(nz):
            a, b = bot[i][j], bot[i][j + 1]
            c, d = bot[i + 1][j + 1], bot[i + 1][j]
            faces.append((a, b, c))
            faces.append((a, c, d))

    # Side walls (outward)
    # -Z edge
    for i in range(nx):
        t0, t1 = top[i][0], top[i + 1][0]
        b0, b1 = bot[i][0], bot[i + 1][0]
        faces.append((b0, b1, t1))
        faces.append((b0, t1, t0))
    # +Z edge
    for i in range(nx):
        t0, t1 = top[i][nz], top[i + 1][nz]
        b0, b1 = bot[i][nz], bot[i + 1][nz]
        faces.append((b0, t0, t1))
        faces.append((b0, t1, b1))
    # -X edge
    for j in range(nz):
        t0, t1 = top[0][j], top[0][j + 1]
        b0, b1 = bot[0][j], bot[0][j + 1]
        faces.append((b0, t0, t1))
        faces.append((b0, t1, b1))
    # +X edge
    for j in range(nz):
        t0, t1 = top[nx][j], top[nx][j + 1]
        b0, b1 = bot[nx][j], bot[nx][j + 1]
        faces.append((b0, b1, t1))
        faces.append((b0, t1, t0))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        f.write("# Wavy closed water body for LumenCore water_pool\n")
        f.write("usemtl Water\n")
        for x, y, z in verts:
            f.write("v {:.6f} {:.6f} {:.6f}\n".format(x, y, z))
        for a, b, c in faces:
            f.write("f {} {} {}\n".format(a, b, c))
    print("Wrote {} ({} verts, {} tris)".format(OUT, len(verts), len(faces)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
