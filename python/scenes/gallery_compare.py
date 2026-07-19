#!/usr/bin/env python3
"""Feature ON/OFF compare renders for the README two-tier gallery.

Same camera / crop per feature; only one switch flips between --mode on|off.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import lumencore as lc


FEATURES = ("normal", "nee", "denoiser", "flame", "beer")


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


def _sparky_materials(scene: lc.Scene, use_normals: bool) -> tuple[dict, int]:
    albedo = scene.add_texture(resolve_asset("assets/models/sparky_albedo.avif"))
    nmap = scene.add_texture(resolve_asset("assets/models/sparky_normal.avif"))
    nt = nmap if use_normals else -1

    glass = scene.add_material(
        lc.Material(base_color=(0.65, 0.85, 1.0), roughness=0.02, transmission=0.92, ior=1.45)
    )
    screen_face = scene.add_material(
        lc.Material(
            base_color=(1, 1, 1),
            roughness=0.25,
            emission=(0.3, 0.6, 0.75),
            albedo_tex=albedo,
            normal_tex=nt,
        )
    )
    screen_chest = scene.add_material(
        lc.Material(
            base_color=(1, 1, 1),
            roughness=0.35,
            emission=(0.08, 0.28, 0.1),
            albedo_tex=albedo,
            normal_tex=nt,
        )
    )
    screen_palm = scene.add_material(
        lc.Material(base_color=(1, 1, 1), roughness=0.45, albedo_tex=albedo, normal_tex=nt)
    )
    plastic_blue = scene.add_material(
        lc.Material(base_color=(0.32, 0.62, 0.88), roughness=0.4, normal_tex=nt)
    )
    plastic_white = scene.add_material(
        lc.Material(base_color=(0.92, 0.93, 0.95), roughness=0.35, normal_tex=nt)
    )
    metal_grey = scene.add_material(
        lc.Material(base_color=(0.55, 0.57, 0.60), metallic=0.7, roughness=0.28, normal_tex=nt)
    )
    accent = scene.add_material(
        lc.Material(base_color=(0.95, 0.45, 0.12), roughness=0.4, normal_tex=nt)
    )
    tread = scene.add_material(
        lc.Material(base_color=(0.95, 0.38, 0.08), roughness=0.55, normal_tex=nt)
    )
    emit_y = scene.add_material(
        lc.Material(base_color=(1.0, 0.9, 0.3), roughness=0.3, emission=(1.8, 1.3, 0.25))
    )
    mtl = {
        "GlassHead": glass,
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
    return mtl, plastic_white


def render_normal(mode: str, out: str, width: int, spp: int, denoise: bool) -> None:
    """Sparky chest/panel close-up: normal map on vs off."""
    on = mode == "on"
    scene = lc.Scene()
    floor = scene.add_material(lc.Material(base_color=(0.36, 0.36, 0.38), roughness=0.92))
    wall = scene.add_material(lc.Material(base_color=(0.48, 0.49, 0.52), roughness=0.94))
    scene.add_mesh(lc.make_quad((-3, 0, -3), (6, 0, 0), (0, 0, 6), floor))
    scene.add_mesh(lc.make_quad((-3, 0, -1.2), (6, 0, 0), (0, 3.5, 0), wall))

    mtl, fallback = _sparky_materials(scene, use_normals=on)
    sparky = lc.load_obj(resolve_asset("assets/models/sparky.obj"), mtl, fallback)
    sparky = lc.transform_mesh(sparky, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (0.0, 0.0, 0.0))
    scene.add_mesh(sparky)

    scene.add_spot_light(
        position=(0.35, 2.4, 1.6),
        direction=(-0.15, -0.85, -0.5),
        emission=(110.0, 100.0, 90.0),
        angle_deg=22.0,
        penumbra_deg=12.0,
    )
    scene.add_quad_light((-0.4, 2.8, 0.2), (0.8, 0, 0), (0, 0, 0.5), (4.0, 4.0, 4.2))
    scene.background_top = (0.22, 0.26, 0.34)
    scene.background_bottom = (0.08, 0.09, 0.10)

    # Chest / panel crop
    camera = lc.Camera(
        eye=(0.55, 1.35, 1.55),
        lookat=(0.05, 1.05, 0.05),
        up=(0.0, 1.0, 0.0),
        fov_y_deg=28.0,
        aspect=1.0,
    )
    cfg = lc.RenderConfig(
        width=width,
        height=width,
        spp=spp,
        denoise=denoise,
        enable_nee=True,
        output_path=out,
    )
    lc.Renderer().render(scene, camera, cfg)


def render_nee(mode: str, out: str, width: int, spp: int, denoise: bool) -> None:
    """Dark room + area light: NEE on vs off (shadow/variance).

    Virtual QuadLight has no BVH geometry, so NEE-off needs an emissive mesh.
    Never register both for the same light (MIS weight is 1 for virtual lights).
    """
    on = mode == "on"
    scene = lc.Scene()
    white = scene.add_material(lc.Material(base_color=(0.73, 0.73, 0.73), roughness=0.85))
    red = scene.add_material(lc.Material(base_color=(0.55, 0.08, 0.06), roughness=0.85))
    green = scene.add_material(lc.Material(base_color=(0.10, 0.40, 0.12), roughness=0.85))
    metal = scene.add_material(lc.Material(base_color=(0.92, 0.88, 0.80), metallic=1.0, roughness=0.08))
    diffuse = scene.add_material(lc.Material(base_color=(0.55, 0.52, 0.48), roughness=0.7))

    # Small dark box (unit-ish room)
    scene.add_mesh(lc.make_quad((0, 0, 0), (1, 0, 0), (0, 0, 1), white))
    scene.add_mesh(lc.make_quad((0, 1, 0), (1, 0, 0), (0, 0, 1), white))
    scene.add_mesh(lc.make_quad((0, 0, 1), (1, 0, 0), (0, 1, 0), white))
    scene.add_mesh(lc.make_quad((0, 0, 0), (0, 0, 1), (0, 1, 0), red))
    scene.add_mesh(lc.make_quad((1, 0, 0), (0, 0, 1), (0, 1, 0), green))

    light_corner = (0.38, 0.998, 0.38)
    light_u = (0.24, 0, 0)
    light_v = (0, 0, 0.24)
    if on:
        # Virtual QuadLight only (+ optional non-emissive panel for silhouette).
        panel = scene.add_material(lc.Material(base_color=(0.95, 0.95, 0.92), roughness=0.9))
        scene.add_mesh(lc.make_quad(light_corner, light_u, light_v, panel))
        scene.add_quad_light(light_corner, light_u, light_v, (28.0, 26.0, 22.0))
    else:
        light_mat = scene.add_material(
            lc.Material(base_color=(0, 0, 0), roughness=1.0, emission=(28.0, 26.0, 22.0))
        )
        scene.add_mesh(lc.make_quad(light_corner, light_u, light_v, light_mat))

    scene.add_mesh(lc.make_box((0.18, 0.0, 0.55), (0.42, 0.45, 0.82), diffuse))
    scene.add_mesh(lc.make_uv_sphere((0.68, 0.18, 0.38), 0.18, metal, 40, 20))

    scene.background_top = (0, 0, 0)
    scene.background_bottom = (0, 0, 0)

    camera = lc.Camera(
        eye=(0.5, 0.48, -1.15),
        lookat=(0.5, 0.42, 0.5),
        fov_y_deg=38.0,
        aspect=1.0,
    )
    cfg = lc.RenderConfig(
        width=width,
        height=width,
        spp=spp,
        denoise=denoise,
        enable_nee=on,
        output_path=out,
    )
    lc.Renderer().render(scene, camera, cfg)


def render_denoiser(mode: str, out: str, width: int, spp: int, denoise: bool) -> None:
    """Mid-shot studio props at low spp: denoise on vs off."""
    on = mode == "on"
    # Force low spp so noise is visible; CLI --spp can raise it but default is low.
    scene = lc.Scene()
    floor = scene.add_material(lc.Material(base_color=(0.34, 0.33, 0.32), roughness=0.9))
    wall = scene.add_material(lc.Material(base_color=(0.50, 0.48, 0.46), roughness=0.92))
    metal = scene.add_material(
        lc.Material(base_color=(0.88, 0.86, 0.82), metallic=1.0, roughness=0.18)
    )
    glass = scene.add_material(
        lc.Material(
            base_color=(0.92, 0.97, 1.0),
            roughness=0.12,
            transmission=0.95,
            ior=1.5,
            absorption=(0.08, 0.04, 0.02),
        )
    )
    diffuse = scene.add_material(lc.Material(base_color=(0.55, 0.28, 0.18), roughness=0.75))

    scene.add_mesh(lc.make_quad((-2, 0, -2), (4, 0, 0), (0, 0, 4), floor))
    scene.add_mesh(lc.make_quad((-2, 0, -1.5), (4, 0, 0), (0, 2.8, 0), wall))
    scene.add_mesh(lc.make_uv_sphere((-0.35, 0.35, 0.1), 0.35, metal, 40, 20))
    scene.add_mesh(lc.make_uv_sphere((0.45, 0.28, 0.25), 0.28, glass, 40, 20))
    scene.add_mesh(lc.make_box((-0.15, 0.0, -0.55), (0.25, 0.5, -0.15), diffuse))

    scene.add_quad_light((-0.4, 2.5, -0.2), (0.8, 0, 0), (0, 0, 0.6), (8.0, 7.5, 7.0))
    scene.background_top = (0.15, 0.16, 0.20)
    scene.background_bottom = (0.05, 0.05, 0.06)

    camera = lc.Camera(
        eye=(1.6, 1.2, 2.4),
        lookat=(0.05, 0.35, 0.0),
        fov_y_deg=36.0,
        aspect=1.0,
    )
    cfg = lc.RenderConfig(
        width=width,
        height=width,
        spp=spp,
        denoise=on and denoise,
        enable_nee=True,
        output_path=out,
    )
    # When mode=off, always disable denoise regardless of --denoise flag.
    if not on:
        cfg.denoise = False
    lc.Renderer().render(scene, camera, cfg)


def render_flame(mode: str, out: str, width: int, spp: int, denoise: bool) -> None:
    """Fireplace hearth crop: flame volume on vs cold ashes only."""
    on = mode == "on"
    scene = lc.Scene()
    stone = scene.add_material(lc.Material(base_color=(0.38, 0.36, 0.34), roughness=0.88))
    ash = scene.add_material(lc.Material(base_color=(0.14, 0.13, 0.12), roughness=0.95))
    wood = scene.add_material(lc.Material(base_color=(0.30, 0.18, 0.10), roughness=0.78))
    floor = scene.add_material(lc.Material(base_color=(0.22, 0.20, 0.18), roughness=0.9))

    scene.add_mesh(lc.make_quad((-2, 0, -2), (4, 0, 0), (0, 0, 4), floor))
    # Hearth shell (matches fireplace proportions, tighter crop)
    scene.add_mesh(lc.make_box((-0.55, 0.0, -2.05), (0.55, 0.10, -1.15), stone))
    scene.add_mesh(lc.make_box((-0.60, 0.10, -2.05), (-0.40, 1.05, -1.25), stone))
    scene.add_mesh(lc.make_box((0.40, 0.10, -2.05), (0.60, 1.05, -1.25), stone))
    scene.add_mesh(lc.make_box((-0.65, 1.00, -2.10), (0.65, 1.15, -1.15), stone))
    scene.add_mesh(lc.make_box((-0.40, 0.10, -2.00), (0.40, 0.95, -1.90), ash))
    scene.add_mesh(lc.make_box((-0.22, 0.12, -1.65), (0.22, 0.24, -1.45), wood))

    if on:
        scene.add_flame_volume(
            center=(0.0, 0.55, -1.65),
            half_extents=(0.28, 0.42, 0.18),
            emission_scale=(140.0, 55.0, 10.0),
            density_scale=2.6,
            absorption=1.8,
            noise_scale=2.5,
            time=1.65,
            add_proxy_light=True,
        )
    else:
        # Dim fill so OFF frame is not pure black.
        scene.add_quad_light((-0.2, 1.4, -0.8), (0.4, 0, 0), (0, 0, 0.3), (1.2, 1.0, 0.8))

    scene.background_top = (0.01, 0.01, 0.015)
    scene.background_bottom = (0.005, 0.005, 0.008)

    camera = lc.Camera(
        eye=(0.05, 0.85, 0.55),
        lookat=(0.0, 0.55, -1.65),
        up=(0.0, 1.0, 0.0),
        fov_y_deg=42.0,
        aspect=1.0,
    )
    cfg = lc.RenderConfig(
        width=width,
        height=width,
        spp=spp,
        denoise=denoise,
        enable_nee=True,
        output_path=out,
    )
    lc.Renderer().render(scene, camera, cfg)


def render_beer(mode: str, out: str, width: int, spp: int, denoise: bool) -> None:
    """Top-down pool: Beer-Lambert absorption on vs zero (flat water plane)."""
    on = mode == "on"
    scene = lc.Scene()
    seabed = scene.add_material(lc.Material(base_color=(0.16, 0.38, 0.36), roughness=0.92))
    rock = scene.add_material(lc.Material(base_color=(0.58, 0.48, 0.40), roughness=0.75))
    rock2 = scene.add_material(lc.Material(base_color=(0.38, 0.40, 0.36), roughness=0.85))
    absorption = (0.95, 0.28, 0.10) if on else (0.0, 0.0, 0.0)
    water = scene.add_material(
        lc.Material(
            base_color=(0.55, 0.82, 0.90),
            roughness=0.0,
            transmission=1.0,
            ior=1.33,
            absorption=absorption,
        )
    )

    # Deep seabed + rocks; flat water surface (no waves) so depth color is readable.
    scene.add_mesh(lc.make_quad((-4, -2.5, -4), (8, 0, 0), (0, 0, 8), seabed))
    scene.add_mesh(lc.make_uv_sphere((0.0, -1.2, 0.15), 0.55, rock, 40, 24))
    scene.add_mesh(lc.make_uv_sphere((-0.7, -1.6, -0.35), 0.38, rock2, 28, 16))
    scene.add_mesh(lc.make_uv_sphere((0.75, -1.75, 0.45), 0.32, rock, 24, 16))
    scene.add_mesh(lc.make_quad((-2.5, 0.0, -2.5), (5.0, 0, 0), (0, 0, 5.0), water))

    scene.add_quad_light((-1.5, 4.0, -1.5), (3.0, 0, 0), (0, 0, 3.0), (20.0, 22.0, 24.0))
    scene.background_top = (0.60, 0.72, 0.85)
    scene.background_bottom = (0.30, 0.42, 0.52)

    camera = lc.Camera(
        eye=(0.2, 2.4, 3.2),
        lookat=(0.0, -1.0, 0.0),
        up=(0.0, 1.0, 0.0),
        fov_y_deg=42.0,
        aspect=1.0,
    )
    cfg = lc.RenderConfig(
        width=width,
        height=width,
        spp=spp,
        denoise=False,  # keep depth color; denoiser softens absorption contrast
        enable_nee=True,
        output_path=out,
    )
    lc.Renderer().render(scene, camera, cfg)


RENDERERS = {
    "normal": render_normal,
    "nee": render_nee,
    "denoiser": render_denoiser,
    "flame": render_flame,
    "beer": render_beer,
}


def default_spp(feature: str) -> int:
    if feature == "denoiser":
        return 24
    if feature == "nee":
        return 128
    return 192


def main() -> int:
    parser = argparse.ArgumentParser(description="LumenCore gallery feature compare renders")
    parser.add_argument("--feature", required=True, choices=FEATURES)
    parser.add_argument("--mode", required=True, choices=("on", "off"))
    parser.add_argument("--out", default="")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--spp", type=int, default=-1)
    parser.add_argument("--denoise", type=int, default=1, help="1=on, 0=off (denoiser feature overrides)")
    args = parser.parse_args()

    out = args.out or f"outputs/gallery/compare/{args.feature}_{args.mode}.avif"
    spp = args.spp if args.spp > 0 else default_spp(args.feature)
    Path(out).parent.mkdir(parents=True, exist_ok=True)

    print(
        f"[gallery_compare] {args.feature} {args.mode} → {out} "
        f"@ {args.width}×{args.width} spp={spp}",
        flush=True,
    )
    RENDERERS[args.feature](args.mode, out, args.width, spp, bool(args.denoise))
    print(f"[gallery_compare] done {args.feature}_{args.mode}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
