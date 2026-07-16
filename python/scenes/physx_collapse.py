#!/usr/bin/env python3
"""PhysX + OptiX dual-stack demo: brick tower collapse after a glass fireball impact."""
from __future__ import annotations

import math
import os
import shutil
import sys
from pathlib import Path

import lumencore as lc

# Cached after first build_render_scene (material IDs stay stable across frames).
_MASCOT_TEMPLATES: dict[str, lc.Mesh] | None = None


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
        (0.50, 0.20, 0.15),
        (0.55, 0.34, 0.20),
        (0.38, 0.22, 0.15),
        (0.57, 0.43, 0.29),
        (0.29, 0.27, 0.25),
        (0.45, 0.32, 0.24),
    ]
    return palette[(ix * 3 + iy * 5 + iz * 7) % len(palette)]


def _scale_mascot_to_brick(mesh: lc.Mesh, model_height: float, model_ymin: float, target_h: float) -> lc.Mesh:
    """Uniform scale so model height ≈ target_h, then center at origin for apply_pose."""
    s = target_h / model_height
    cy = model_ymin * s + target_h * 0.5
    return lc.transform_mesh(mesh, (0.0, -cy, 0.0), (s, s, s), (0.0, 0.0, 0.0))


def _register_mascot_materials(scene: lc.Scene) -> tuple[dict[str, int], dict[str, int], int, int]:
    """Register Sparky / Capsule materials in a fixed order (IDs must match cached meshes)."""
    albedo_path = resolve_asset("assets/models/sparky_albedo.png")
    tex = scene.add_texture(albedo_path)

    glass = scene.add_material(
        lc.Material(base_color=(0.65, 0.85, 1.0), roughness=0.02, transmission=0.92, ior=1.45)
    )
    screen_face = scene.add_material(
        lc.Material(
            base_color=(1.0, 1.0, 1.0), roughness=0.25, emission=(0.25, 0.55, 0.65), albedo_tex=tex
        )
    )
    screen_chest = scene.add_material(
        lc.Material(
            base_color=(1.0, 1.0, 1.0), roughness=0.35, emission=(0.08, 0.28, 0.1), albedo_tex=tex
        )
    )
    screen_palm = scene.add_material(
        lc.Material(base_color=(1.0, 1.0, 1.0), roughness=0.45, albedo_tex=tex)
    )
    plastic_blue = scene.add_material(lc.Material(base_color=(0.32, 0.62, 0.88), roughness=0.4))
    plastic_white = scene.add_material(lc.Material(base_color=(0.92, 0.93, 0.95), roughness=0.35))
    metal_grey = scene.add_material(
        lc.Material(base_color=(0.55, 0.57, 0.60), metallic=0.7, roughness=0.28)
    )
    accent_orange = scene.add_material(lc.Material(base_color=(0.95, 0.45, 0.12), roughness=0.4))
    tread_orange = scene.add_material(lc.Material(base_color=(0.95, 0.38, 0.08), roughness=0.55))
    emit_yellow = scene.add_material(
        lc.Material(base_color=(1.0, 0.9, 0.3), roughness=0.3, emission=(1.8, 1.3, 0.25))
    )

    sparky_mtl = {
        "GlassHead": glass,
        "ScreenFace": screen_face,
        "ScreenChest": screen_chest,
        "ScreenPalm": screen_palm,
        "PlasticBlue": plastic_blue,
        "PlasticWhite": plastic_white,
        "MetalGrey": metal_grey,
        "AccentOrange": accent_orange,
        "TreadOrange": tread_orange,
        "EmitYellow": emit_yellow,
    }

    yellow = scene.add_material(lc.Material(base_color=(0.95, 0.82, 0.18), roughness=0.42))
    visor = scene.add_material(
        lc.Material(base_color=(0.22, 0.24, 0.28), metallic=0.75, roughness=0.22)
    )
    eye = scene.add_material(lc.Material(base_color=(0.96, 0.96, 0.98), roughness=0.3))
    belt = scene.add_material(lc.Material(base_color=(0.10, 0.18, 0.35), roughness=0.55))
    leather = scene.add_material(lc.Material(base_color=(0.22, 0.12, 0.06), roughness=0.7))
    ant_stem = scene.add_material(
        lc.Material(base_color=(0.55, 0.57, 0.60), metallic=0.65, roughness=0.3)
    )
    ant_tip = scene.add_material(
        lc.Material(base_color=(1.0, 0.9, 0.3), roughness=0.3, emission=(1.5, 1.1, 0.2))
    )

    mascot_mtl = {
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
        "mascot_antenna_stem": ant_stem,
        "mascot_antenna_tip": ant_tip,
    }
    return sparky_mtl, mascot_mtl, plastic_white, yellow


