#!/usr/bin/env python3
"""Stone pool with procedural wavy water and above-water reflections."""
from __future__ import print_function

import sys

import lumencore as lc


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "water_pool.png"
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    denoise = (int(sys.argv[3]) != 0) if len(sys.argv) > 3 else True
    time = float(sys.argv[4]) if len(sys.argv) > 4 else 1.25

    scene = lc.Scene()

    stone = scene.add_material(lc.Material(base_color=(0.40, 0.38, 0.36), roughness=0.88))
    stone_dark = scene.add_material(lc.Material(base_color=(0.26, 0.25, 0.24), roughness=0.9))
    wood = scene.add_material(lc.Material(base_color=(0.48, 0.30, 0.14), roughness=0.72))
    tile = scene.add_material(lc.Material(base_color=(0.50, 0.58, 0.55), roughness=0.5))
    sand = scene.add_material(lc.Material(base_color=(0.62, 0.58, 0.50), roughness=0.95))
    water = scene.add_material(
        lc.Material(
            base_color=(0.7, 0.88, 0.92),
            roughness=0.0,
            transmission=1.0,
            ior=1.33,
            absorption=(0.28, 0.10, 0.06),
        )
    )
    chrome = scene.add_material(
        lc.Material(base_color=(0.95, 0.95, 0.98), metallic=1.0, roughness=0.04)
    )
    accent = scene.add_material(lc.Material(base_color=(0.90, 0.22, 0.18), roughness=0.35))
    accent_b = scene.add_material(lc.Material(base_color=(0.15, 0.45, 0.85), roughness=0.4))

    # Ground
    scene.add_mesh(lc.make_quad((-8, 0, -8), (16, 0, 0), (0, 0, 16), sand))

    # Full four-walled stone pool (inner approx x,z in [-1.7,1.7]x[-1.1,1.1])
    scene.add_mesh(lc.make_box((-2.0, 0.0, -1.4), (2.0, 0.08, 1.4), tile))  # floor
    scene.add_mesh(lc.make_box((-2.0, 0.08, -1.4), (2.0, 0.70, -1.1), stone))  # -Z
    scene.add_mesh(lc.make_box((-2.0, 0.08, 1.1), (2.0, 0.70, 1.4), stone))  # +Z
    scene.add_mesh(lc.make_box((-2.0, 0.08, -1.1), (-1.7, 0.70, 1.1), stone))  # -X
    scene.add_mesh(lc.make_box((1.7, 0.08, -1.1), (2.0, 0.70, 1.1), stone))  # +X
    # Coping rim only (NOT a solid slab — that previously covered the water)
    scene.add_mesh(lc.make_box((-2.2, 0.70, -1.6), (2.2, 0.80, -1.4), stone_dark))  # -Z
    scene.add_mesh(lc.make_box((-2.2, 0.70, 1.4), (2.2, 0.80, 1.6), stone_dark))  # +Z
    scene.add_mesh(lc.make_box((-2.2, 0.70, -1.4), (-2.0, 0.80, 1.4), stone_dark))  # -X
    scene.add_mesh(lc.make_box((2.0, 0.70, -1.4), (2.2, 0.80, 1.4), stone_dark))  # +X
    # Far deck (-Z) for reflection props
    scene.add_mesh(lc.make_box((-2.4, 0.80, -2.7), (2.4, 0.88, -1.6), wood))

    # Procedural water surface (generated each run; phase = time)
    water_mesh = lc.make_water_surface(
        center=(0.0, 0.0, 0.0),
        half_extents_xz=(1.65, 0.0, 1.05),
        y_base=0.58,
        material_id=water,
        nx=96,
        nz=64,
        time=time,
    )
    scene.add_mesh(water_mesh)
    print("Procedural water surface time={}".format(time))

    # Above-water reflection subjects on far deck (clear of water edge)
    scene.add_mesh(lc.make_uv_sphere((-0.55, 1.35, -2.15), 0.38, chrome))
    scene.add_mesh(lc.make_uv_sphere((0.70, 1.28, -2.20), 0.34, accent))
    # Thin posts so spheres read as standing above water
    scene.add_mesh(lc.make_box((-0.58, 0.88, -2.18), (-0.52, 1.10, -2.12), stone_dark))
    scene.add_mesh(lc.make_box((0.67, 0.88, -2.23), (0.73, 1.06, -2.17), stone_dark))
    # One submerged accent for refraction only (pool center, not at edge)
    scene.add_mesh(lc.make_uv_sphere((0.15, 0.22, 0.1), 0.18, accent_b))

    # Soft sun
    light_corner = (3.0, 5.8, -0.5)
    light_u = (2.2, 0.0, 0.3)
    light_v = (-0.2, 0.0, 2.2)
    light_mat = scene.add_material(
        lc.Material(base_color=(0, 0, 0), roughness=1.0, emission=(36, 34, 28))
    )
    scene.add_mesh(lc.make_quad(light_corner, light_u, light_v, light_mat))
    scene.add_quad_light(light_corner, light_u, light_v, (36, 34, 28))
    # Fill from side so deck props light the water
    scene.add_spot_light(
        position=(-1.5, 3.8, 2.0),
        direction=(0.3, -0.75, -0.6),
        emission=(70, 64, 55),
        angle_deg=32.0,
        penumbra_deg=14.0,
    )

    scene.background_top = (0.42, 0.60, 0.88)
    scene.background_bottom = (0.58, 0.64, 0.72)

    # Grazing view across open water toward far-deck props / reflections
    camera = lc.Camera(
        eye=(0.1, 1.05, 3.2),
        lookat=(0.05, 0.70, -0.9),
        fov_y_deg=40,
        aspect=16 / 9,
        aperture=0.008,
        focus_dist=3.8,
    )
    cfg = lc.RenderConfig(width=2560, height=1440, spp=spp, denoise=denoise, output_path=out)
    lc.Renderer().render(scene, camera, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
