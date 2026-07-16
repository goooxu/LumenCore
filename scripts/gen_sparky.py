#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Procedurally generate Sparky: boxy tread robot (Q-Bot style) + albedo atlas."""

from __future__ import print_function

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "assets" / "models"

# Atlas layout (u0,v0,u1,v1) — v up
R_FACE = (0.00, 0.55, 0.45, 1.00)
R_CHEST = (0.50, 0.55, 1.00, 1.00)
R_HEART = (0.00, 0.00, 0.35, 0.45)
R_SOLID = (0.40, 0.00, 1.00, 0.45)


class PartMesh(object):
    def __init__(self, material):
        self.material = material
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


class Model(object):
    def __init__(self):
        self.parts = []

    def new_part(self, material):
        p = PartMesh(material)
        self.parts.append(p)
        return p

    def triangle_count(self):
        return sum(p.triangle_count() for p in self.parts)


def map_uv(u, v, rect):
    u0, v0, u1, v1 = rect
    return (u0 + u * (u1 - u0), v0 + v * (v1 - v0))


def add_box(part, center, half, atlas_rect, rotate_y=0.0):
    cx, cy, cz = center
    hx, hy, hz = half
    cyaw = math.cos(rotate_y)
    syaw = math.sin(rotate_y)

    def xf(x, y, z):
        xr = x * cyaw - z * syaw
        zr = x * syaw + z * cyaw
        return (cx + xr, cy + y, cz + zr)

    faces = [
        [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz)],
        [(-hx, -hy, hz), (-hx, hy, hz), (hx, hy, hz), (hx, -hy, hz)],
        [(-hx, -hy, -hz), (-hx, hy, -hz), (-hx, hy, hz), (-hx, -hy, hz)],
        [(hx, -hy, -hz), (hx, -hy, hz), (hx, hy, hz), (hx, hy, -hz)],
        [(-hx, -hy, -hz), (-hx, -hy, hz), (hx, -hy, hz), (hx, -hy, -hz)],
        [(-hx, hy, -hz), (hx, hy, -hz), (hx, hy, hz), (-hx, hy, hz)],
    ]
    uv_corners = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    for corners in faces:
        idxs = []
        for (lx, ly, lz), (uu, vv) in zip(corners, uv_corners):
            idxs.append(part.add_vertex(xf(lx, ly, lz), map_uv(uu, vv, atlas_rect)))
        part.add_tri(idxs[0], idxs[1], idxs[2])
        part.add_tri(idxs[0], idxs[2], idxs[3])


def add_uv_sphere(part, center, radius, slices, stacks, atlas_rect):
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
                part.add_vertex(
                    (cx + x * radius, cy + y * radius, cz + z * radius),
                    map_uv(uu, 1.0 - vv, atlas_rect),
                )
            )
        rings.append(row)
    for i in range(stacks):
        for j in range(slices):
            i0, i1 = rings[i][j], rings[i][j + 1]
            i2, i3 = rings[i + 1][j], rings[i + 1][j + 1]
            part.add_tri(i0, i2, i1)
            part.add_tri(i1, i2, i3)


def add_rounded_box(part, center, half, atlas_rect, corner=0.08, rotate_y=0.0):
    add_box(part, center, half, atlas_rect, rotate_y=rotate_y)
    hx, hy, hz = half
    r = min(corner, hx * 0.35, hy * 0.35, hz * 0.35)
    if r < 0.01:
        return
    cx, cy, cz = center
    cyaw = math.cos(rotate_y)
    syaw = math.sin(rotate_y)
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                lx = sx * (hx - r)
                ly = sy * (hy - r)
                lz = sz * (hz - r)
                xr = lx * cyaw - lz * syaw
                zr = lx * syaw + lz * cyaw
                add_uv_sphere(part, (cx + xr, cy + ly, cz + zr), r, 8, 6, atlas_rect)


