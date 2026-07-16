#!/usr/bin/env python3
"""Dark stone fireplace lit by a procedural OptiX flame volume."""
from __future__ import annotations

import sys

import lumencore as lc


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
    # Floor
    scene.add_mesh(lc.make_quad((-2.4, 0, -2.2), (4.8, 0, 0), (0, 0, 4.4), wood))
    # Back wall
    scene.add_mesh(lc.make_quad((-2.4, 0, -2.0), (4.8, 0, 0), (0, 2.6, 0), plaster))
    # Left / right walls
    scene.add_mesh(lc.make_quad((-2.4, 0, -2.0), (0, 0, 4.0), (0, 2.6, 0), plaster))
    scene.add_mesh(lc.make_quad((2.4, 0, 2.0), (0, 0, -4.0), (0, 2.6, 0), plaster))
    # Ceiling
    scene.add_mesh(lc.make_quad((-2.4, 2.6, -2.0), (4.8, 0, 0), (0, 0, 4.0), stone_dark))

    # Fireplace surround
    # Hearth slab
    scene.add_mesh(lc.make_box((-0.75, 0.0, -1.95), (0.75, 0.12, -1.15), stone))
    # Side pillars
    scene.add_mesh(lc.make_box((-0.85, 0.12, -1.95), (-0.55, 1.35, -1.25), brick))
    scene.add_mesh(lc.make_box((0.55, 0.12, -1.95), (0.85, 1.35, -1.25), brick))
    # Mantel
    scene.add_mesh(lc.make_box((-0.95, 1.30, -2.00), (0.95, 1.48, -1.15), stone))
    # Inner back of firebox
    scene.add_mesh(lc.make_box((-0.55, 0.12, -1.95), (0.55, 1.30, -1.85), ash))
    # Inner sides
    scene.add_mesh(lc.make_box((-0.55, 0.12, -1.85), (-0.48, 1.25, -1.30), ash))
    scene.add_mesh(lc.make_box((0.48, 0.12, -1.85), (0.55, 1.25, -1.30), ash))
    # Firebox floor / grate ash
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

    # Props lit by the fire
    scene.add_mesh(lc.make_uv_sphere((-1.15, 0.22, -0.55), 0.22, pottery, 40, 20))
    scene.add_mesh(lc.make_box((1.05, 0.0, -0.35), (1.45, 0.55, 0.05), metal))
    scene.add_mesh(lc.make_uv_sphere((1.25, 0.72, -0.15), 0.18, metal, 36, 18))
    # Andiron tips
    scene.add_mesh(lc.make_box((-0.40, 0.18, -1.40), (-0.34, 0.42, -1.34), metal))
    scene.add_mesh(lc.make_box((0.34, 0.18, -1.40), (0.40, 0.42, -1.34), metal))

    # Procedural volumetric flame (primary look) + auto NEE proxy light
    # Tall narrow AABB for sparse filament tongues
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
    # Warm fill so the room reads clearly under the fire key
    scene.add_quad_light(
        (-0.28, 0.45, -1.28),
        (0.56, 0.0, 0.0),
        (0.0, 0.35, 0.0),
        (90.0, 36.0, 6.0),
    )

    # Nearly black environment — fire is the key light
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