def ensure_mascot_templates(scene: lc.Scene, target_h: float) -> dict[str, lc.Mesh]:
    global _MASCOT_TEMPLATES
    sparky_mtl, mascot_mtl, plastic_white, yellow = _register_mascot_materials(scene)
    if _MASCOT_TEMPLATES is not None:
        return _MASCOT_TEMPLATES

    sparky_path = resolve_asset("assets/models/sparky.obj")
    mascot_path = resolve_asset("assets/models/capsule_mascot.obj")
    sparky = lc.load_obj(sparky_path, sparky_mtl, plastic_white)
    capsule = lc.load_obj(mascot_path, mascot_mtl, yellow)
    # Measured AABB heights from assets (feet near y=0).
    sparky = _scale_mascot_to_brick(sparky, model_height=2.092721, model_ymin=-0.002721, target_h=target_h)
    capsule = _scale_mascot_to_brick(capsule, model_height=2.0, model_ymin=0.0, target_h=target_h)
    _MASCOT_TEMPLATES = {"sparky": sparky, "capsule": capsule}
    print(f"[physx_collapse] loaded mascots @ height≈{target_h:.3f}m", flush=True)
    return _MASCOT_TEMPLATES


def build_render_scene(
    world: lc.PhysXWorld,
    actors: list[dict],
    brick_half: tuple[float, float, float],
    flame_time: float = 0.0,
) -> lc.Scene:
    scene = lc.Scene()
    mat_ids = {
        "floor": scene.add_material(lc.Material(base_color=(0.28, 0.28, 0.30), roughness=0.88)),
        "ramp": scene.add_material(lc.Material(base_color=(0.24, 0.25, 0.27), roughness=0.75)),
        "wall": scene.add_material(lc.Material(base_color=(0.32, 0.32, 0.34), roughness=0.85)),
        "glass": scene.add_material(
            lc.Material(
                base_color=(0.92, 0.97, 1.0),
                roughness=0.0,
                transmission=1.0,
                ior=1.5,
                absorption=(0.08, 0.04, 0.02),
            )
        ),
        "light": scene.add_material(
            lc.Material(base_color=(0, 0, 0), roughness=1.0, emission=(2.2, 2.0, 1.8))
        ),
    }
    brick_cache: dict[tuple[float, float, float], int] = {}

    def brick_mat(color: tuple[float, float, float]) -> int:
        if color not in brick_cache:
            brick_cache[color] = scene.add_material(
                lc.Material(base_color=color, roughness=0.78, metallic=0.0)
            )
        return brick_cache[color]

    target_h = 2.0 * max(brick_half[0], brick_half[1], brick_half[2]) * 1.15
    templates = ensure_mascot_templates(scene, target_h)

    for entry in actors:
        pose = world.get_pose(entry["id"])
        kind = entry["kind"]
        if kind == "static_box":
            scene.add_mesh(lc.apply_pose_to_box_mesh(entry["half"], pose, mat_ids[entry["mat"]]))
        elif kind == "brick":
            scene.add_mesh(lc.apply_pose_to_box_mesh(entry["half"], pose, brick_mat(entry["color"])))
        elif kind == "mascot":
            scene.add_mesh(lc.apply_pose_to_mesh(templates[entry["which"]], pose))
        elif kind == "sphere":
            radius = float(entry["radius"])
            scene.add_mesh(
                lc.apply_pose_to_sphere_mesh(radius, pose, mat_ids["glass"], 48, 24)
            )
            # Flame AABB inscribed in the glass sphere (slightly taller for tongue look).
            he = radius * 0.52
            cx, cy, cz = pose.position
            scene.add_flame_volume(
                center=(cx, cy, cz),
                half_extents=(he * 0.85, he * 1.05, he * 0.85),
                emission_scale=(280.0, 110.0, 16.0),
                density_scale=3.2,
                absorption=2.4,
                noise_scale=3.0,
                time=flame_time,
                add_proxy_light=True,
            )

    # Dim fill — the fireball is the key light.
    scene.add_mesh(lc.make_quad((-1.5, 7.5, -1.5), (3.0, 0, 0), (0, 0, 3.0), mat_ids["light"]))
    scene.add_quad_light((-1.5, 7.5, -1.5), (3.0, 0, 0), (0, 0, 3.0), (2.2, 2.0, 1.8))
    scene.add_quad_light((4.0, 5.0, -3.0), (0.0, 0, 2.0), (0, -2.0, 0), (0.8, 0.85, 1.0))

    scene.background_top = (0.10, 0.11, 0.14)
    scene.background_bottom = (0.03, 0.03, 0.04)
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
    mascot_count = 0
    for iy in range(ny):
        for ix in range(nx):
            for iz in range(nz):
                x = ox + ix * (brick_half[0] * 2 + gap) + 1.2
                y = brick_half[1] + iy * (brick_half[1] * 2 + gap)
                z = oz + iz * (brick_half[2] * 2 + gap)
                aid = world.add_dynamic_box(brick_half, 1.2, lc.Pose(position=(x, y, z)))
                # Deterministic sparse replacements (~11 in an 8×12×8 tower).
                if (ix + iy * 3 + iz * 5) % 41 == 0 and 3 <= iy <= 9:
                    which = "sparky" if (mascot_count % 2 == 0) else "capsule"
                    actors.append({"id": aid, "kind": "mascot", "which": which})
                    mascot_count += 1
                else:
                    actors.append(
                        {
                            "id": aid,
                            "kind": "brick",
                            "half": brick_half,
                            "color": brick_color(ix, iy, iz),
                        }
                    )
    print(f"[physx_collapse] mascots in tower: {mascot_count}", flush=True)

    # Single heavy glass fireball rolling down the ramp.
    ball_r = 0.75
    ball_pos = (-6.6, 3.75, 0.0)
    ball_vel = (2.9, -0.15, 0.0)
    aid = world.add_dynamic_sphere(ball_r, 14.0, lc.Pose(position=ball_pos))
    world.set_linear_velocity(aid, ball_vel)
    actors.append({"id": aid, "kind": "sphere", "radius": ball_r})

    camera = lc.Camera(
        eye=(8.2, 4.6, 10.2),
        lookat=(0.2, 1.2, 0.0),
        up=(0.0, 1.0, 0.0),
        fov_y_deg=38.0,
        aspect=2560 / 1440,
    )

    sim_steps = 180
    frame_every = 15
    hero_step = 150  # frame_0010 — homepage pick
    renderer = lc.Renderer()
    frame_paths: list[Path] = []

    step_i = 0
    frame_idx = 0
    while step_i <= sim_steps:
        if step_i % frame_every == 0:
            flame_time = 1.2 + step_i * 0.035
            scene = build_render_scene(world, actors, brick_half, flame_time=flame_time)
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

    # Build contact sheet in a child process so a PIL crash cannot kill the demo.
    sheet_path = frames_dir / "contact_sheet.png"
    try:
        import subprocess

        picks = frame_paths[:: max(1, len(frame_paths) // 6)][:6]
        if picks:
            script = (
                "from PIL import Image\n"
                "from pathlib import Path\n"
                f"paths = {[str(p) for p in picks]!r}\n"
                f"out = {str(sheet_path)!r}\n"
                "imgs = [Image.open(p) for p in paths]\n"
                "w, h = imgs[0].size\n"
                "sheet = Image.new('RGB', (w * len(imgs), h))\n"
                "for i, im in enumerate(imgs):\n"
                "    sheet.paste(im, (i * w, 0))\n"
                "sheet.save(out)\n"
            )
            rc = subprocess.run(
                [sys.executable, "-c", script],
                check=False,
            ).returncode
            if rc == 0 and sheet_path.is_file():
                print(f"[physx_collapse] contact sheet → {sheet_path}", flush=True)
            else:
                print(f"[physx_collapse] contact sheet skipped (exit {rc})", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[physx_collapse] contact sheet skipped ({exc})", flush=True)

    print(f"[physx_collapse] done. frames={len(frame_paths)} backend={world.backend()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