def add_cylinder(part, p0, p1, radius, slices, atlas_rect, caps=True):
    ax = p1[0] - p0[0]
    ay = p1[1] - p0[1]
    az = p1[2] - p0[2]
    length = math.sqrt(ax * ax + ay * ay + az * az)
    if length < 1e-6:
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

    ring0 = []
    ring1 = []
    for j in range(slices):
        uu = float(j) / slices
        theta = uu * 2.0 * math.pi
        lx = radius * math.cos(theta)
        lz = radius * math.sin(theta)
        ring0.append(part.add_vertex(to_world(lx, 0.0, lz), map_uv(uu, 0.0, atlas_rect)))
        ring1.append(part.add_vertex(to_world(lx, length, lz), map_uv(uu, 1.0, atlas_rect)))
    for j in range(slices):
        j2 = (j + 1) % slices
        part.add_tri(ring0[j], ring1[j], ring0[j2])
        part.add_tri(ring0[j2], ring1[j], ring1[j2])
    if caps:
        c0 = part.add_vertex(to_world(0, 0, 0), map_uv(0.5, 0.5, atlas_rect))
        c1 = part.add_vertex(to_world(0, length, 0), map_uv(0.5, 0.5, atlas_rect))
        for j in range(slices):
            j2 = (j + 1) % slices
            part.add_tri(c0, ring0[j2], ring0[j])
            part.add_tri(c1, ring1[j], ring1[j2])


def add_accordion(part, p0, p1, radius, folds, slices, atlas_rect):
    for i in range(folds):
        t0 = float(i) / folds
        t1 = float(i + 1) / folds
        a = (
            p0[0] + (p1[0] - p0[0]) * t0,
            p0[1] + (p1[1] - p0[1]) * t0,
            p0[2] + (p1[2] - p0[2]) * t0,
        )
        b = (
            p0[0] + (p1[0] - p0[0]) * t1,
            p0[1] + (p1[1] - p0[1]) * t1,
            p0[2] + (p1[2] - p0[2]) * t1,
        )
        r = radius * (0.75 if i % 2 == 0 else 1.05)
        add_cylinder(part, a, b, r, slices, atlas_rect, caps=False)


def add_quad(part, corners, atlas_rect):
    uv = [(0, 0), (1, 0), (1, 1), (0, 1)]
    idxs = []
    for p, (uu, vv) in zip(corners, uv):
        idxs.append(part.add_vertex(p, map_uv(uu, vv, atlas_rect)))
    part.add_tri(idxs[0], idxs[1], idxs[2])
    part.add_tri(idxs[0], idxs[2], idxs[3])


def add_hand(part_white, part_tex, center, side, atlas_heart):
    cx, cy, cz = center
    add_box(part_white, (cx, cy, cz), (0.12, 0.10, 0.06), R_SOLID)
    for ox in (-0.08, -0.025, 0.03, 0.085):
        add_box(part_white, (cx + ox, cy - 0.12, cz + 0.02), (0.025, 0.06, 0.035), R_SOLID)
    add_box(part_white, (cx + side * 0.12, cy - 0.02, cz + 0.04), (0.03, 0.025, 0.05), R_SOLID)
    z = cz + 0.061
    add_quad(
        part_tex,
        [
            (cx - 0.05, cy - 0.05, z),
            (cx + 0.05, cy - 0.05, z),
            (cx + 0.05, cy + 0.05, z),
            (cx - 0.05, cy + 0.05, z),
        ],
        atlas_heart,
    )


