#!/usr/bin/env python3
"""GGX studio showcase: metal / dielectric / rough-glass rows under HDRI."""
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
    out = sys.argv[1] if len(sys.argv) > 1 else "ggx_studio.png"
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    denoise = (int(sys.argv[3]) != 0) if len(sys.argv) > 3 else True

    scene = lc.Scene()
    env_path = resolve_asset("assets/env/studio.hdr")
    scene.load_env_map(env_path)
    print("Loaded env", env_path)

    ground = scene.add_material(
        lc.Material(base_color=(0.18, 0.18, 0.20), roughness=0.65, metallic=0.0)
    )
    scene.add_mesh(lc.make_quad((-6, 0, -6), (12, 0, 0), (0, 0, 12), ground))

    # Metal row: chrome-ish, roughness 0.02 → 0.85
    metal_color = (0.92, 0.93, 0.96)
    for i in range(6):
        rough = 0.02 + 0.16 * i
        mat = scene.add_material(
            lc.Material(base_color=metal_color, metallic=1.0, roughness=rough)
        )
        x = -2.5 + i * 1.0
        scene.add_mesh(lc.make_uv_sphere((x, 0.45, 0.0), 0.42, mat))

    # Dielectric / colored row with rising metallic
    colors = [
        (0.75, 0.15, 0.12),
        (0.85, 0.55, 0.12),
        (0.15, 0.55, 0.25),
        (0.15, 0.35, 0.85),
        (0.55, 0.25, 0.75),
        (0.9, 0.9, 0.92),
    ]
    for i in range(6):
        metallic = i / 5.0
        mat = scene.add_material(
            lc.Material(base_color=colors[i], metallic=metallic, roughness=0.25)
        )
        x = -2.5 + i * 1.0
        scene.add_mesh(lc.make_uv_sphere((x, 0.45, 1.5), 0.38, mat))

    # Glass row: roughness 0.02 → ~0.55 (GGX microfacet transmission)
    for i in range(6):
        rough = 0.02 + 0.10 * i
        mat = scene.add_material(
            lc.Material(
                base_color=(1.0, 1.0, 1.0),
                roughness=rough,
                transmission=1.0,
                ior=1.5,
            )
        )
        x = -2.5 + i * 1.0
        scene.add_mesh(lc.make_uv_sphere((x, 0.45, -1.5), 0.40, mat))

    # Soft fill so shadowed sides aren't black (HDRI is primary)
    scene.add_spot_light(
        position=(0.0, 4.0, 3.0),
        direction=(0.0, -0.85, -0.4),
        emission=(4.0, 4.2, 4.5),
        angle_deg=50.0,
        penumbra_deg=20.0,
    )

    scene.background_top = (0.05, 0.06, 0.08)
    scene.background_bottom = (0.02, 0.02, 0.025)

    camera = lc.Camera(
        eye=(0.0, 2.2, 6.2),
        lookat=(0.0, 0.55, 0.3),
        fov_y_deg=36,
        aspect=16 / 9,
    )
    cfg = lc.RenderConfig(width=2560, height=1440, spp=spp, denoise=denoise, output_path=out)
    lc.Renderer().render(scene, camera, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
