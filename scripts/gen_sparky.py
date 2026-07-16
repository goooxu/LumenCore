#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Procedurally generate Sparky: cartoon robot OBJ + UV atlas albedo PNG."""

from __future__ import print_function

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "assets" / "models"

CREAM = (232, 226, 214, 255)
CYAN = (64, 196, 196, 255)
CYAN_DARK = (32, 140, 148, 255)
DARK = (48, 52, 58, 255)
PANEL = (210, 204, 192, 255)
GLOW = (120, 240, 255, 255)
GLOW_CORE = (220, 255, 255, 255)
ANTENNA = (80, 88, 96, 255)
CHEST = (40, 210, 200, 255)


class MeshBuilder(object):
    def __init__(self):
        self.positions = []
        self.uvs = []
        self.faces = []

    def add_vertex(self, p, uv):
        self.positions.append(p)
        self.uvs.append(uv)
        return len(self.positions) - 1

    def add_tri(self, a, b, c):
        self.faces.append((a, b, c))

    def triangle_count(self):
        return len(self.faces)


def map_uv(u, v, rect):
    u0, v0, u1, v1 = rect
    return (u0 + u * (u1 - u0), v0 + v * (v1 - v0))


def add_uv_sphere(mesh, center, radius, slices, stacks, atlas_rect):
    cx, cy, cz = center
    rings = []
    for i in range(stacks + 1):
        vv = float(i) / stacks
        phi = vv * math.pi
        row = []
        for j in range(slices + 1):
            uu = float(j) / slices
            theta = uu * 2.0 * math.pi
            x = math.sin(phi) * math.cos(theta)
            y = math.cos(phi)
            z = math.sin(phi) * math.sin(theta)
            row.append(
                mesh.add_vertex(
                    (cx + x * radius, cy + y * radius, cz + z * radius),
                    map_uv(uu, 1.0 - vv, atlas_rect),
                )
            )
        rings.append(row)
    for i in range(stacks):
        for j in range(slices):
            i0 = rings[i][j]
            i1 = rings[i][j + 1]
            i2 = rings[i + 1][j]
            i3 = rings[i + 1][j + 1]
            mesh.add_tri(i0, i2, i1)
            mesh.add_tri(i1, i2, i3)


def add_capsule(mesh, p0, p1, radius, slices, stacks_hem, stacks_cyl, atlas_rect):
    ax = p1[0] - p0[0]
    ay = p1[1] - p0[1]
    az = p1[2] - p0[2]
    length = math.sqrt(ax * ax + ay * ay + az * az)
    if length < 1e-6:
        add_uv_sphere(mesh, p0, radius, slices, stacks_hem * 2, atlas_rect)
        return
    ax, ay, az = ax / length, ay / length, az / length
    if abs(ay) < 0.9:
        bx, by, bz = 0.0, 1.0, 0.0
    else:
        bx, by, bz = 1.0, 0.0, 0.0
    rx = by * az - bz * ay
    ry = bz * ax - bx * az
    rz = bx * ay - by * ax
    rl = math.sqrt(rx * rx + ry * ry + rz * rz)
    rx, ry, rz = rx / rl, ry / rl, rz / rl
    fx = ay * rz - az * ry
    fy = az * rx - ax * rz
    fz = ax * ry - ay * rx

    def to_world(lx, ly, lz):
        return (
            p0[0] + rx * lx + ax * ly + fx * lz,
            p0[1] + ry * lx + ay * ly + fy * lz,
            p0[2] + rz * lx + az * ly + fz * lz,
        )

    total_h = length + 2.0 * radius
    rings = []
    rows = stacks_hem * 2 + stacks_cyl
    for i in range(rows + 1):
        t = float(i) / rows
        y_local = -radius + t * total_h
        if y_local < 0.0:
            phi = math.acos(max(-1.0, min(1.0, y_local / radius)))
            rr = radius * math.sin(phi)
            y_axis = y_local
        elif y_local > length:
            yy = y_local - length
            phi = math.acos(max(-1.0, min(1.0, yy / radius)))
            rr = radius * math.sin(phi)
            y_axis = length + yy
        else:
            rr = radius
            y_axis = y_local

        row = []
        for j in range(slices + 1):
            uu = float(j) / slices
            theta = uu * 2.0 * math.pi
            lx = rr * math.cos(theta)
            lz = rr * math.sin(theta)
            row.append(mesh.add_vertex(to_world(lx, y_axis, lz), map_uv(uu, 1.0 - t, atlas_rect)))
        rings.append(row)

    for i in range(rows):
        for j in range(slices):
            i0 = rings[i][j]
            i1 = rings[i][j + 1]
            i2 = rings[i + 1][j]
            i3 = rings[i + 1][j + 1]
            mesh.add_tri(i0, i2, i1)
            mesh.add_tri(i1, i2, i3)


