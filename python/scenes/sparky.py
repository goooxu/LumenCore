#!/usr/bin/env python3
"""Sparky cartoon robot scene for LumenCore (textured OBJ)."""
from __future__ import print_function

import os
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


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "sparky.png"
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    denoise = (int(sys.argv[3]) != 0) if len(sys.argv) > 3 else True

    scene = lc.Scene()
    albedo_path = resolve_asset("assets/models/sparky_albedo.png")
    tex = scene.add_texture(albedo_path)
    sparky_mat = scene.add_material(
        lc.Material(base_color=(1.0, 1.0, 1.0), roughness=0.42, albedo_tex=tex)
    )
    floor_mat = scene.add_material(lc.Material(base_color=(0.55, 0.55, 0.58), roughness=0.85))
    wall = scene.add_material(lc.Material(base_color=(0.82, 0.8, 0.78), roughness=0.9))
    chrome = scene.add_material(
        lc.Material(base_color=(0.95, 0.95, 0.98), metallic=1.0, roughness=0.05)
    )
    accent = scene.add_material(lc.Material(base_color=(0.25, 0.72, 0.72), roughness=0.35))

    obj_path = resolve_asset("assets/models/sparky.obj")
    robot = lc.load_obj(obj_path, {"Sparky": sparky_mat}, sparky_mat)
    robot = lc.transform_mesh(robot, (0, 0, 0), (1, 1, 1), (0, 0.4, 0))
    scene.add_mesh(robot)
    print("Loaded {} (albedo {})".format(obj_path, albedo_path))

    scene.add_mesh(lc.make_quad((-4, 0, -4), (8, 0, 0), (0, 0, 8), floor_mat))
    scene.add_mesh(lc.make_quad((-4, 0, -2.2), (8, 0, 0), (0, 4, 0), wall))
    scene.add_mesh(lc.make_uv_sphere((-1.35, 0.35, 0.8), 0.35, chrome))
    scene.add_mesh(lc.make_box((1.1, 0.0, 0.4), (1.7, 0.7, 1.0), accent))

    light_corner = (-1.2, 3.6, -0.5)
    light_u = (2.4, 0, 0)
    light_v = (0, 0, 2.0)
    light_mat = scene.add_material(
        lc.Material(base_color=(0, 0, 0), roughness=1.0, emission=(18, 17, 15))
    )
    scene.add_mesh(lc.make_quad(light_corner, light_u, light_v, light_mat))
    scene.add_quad_light(light_corner, light_u, light_v, (18, 17, 15))

    scene.background_top = (0.55, 0.68, 0.88)
    scene.background_bottom = (0.35, 0.35, 0.4)

    camera = lc.Camera(eye=(2.6, 1.65, 3.5), lookat=(0.0, 1.1, 0.1), fov_y_deg=35, aspect=16 / 9)
    cfg = lc.RenderConfig(width=2560, height=1440, spp=spp, denoise=denoise, output_path=out)
    lc.Renderer().render(scene, camera, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
