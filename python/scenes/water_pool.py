#!/usr/bin/env python3
"""Stone pool with procedural water; Sparky + Capsule Mascot as reflection subjects."""
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
    out = sys.argv[1] if len(sys.argv) > 1 else "water_pool.png"
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    denoise = (int(sys.argv[3]) != 0) if len(sys.argv) > 3 else True
    time = float(sys.argv[4]) if len(sys.argv) > 4 else 1.25

    scene = lc.Scene()

    stone = scene.add_material(lc.Material(base_color=(0.32, 0.30, 0.28), roughness=0.88))
    stone_dark = scene.add_material(lc.Material(base_color=(0.18, 0.17, 0.16), roughness=0.9))
    wood = scene.add_material(lc.Material(base_color=(0.42, 0.26, 0.12), roughness=0.72))
    tile = scene.add_material(lc.Material(base_color=(0.08, 0.22, 0.28), roughness=0.5))
    sand = scene.add_material(lc.Material(base_color=(0.45, 0.40, 0.32), roughness=0.95))
    # Dark backdrop so water mirrors characters instead of a white wash.
    plaster = scene.add_material(lc.Material(base_color=(0.12, 0.16, 0.28), roughness=0.92))
    water = scene.add_material(
        lc.Material(
            base_color=(0.40, 0.75, 0.88),
            roughness=0.0,
            transmission=1.0,
            ior=1.33,
            absorption=(1.1, 0.28, 0.12),
        )
    )
    accent_b = scene.add_material(lc.Material(base_color=(0.95, 0.35, 0.12), roughness=0.35))

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
            emission=(0.25, 0.55, 0.65),
            albedo_tex=tex,
        )
    )
    screen_chest = scene.add_material(
        lc.Material(
            base_color=(1.0, 1.0, 1.0),
            roughness=0.35,
            emission=(0.08, 0.28, 0.1),
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
            base_color=(1.0, 0.9, 0.3), roughness=0.3, emission=(1.8, 1.3, 0.25)
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

    yellow = scene.add_material(lc.Material(base_color=(0.95, 0.82, 0.18), roughness=0.42))
    visor = scene.add_material(
        lc.Material(base_color=(0.22, 0.24, 0.28), metallic=0.75, roughness=0.22)
    )
    eye = scene.add_material(lc.Material(base_color=(0.96, 0.96, 0.98), roughness=0.3))
    belt = scene.add_material(lc.Material(base_color=(0.10, 0.18, 0.35), roughness=0.55))
    leather = scene.add_material(lc.Material(base_color=(0.22, 0.12, 0.06), roughness=0.7))
    ant_stem = scene.add_material(
        lc.Material(base_color=(0.55, 0.57, 0.60), metallic=0.65, roughness=0.3)
    )
    ant_tip = scene.add_material(
        lc.Material(base_color=(1.0, 0.9, 0.3), roughness=0.3, emission=(1.5, 1.1, 0.2))
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

    scene.add_mesh(lc.make_quad((-12, 0, -12), (24, 0, 0), (0, 0, 24), sand))

    # Three-walled pool open toward +Z (camera) so the water surface is unobstructed.
    scene.add_mesh(lc.make_box((-2.1, 0.0, -1.5), (2.1, 0.06, 1.5), tile))  # floor
    scene.add_mesh(lc.make_box((-2.1, 0.06, -1.5), (2.1, 0.72, -1.2), stone))  # -Z back
    scene.add_mesh(lc.make_box((-2.1, 0.06, -1.2), (-1.8, 0.72, 1.5), stone))  # -X
    scene.add_mesh(lc.make_box((1.8, 0.06, -1.2), (2.1, 0.72, 1.5), stone))  # +X
    # Coping on three walls only
    scene.add_mesh(lc.make_box((-2.3, 0.72, -1.7), (2.3, 0.82, -1.5), stone_dark))
    scene.add_mesh(lc.make_box((-2.3, 0.72, -1.5), (-2.1, 0.82, 1.5), stone_dark))
    scene.add_mesh(lc.make_box((2.1, 0.72, -1.5), (2.3, 0.82, 1.5), stone_dark))
    # Far deck behind back wall
    scene.add_mesh(lc.make_box((-2.6, 0.82, -3.3), (2.6, 0.90, -1.7), wood))
    scene.add_mesh(lc.make_quad((-3.2, 0.90, -3.25), (6.4, 0, 0), (0, 3.4, 0), plaster))

    water_mesh = lc.make_water_surface(
        center=(0.0, 0.0, 0.15),
        half_extents_xz=(1.75, 0.0, 1.25),
        y_base=0.58,
        material_id=water,
        nx=128,
        nz=96,
        time=time,
    )
    scene.add_mesh(water_mesh)
    print("Procedural water surface time={}".format(time))

    char_scale = 0.45
    deck_y = 0.90

    sparky_path = resolve_asset("assets/models/sparky.obj")
    sparky = lc.load_obj(sparky_path, sparky_mtl, plastic_white)
    sparky = lc.transform_mesh(
        sparky, (0.75, deck_y, -2.40), (char_scale,) * 3, (0.0, -0.15, 0.0)
    )
    scene.add_mesh(sparky)
    print("Loaded {}".format(sparky_path))

    mascot_path = resolve_asset("assets/models/capsule_mascot.obj")
    mascot = lc.load_obj(mascot_path, mascot_mtl, yellow)
    mascot = lc.transform_mesh(
        mascot, (-0.80, deck_y, -2.35), (char_scale,) * 3, (0.0, 0.20, 0.0)
    )
    scene.add_mesh(mascot)
    print("Loaded {}".format(mascot_path))

    # Bright submerged accent for refraction through the water volume
    scene.add_mesh(lc.make_uv_sphere((0.25, 0.25, 0.35), 0.20, accent_b))

    light_corner = (1.8, 4.8, 0.5)
    light_u = (1.8, 0.0, 0.3)
    light_v = (-0.2, 0.0, 1.8)
    light_mat = scene.add_material(
        lc.Material(base_color=(0, 0, 0), roughness=1.0, emission=(22, 20, 17))
    )
    scene.add_mesh(lc.make_quad(light_corner, light_u, light_v, light_mat))
    scene.add_quad_light(light_corner, light_u, light_v, (22, 20, 17))

    warm = (80.0, 70.0, 55.0)
    scene.add_spot_light(
        position=(-0.80, 3.0, -1.6),
        direction=(0.05, -0.75, -0.55),
        emission=warm,
        angle_deg=26.0,
        penumbra_deg=12.0,
    )
    scene.add_spot_light(
        position=(0.75, 3.0, -1.6),
        direction=(-0.05, -0.75, -0.55),
        emission=warm,
        angle_deg=26.0,
        penumbra_deg=12.0,
    )
    # Cool skim light across the water toward camera
    scene.add_spot_light(
        position=(0.0, 2.0, 3.2),
        direction=(0.0, -0.45, -0.85),
        emission=(35, 50, 70),
        angle_deg=50.0,
        penumbra_deg=18.0,
    )

    scene.background_top = (0.18, 0.28, 0.48)
    scene.background_bottom = (0.30, 0.34, 0.40)

    # Look down across open water; characters sit in the upper third with clear reflections.
    camera = lc.Camera(
        eye=(0.0, 1.55, 3.6),
        lookat=(0.0, 0.55, -0.4),
        fov_y_deg=40,
        aspect=16 / 9,
        aperture=0.0,
        focus_dist=4.0,
    )
    cfg = lc.RenderConfig(width=2560, height=1440, spp=spp, denoise=denoise, output_path=out)
    lc.Renderer().render(scene, camera, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