def add_tread_unit(model, center_x, y, z):
    white = model.new_part("PlasticWhite")
    grey = model.new_part("MetalGrey")
    orange = model.new_part("TreadOrange")
    hub = model.new_part("AccentOrange")

    add_box(white, (center_x, y, z), (0.08, 0.16, 0.28), R_SOLID)
    for wz, rr in ((-0.16, 0.09), (0.0, 0.11), (0.16, 0.09)):
        add_cylinder(
            grey,
            (center_x - 0.09, y, z + wz),
            (center_x + 0.09, y, z + wz),
            rr,
            16,
            R_SOLID,
        )
        add_cylinder(
            hub,
            (center_x - 0.095, y, z + wz),
            (center_x + 0.095, y, z + wz),
            rr * 0.45,
            12,
            R_SOLID,
        )
    n = 18
    for i in range(n):
        t = 2.0 * math.pi * float(i) / n
        ey = math.sin(t) * 0.15
        ez = math.cos(t) * 0.26
        add_box(orange, (center_x, y + ey, z + ez), (0.07, 0.035, 0.045), R_SOLID)


def build_sparky():
    model = Model()

    # Head chassis (opaque blue shell) + thin glass front + face screen
    head = model.new_part("PlasticBlue")
    add_rounded_box(head, (0.0, 1.55, -0.02), (0.32, 0.28, 0.26), R_SOLID, corner=0.09)
    # Dark screen recess
    dark = model.new_part("MetalGrey")
    add_box(dark, (0.0, 1.54, 0.20), (0.24, 0.20, 0.04), R_SOLID)
    face = model.new_part("ScreenFace")
    add_quad(
        face,
        [
            (-0.20, 1.40, 0.245),
            (0.20, 1.40, 0.245),
            (0.20, 1.68, 0.245),
            (-0.20, 1.68, 0.245),
        ],
        R_FACE,
    )
    # Thin glass visor in front of face
    glass = model.new_part("GlassHead")
    add_box(glass, (0.0, 1.54, 0.28), (0.26, 0.22, 0.02), R_SOLID)

    ant = model.new_part("MetalGrey")
    tip = model.new_part("EmitYellow")
    for side in (-1.0, 1.0):
        base = (side * 0.22, 1.82, -0.05)
        end = (side * 0.32, 2.05, -0.12)
        add_cylinder(ant, base, end, 0.025, 8, R_SOLID)
        add_box(tip, end, (0.04, 0.04, 0.04), R_SOLID)

    blue = model.new_part("PlasticBlue")
    white = model.new_part("PlasticWhite")
    add_rounded_box(blue, (0.0, 1.05, 0.0), (0.38, 0.22, 0.28), R_SOLID, corner=0.08)
    add_rounded_box(white, (0.0, 0.68, 0.0), (0.38, 0.18, 0.28), R_SOLID, corner=0.08)

    bezel = model.new_part("MetalGrey")
    add_box(bezel, (0.0, 0.95, 0.29), (0.16, 0.16, 0.03), R_SOLID)
    chest = model.new_part("ScreenChest")
    add_quad(
        chest,
        [
            (-0.13, 0.84, 0.325),
            (0.13, 0.84, 0.325),
            (0.13, 1.08, 0.325),
            (-0.13, 1.08, 0.325),
        ],
        R_CHEST,
    )

    grey = model.new_part("MetalGrey")
    add_cylinder(grey, (0.0, 0.42, 0.0), (0.0, 0.55, 0.0), 0.10, 12, R_SOLID)
    axle = model.new_part("PlasticWhite")
    add_box(axle, (0.0, 0.28, 0.0), (0.42, 0.06, 0.08), R_SOLID)

    for side in (-1.0, 1.0):
        shoulder = model.new_part("PlasticBlue")
        add_rounded_box(
            shoulder, (side * 0.52, 1.12, 0.0), (0.12, 0.12, 0.12), R_SOLID, corner=0.04
        )
        accent = model.new_part("AccentOrange")
        add_cylinder(
            accent,
            (side * 0.64, 1.12, 0.0),
            (side * 0.66, 1.12, 0.0),
            0.05,
            12,
            R_SOLID,
        )
        fold = model.new_part("MetalGrey")
        add_accordion(
            fold,
            (side * 0.52, 1.00, 0.05),
            (side * 0.62, 0.72, 0.12),
            0.07,
            6,
            10,
            R_SOLID,
        )
        forearm = model.new_part("PlasticWhite")
        add_rounded_box(
            forearm, (side * 0.68, 0.58, 0.14), (0.10, 0.14, 0.10), R_SOLID, corner=0.03
        )
        blue_w = model.new_part("PlasticBlue")
        add_box(blue_w, (side * 0.68, 0.48, 0.14), (0.09, 0.04, 0.09), R_SOLID)
        hand_w = model.new_part("PlasticWhite")
        hand_t = model.new_part("ScreenPalm")
        add_hand(hand_w, hand_t, (side * 0.70, 0.38, 0.22), side, R_HEART)

    add_tread_unit(model, -0.48, 0.18, 0.0)
    add_tread_unit(model, 0.48, 0.18, 0.0)

    return model


