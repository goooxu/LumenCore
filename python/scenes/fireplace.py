#!/usr/bin/env python3
"""Dark stone fireplace lit by a procedural OptiX flame volume, with Sparky / Capsule mascots."""
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
    out = sys.argv[1] if len(sys.argv) > 1 else "fireplace.png"
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    denoise = (int(sys.argv[3]) != 0) if len(sys.argv) > 3 else True
    time = float(sys.argv[4]) if len(sys.argv) > 4 else 1.7

    scene = lc.Scene()

    stone = scene.add_material(lc.Material(base_color=(0.32, 0.30, 0.28), roughness=0.92))
    stone_dark = scene.add_material(lc.Material(base_color=(0.18, 0.17, 0.16), roughness=0.95))
    brick = scene.add_material(lc.Material(base_color=(0.42, 0.28, 0.20), roughness=0.88))
    wood = scene.add_material(lc.Material(base_color=(0.28, 0.16, 0.08), roughness=0.8))
    ash = scene.add_material(lc.Material(base_color=(0.12, 0.11, 0.10), roughness=0.98))
    metal = scene.add_material(
        lc.Material(base_color=(0.72, 0.70, 0.68), metallic=1.0, roughness=0.28)
    )
    pottery = scene.add_material(lc.Material(base_color=(0.45, 0.28, 0.18), roughness=0.7))
    plaster = scene.add_material(lc.Material(base_color=(0.55, 0.52, 0.48), roughness=0.9))

    # Room shell (inward-facing large box via floor / walls / ceiling quads)
    scene.add_mesh(lc.make_quad((-2.4, 0, -2.2), (4.8, 0, 0), (0, 0, 4.4), wood))
    scene.add_mesh(lc.make_quad((-2.4, 0, -2.0), (4.8, 0, 0), (0, 2.6, 0), plaster))
    scene.add_mesh(lc.make_quad((-2.4, 0, -2.0), (0, 0, 4.0), (0, 2.6, 0), plaster))
    scene.add_mesh(lc.make_quad((2.4, 0, 2.0), (0, 0, -4.0), (0, 2.6, 0), plaster))
    scene.add_mesh(lc.make_quad((-2.4, 2.6, -2.0), (4.8, 0, 0), (0, 0, 4.0), stone_dark))

    # Fireplace surround
    scene.add_mesh(lc.make_box((-0.75, 0.0, -1.95), (0.75, 0.12, -1.15), stone))
    scene.add_mesh(lc.make_box((-0.85, 0.12, -1.95), (-0.55, 1.35, -1.25), brick))
    scene.add_mesh(lc.make_box((0.55, 0.12, -1.95), (0.85, 1.35, -1.25), brick))
    scene.add_mesh(lc.make_box((-0.95, 1.30, -2.00), (0.95, 1.48, -1.15), stone))
    scene.add_mesh(lc.make_box((-0.55, 0.12, -1.95), (0.55, 1.30, -1.85), ash))
    scene.add_mesh(lc.make_box((-0.55, 0.12, -1.85), (-0.48, 1.25, -1.30), ash))
    scene.add_mesh(lc.make_box((0.48, 0.12, -1.85), (0.55, 1.25, -1.30), ash))
    scene.add_mesh(lc.make_box((-0.48, 0.12, -1.85), (0.48, 0.18, -1.30), ash))

    # Logs
    scene.add_mesh(lc.make_box((-0.28, 0.18, -1.62), (0.30, 0.30, -1.48), wood))
    scene.add_mesh(
        lc.transform_mesh(
            lc.make_box((-0.22, 0.0, -0.06), (0.22, 0.11, 0.06), wood),
            translate=(0.05, 0.28, -1.55),
            scale=(1, 1, 1),
            rotate_xyz_radians=(0.0, 0.35, 0.15),
        )
    )

    # Props lit by the fire (rear corners — clear of foreground mascots)
    scene.add_mesh(lc.make_uv_sphere((-1.85, 0.22, -1.55), 0.20, pottery, 40, 20))
    scene.add_mesh(lc.make_box((1.25, 0.0, -0.85), (1.65, 0.55, -0.45), metal))
    scene.add_mesh(lc.make_uv_sphere((1.45, 0.72, -0.65), 0.18, metal, 36, 18))
    scene.add_mesh(lc.make_box((-0.40, 0.18, -1.40), (-0.34, 0.42, -1.34), metal))
    scene.add_mesh(lc.make_box((0.34, 0.18, -1.40), (0.40, 0.42, -1.34), metal))

    # --- Mascots with different material looks ---------------------------------
    albedo_path = resolve_asset("assets/models/sparky_albedo.png")
    normal_path = resolve_asset("assets/models/sparky_normal.png")
    tex = scene.add_texture(albedo_path)
    nmap = scene.add_texture(normal_path)

    # Sparky A: stock plastic / screen look
    glass_a = scene.add_material(
        lc.Material(base_color=(0.65, 0.85, 1.0), roughness=0.02, transmission=0.92, ior=1.45)
    )
    screen_face_a = scene.add_material(
        lc.Material(
            base_color=(1.0, 1.0, 1.0),
            roughness=0.25,
            emission=(0.35, 0.7, 0.85),
            albedo_tex=tex,
            normal_tex=nmap,
        )
    )
    screen_chest_a = scene.add_material(
        lc.Material(
            base_color=(1.0, 1.0, 1.0),
            roughness=0.35,
            emission=(0.1, 0.35, 0.12),
            albedo_tex=tex,
            normal_tex=nmap,
        )
    )
    screen_palm_a = scene.add_material(
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
        lc.Material(base_color=(1.0, 0.9, 0.3), roughness=0.3, emission=(2.2, 1.5, 0.3))
    )
    sparky_plastic = {
        "GlassHead": glass_a,
        "ScreenFace": screen_face_a,
        "ScreenChest": screen_chest_a,
        "ScreenPalm": screen_palm_a,
        "PlasticBlue": plastic_blue,
        "PlasticWhite": plastic_white,
        "MetalGrey": metal_grey,
        "AccentOrange": accent_orange,
        "TreadOrange": tread_orange,
        "EmitYellow": emit_yellow,
    }

    # Sparky B: brushed chrome / dark glass
    glass_b = scene.add_material(
        lc.Material(base_color=(0.35, 0.4, 0.45), roughness=0.05, transmission=0.85, ior=1.52)
    )
    chrome = scene.add_material(
        lc.Material(
            base_color=(0.94, 0.95, 0.98), metallic=1.0, roughness=0.08, normal_tex=nmap
        )
    )
    chrome_dark = scene.add_material(
        lc.Material(
            base_color=(0.35, 0.36, 0.38), metallic=1.0, roughness=0.22, normal_tex=nmap
        )
    )
    copper = scene.add_material(
        lc.Material(
            base_color=(0.85, 0.42, 0.18), metallic=1.0, roughness=0.18, normal_tex=nmap
        )
    )
    screen_chrome = scene.add_material(
        lc.Material(
            base_color=(1.0, 1.0, 1.0),
            roughness=0.2,
            emission=(1.8, 0.55, 0.2),
            albedo_tex=tex,
            normal_tex=nmap,
        )
    )
    sparky_chrome = {
        "GlassHead": glass_b,
        "ScreenFace": screen_chrome,
        "ScreenChest": screen_chrome,
        "ScreenPalm": chrome_dark,
        "PlasticBlue": chrome,
        "PlasticWhite": chrome,
        "MetalGrey": chrome_dark,
        "AccentOrange": copper,
        "TreadOrange": copper,
        "EmitYellow": emit_yellow,
    }

    # Capsule A: classic warm yellow
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
        lc.Material(base_color=(1.0, 0.9, 0.3), roughness=0.3, emission=(2.0, 1.4, 0.25))
    )
    mascot_yellow = {
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

    # Capsule B: frosted glass body + emissive core accents
    glass_body = scene.add_material(
        lc.Material(
            base_color=(0.85, 0.92, 1.0),
            roughness=0.12,
            transmission=0.88,
            ior=1.45,
            absorption=(0.15, 0.08, 0.04),
        )
    )
    glass_soft = scene.add_material(
        lc.Material(base_color=(0.9, 0.95, 1.0), roughness=0.35, transmission=0.7, ior=1.4)
    )
    glow_core = scene.add_material(
        lc.Material(base_color=(1.0, 0.55, 0.15), roughness=0.4, emission=(6.0, 2.2, 0.4))
    )
    visor_glass = scene.add_material(
        lc.Material(base_color=(0.15, 0.18, 0.22), metallic=0.4, roughness=0.15)
    )
    mascot_glass = {
        "mascot_torso": glass_body,
        "mascot_arm_left": glass_soft,
        "mascot_arm_right": glass_soft,
        "mascot_leg_left": glass_soft,
        "mascot_leg_right": glass_soft,
        "mascot_visor": visor_glass,
        "mascot_eye_left": glow_core,
        "mascot_eye_right": glow_core,
        "mascot_belt_flange": chrome_dark,
        "mascot_glove_left": chrome_dark,
        "mascot_glove_right": chrome_dark,
        "mascot_boot_left": chrome_dark,
        "mascot_boot_right": chrome_dark,
        "mascot_antenna_stem": chrome,
        "mascot_antenna_tip": glow_core,
    }

    sparky_path = resolve_asset("assets/models/sparky.obj")
    mascot_path = resolve_asset("assets/models/capsule_mascot.obj")

    # Floor-left foreground: plastic Sparky (clear of pottery ball)
    sparky_plastic_mesh = lc.load_obj(sparky_path, sparky_plastic, plastic_white)
    sparky_plastic_mesh = lc.transform_mesh(
        sparky_plastic_mesh, (-0.95, 0.0, 0.45), (0.38, 0.38, 0.38), (0.0, 0.35, 0.0)
    )
    scene.add_mesh(sparky_plastic_mesh)

    # Floor-right foreground: chrome Sparky (clear of metal pedestal / gold ball)
    sparky_chrome_mesh = lc.load_obj(sparky_path, sparky_chrome, chrome)
    sparky_chrome_mesh = lc.transform_mesh(
        sparky_chrome_mesh, (0.35, 0.0, 0.55), (0.36, 0.36, 0.36), (0.0, -0.4, 0.0)
    )
    scene.add_mesh(sparky_chrome_mesh)

    # Hearth-left: yellow Capsule (on stone slab, clear of andirons)
    mascot_y = lc.load_obj(mascot_path, mascot_yellow, yellow)
    mascot_y = lc.transform_mesh(
        mascot_y, (-0.42, 0.12, -1.00), (0.26, 0.26, 0.26), (0.0, 0.4, 0.0)
    )
    scene.add_mesh(mascot_y)

    # Mantel-right: glass Capsule catching firelight
    mascot_g = lc.load_obj(mascot_path, mascot_glass, glass_body)
    mascot_g = lc.transform_mesh(
        mascot_g, (0.62, 1.48, -1.50), (0.22, 0.22, 0.22), (0.0, -0.35, 0.0)
    )
    scene.add_mesh(mascot_g)

    print("Loaded Sparky + Capsule mascots (plastic / chrome / yellow / glass)", flush=True)

    # Procedural volumetric flame (primary look) + auto NEE proxy light
    scene.add_flame_volume(
        center=(0.0, 0.62, -1.55),
        half_extents=(0.30, 0.55, 0.20),
        emission_scale=(320.0, 120.0, 18.0),
        density_scale=3.4,
        absorption=1.2,
        noise_scale=3.0,
        time=time,
        add_proxy_light=True,
    )
    scene.add_quad_light(
        (-0.28, 0.45, -1.28),
        (0.56, 0.0, 0.0),
        (0.0, 0.35, 0.0),
        (90.0, 36.0, 6.0),
    )

    scene.background_top = (0.01, 0.01, 0.015)
    scene.background_bottom = (0.005, 0.005, 0.008)

    camera = lc.Camera(
        eye=(0.15, 1.05, 2.35),
        lookat=(0.0, 0.75, -1.45),
        up=(0.0, 1.0, 0.0),
        fov_y_deg=38.0,
        aspect=2560 / 1440,
        aperture=0.012,
        focus_dist=3.6,
    )
    cfg = lc.RenderConfig(width=2560, height=1440, spp=spp, denoise=denoise, output_path=out)
    lc.Renderer().render(scene, camera, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
