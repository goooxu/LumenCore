#!/usr/bin/env python3
"""LumenCore video demo: coastal beacon loop (HDR AV1, 5 s / 720p / 24 fps).

Animates tide-pool wave phase, flame volume time, and a gentle camera orbit.
No PhysX. Uses ``python/video_render.py`` for the frame loop + ffmpeg mux.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import lumencore as lc

# Allow ``from video_render import ...`` when run as a scene script.
_PY_ROOT = Path(__file__).resolve().parents[1]
if str(_PY_ROOT) not in sys.path:
    sys.path.insert(0, str(_PY_ROOT))

from video_render import encode_hdr_av1, render_frames  # noqa: E402


WIDTH = 1280
HEIGHT = 720
FPS = 24
DURATION_S = 5
FRAME_COUNT = FPS * DURATION_S  # 120


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


def camera_for_frame(frame: int, frame_count: int) -> lc.Camera:
    """Partial orbit (~50°) around the platform look-at over the clip."""
    lookat = (-0.15, 0.95, -0.35)
    t = frame / max(1, frame_count - 1)
    # Sweep from seaward right toward the flame beacon on the left.
    yaw0 = math.radians(42.0)
    yaw1 = math.radians(-8.0)
    yaw = yaw0 + (yaw1 - yaw0) * t
    radius = 6.35
    height = 1.48 + 0.12 * math.sin(t * math.pi)
    eye = (
        lookat[0] + radius * math.sin(yaw),
        height,
        lookat[2] + radius * math.cos(yaw),
    )
    return lc.Camera(
        eye=eye,
        lookat=lookat,
        up=(0.0, 1.0, 0.0),
        fov_y_deg=36.0,
        aspect=WIDTH / HEIGHT,
    )


def build_scene(water_time: float, flame_time: float) -> lc.Scene:
    scene = lc.Scene()

    hdri = resolve_asset("assets/env/dusk.hdr")
    if Path(hdri).is_file():
        scene.load_env_map(hdri)

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

    spot_tex = scene.add_texture(resolve_asset("assets/models/spot_texture.avif"))

    # Platform
    scene.add_mesh(lc.make_box((-4.5, -0.35, -3.5), (4.5, 0.0, 3.2), concrete))
    scene.add_mesh(lc.make_quad((-4.5, 0.0, -3.5), (9.0, 0.0, 0.0), (0.0, 0.0, 6.7), deck))
    scene.add_mesh(lc.make_box((-4.5, -1.2, 3.0), (4.5, 0.0, 3.5), concrete))
    for x in (-4.3, 4.3):
        scene.add_mesh(lc.make_box((x - 0.04, 0.0, -3.2), (x + 0.04, 1.05, 2.8), rail))
    scene.add_mesh(lc.make_box((-4.3, 0.95, -3.2), (4.3, 1.05, -3.1), rail))
    scene.add_mesh(lc.make_box((-4.3, 0.95, 2.7), (4.3, 1.05, 2.8), rail))

    # Central desk + instruments
    scene.add_mesh(lc.make_box((-0.85, 0.0, -0.55), (0.85, 0.78, 0.55), rough_metal))
    scene.add_mesh(lc.make_box((-0.90, 0.78, -0.60), (0.90, 0.84, 0.60), chrome))
    scene.add_mesh(lc.make_uv_sphere((-0.45, 1.05, 0.0), 0.18, ceramic, 36, 18))
    scene.add_mesh(lc.make_box((-0.12, 0.84, -0.12), (0.12, 1.15, 0.12), chrome))
    scene.add_mesh(lc.make_uv_sphere((0.42, 1.08, 0.05), 0.16, optical, 40, 20))
    scene.add_mesh(lc.make_box((0.25, 0.84, -0.35), (0.55, 0.92, -0.05), panel))

    # Tide pool
    scene.add_mesh(lc.make_box((-2.4, -0.05, 1.45), (2.4, 0.06, 2.95), rock))
    scene.add_mesh(
        lc.make_water_surface(
            center=(0.0, 0.10, 2.20),
            half_extents_xz=(2.15, 0.0, 0.65),
            y_base=0.10,
            material_id=water_m,
            nx=64,
            nz=32,
            time=water_time,
        )
    )
    scene.add_mesh(lc.make_uv_sphere((-0.6, -0.15, 2.15), 0.18, rock, 24, 14))
    scene.add_mesh(lc.make_uv_sphere((0.9, -0.10, 2.35), 0.14, rock, 20, 12))

    # Flame beacon
    scene.add_mesh(lc.make_box((-3.85, 0.0, -3.15), (-3.15, 0.55, -2.45), beacon_stone))
    scene.add_mesh(lc.make_box((-3.75, 0.55, -3.05), (-3.25, 1.85, -2.55), beacon_stone))
    scene.add_flame_volume(
        center=(-3.50, 2.25, -2.80),
        half_extents=(0.22, 0.48, 0.18),
        emission_scale=(160.0, 60.0, 12.0),
        density_scale=2.8,
        absorption=1.6,
        noise_scale=2.6,
        time=flame_time,
        add_proxy_light=True,
    )

    # Spot on the desk (single character keeps the 120-frame budget manageable)
    spot_scale = 0.58
    spot_ymin = -0.736784
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

    scene.add_spot_light(
        position=(0.2, 2.8, 1.0),
        direction=(-0.05, -1.0, -0.35),
        emission=(28.0, 32.0, 48.0),
        angle_deg=26.0,
        penumbra_deg=14.0,
    )
    scene.add_spot_light(
        position=(-2.8, 2.7, -1.2),
        direction=(0.25, -0.85, -0.35),
        emission=(70.0, 42.0, 18.0),
        angle_deg=22.0,
        penumbra_deg=12.0,
    )
    scene.add_quad_light(
        (0.55, 0.96, -0.20),
        (0.35, 0.0, 0.0),
        (0.0, 0.0, 0.35),
        (3.5, 2.8, 1.8),
    )

    scene.background_top = (0.10, 0.12, 0.22)
    scene.background_bottom = (0.04, 0.035, 0.04)
    return scene


def main() -> int:
    # CLI: [out.mkv] [spp] [denoise=1|0] [frames] [fps]
    out_video = Path(sys.argv[1] if len(sys.argv) > 1 else "outputs/beacon_loop.mkv")
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 64
    denoise = (int(sys.argv[3]) != 0) if len(sys.argv) > 3 else True
    frame_count = int(sys.argv[4]) if len(sys.argv) > 4 else FRAME_COUNT
    fps = float(sys.argv[5]) if len(sys.argv) > 5 else float(FPS)

    frames_dir = out_video.with_suffix("")  # outputs/beacon_loop/
    frames_dir.mkdir(parents=True, exist_ok=True)
    out_video.parent.mkdir(parents=True, exist_ok=True)

    renderer = lc.Renderer()

    def render_one(frame: int, path: Path) -> None:
        # ~1.5 water cycles and lively flame scroll over 5 s
        water_time = 1.0 + frame * (3.2 / max(1, frame_count - 1))
        flame_time = 1.5 + frame * (2.8 / max(1, frame_count - 1))
        scene = build_scene(water_time, flame_time)
        camera = camera_for_frame(frame, frame_count)
        cfg = lc.RenderConfig(
            width=WIDTH,
            height=HEIGHT,
            spp=spp,
            denoise=denoise,
            enable_nee=True,
            output_path=str(path),
        )
        print(
            f"[beacon_loop] frame {frame + 1}/{frame_count} "
            f"water={water_time:.2f} flame={flame_time:.2f} → {path}",
            flush=True,
        )
        renderer.render(scene, camera, cfg)

    print(
        f"[beacon_loop] {frame_count} frames @ {fps:g} fps, {WIDTH}x{HEIGHT}, "
        f"spp={spp}, denoise={int(denoise)}",
        flush=True,
    )
    render_frames(render_one, frames_dir, frame_count)
    encode_hdr_av1(frames_dir, out_video, fps=fps)
    print(f"[beacon_loop] done → {out_video}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