def add_box(mesh, center, half, atlas_rect):
    cx, cy, cz = center
    hx, hy, hz = half
    faces = [
        (
            [
                (cx - hx, cy - hy, cz - hz),
                (cx + hx, cy - hy, cz - hz),
                (cx + hx, cy + hy, cz - hz),
                (cx - hx, cy + hy, cz - hz),
            ],
            (0.0, 0.0, 0.5, 0.5),
        ),
        (
            [
                (cx - hx, cy - hy, cz + hz),
                (cx - hx, cy + hy, cz + hz),
                (cx + hx, cy + hy, cz + hz),
                (cx + hx, cy - hy, cz + hz),
            ],
            (0.5, 0.0, 1.0, 0.5),
        ),
        (
            [
                (cx - hx, cy - hy, cz - hz),
                (cx - hx, cy + hy, cz - hz),
                (cx - hx, cy + hy, cz + hz),
                (cx - hx, cy - hy, cz + hz),
            ],
            (0.0, 0.5, 0.5, 1.0),
        ),
        (
            [
                (cx + hx, cy - hy, cz - hz),
                (cx + hx, cy - hy, cz + hz),
                (cx + hx, cy + hy, cz + hz),
                (cx + hx, cy + hy, cz - hz),
            ],
            (0.5, 0.5, 1.0, 1.0),
        ),
        (
            [
                (cx - hx, cy - hy, cz - hz),
                (cx - hx, cy - hy, cz + hz),
                (cx + hx, cy - hy, cz + hz),
                (cx + hx, cy - hy, cz - hz),
            ],
            (0.25, 0.25, 0.75, 0.75),
        ),
        (
            [
                (cx - hx, cy + hy, cz - hz),
                (cx + hx, cy + hy, cz - hz),
                (cx + hx, cy + hy, cz + hz),
                (cx - hx, cy + hy, cz + hz),
            ],
            (0.1, 0.1, 0.9, 0.9),
        ),
    ]
    uv_corners = [(0, 0), (1, 0), (1, 1), (0, 1)]
    for corners, local in faces:
        u0, v0, u1, v1 = local
        idxs = []
        for p, (lu, lv) in zip(corners, uv_corners):
            uu = u0 + lu * (u1 - u0)
            vv = v0 + lv * (v1 - v0)
            idxs.append(mesh.add_vertex(p, map_uv(uu, vv, atlas_rect)))
        mesh.add_tri(idxs[0], idxs[1], idxs[2])
        mesh.add_tri(idxs[0], idxs[2], idxs[3])


