#!/usr/bin/env python3
"""PhysX + OptiX dual-stack demo: brick tower collapse after a metal ball impact."""
from __future__ import annotations

import math
import shutil
import sys
from pathlib import Path

import lumencore as lc


def quat_axis_angle(axis: tuple[float, float, float], angle_rad: float) -> tuple[float, float, float, float]:
    ax, ay, az = axis
    n = math.sqrt(ax * ax + ay * ay + az * az)
    if n < 1e-8:
        return (0.0, 0.0, 0.0, 1.0)
    ax, ay, az = ax / n, ay / n, az / n
    s = math.sin(angle_rad * 0.5)
    return (ax * s, ay * s, az * s, math.cos(angle_rad * 0.5))


def brick_color(ix: int, iy: int, iz: int) -> tuple[float, float, float]:
    palette = [
        (0.72, 0.28, 0.22),
        (0.78, 0.48, 0.28),
        (0.55, 0.32, 0.22),
        (0.82, 0.62, 0.42),
        (0.42, 0.38, 0.36),
        (0.65, 0.45, 0.35),
    ]
    return palette[(ix * 3 + iy * 5 + iz * 7) % len(palette)]


def build_render_scene(world: lc.PhysXWorld, actors: list[dict]) -> lc.Scene:
    scene = lc.Scene()
    mat_ids = {
        "floor": scene.add_material(lc.Material(base_color=(0.42, 0.42, 0.44), roughness=0.85)),
        "ramp": scene.add_material(lc.Material(base_color=(0.35, 0.36, 0.38), roughness=0.7)),
        "wall": scene.add_material(lc.Material(base_color=(0.55, 0.55, 0.58), roughness=0.8)),
        "metal": scene.add_material(lc.Material(base_color=(0.92, 0.92, 0.95), metallic=1.0, roughness=0.12)),
        "light": scene.add_material(lc.Material(base_color=(0, 0, 0), roughness=1.0, emission=(18, 17, 15))),
    }
    brick_cache: dict[tuple[float, float, float], int] = {}

    def brick_mat(color: tuple[float, float, float]) -> int:
        if color not in brick_cache:
            brick_cache[color] = scene.add_material(
                lc.Material(base_color=color, roughness=0.78, metallic=0.0)
            )
        return brick_cache[color]

    for entry in actors:
        pose = world.get_pose(entry["id"])
        kind = entry["kind"]
        if kind == "static_box":
            scene.add_mesh(lc.apply_pose_to_box_mesh(entry["half"], pose, mat_ids[entry["mat"]]))
        elif kind == "brick":
            scene.add_mesh(lc.apply_pose_to_box_mesh(entry["half"], pose, brick_mat(entry["color"])))
        elif kind == "sphere":
            scene.add_mesh(
                lc.apply_pose_to_sphere_mesh(entry["radius"], pose, mat_ids["metal"], 40, 20)
            )

    scene.add_mesh(lc.make_quad((-1.5, 7.5, -1.5), (3.0, 0, 0), (0, 0, 3.0), mat_ids["light"]))
    scene.add_quad_light((-1.5, 7.5, -1.5), (3.0, 0, 0), (0, 0, 3.0), (18, 17, 15))
    scene.add_quad_light((4.0, 5.0, -3.0), (0.0, 0, 2.0), (0, -2.0, 0), (6, 6.5, 8))

    scene.background_top = (0.55, 0.62, 0.75)
    scene.background_bottom = (0.18, 0.18, 0.22)
    return scene


