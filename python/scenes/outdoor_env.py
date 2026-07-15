#!/usr/bin/env python3
"""Outdoor environment scene for LumenCore."""
from __future__ import annotations

import sys

import lumencore as lc


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "outdoor_env.png"
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    denoise = (int(sys.argv[3]) != 0) if len(sys.argv) > 3 else True

    scene = lc.Scene()
    grass = scene.add_material(lc.Material(base_color=(0.2, 0.35, 0.15), roughness=0.95))
    stone = scene.add_material(lc.Material(base_color=(0.45, 0.45, 0.48), roughness=0.7))
    chrome = scene.add_material(lc.Material(base_color=(0.95, 0.95, 0.98), metallic=1.0, roughness=0.02))
    glass = scene.add_material(lc.Material(base_color=(1, 1, 1), roughness=0.0, transmission=1.0, ior=1.5))
    warm = scene.add_material(lc.Material(base_color=(0.85, 0.45, 0.2), roughness=0.4))

    scene.add_mesh(lc.make_quad((-20, 0, -20), (40, 0, 0), (0, 0, 40), grass))
    scene.add_mesh(lc.make_box((-1.2, 0, -0.4), (-0.3, 1.6, 0.5), stone))
    scene.add_mesh(lc.make_uv_sphere((0.8, 0.6, 0.2), 0.6, chrome))
    scene.add_mesh(lc.make_uv_sphere((-0.1, 0.4, 1.4), 0.4, glass))
    scene.add_mesh(lc.make_uv_sphere((1.8, 0.35, 1.2), 0.35, warm))

    light_corner = (4.0, 8.0, -2.0)
    light_u = (2.5, 0, 0.5)
    light_v = (0, 0, 2.5)
    light_mat = scene.add_material(lc.Material(base_color=(0, 0, 0), roughness=1.0, emission=(40, 36, 28)))
    scene.add_mesh(lc.make_quad(light_corner, light_u, light_v, light_mat))
    scene.add_quad_light(light_corner, light_u, light_v, (40, 36, 28))

    scene.background_top = (0.45, 0.65, 0.95)
    scene.background_bottom = (0.75, 0.8, 0.85)

    camera = lc.Camera(
        eye=(-2.8, 1.8, 4.2),
        lookat=(0.3, 0.5, 0.4),
        fov_y_deg=40,
        aspect=16 / 9,
        aperture=0.04,
        focus_dist=4.5,
    )
    cfg = lc.RenderConfig(width=2560, height=1440, spp=spp, denoise=denoise, output_path=out)
    lc.Renderer().render(scene, camera, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
