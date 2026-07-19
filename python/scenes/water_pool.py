#!/usr/bin/env python3
"""Open deep water with a wooden pier; Sparky + Capsule Mascot as reflection subjects."""
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
    out = sys.argv[1] if len(sys.argv) > 1 else "water_pool.avif"
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    denoise = (int(sys.argv[3]) != 0) if len(sys.argv) > 3 else True
    time = float(sys.argv[4]) if len(sys.argv) > 4 else 1.25

    scene = lc.Scene()

    wood = scene.add_material(lc.Material(base_color=(0.48, 0.30, 0.14), roughness=0.72))
    wood_dark = scene.add_material(lc.Material(base_color=(0.32, 0.20, 0.10), roughness=0.8))
    seabed = scene.add_material(lc.Material(base_color=(0.12, 0.32, 0.36), roughness=0.92))
    rock = scene.add_material(lc.Material(base_color=(0.35, 0.34, 0.32), roughness=0.88))
    # Deep water: stronger Beer-Lambert so ~4 m depth reads cyan/teal.
    water = scene.add_material(
        lc.Material(
            base_color=(0.50, 0.80, 0.90),
            roughness=0.0,
            transmission=1.0,
            ior=1.33,
            absorption=(0.45, 0.14, 0.06),
        )
    )
    accent = scene.add_material(lc.Material(base_color=(0.95, 0.35, 0.12), roughness=0.35))
    accent_b = scene.add_material(lc.Material(base_color=(0.15, 0.55, 0.85), roughness=0.4))

    albedo_path = resolve_asset("assets/models/sparky_albedo.avif")
    normal_path = resolve_asset("assets/models/sparky_normal.avif")
    tex = scene.add_texture(albedo_path)
    nmap = scene.add_texture(normal_path)

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
            normal_tex=nmap,
        )
    )
    screen_chest = scene.add_material(
        lc.Material(
            base_color=(1.0, 1.0, 1.0),
            roughness=0.35,
            emission=(0.08, 0.28, 0.1),
            albedo_tex=tex,
            normal_tex=nmap,
        )
    )
    screen_palm = scene.add_material(
        lc.Material(
            base_color=(1.0, 1.0, 1.0), roughness=0.45, albedo_tex=tex, normal_tex=nmap
        )
    )
    plastic_blue = scene.add_material(
        lc.Material(base_color=(0.32, 0.62, 0.88), roughness=0.4, normal_tex=nmap)
    )
    plastic_white = scene.add_material(
        lc.Material(base_color=(0.92, 0.93, 0.95), roughness=0.35, normal_tex=nmap)
    )
    metal_grey = scene.add_material(
        lc.Material(
            base_color=(0.55, 0.57, 0.60), metallic=0.7, roughness=0.28, normal_tex=nmap
        )
    )
    accent_orange = scene.add_material(
        lc.Material(base_color=(0.95, 0.45, 0.12), roughness=0.4, normal_tex=nmap)
    )
    tread_orange = scene.add_material(
        lc.Material(base_color=(0.95, 0.38, 0.08), roughness=0.55, normal_tex=nmap)
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

    # Deep seabed (~3.5 m below water surface at y=0)
    scene.add_mesh(lc.make_quad((-50, -3.5, -50), (100, 0, 0), (0, 0, 100), seabed))

    # Open water covering the view
    water_mesh = lc.make_water_surface(
        center=(0.0, 0.0, 4.0),
        half_extents_xz=(20.0, 0.0, 20.0),
        y_base=0.0,
        material_id=water,
        nx=180,
        nz=140,
        time=time,
    )
    scene.add_mesh(water_mesh)
    print("Open deep water surface time={}".format(time))

    # Wooden pier along -Z (deck top slightly above water)
    pier_y0 = 0.12
    pier_y1 = 0.22
    scene.add_mesh(lc.make_box((-2.4, pier_y0, -5.2), (2.4, pier_y1, -1.6), wood))
    # Support piles into the deep water
    for x in (-2.0, -0.7, 0.7, 2.0):
        for z in (-4.8, -3.2, -1.9):
            scene.add_mesh(lc.make_box((x - 0.08, -3.5, z - 0.08), (x + 0.08, pier_y0, z + 0.08), wood_dark))
    # Simple railing posts
    scene.add_mesh(lc.make_box((-2.35, pier_y1, -5.15), (-2.25, 0.85, -5.05), wood_dark))
    scene.add_mesh(lc.make_box((2.25, pier_y1, -5.15), (2.35, 0.85, -5.05), wood_dark))
    scene.add_mesh(lc.make_box((-2.35, pier_y1, -1.75), (-2.25, 0.85, -1.65), wood_dark))
    scene.add_mesh(lc.make_box((2.25, pier_y1, -1.75), (2.35, 0.85, -1.65), wood_dark))

    # Submerged rocks closer to the surface in the near field for depth cues
    scene.add_mesh(lc.make_uv_sphere((-1.4, -1.6, 2.5), 0.70, rock))
    scene.add_mesh(lc.make_uv_sphere((1.8, -1.1, 3.2), 0.48, rock))
    scene.add_mesh(lc.make_uv_sphere((0.4, -2.2, 1.8), 0.55, accent_b))
    scene.add_mesh(lc.make_uv_sphere((-0.6, -0.7, 1.2), 0.28, accent))

    scene.background_top = (0.20, 0.38, 0.65)
    scene.background_bottom = (0.45, 0.55, 0.68)
    char_scale = 0.45
    deck_y = pier_y1

    sparky_path = resolve_asset("assets/models/sparky.obj")
    sparky = lc.load_obj(sparky_path, sparky_mtl, plastic_white)
    sparky = lc.transform_mesh(
        sparky, (0.85, deck_y, -3.2), (char_scale,) * 3, (0.0, -0.15, 0.0)
    )
    scene.add_mesh(sparky)
    print("Loaded {}".format(sparky_path))

    mascot_path = resolve_asset("assets/models/capsule_mascot.obj")
    mascot = lc.load_obj(mascot_path, mascot_mtl, yellow)
    mascot = lc.transform_mesh(
        mascot, (-0.90, deck_y, -3.1), (char_scale,) * 3, (0.0, 0.20, 0.0)
    )
    scene.add_mesh(mascot)
    print("Loaded {}".format(mascot_path))

    # Soft sun over open water
    light_corner = (4.0, 8.0, 2.0)
    light_u = (3.5, 0.0, 0.5)
    light_v = (-0.4, 0.0, 3.5)
    light_panel = scene.add_material(lc.Material(base_color=(0.92, 0.90, 0.85), roughness=0.9))
    scene.add_mesh(lc.make_quad(light_corner, light_u, light_v, light_panel))
    scene.add_quad_light(light_corner, light_u, light_v, (18, 17, 14))

    warm = (60.0, 52.0, 42.0)
    scene.add_spot_light(
        position=(-0.90, 3.2, -2.4),
        direction=(0.05, -0.75, -0.55),
        emission=warm,
        angle_deg=26.0,
        penumbra_deg=12.0,
    )
    scene.add_spot_light(
        position=(0.85, 3.2, -2.4),
        direction=(-0.05, -0.75, -0.55),
        emission=warm,
        angle_deg=26.0,
        penumbra_deg=12.0,
    )
    # Cool skim across the open water toward camera
    scene.add_spot_light(
        position=(0.0, 3.5, 6.0),
        direction=(0.0, -0.45, -0.85),
        emission=(22, 34, 48),
        angle_deg=55.0,
        penumbra_deg=18.0,
    )

    # Slightly elevated view: open water fills the frame, pier reflections read clearly.
    camera = lc.Camera(
        eye=(0.4, 2.9, 8.2),
        lookat=(0.0, 0.05, -2.4),
        fov_y_deg=44,
        aspect=16 / 9,
        aperture=0.0,
        focus_dist=9.5,
    )
    cfg = lc.RenderConfig(width=2560, height=1440, spp=spp, denoise=denoise, output_path=out)
    lc.Renderer().render(scene, camera, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