def main() -> int:
    out_arg = Path(sys.argv[1] if len(sys.argv) > 1 else "outputs/physx_collapse")
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 128
    denoise = (int(sys.argv[3]) != 0) if len(sys.argv) > 3 else True

    if out_arg.suffix.lower() == ".png":
        hero_path = out_arg
        frames_dir = out_arg.parent / out_arg.stem
    else:
        frames_dir = out_arg
        hero_path = out_arg.parent / f"{out_arg.name}.png"
    frames_dir.mkdir(parents=True, exist_ok=True)
    hero_path.parent.mkdir(parents=True, exist_ok=True)

    world = lc.PhysXWorld()
    world.init()
    print(f"[physx_collapse] PhysX backend: {world.backend()}", flush=True)

    actors: list[dict] = []

    ground_half = (8.0, 0.25, 8.0)
    actors.append(
        {
            "id": world.add_static_box(ground_half, lc.Pose(position=(0.0, -0.25, 0.0))),
            "kind": "static_box",
            "half": ground_half,
            "mat": "floor",
        }
    )

    ramp_half = (3.5, 0.12, 1.2)
    ramp_pose = lc.Pose(
        position=(-4.2, 1.6, 0.0),
        quat=quat_axis_angle((0.0, 0.0, 1.0), math.radians(-28.0)),
    )
    actors.append(
        {
            "id": world.add_static_box(ramp_half, ramp_pose),
            "kind": "static_box",
            "half": ramp_half,
            "mat": "ramp",
        }
    )

    for half, pos in [
        ((0.15, 1.5, 4.0), (7.5, 1.5, 0.0)),
        ((0.15, 1.5, 4.0), (-7.5, 1.5, 0.0)),
        ((4.0, 1.5, 0.15), (0.0, 1.5, 7.5)),
        ((4.0, 1.5, 0.15), (0.0, 1.5, -7.5)),
    ]:
        actors.append(
            {
                "id": world.add_static_box(half, lc.Pose(position=pos)),
                "kind": "static_box",
                "half": half,
                "mat": "wall",
            }
        )

    nx, ny, nz = 8, 12, 8
    brick_half = (0.18, 0.12, 0.18)
    gap = 0.01
    ox = -(nx - 1) * (brick_half[0] * 2 + gap) * 0.5
    oz = -(nz - 1) * (brick_half[2] * 2 + gap) * 0.5
    for iy in range(ny):
        for ix in range(nx):
            for iz in range(nz):
                x = ox + ix * (brick_half[0] * 2 + gap) + 1.2
                y = brick_half[1] + iy * (brick_half[1] * 2 + gap)
                z = oz + iz * (brick_half[2] * 2 + gap)
                aid = world.add_dynamic_box(brick_half, 1.2, lc.Pose(position=(x, y, z)))
                actors.append(
                    {
                        "id": aid,
                        "kind": "brick",
                        "half": brick_half,
                        "color": brick_color(ix, iy, iz),
                    }
                )

    ball_r = 0.35
    for pos, vel in [
        ((-6.6, 3.35, 0.15), (2.8, -0.2, 0.0)),
        ((-6.9, 3.55, -0.35), (2.5, -0.1, 0.4)),
    ]:
        aid = world.add_dynamic_sphere(ball_r, 40.0, lc.Pose(position=pos))
        world.set_linear_velocity(aid, vel)
        actors.append({"id": aid, "kind": "sphere", "radius": ball_r})

    camera = lc.Camera(
        eye=(7.5, 4.2, 9.5),
        lookat=(0.8, 1.4, 0.0),
        up=(0.0, 1.0, 0.0),
        fov_y_deg=38.0,
        aspect=2560 / 1440,
    )

    sim_steps = 180
    frame_every = 15
    hero_step = 135  # mid-collapse after ball impact
    renderer = lc.Renderer()
    frame_paths: list[Path] = []

    step_i = 0
    frame_idx = 0
    while step_i <= sim_steps:
        if step_i % frame_every == 0:
            scene = build_render_scene(world, actors)
            out_png = frames_dir / f"frame_{frame_idx:04d}.png"
            cfg = lc.RenderConfig(
                width=2560,
                height=1440,
                spp=spp,
                denoise=denoise,
                output_path=str(out_png),
            )
            print(
                f"[physx_collapse] render frame {frame_idx} @ sim step {step_i} → {out_png}",
                flush=True,
            )
            renderer.render(scene, camera, cfg)
            frame_paths.append(out_png)
            if step_i == hero_step:
                shutil.copyfile(out_png, hero_path)
                print(f"[physx_collapse] hero image → {hero_path}", flush=True)
            frame_idx += 1

        if step_i == sim_steps:
            break
        world.step(1.0 / 60.0, 1)
        step_i += 1

    try:
        from PIL import Image  # type: ignore

        picks = frame_paths[:: max(1, len(frame_paths) // 6)][:6]
        if picks:
            imgs = [Image.open(p) for p in picks]
            w, h = imgs[0].size
            sheet = Image.new("RGB", (w * len(imgs), h))
            for i, im in enumerate(imgs):
                sheet.paste(im, (i * w, 0))
            sheet_path = frames_dir / "contact_sheet.png"
            sheet.save(sheet_path)
            print(f"[physx_collapse] contact sheet → {sheet_path}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[physx_collapse] contact sheet skipped ({exc})", flush=True)

    print(f"[physx_collapse] done. frames={len(frame_paths)} backend={world.backend()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
