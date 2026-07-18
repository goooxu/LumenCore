#!/usr/bin/env python3
"""LumenCore cover: 暮潮观测站 — coastal dusk platform (Spot / Sparky / Capsule).

Low-angle HDR skylight, multi-material optical instruments, Beer-Lambert tide pool,
and a distant absorption–emissive flame beacon. Static poses (no PhysX).
"""
from __future__ import annotations

import math
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
    out = sys.argv[1] if len(sys.argv) > 1 else "outputs/gallery/dusk_observatory.avif"
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 192
    denoise = (int(sys.argv[3]) != 0) if len(sys.argv) > 3 else True

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    scene = lc.Scene()

    hdri = resolve_asset("assets/env/dusk.hdr")
    if Path(hdri).is_file():
        scene.load_env_map(hdri)
        print(f"[dusk] HDRI {hdri}", flush=True)

    # --- Materials ----------------------------------------------------------------
    deck = scene.add_material(lc.Material(base_color=(0.28, 0.30, 0.32), roughness=0.88))
    concrete = scene.add_material(lc.Material(base_color=(0.42, 0.40, 0.38), roughness=0.92))
    rail = scene.add_material(
        lc.Material(base_color=(0.55, 0.52, 0.48), metallic=0.85, roughness=0.35)
    )
    ceramic = scene.add_material(lc.Material(base_color=(0.78, 0.74, 0.68), roughness=0.55))
    rough_metal = scene.add_material(
        lc.Material(base_color=(0.62, 0.58, 0.52), metallic=1.0, roughness=0.55)
    )
    chrome = scene.add_material(
        lc.Material(base_color=(0.95, 0.96, 0.98), metallic=1.0, roughness=0.02)
    )
    optical = scene.add_material(
        lc.Material(
            base_color=(0.85, 0.92, 0.98),
            roughness=0.04,
            transmission=0.96,
            ior=1.52,
            absorption=(0.08, 0.04, 0.02),
        )
    )
    water_m = scene.add_material(
        lc.Material(
            base_color=(0.40, 0.72, 0.88),
            roughness=0.02,
            transmission=1.0,
            ior=1.33,
            absorption=(0.50, 0.16, 0.07),
        )
    )
    rock = scene.add_material(lc.Material(base_color=(0.22, 0.24, 0.26), roughness=0.9))
    beacon_stone = scene.add_material(lc.Material(base_color=(0.30, 0.28, 0.26), roughness=0.9))
    panel = scene.add_material(
        lc.Material(base_color=(0.18, 0.20, 0.24), metallic=0.4, roughness=0.4)
    )

    albedo = scene.add_texture(resolve_asset("assets/models/sparky_albedo.avif"))
    nmap = scene.add_texture(resolve_asset("assets/models/sparky_normal.avif"))
    spot_tex = scene.add_texture(resolve_asset("assets/models/spot_texture.avif"))

    glass_h = scene.add_material(
        lc.Material(base_color=(0.65, 0.85, 1.0), roughness=0.02, transmission=0.92, ior=1.45)
    )
    screen_face = scene.add_material(
        lc.Material(
            base_color=(1, 1, 1),
            roughness=0.25,
            emission=(0.35, 0.55, 0.70),
            albedo_tex=albedo,
            normal_tex=nmap,
        )
    )
    screen_chest = scene.add_material(
        lc.Material(
            base_color=(1, 1, 1),
            roughness=0.35,
            emission=(0.06, 0.22, 0.12),
            albedo_tex=albedo,
            normal_tex=nmap,
        )
    )
    screen_palm = scene.add_material(
        lc.Material(base_color=(1, 1, 1), roughness=0.45, albedo_tex=albedo, normal_tex=nmap)
    )
    plastic_blue = scene.add_material(
        lc.Material(base_color=(0.32, 0.62, 0.88), roughness=0.4, normal_tex=nmap)
    )
    plastic_white = scene.add_material(
        lc.Material(base_color=(0.92, 0.93, 0.95), roughness=0.35, normal_tex=nmap)
    )
    metal_grey = scene.add_material(
        lc.Material(base_color=(0.55, 0.57, 0.60), metallic=0.7, roughness=0.28, normal_tex=nmap)
    )
    accent = scene.add_material(
        lc.Material(base_color=(0.95, 0.45, 0.12), roughness=0.4, normal_tex=nmap)
    )
    tread = scene.add_material(
        lc.Material(base_color=(0.95, 0.38, 0.08), roughness=0.55, normal_tex=nmap)
    )
    emit_y = scene.add_material(
        lc.Material(base_color=(1.0, 0.9, 0.3), roughness=0.3, emission=(1.8, 1.3, 0.25))
    )
    sparky_mtl = {
        "GlassHead": glass_h,
        "ScreenFace": screen_face,
        "ScreenChest": screen_chest,
        "ScreenPalm": screen_palm,
        "PlasticBlue": plastic_blue,
        "PlasticWhite": plastic_white,
        "MetalGrey": metal_grey,
        "AccentOrange": accent,
        "TreadOrange": tread,
        "EmitYellow": emit_y,
    }

    yellow = scene.add_material(lc.Material(base_color=(0.95, 0.82, 0.18), roughness=0.42))
    visor = scene.add_material(
        lc.Material(base_color=(0.22, 0.24, 0.28), metallic=0.75, roughness=0.22)
    )
    eye = scene.add_material(lc.Material(base_color=(0.96, 0.96, 0.98), roughness=0.3))
    belt = scene.add_material(lc.Material(base_color=(0.10, 0.18, 0.35), roughness=0.55))
    leather = scene.add_material(lc.Material(base_color=(0.22, 0.12, 0.06), roughness=0.7))
    ant = scene.add_material(
        lc.Material(base_color=(0.55, 0.57, 0.60), metallic=0.65, roughness=0.3)
    )
    tip = scene.add_material(
        lc.Material(base_color=(1.0, 0.9, 0.3), roughness=0.3, emission=(1.6, 1.2, 0.25))
    )
    capsule_mtl = {
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
        "mascot_antenna_stem": ant,
        "mascot_antenna_tip": tip,
    }

    # Normal-mapped metal sample plaques for Capsule's calibration bench
    sample_metal = scene.add_material(
        lc.Material(
            base_color=(0.72, 0.74, 0.78),
            metallic=1.0,
            roughness=0.22,
            normal_tex=nmap,
            albedo_tex=albedo,
        )
    )

    # --- Coastal platform ---------------------------------------------------------
    # Main deck
    scene.add_mesh(lc.make_box((-4.5, -0.35, -3.5), (4.5, 0.0, 3.2), concrete))
    scene.add_mesh(lc.make_quad((-4.5, 0.0, -3.5), (9.0, 0.0, 0.0), (0.0, 0.0, 6.7), deck))
    # Seaward apron steps into water
    scene.add_mesh(lc.make_box((-4.5, -1.2, 3.0), (4.5, 0.0, 3.5), concrete))

    # Railings
    for x in (-4.3, 4.3):
        scene.add_mesh(lc.make_box((x - 0.04, 0.0, -3.2), (x + 0.04, 1.05, 2.8), rail))
    scene.add_mesh(lc.make_box((-4.3, 0.95, -3.2), (4.3, 1.05, -3.1), rail))
    scene.add_mesh(lc.make_box((-4.3, 0.95, 2.7), (4.3, 1.05, 2.8), rail))

    # Central maintenance desk — Spot stands here
    scene.add_mesh(lc.make_box((-0.85, 0.0, -0.55), (0.85, 0.78, 0.55), rough_metal))
    scene.add_mesh(lc.make_box((-0.90, 0.78, -0.60), (0.90, 0.84, 0.60), chrome))
    # Desk instruments: ceramic body, chrome mounts, optical shells
    scene.add_mesh(lc.make_uv_sphere((-0.45, 1.05, 0.0), 0.18, ceramic, 36, 18))
    scene.add_mesh(lc.make_box((-0.12, 0.84, -0.12), (0.12, 1.15, 0.12), chrome))
    scene.add_mesh(lc.make_uv_sphere((0.42, 1.08, 0.05), 0.16, optical, 40, 20))
    scene.add_mesh(lc.make_box((0.25, 0.84, -0.35), (0.55, 0.92, -0.05), panel))

    # Sparky optical instrument bench (right)
    scene.add_mesh(lc.make_box((1.55, 0.0, -1.35), (3.15, 0.72, -0.15), rough_metal))
    scene.add_mesh(lc.make_box((1.50, 0.72, -1.40), (3.20, 0.78, -0.10), chrome))
    # Multi-material optics rack
    scene.add_mesh(lc.make_box((1.75, 0.78, -1.05), (2.05, 1.35, -0.75), chrome))
    scene.add_mesh(lc.make_uv_sphere((1.90, 1.48, -0.90), 0.14, optical, 36, 18))
    scene.add_mesh(lc.make_box((2.25, 0.78, -1.15), (2.95, 0.95, -0.35), panel))
    scene.add_mesh(lc.make_uv_sphere((2.55, 1.15, -0.75), 0.20, ceramic, 32, 16))
    scene.add_mesh(lc.make_uv_sphere((2.90, 1.00, -0.45), 0.12, chrome, 28, 14))
    scene.add_mesh(lc.make_box((2.15, 0.78, -0.55), (2.45, 1.20, -0.25), rough_metal))

    # Capsule side calibration bench (left)
    scene.add_mesh(lc.make_box((-3.20, 0.0, -0.85), (-1.55, 0.70, 0.55), rough_metal))
    scene.add_mesh(lc.make_box((-3.25, 0.70, -0.90), (-1.50, 0.76, 0.60), chrome))
    # Metal sample plaques with normal textures
    scene.add_mesh(lc.make_box((-2.95, 0.76, -0.35), (-2.45, 0.82, 0.15), sample_metal))
    scene.add_mesh(lc.make_box((-2.35, 0.76, -0.40), (-1.85, 0.82, 0.20), sample_metal))
    scene.add_mesh(lc.make_uv_sphere((-2.70, 0.95, 0.25), 0.14, sample_metal, 32, 16))
    scene.add_mesh(lc.make_uv_sphere((-2.15, 0.92, -0.55), 0.11, chrome, 28, 14))
    scene.add_mesh(lc.make_uv_sphere((-1.85, 0.95, 0.30), 0.10, ceramic, 24, 12))

    # Foreground tide pool (Beer-Lambert + microfacet water)
    scene.add_mesh(lc.make_box((-2.4, -0.05, 1.45), (2.4, 0.06, 2.95), rock))
    scene.add_mesh(
        lc.make_water_surface(
            center=(0.0, 0.10, 2.20),
            half_extents_xz=(2.15, 0.0, 0.65),
            y_base=0.10,
            material_id=water_m,
            nx=72,
            nz=36,
            time=1.35,
        )
    )
    scene.add_mesh(lc.make_uv_sphere((-0.6, -0.15, 2.15), 0.18, rock, 24, 14))
    scene.add_mesh(lc.make_uv_sphere((0.9, -0.10, 2.35), 0.14, rock, 20, 12))

    # Distant flame beacon (warm absorption–emissive volume)
    scene.add_mesh(lc.make_box((-3.85, 0.0, -3.15), (-3.15, 0.55, -2.45), beacon_stone))
    scene.add_mesh(lc.make_box((-3.75, 0.55, -3.05), (-3.25, 1.85, -2.55), beacon_stone))
    scene.add_flame_volume(
        center=(-3.50, 2.25, -2.80),
        half_extents=(0.22, 0.48, 0.18),
        emission_scale=(160.0, 60.0, 12.0),
        density_scale=2.8,
        absorption=1.6,
        noise_scale=2.6,
        time=1.8,
        add_proxy_light=True,
    )

    # --- Characters (static poses) ------------------------------------------------
    sparky_scale = 0.50
    sparky_ymin, sparky_ymax = -0.002721, 2.09
    sparky_h = (sparky_ymax - sparky_ymin) * sparky_scale
    sparky = lc.load_obj(resolve_asset("assets/models/sparky.obj"), sparky_mtl, plastic_white)
    sparky = lc.transform_mesh(
        sparky,
        (2.35, -sparky_ymin * sparky_scale, -0.75),
        (sparky_scale,) * 3,
        (0.0, math.radians(-55), 0.0),
    )
    scene.add_mesh(sparky)

    capsule_scale = 0.48
    capsule = lc.load_obj(resolve_asset("assets/models/capsule_mascot.obj"), capsule_mtl, yellow)
    capsule = lc.transform_mesh(
        capsule,
        (-2.35, 0.0, -0.15),
        (capsule_scale,) * 3,
        (0.0, math.radians(40), 0.0),
    )
    scene.add_mesh(capsule)

    spot_scale = 0.58
    spot_ymin, spot_ymax = -0.736784, 0.953646
    spot_mat = scene.add_material(
        lc.Material(base_color=(1.0, 1.0, 1.0), roughness=0.55, albedo_tex=spot_tex)
    )
    spot = lc.load_obj(resolve_asset("assets/models/spot_triangulated.obj"), spot_mat)
    spot = lc.transform_mesh(
        spot,
        (0.05, -spot_ymin * spot_scale + 0.84, 0.05),
        (spot_scale,) * 3,
        (0.0, math.radians(25), 0.0),
    )
    scene.add_mesh(spot)
    print("[dusk] loaded Spot + Sparky + Capsule", flush=True)

    # --- Lights: limited local fill under low-angle HDR ---------------------------
    scene.add_spot_light(
        position=(0.2, 2.8, 1.0),
        direction=(-0.05, -1.0, -0.35),
        emission=(28.0, 32.0, 48.0),
        angle_deg=26.0,
        penumbra_deg=14.0,
    )
    scene.add_spot_light(
        position=(2.4, 2.6, 0.4),
        direction=(-0.15, -1.0, -0.55),
        emission=(55.0, 42.0, 28.0),
        angle_deg=18.0,
        penumbra_deg=10.0,
    )
    scene.add_spot_light(
        position=(-2.4, 2.5, 0.5),
        direction=(0.1, -1.0, -0.4),
        emission=(40.0, 48.0, 55.0),
        angle_deg=20.0,
        penumbra_deg=12.0,
    )
    # Instrument panel glow (warm/cool contrast into the tide pool)
    scene.add_quad_light(
        (2.28, 0.96, -1.12),
        (0.55, 0.0, 0.0),
        (0.0, 0.0, 0.55),
        (4.5, 3.2, 2.0),
    )

    scene.background_top = (0.10, 0.12, 0.22)
    scene.background_bottom = (0.04, 0.035, 0.04)

    camera = lc.Camera(
        eye=(3.9, 1.55, 5.4),
        lookat=(-0.2, 0.85, -0.3),
        up=(0.0, 1.0, 0.0),
        fov_y_deg=36.0,
        aspect=2560 / 1440,
    )
    cfg = lc.RenderConfig(
        width=2560,
        height=1440,
        spp=spp,
        denoise=denoise,
        enable_nee=True,
        output_path=out,
    )
    print(f"[dusk] render → {out} @ {spp} spp", flush=True)
    lc.Renderer().render(scene, camera, cfg)
    print("[dusk] done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
