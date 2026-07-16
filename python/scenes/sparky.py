#!/usr/bin/env python3
"""Sparky boxy tread robot scene for LumenCore."""
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

    glass = scene.add_material(
        lc.Material(
            base_color=(0.65, 0.85, 1.0), roughness=0.02, transmission=0.92, ior=1.45
        )
    )
    screen_face = scene.add_material(
        lc.Material(
            base_color=(1.0, 1.0, 1.0),
            roughness=0.25,
            emission=(1.2, 2.8, 3.2),
            albedo_tex=tex,
        )
    )
    screen_chest = scene.add_material(
        lc.Material(
            base_color=(1.0, 1.0, 1.0),
            roughness=0.35,
            emission=(0.4, 1.4, 0.5),
            albedo_tex=tex,
        )
    )
    screen_palm = scene.add_material(
        lc.Material(base_color=(1.0, 1.0, 1.0), roughness=0.45, albedo_tex=tex)
    )
    plastic_blue = scene.add_material(
        lc.Material(base_color=(0.32, 0.62, 0.88), roughness=0.4)
    )
    plastic_white = scene.add_material(
        lc.Material(base_color=(0.92, 0.93, 0.95), roughness=0.35)
    )
    metal_grey = scene.add_material(
        lc.Material(base_color=(0.55, 0.57, 0.60), metallic=0.7, roughness=0.28)
    )
    accent_orange = scene.add_material(
        lc.Material(base_color=(0.95, 0.45, 0.12), roughness=0.4)
    )
    tread_orange = scene.add_material(
        lc.Material(base_color=(0.95, 0.38, 0.08), roughness=0.55)
    )
    emit_yellow = scene.add_material(
        lc.Material(
            base_color=(1.0, 0.9, 0.3), roughness=0.3, emission=(8.0, 6.0, 1.2)
        )
    )

    mtl_map = {
        "GlassHead": glass,
        "ScreenFace": screen_face,
        "ScreenChest": screen_chest,
        "ScreenPalm": screen_palm,
        "PlasticBlue": plastic_blue,
        "PlasticWhite": plastic_white,
        "MetalGrey": metal_grey,
        "AccentOrange": accent_orange,
        "TreadOrange": tread_orange,
        "EmitYellow": emit_yellow,
    }

    obj_path = resolve_asset("assets/models/sparky.obj")
    robot = lc.load_obj(obj_path, mtl_map, plastic_white)
    robot = lc.transform_mesh(robot, (0, 0, 0), (1, 1, 1), (0, 0.45, 0))
    scene.add_mesh(robot)
    print("Loaded {} (albedo {})".format(obj_path, albedo_path))

    floor_mat = scene.add_material(lc.Material(base_color=(0.78, 0.78, 0.80), roughness=0.88))
    wall = scene.add_material(lc.Material(base_color=(0.88, 0.90, 0.92), roughness=0.92))
    chrome = scene.add_material(
        lc.Material(base_color=(0.95, 0.95, 0.98), metallic=1.0, roughness=0.05)
    )
    prop_orange = scene.add_material(
        lc.Material(base_color=(0.95, 0.42, 0.12), roughness=0.4)
    )

    scene.add_mesh(lc.make_quad((-4, 0, -4), (8, 0, 0), (0, 0, 8), floor_mat))
    scene.add_mesh(lc.make_quad((-4, 0, -2.4), (8, 0, 0), (0, 4, 0), wall))
    scene.add_mesh(lc.make_uv_sphere((-1.45, 0.32, 0.7), 0.32, chrome))
    scene.add_mesh(lc.make_box((1.15, 0.0, 0.35), (1.75, 0.55, 0.95), prop_orange))

    light_corner = (-1.3, 3.5, -0.6)
    light_u = (2.6, 0, 0)
    light_v = (0, 0, 2.1)
    light_mat = scene.add_material(
        lc.Material(base_color=(0, 0, 0), roughness=1.0, emission=(16, 15.5, 14))
    )
    scene.add_mesh(lc.make_quad(light_corner, light_u, light_v, light_mat))
    scene.add_quad_light(light_corner, light_u, light_v, (16, 15.5, 14))

    scene.background_top = (0.62, 0.72, 0.88)
    scene.background_bottom = (0.40, 0.42, 0.46)

    camera = lc.Camera(
        eye=(2.9, 1.55, 3.7), lookat=(0.0, 0.95, 0.05), fov_y_deg=34, aspect=16 / 9
    )
    cfg = lc.RenderConfig(width=2560, height=1440, spp=spp, denoise=denoise, output_path=out)
    lc.Renderer().render(scene, camera, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
