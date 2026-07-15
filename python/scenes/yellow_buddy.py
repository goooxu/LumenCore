#!/usr/bin/env python3
"""Yellow Buddy OBJ character scene for LumenCore."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import lumencore as lc


def resolve_asset(relative: str) -> str:
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


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "yellow_buddy.png"
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    denoise = (int(sys.argv[3]) != 0) if len(sys.argv) > 3 else True

    scene = lc.Scene()
    yellow = scene.add_material(lc.Material(base_color=(0.95, 0.82, 0.12), roughness=0.45))
    overalls = scene.add_material(lc.Material(base_color=(0.15, 0.35, 0.75), roughness=0.55))
    strap = scene.add_material(lc.Material(base_color=(0.08, 0.08, 0.08), roughness=0.7))
    goggle = scene.add_material(lc.Material(base_color=(0.7, 0.7, 0.75), metallic=0.85, roughness=0.15))
    lens = scene.add_material(
        lc.Material(base_color=(0.75, 0.88, 0.98), roughness=0.05, transmission=0.85, ior=1.5)
    )
    eye_white = scene.add_material(lc.Material(base_color=(0.95, 0.95, 0.95), roughness=0.4))
    pupil = scene.add_material(lc.Material(base_color=(0.05, 0.05, 0.05), roughness=0.6))
    boot = scene.add_material(lc.Material(base_color=(0.18, 0.1, 0.06), roughness=0.75))
    floor_mat = scene.add_material(lc.Material(base_color=(0.55, 0.55, 0.58), roughness=0.85))
    wall = scene.add_material(lc.Material(base_color=(0.82, 0.8, 0.78), roughness=0.9))
    chrome = scene.add_material(lc.Material(base_color=(0.95, 0.95, 0.98), metallic=1.0, roughness=0.05))

    mtl_map = {
        "Yellow": yellow,
        "Overalls": overalls,
        "Strap": strap,
        "Goggle": goggle,
        "Lens": lens,
        "EyeWhite": eye_white,
        "Pupil": pupil,
        "Boot": boot,
    }

    obj_path = resolve_asset("assets/models/yellow_buddy.obj")
    buddy = lc.load_obj(obj_path, mtl_map, yellow)
    buddy = lc.transform_mesh(buddy, (0, 0, 0), (1, 1, 1), (0, 0.35, 0))
    scene.add_mesh(buddy)
    print(f"Loaded {obj_path}")

    scene.add_mesh(lc.make_quad((-4, 0, -4), (8, 0, 0), (0, 0, 8), floor_mat))
    scene.add_mesh(lc.make_quad((-4, 0, -2.2), (8, 0, 0), (0, 4, 0), wall))
    scene.add_mesh(lc.make_uv_sphere((-1.35, 0.35, 0.8), 0.35, chrome))
    scene.add_mesh(lc.make_box((1.1, 0.0, 0.4), (1.7, 0.7, 1.0), overalls))

    light_corner = (-1.2, 3.6, -0.5)
    light_u = (2.4, 0, 0)
    light_v = (0, 0, 2.0)
    light_mat = scene.add_material(lc.Material(base_color=(0, 0, 0), roughness=1.0, emission=(18, 17, 15)))
    scene.add_mesh(lc.make_quad(light_corner, light_u, light_v, light_mat))
    scene.add_quad_light(light_corner, light_u, light_v, (18, 17, 15))

    scene.background_top = (0.55, 0.68, 0.88)
    scene.background_bottom = (0.35, 0.35, 0.4)

    camera = lc.Camera(eye=(2.6, 1.55, 3.4), lookat=(0.0, 1.0, 0.15), fov_y_deg=35, aspect=16 / 9)
    cfg = lc.RenderConfig(width=2560, height=1440, spp=spp, denoise=denoise, output_path=out)
    lc.Renderer().render(scene, camera, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