def paint_atlas(path, size=1024):
    img = Image.new("RGBA", (size, size), CREAM)
    draw = ImageDraw.Draw(img)

    def rect(r):
        u0, v0, u1, v1 = r
        x0 = int(u0 * size)
        x1 = int(u1 * size)
        y0 = int((1.0 - v1) * size)
        y1 = int((1.0 - v0) * size)
        return x0, y0, x1, y1

    head = (0.00, 0.50, 0.50, 1.00)
    body = (0.00, 0.00, 0.50, 0.50)
    limbs = (0.50, 0.50, 1.00, 1.00)
    accents = (0.50, 0.00, 1.00, 0.50)

    hx0, hy0, hx1, hy1 = rect(head)
    draw.rectangle([hx0, hy0, hx1, hy1], fill=CREAM)
    mx0 = hx0 + int((hx1 - hx0) * 0.22)
    mx1 = hx0 + int((hx1 - hx0) * 0.78)
    my0 = hy0 + int((hy1 - hy0) * 0.32)
    my1 = hy0 + int((hy1 - hy0) * 0.62)
    draw.rounded_rectangle([mx0, my0, mx1, my1], radius=28, fill=DARK)
    eye_y = (my0 + my1) // 2
    eye_r = int((hx1 - hx0) * 0.07)
    for ex in (0.38, 0.62):
        ecx = hx0 + int((hx1 - hx0) * ex)
        draw.ellipse([ecx - eye_r, eye_y - eye_r, ecx + eye_r, eye_y + eye_r], fill=GLOW)
        ir = int(eye_r * 0.45)
        draw.ellipse([ecx - ir, eye_y - ir, ecx + ir, eye_y + ir], fill=GLOW_CORE)
    draw.rectangle(
        [
            hx0 + int((hx1 - hx0) * 0.45),
            hy0 + 8,
            hx0 + int((hx1 - hx0) * 0.55),
            hy0 + int((hy1 - hy0) * 0.18),
        ],
        fill=CYAN,
    )

    bx0, by0, bx1, by1 = rect(body)
    draw.rectangle([bx0, by0, bx1, by1], fill=CREAM)
    band_y0 = by0 + int((by1 - by0) * 0.35)
    band_y1 = by0 + int((by1 - by0) * 0.62)
    draw.rectangle([bx0, band_y0, bx1, band_y1], fill=CYAN)
    draw.rectangle([bx0, band_y0, bx1, band_y0 + 6], fill=CYAN_DARK)
    draw.rectangle([bx0, band_y1 - 6, bx1, band_y1], fill=CYAN_DARK)
    cx = (bx0 + bx1) // 2
    cy = (band_y0 + band_y1) // 2
    cr = int((bx1 - bx0) * 0.08)
    draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=CHEST)
    draw.ellipse([cx - cr // 2, cy - cr // 2, cx + cr // 2, cy + cr // 2], fill=GLOW_CORE)
    for t in (0.2, 0.4, 0.6, 0.8):
        x = bx0 + int((bx1 - bx0) * t)
        draw.line([(x, by0 + 12), (x, by1 - 12)], fill=PANEL, width=2)

    lx0, ly0, lx1, ly1 = rect(limbs)
    draw.rectangle([lx0, ly0, lx1, ly1], fill=CREAM)
    for t in (0.25, 0.5, 0.75):
        y = ly0 + int((ly1 - ly0) * t)
        draw.rectangle([lx0, y - 10, lx1, y + 10], fill=DARK)
    for t in (0.33, 0.66):
        x = lx0 + int((lx1 - lx0) * t)
        draw.line([(x, ly0), (x, ly1)], fill=PANEL, width=3)

    ax0, ay0, ax1, ay1 = rect(accents)
    draw.rectangle([ax0, ay0, ax1, ay1], fill=DARK)
    stripe_h = max(1, (ay1 - ay0) // 8)
    for i in range(8):
        y0 = ay0 + i * stripe_h
        col = CYAN if i % 2 == 0 else ANTENNA
        draw.rectangle([ax0, y0, ax0 + (ax1 - ax0) // 2, y0 + stripe_h], fill=col)
    draw.ellipse(
        [ax0 + (ax1 - ax0) // 2 + 20, ay0 + 30, ax1 - 20, ay0 + (ay1 - ay0) // 2],
        fill=(36, 40, 46, 255),
    )
    draw.rounded_rectangle(
        [ax0 + (ax1 - ax0) // 2 + 30, ay0 + (ay1 - ay0) // 2 + 20, ax1 - 30, ay1 - 30],
        radius=16,
        fill=CYAN,
    )

    img.save(str(path), "PNG")


def build_sparky():
    mesh = MeshBuilder()
    R_HEAD = (0.00, 0.50, 0.50, 1.00)
    R_BODY = (0.00, 0.00, 0.50, 0.50)
    R_LIMB = (0.50, 0.50, 1.00, 1.00)
    R_ACC = (0.50, 0.00, 1.00, 0.50)

    add_capsule(mesh, (0.0, 0.55, 0.0), (0.0, 1.15, 0.0), 0.38, 32, 8, 12, R_BODY)
    add_uv_sphere(mesh, (0.0, 1.62, 0.0), 0.42, 36, 20, R_HEAD)
    add_box(mesh, (0.0, 0.95, 0.32), (0.22, 0.16, 0.04), R_ACC)

    for side in (-1.0, 1.0):
        shoulder = (side * 0.48, 1.15, 0.0)
        elbow = (side * 0.72, 0.85, 0.08)
        hand = (side * 0.78, 0.55, 0.12)
        add_capsule(mesh, shoulder, elbow, 0.11, 18, 5, 7, R_LIMB)
        add_capsule(mesh, elbow, hand, 0.10, 16, 4, 6, R_LIMB)
        add_uv_sphere(mesh, hand, 0.13, 14, 8, R_ACC)

    for side in (-1.0, 1.0):
        hip = (side * 0.18, 0.55, 0.02)
        knee = (side * 0.22, 0.28, 0.04)
        foot = (side * 0.24, 0.08, 0.06)
        add_capsule(mesh, hip, knee, 0.13, 18, 5, 7, R_LIMB)
        add_capsule(mesh, knee, foot, 0.12, 16, 4, 6, R_LIMB)
        add_uv_sphere(mesh, (foot[0], 0.07, foot[2] + 0.05), 0.14, 14, 8, R_ACC)

    add_capsule(mesh, (0.0, 1.98, 0.0), (0.0, 2.28, 0.0), 0.035, 12, 4, 6, R_ACC)
    add_uv_sphere(mesh, (0.0, 2.32, 0.0), 0.07, 12, 8, R_ACC)
    return mesh


def write_obj(mesh, obj_path, mtl_name):
    with obj_path.open("w", encoding="utf-8") as f:
        f.write("# Sparky - original cartoon robot for LumenCore\n")
        f.write("mtllib {}\n".format(mtl_name))
        f.write("usemtl Sparky\n")
        for x, y, z in mesh.positions:
            f.write("v {:.6f} {:.6f} {:.6f}\n".format(x, y, z))
        for u, v in mesh.uvs:
            f.write("vt {:.6f} {:.6f}\n".format(u, v))
        for a, b, c in mesh.faces:
            a1, b1, c1 = a + 1, b + 1, c + 1
            f.write("f {}/{} {}/{} {}/{}\n".format(a1, a1, b1, b1, c1, c1))


def write_mtl(mtl_path, albedo_name):
    with mtl_path.open("w", encoding="utf-8") as f:
        f.write("newmtl Sparky\n")
        f.write("Kd 1.0 1.0 1.0\n")
        f.write("map_Kd {}\n".format(albedo_name))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mesh = build_sparky()
    tris = mesh.triangle_count()
    print("Sparky triangles: {}".format(tris))
    if not (8000 <= tris <= 14000):
        print("WARNING: triangle count {} outside target 8k-12k".format(tris))

    albedo = "sparky_albedo.png"
    paint_atlas(OUT_DIR / albedo, 1024)
    write_mtl(OUT_DIR / "sparky.mtl", albedo)
    write_obj(mesh, OUT_DIR / "sparky.obj", "sparky.mtl")
    print("Wrote {}".format(OUT_DIR / "sparky.obj"))
    print("Wrote {}".format(OUT_DIR / "sparky.mtl"))
    print("Wrote {}".format(OUT_DIR / albedo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
