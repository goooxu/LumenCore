#!/usr/bin/env python3
"""Stone pool with wavy water (Beer-Lambert absorption) for LumenCore."""
from __future__ import print_function

import os
import subprocess
import sys
from pathlib import Path

import lumencore as lc


def resolve_asset(relative):
    candidates = []
    root = os.environ.get("LUMENCORE_ROOT")
    if root:
        candidates.append(str(Path(root) / relative))
    candidates.extend(
        [
            relative,
            str(Path("..") / relative),
            str(Path("../..") / relative),
            str(Path("/work") / relative),
        ]
    )
    for path in candidates:
        if Path(path).is_file():
            return path
    return candidates[0]


def ensure_water_obj():
    path = resolve_asset("assets/models/water_surface.obj")
    if Path(path).is_file():
        return path
    # Generate next to repo if missing
    script = resolve_asset("scripts/gen_water_surface.py")
    if Path(script).is_file():
        subprocess.check_call([sys.executable, script])
    return resolve_asset("assets/models/water_surface.obj")


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "water_pool.png"
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    denoise = (int(sys.argv[3]) != 0) if len(sys.argv) > 3 else True

    scene = lc.Scene()

    stone = scene.add_material(lc.Material(base_color=(0.42, 0.40, 0.38), roughness=0.88))
    stone_dark = scene.add_material(lc.Material(base_color=(0.28, 0.27, 0.26), roughness=0.9))
    wood = scene.add_material(lc.Material(base_color=(0.45, 0.28, 0.14), roughness=0.75))
    water = scene.add_material(
        lc.Material(
            base_color=(0.6, 0.85, 0.9),
            roughness=0.0,
            transmission=1.0,
            ior=1.33,
            absorption=(0.35, 0.12, 0.08),
        )
    )
    tile = scene.add_material(lc.Material(base_color=(0.55, 0.62, 0.58), roughness=0.55))
    coral = scene.add_material(lc.Material(base_color=(0.85, 0.25, 0.22), roughness=0.45))
    chrome = scene.add_material(
        lc.Material(base_color=(0.95, 0.95, 0.98), metallic=1.0, roughness=0.05)
    )
    sand = scene.add_material(lc.Material(base_color=(0.72, 0.65, 0.48), roughness=0.95))

    # Outer ground
    scene.add_mesh(lc.make_quad((-6, 0, -6), (12, 0, 0), (0, 0, 12), sand))

    # Cutaway pool: omit +Z wall so the camera sees into the water.
    scene.add_mesh(lc.make_box((-1.85, 0.0, -1.25), (1.85, 0.08, 1.05), tile))  # pool floor
    scene.add_mesh(lc.make_box((-1.85, 0.08, -1.25), (1.85, 0.72, -0.95), stone))  # -Z
    scene.add_mesh(lc.make_box((-1.85, 0.08, -0.95), (-1.55, 0.72, 0.95), stone))  # -X
    scene.add_mesh(lc.make_box((1.55, 0.08, -0.95), (1.85, 0.72, 0.95), stone))  # +X
    # Coping on three sides
    scene.add_mesh(lc.make_box((-2.05, 0.72, -1.45), (2.05, 0.82, -0.95), stone_dark))
    scene.add_mesh(lc.make_box((-2.05, 0.72, -0.95), (-1.55, 0.82, 1.05), stone_dark))
    scene.add_mesh(lc.make_box((1.55, 0.72, -0.95), (2.05, 0.82, 1.05), stone_dark))
    # Deck behind pool
    scene.add_mesh(lc.make_box((-2.4, 0.82, -2.5), (2.4, 0.90, -1.45), wood))

    water_path = ensure_water_obj()
    water_mesh = lc.load_obj(water_path, {"Water": water}, water)
    scene.add_mesh(water_mesh)
    print("Loaded {}".format(water_path))

    # Underwater props (inside water volume)
    scene.add_mesh(lc.make_uv_sphere((-0.55, 0.28, 0.15), 0.22, coral))
    scene.add_mesh(lc.make_uv_sphere((0.65, 0.32, -0.25), 0.26, chrome))
    scene.add_mesh(lc.make_box((-0.15, 0.08, 0.35), (0.25, 0.22, 0.65), stone_dark))

    light_corner = (2.5, 5.5, -1.5)
    light_u = (2.0, 0.0, 0.4)
    light_v = (0.0, 0.0, 2.0)
    light_mat = scene.add_material(
        lc.Material(base_color=(0, 0, 0), roughness=1.0, emission=(28, 26, 22))
    )
    scene.add_mesh(lc.make_quad(light_corner, light_u, light_v, light_mat))
    scene.add_quad_light(light_corner, light_u, light_v, (28, 26, 22))

    scene.background_top = (0.40, 0.58, 0.85)
    scene.background_bottom = (0.55, 0.62, 0.70)

    camera = lc.Camera(
        eye=(-2.4, 1.65, 3.6),
        lookat=(0.05, 0.30, 0.0),
        fov_y_deg=42,
        aspect=16 / 9,
        aperture=0.012,
        focus_dist=4.3,
    )
    cfg = lc.RenderConfig(width=2560, height=1440, spp=spp, denoise=denoise, output_path=out)
    lc.Renderer().render(scene, camera, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
