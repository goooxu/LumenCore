#!/usr/bin/env python3
"""Sparky + Capsule Mascot duo scene for LumenCore."""
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

    sparky_mtl = {
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

    # Capsule mascot materials
    yellow = scene.add_material(lc.Material(base_color=(0.95, 0.82, 0.18), roughness=0.42))
    visor = scene.add_material(
        lc.Material(base_color=(0.22, 0.24, 0.28), metallic=0.75, roughness=0.22)
    )
    eye = scene.add_material(
        lc.Material(base_color=(0.96, 0.96, 0.98), roughness=0.3, emission=(0.4, 0.4, 0.45))
    )
    belt = scene.add_material(lc.Material(base_color=(0.10, 0.18, 0.35), roughness=0.55))
    leather = scene.add_material(lc.Material(base_color=(0.22, 0.12, 0.06), roughness=0.7))
    ant_stem = scene.add_material(
        lc.Material(base_color=(0.55, 0.57, 0.60), metallic=0.65, roughness=0.3)
    )
    ant_tip = scene.add_material(
        lc.Material(base_color=(1.0, 0.9, 0.3), roughness=0.3, emission=(6.0, 4.5, 0.8))
    )

    mascot_mtl = {
        "mascot_torso": yellow,
        "mascot_arm_left": yellow,
        "mascot_arm_right": yellow,
        "mascot_leg_left": yellow,
        "mascot_leg_right": yellow,
        "mascot_visor": visor,
        "mascot_eye_left": eye,
        "mascot_eye_right": eye,
        "mascot_belt_flange": belt,
        "mascot_glove_left": leather,
        "mascot_glove_right": leather,
        "mascot_boot_left": leather,
        "mascot_boot_right": leather,
        "mascot_antenna_stem": ant_stem,
        "mascot_antenna_tip": ant_tip,
    }

    # Sparky on the right
    sparky_path = resolve_asset("assets/models/sparky.obj")
    sparky = lc.load_obj(sparky_path, sparky_mtl, plastic_white)
    sparky = lc.transform_mesh(sparky, (0.85, 0.0, 0.0), (1.0, 1.0, 1.0), (0.0, -0.35, 0.0))
    scene.add_mesh(sparky)
    print("Loaded {}".format(sparky_path))

    # Capsule mascot on the left (source height ~2m, matches Sparky scale)
    mascot_path = resolve_asset("assets/models/capsule_mascot.obj")
    mascot = lc.load_obj(mascot_path, mascot_mtl, yellow)
    mascot = lc.transform_mesh(mascot, (-0.95, 0.0, 0.05), (1.0, 1.0, 1.0), (0.0, 0.45, 0.0))
    scene.add_mesh(mascot)
    print("Loaded {}".format(mascot_path))

    floor_mat = scene.add_material(lc.Material(base_color=(0.78, 0.78, 0.80), roughness=0.88))
    wall = scene.add_material(lc.Material(base_color=(0.88, 0.90, 0.92), roughness=0.92))

    scene.add_mesh(lc.make_quad((-5, 0, -5), (10, 0, 0), (0, 0, 10), floor_mat))
    scene.add_mesh(lc.make_quad((-5, 0, -2.6), (10, 0, 0), (0, 4.2, 0), wall))

    light_corner = (-1.6, 3.7, -0.8)
    light_u = (3.2, 0, 0)
    light_v = (0, 0, 2.4)
    light_mat = scene.add_material(
        lc.Material(base_color=(0, 0, 0), roughness=1.0, emission=(15, 14.5, 13.5))
    )
    scene.add_mesh(lc.make_quad(light_corner, light_u, light_v, light_mat))
    scene.add_quad_light(light_corner, light_u, light_v, (15, 14.5, 13.5))

    scene.background_top = (0.62, 0.72, 0.88)
    scene.background_bottom = (0.40, 0.42, 0.46)

    camera = lc.Camera(
        eye=(0.15, 1.7, 4.6), lookat=(0.0, 1.0, 0.0), fov_y_deg=36, aspect=16 / 9
    )
    cfg = lc.RenderConfig(width=2560, height=1440, spp=spp, denoise=denoise, output_path=out)
    lc.Renderer().render(scene, camera, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
