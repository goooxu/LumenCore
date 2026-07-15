#!/usr/bin/env python3
"""Materials chart scene for LumenCore."""
from __future__ import annotations

import sys

import lumencore as lc


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "materials_ball.png"
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    denoise = (int(sys.argv[3]) != 0) if len(sys.argv) > 3 else True

    scene = lc.Scene()
    ground = scene.add_material(lc.Material(base_color=(0.25, 0.25, 0.28), roughness=0.9))
    scene.add_mesh(lc.make_quad((-4, 0, -4), (8, 0, 0), (0, 0, 8), ground))

    colors = [
        (0.9, 0.2, 0.2),
        (0.2, 0.8, 0.3),
        (0.2, 0.4, 0.95),
        (0.95, 0.85, 0.2),
        (0.9, 0.9, 0.95),
        (0.8, 0.5, 0.2),
    ]

    idx = 0
    for row in range(3):
        for col in range(4):
            if row == 0:
                mat = lc.Material(base_color=colors[idx % 6], metallic=0.0, roughness=0.15 + 0.25 * col)
            elif row == 1:
                mat = lc.Material(base_color=colors[idx % 6], metallic=1.0, roughness=0.05 + 0.25 * col)
            else:
                mat = lc.Material(
                    base_color=(1, 1, 1),
                    transmission=1.0,
                    ior=1.1 + 0.2 * col,
                    roughness=0.0,
                )
            mid = scene.add_material(mat)
            x = -1.5 + col * 1.0
            z = -0.5 + row * 1.0
            scene.add_mesh(lc.make_uv_sphere((x, 0.35, z), 0.32, mid))
            idx += 1

    light_corner = (-1.0, 3.5, -1.0)
    light_u = (2.0, 0, 0)
    light_v = (0, 0, 2.0)
    light_mat = scene.add_material(lc.Material(base_color=(0, 0, 0), roughness=1.0, emission=(20, 18, 14)))
    scene.add_mesh(lc.make_quad(light_corner, light_u, light_v, light_mat))
    scene.add_quad_light(light_corner, light_u, light_v, (20, 18, 14))

    scene.background_top = (0.55, 0.65, 0.85)
    scene.background_bottom = (0.2, 0.2, 0.25)

    camera = lc.Camera(eye=(0.0, 2.2, 4.5), lookat=(0.0, 0.4, 0.3), fov_y_deg=35, aspect=16 / 9)
    cfg = lc.RenderConfig(width=2560, height=1440, spp=spp, denoise=denoise, output_path=out)
    lc.Renderer().render(scene, camera, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
