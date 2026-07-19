#!/usr/bin/env python3
"""Cornell Box scene for LumenCore."""
from __future__ import annotations

import sys

import lumencore as lc


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "cornell.avif"
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    denoise = (int(sys.argv[3]) != 0) if len(sys.argv) > 3 else True

    scene = lc.Scene()
    white = scene.add_material(lc.Material(base_color=(0.73, 0.73, 0.73), roughness=0.8))
    red = scene.add_material(lc.Material(base_color=(0.65, 0.05, 0.05), roughness=0.8))
    green = scene.add_material(lc.Material(base_color=(0.12, 0.45, 0.15), roughness=0.8))
    light_mat = scene.add_material(
        lc.Material(base_color=(0, 0, 0), roughness=1.0, emission=(15, 15, 12))
    )
    glass = scene.add_material(lc.Material(base_color=(1, 1, 1), roughness=0.0, transmission=1.0, ior=1.5))
    metal = scene.add_material(lc.Material(base_color=(0.95, 0.85, 0.55), metallic=1.0, roughness=0.05))

    scene.add_mesh(lc.make_quad((0, 0, 0), (1, 0, 0), (0, 0, 1), white))
    scene.add_mesh(lc.make_quad((0, 1, 0), (1, 0, 0), (0, 0, 1), white))
    scene.add_mesh(lc.make_quad((0, 0, 1), (1, 0, 0), (0, 1, 0), white))
    scene.add_mesh(lc.make_quad((0, 0, 0), (0, 0, 1), (0, 1, 0), red))
    scene.add_mesh(lc.make_quad((1, 0, 0), (0, 0, 1), (0, 1, 0), green))

    light_corner = (0.35, 0.999, 0.35)
    light_u = (0.3, 0, 0)
    light_v = (0, 0, 0.3)
    # Emissive panel + QuadLight with MIS (visible lamp, no double-count).
    scene.add_mesh(lc.make_quad(light_corner, light_u, light_v, light_mat))
    scene.add_quad_light(light_corner, light_u, light_v, (15, 15, 12), use_mis=True)

    scene.add_mesh(lc.make_box((0.15, 0.0, 0.55), (0.4, 0.4, 0.8), white))
    scene.add_mesh(lc.make_uv_sphere((0.7, 0.2, 0.35), 0.2, glass))
    scene.add_mesh(lc.make_uv_sphere((0.35, 0.15, 0.3), 0.15, metal))

    scene.background_top = (0, 0, 0)
    scene.background_bottom = (0, 0, 0)

    camera = lc.Camera(eye=(0.5, 0.5, -1.35), lookat=(0.5, 0.5, 0.5), fov_y_deg=40, aspect=1.0)
    cfg = lc.RenderConfig(width=2048, height=2048, spp=spp, denoise=denoise, output_path=out)
    lc.Renderer().render(scene, camera, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