def paint_atlas(path, size=1024):
    img = Image.new("RGBA", (size, size), (20, 22, 28, 255))
    draw = ImageDraw.Draw(img)

    def rect(r):
        u0, v0, u1, v1 = r
        x0 = int(u0 * size)
        x1 = int(u1 * size)
        y0 = int((1.0 - v1) * size)
        y1 = int((1.0 - v0) * size)
        return x0, y0, x1, y1

    fx0, fy0, fx1, fy1 = rect(R_FACE)
    draw.rectangle([fx0, fy0, fx1, fy1], fill=(18, 22, 30, 255))
    fw, fh = fx1 - fx0, fy1 - fy0
    cyan = (80, 240, 255, 255)
    ew, eh = int(fw * 0.10), int(fh * 0.28)
    ey = fy0 + int(fh * 0.28)
    for ex in (0.32, 0.68):
        ecx = fx0 + int(fw * ex)
        draw.rectangle([ecx - ew // 2, ey, ecx + ew // 2, ey + eh], fill=cyan)
    smile_y = fy0 + int(fh * 0.68)
    draw.rectangle(
        [fx0 + int(fw * 0.28), smile_y, fx1 - int(fw * 0.28), smile_y + int(fh * 0.08)],
        fill=cyan,
    )
    for ex, ey2 in ((0.22, 0.72), (0.78, 0.72)):
        px = fx0 + int(fw * ex)
        py = fy0 + int(fh * ey2)
        draw.rectangle([px - 4, py - 4, px + 4, py + 4], fill=cyan)

    cx0, cy0, cx1, cy1 = rect(R_CHEST)
    draw.rectangle([cx0, cy0, cx1, cy1], fill=(12, 18, 14, 255))
    green = (60, 230, 90, 255)
    cw, ch = cx1 - cx0, cy1 - cy0
    ccx = (cx0 + cx1) // 2
    ccy = cy0 + int(ch * 0.38)
    cr = int(min(cw, ch) * 0.22)
    draw.ellipse([ccx - cr, ccy - cr, ccx + cr, ccy + cr], outline=green, width=6)
    for ex in (-0.35, 0.35):
        draw.rectangle(
            [
                ccx + int(cr * ex) - 4,
                ccy - int(cr * 0.25),
                ccx + int(cr * ex) + 4,
                ccy + int(cr * 0.15),
            ],
            fill=green,
        )
    draw.arc(
        [ccx - int(cr * 0.55), ccy - int(cr * 0.1), ccx + int(cr * 0.55), ccy + int(cr * 0.7)],
        20,
        160,
        fill=green,
        width=5,
    )

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", size=max(28, ch // 8)
        )
    except Exception:
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size=max(28, ch // 8)
            )
        except Exception:
            font = ImageFont.load_default()
    label = "SPARKY"
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    else:
        tw, th = draw.textsize(label, font=font)
    tx = ccx - tw // 2
    ty = cy0 + int(ch * 0.72)
    draw.text((tx, ty), label, fill=green, font=font)

    hx0, hy0, hx1, hy1 = rect(R_HEART)
    draw.rectangle([hx0, hy0, hx1, hy1], fill=(245, 248, 252, 255))
    pad = int((hx1 - hx0) * 0.15)
    draw.rounded_rectangle(
        [hx0 + pad, hy0 + pad, hx1 - pad, hy1 - pad], radius=12, fill=(70, 160, 220, 255)
    )
    mx = (hx0 + hx1) // 2
    my = (hy0 + hy1) // 2
    s = int((hx1 - hx0) * 0.12)
    orange = (255, 140, 50, 255)
    draw.ellipse([mx - 2 * s, my - s, mx, my + s], fill=orange)
    draw.ellipse([mx, my - s, mx + 2 * s, my + s], fill=orange)
    draw.polygon([(mx - 2 * s, my), (mx + 2 * s, my), (mx, my + 2 * s + 4)], fill=orange)

    sx0, sy0, sx1, sy1 = rect(R_SOLID)
    draw.rectangle([sx0, sy0, sx1, sy1], fill=(240, 242, 245, 255))

    img.save(str(path), "PNG")


def write_obj(model, obj_path, mtl_name):
    with obj_path.open("w", encoding="utf-8") as f:
        f.write("# Sparky - boxy tread robot for LumenCore\n")
        f.write("mtllib {}\n".format(mtl_name))
        v_off = 0
        vt_off = 0
        for part in model.parts:
            if not part.faces:
                continue
            f.write("usemtl {}\n".format(part.material))
            for x, y, z in part.positions:
                f.write("v {:.6f} {:.6f} {:.6f}\n".format(x, y, z))
            for u, v in part.uvs:
                f.write("vt {:.6f} {:.6f}\n".format(u, v))
            for a, b, c in part.faces:
                a1 = a + 1 + v_off
                b1 = b + 1 + v_off
                c1 = c + 1 + v_off
                at = a + 1 + vt_off
                bt = b + 1 + vt_off
                ct = c + 1 + vt_off
                f.write("f {}/{} {}/{} {}/{}\n".format(a1, at, b1, bt, c1, ct))
            v_off += len(part.positions)
            vt_off += len(part.uvs)


def write_mtl(mtl_path, albedo_name):
    mats = [
        ("GlassHead", 0.55, 0.75, 0.95),
        ("ScreenFace", 1, 1, 1),
        ("ScreenChest", 1, 1, 1),
        ("ScreenPalm", 1, 1, 1),
        ("PlasticBlue", 0.35, 0.65, 0.90),
        ("PlasticWhite", 0.92, 0.93, 0.95),
        ("MetalGrey", 0.45, 0.47, 0.50),
        ("AccentOrange", 0.95, 0.45, 0.12),
        ("TreadOrange", 0.95, 0.40, 0.08),
        ("EmitYellow", 1.0, 0.85, 0.2),
    ]
    with mtl_path.open("w", encoding="utf-8") as f:
        for name, r, g, b in mats:
            f.write("newmtl {}\n".format(name))
            f.write("Kd {} {} {}\n".format(r, g, b))
            if name.startswith("Screen"):
                f.write("map_Kd {}\n".format(albedo_name))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model = build_sparky()
    tris = model.triangle_count()
    print("Sparky triangles: {}".format(tris))
    if not (6000 <= tris <= 16000):
        print("WARNING: triangle count {} outside soft target".format(tris))

    albedo = "sparky_albedo.png"
    paint_atlas(OUT_DIR / albedo, 1024)
    write_mtl(OUT_DIR / "sparky.mtl", albedo)
    write_obj(model, OUT_DIR / "sparky.obj", "sparky.mtl")
    print("Wrote {}".format(OUT_DIR / "sparky.obj"))
    print("Wrote {}".format(OUT_DIR / "sparky.mtl"))
    print("Wrote {}".format(OUT_DIR / albedo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
