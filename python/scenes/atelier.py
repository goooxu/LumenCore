#!/usr/bin/env python3
"""LumenCore gallery showcase: multi-feature atelier (PhysX freeze + OptiX path trace).

Packs PhysX/IAS bricks, flame volume, HDRI+NEE, GGX metal/glass, Sparky normals,
Capsule, Spot cow, and a small Beer-Lambert water basin into one 2K still.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import lumencore as lc


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


def _local_box(half: tuple[float, float, float], mat_id: int) -> lc.Mesh:
    hx, hy, hz = half
    return lc.make_box((-hx, -hy, -hz), (hx, hy, hz), mat_id)


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "outputs/gallery/showcase.png"
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 192
    denoise = (int(sys.argv[3]) != 0) if len(sys.argv) > 3 else True
    sim_steps = int(sys.argv[4]) if len(sys.argv) > 4 else 90

    Path(out).parent.mkdir(parents=True, exist_ok=True)

    # --- PhysX: short tumble of colored bricks, then freeze poses ---------------
    world = lc.PhysXWorld()
    world.init()
    print(f"[atelier] PhysX backend: {world.backend()}", flush=True)

    ground_half = (4.0, 0.2, 3.5)
    ground_id = world.add_static_box(ground_half, lc.Pose(position=(0.0, -0.2, 0.0)))

    brick_half = (0.16, 0.10, 0.16)
    brick_actors: list[tuple[int, tuple[float, float, float]]] = []
    palette = [
        (0.52, 0.22, 0.16),
        (0.48, 0.34, 0.22),
        (0.35, 0.36, 0.38),
        (0.55, 0.42, 0.28),
        (0.28, 0.30, 0.32),
    ]
    for iy in range(4):
        for ix in range(5):
            x = -0.9 + ix * (brick_half[0] * 2 + 0.02)
            y = brick_half[1] + iy * (brick_half[1] * 2 + 0.01)
            z = -0.35 + (ix % 2) * 0.03
            aid = world.add_dynamic_box(brick_half, 1.0, lc.Pose(position=(x, y, z)))
            brick_actors.append((aid, palette[(ix + iy * 3) % len(palette)]))

    # Gentle push so the pile settles into a natural heap.
    ball_id = world.add_dynamic_sphere(0.22, 6.0, lc.Pose(position=(-1.6, 0.9, -0.2)))
    world.set_linear_velocity(ball_id, (2.4, -0.2, 0.15))

    for _ in range(sim_steps):
        world.step(1.0 / 60.0, 1)
    print(f"[atelier] sim settled after {sim_steps} steps", flush=True)

    # --- Render scene (IAS for PhysX + identity meshes for characters/props) ---
    scene = lc.Scene()
    hdri = resolve_asset("assets/env/studio.hdr")
    if Path(hdri).is_file():
        scene.load_env_map(hdri)
        print(f"[atelier] HDRI {hdri}", flush=True)

    floor_m = scene.add_material(lc.Material(base_color=(0.34, 0.33, 0.32), roughness=0.9))
    wall_m = scene.add_material(lc.Material(base_color=(0.52, 0.50, 0.48), roughness=0.92))
    wood_m = scene.add_material(lc.Material(base_color=(0.30, 0.18, 0.10), roughness=0.78))
    metal_m = scene.add_material(
        lc.Material(base_color=(0.88, 0.86, 0.82), metallic=1.0, roughness=0.18)
    )
    glass_m = scene.add_material(
        lc.Material(
            base_color=(0.92, 0.97, 1.0),
            roughness=0.22,
            transmission=0.95,
            ior=1.5,
            absorption=(0.12, 0.05, 0.03),
        )
    )
    water_m = scene.add_material(
        lc.Material(
            base_color=(0.45, 0.75, 0.88),
            roughness=0.02,
            transmission=1.0,
            ior=1.33,
            absorption=(0.55, 0.18, 0.08),
        )
    )
    stone_m = scene.add_material(lc.Material(base_color=(0.38, 0.36, 0.34), roughness=0.88))
    ash_m = scene.add_material(lc.Material(base_color=(0.14, 0.13, 0.12), roughness=0.95))

    # Room shell (world-space meshes → identity IAS instances when mixed with PhysX)
    scene.add_mesh(lc.make_quad((-3.2, 0.0, -2.8), (6.4, 0.0, 0.0), (0.0, 0.0, 5.6), floor_m))
    scene.add_mesh(lc.make_quad((-3.2, 0.0, -2.6), (6.4, 0.0, 0.0), (0.0, 3.0, 0.0), wall_m))
    scene.add_mesh(lc.make_quad((-3.2, 0.0, -2.6), (0.0, 0.0, 5.2), (0.0, 3.0, 0.0), wall_m))
    scene.add_mesh(lc.make_quad((3.2, 0.0, 2.6), (0.0, 0.0, -5.2), (0.0, 3.0, 0.0), wall_m))
    scene.add_mesh(lc.make_quad((-3.2, 3.0, -2.6), (6.4, 0.0, 0.0), (0.0, 0.0, 5.2), stone_m))

    # Hearth + flame volume
    scene.add_mesh(lc.make_box((-0.55, 0.0, -2.45), (0.55, 0.10, -1.55), stone_m))
    scene.add_mesh(lc.make_box((-0.60, 0.10, -2.45), (-0.40, 1.05, -1.65), stone_m))
    scene.add_mesh(lc.make_box((0.40, 0.10, -2.45), (0.60, 1.05, -1.65), stone_m))
    scene.add_mesh(lc.make_box((-0.65, 1.00, -2.50), (0.65, 1.15, -1.55), stone_m))
    scene.add_mesh(lc.make_box((-0.40, 0.10, -2.40), (0.40, 0.95, -2.30), ash_m))
    scene.add_mesh(lc.make_box((-0.22, 0.12, -2.05), (0.22, 0.24, -1.85), wood_m))
    scene.add_flame_volume(
        center=(0.0, 0.55, -2.05),
        half_extents=(0.28, 0.42, 0.18),
        emission_scale=(140.0, 55.0, 10.0),
        density_scale=2.6,
        absorption=1.8,
        noise_scale=2.5,
        time=1.65,
        add_proxy_light=True,
    )

    # Metal can + frosted glass orb (GGX showcase props)
    scene.add_mesh(lc.make_box((1.55, 0.0, -0.85), (1.85, 0.48, -0.55), metal_m))
    scene.add_mesh(lc.make_uv_sphere((1.70, 0.68, -0.70), 0.18, metal_m, 40, 20))
    scene.add_mesh(lc.make_uv_sphere((-1.55, 0.28, 0.55), 0.28, glass_m, 48, 24))

    # Shallow water basin with Beer-Lambert
    scene.add_mesh(lc.make_box((1.35, 0.0, 0.85), (2.35, 0.08, 1.75), stone_m))
    scene.add_mesh(
        lc.make_water_surface(
            center=(1.85, 0.12, 1.30),
            half_extents_xz=(0.42, 0.0, 0.38),
            y_base=0.12,
            material_id=water_m,
            nx=48,
            nz=40,
            time=1.1,
        )
    )
    rock = scene.add_material(lc.Material(base_color=(0.30, 0.32, 0.28), roughness=0.9))
    scene.add_mesh(lc.make_uv_sphere((1.78, -0.02, 1.25), 0.12, rock, 24, 16))

    # Characters ----------------------------------------------------------------
    albedo = scene.add_texture(resolve_asset("assets/models/sparky_albedo.png"))
    nmap = scene.add_texture(resolve_asset("assets/models/sparky_normal.png"))
    spot_tex = scene.add_texture(resolve_asset("assets/models/spot_texture.png"))

    glass_h = scene.add_material(
        lc.Material(base_color=(0.65, 0.85, 1.0), roughness=0.02, transmission=0.92, ior=1.45)
    )
    screen_face = scene.add_material(
        lc.Material(
            base_color=(1, 1, 1),
            roughness=0.25,
            emission=(0.3, 0.6, 0.75),
            albedo_tex=albedo,
            normal_tex=nmap,
        )
    )
    screen_chest = scene.add_material(
        lc.Material(
            base_color=(1, 1, 1),
            roughness=0.35,
            emission=(0.08, 0.28, 0.1),
            albedo_tex=albedo,
            normal_tex=nmap,
        )
    )
    screen_palm = scene.add_material(
        lc.Material(base_color=(1, 1, 1), roughness=0.45, albedo_tex=albedo, normal_tex=nmap)
    )
    plastic_blue = scene.add_material(
        lc.Material(base_color=(0.32, 0.62, 0.88), roughness=0.4, normal_tex=nmap)
    )
    plastic_white = scene.add_material(
        lc.Material(base_color=(0.92, 0.93, 0.95), roughness=0.35, normal_tex=nmap)
    )
    metal_grey = scene.add_material(
        lc.Material(base_color=(0.55, 0.57, 0.60), metallic=0.7, roughness=0.28, normal_tex=nmap)
    )
    accent = scene.add_material(
        lc.Material(base_color=(0.95, 0.45, 0.12), roughness=0.4, normal_tex=nmap)
    )
    tread = scene.add_material(
        lc.Material(base_color=(0.95, 0.38, 0.08), roughness=0.55, normal_tex=nmap)
    )
    emit_y = scene.add_material(
        lc.Material(base_color=(1.0, 0.9, 0.3), roughness=0.3, emission=(1.8, 1.3, 0.25))
    )
    sparky_mtl = {
        "GlassHead": glass_h,
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

    yellow = scene.add_material(lc.Material(base_color=(0.95, 0.82, 0.18), roughness=0.42))
    visor = scene.add_material(
        lc.Material(base_color=(0.22, 0.24, 0.28), metallic=0.75, roughness=0.22)
    )
    eye = scene.add_material(lc.Material(base_color=(0.96, 0.96, 0.98), roughness=0.3))
    belt = scene.add_material(lc.Material(base_color=(0.10, 0.18, 0.35), roughness=0.55))
    leather = scene.add_material(lc.Material(base_color=(0.22, 0.12, 0.06), roughness=0.7))
    ant = scene.add_material(
        lc.Material(base_color=(0.55, 0.57, 0.60), metallic=0.65, roughness=0.3)
    )
    tip = scene.add_material(
        lc.Material(base_color=(1.0, 0.9, 0.3), roughness=0.3, emission=(1.6, 1.2, 0.25))
    )
    capsule_mtl = {
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
        "mascot_antenna_stem": ant,
        "mascot_antenna_tip": tip,
    }

    sparky = lc.load_obj(resolve_asset("assets/models/sparky.obj"), sparky_mtl, plastic_white)
    sparky = lc.transform_mesh(sparky, (1.05, 0.0, 0.15), (0.55, 0.55, 0.55), (0.0, -0.55, 0.0))
    scene.add_mesh(sparky)

    capsule = lc.load_obj(resolve_asset("assets/models/capsule_mascot.obj"), capsule_mtl, yellow)
    capsule = lc.transform_mesh(capsule, (-1.35, 0.0, 0.35), (0.55, 0.55, 0.55), (0.0, 0.4, 0.0))
    scene.add_mesh(capsule)

    spot_mat = scene.add_material(
        lc.Material(base_color=(1.0, 1.0, 1.0), roughness=0.55, albedo_tex=spot_tex)
    )
    spot = lc.load_obj(resolve_asset("assets/models/spot_triangulated.obj"), spot_mat)
    # Spot is roughly unit-sized; stand on floor, face camera-ish.
    spot = lc.transform_mesh(spot, (0.15, 0.0, 0.85), (0.85, 0.85, 0.85), (0.0, math.radians(25), 0.0))
    scene.add_mesh(spot)
    print("[atelier] loaded Sparky + Capsule + Spot", flush=True)

    # PhysX prototypes + instances
    box_proto: dict[tuple, int] = {}
    brick_mat_cache: dict[tuple[float, float, float], int] = {}

    def brick_mat(color: tuple[float, float, float]) -> int:
        if color not in brick_mat_cache:
            brick_mat_cache[color] = scene.add_material(
                lc.Material(base_color=color, roughness=0.78)
            )
        return brick_mat_cache[color]

    def box_id(half: tuple[float, float, float], mat: int) -> int:
        key = (half, mat)
        if key not in box_proto:
            box_proto[key] = scene.add_mesh(_local_box(half, mat))
        return box_proto[key]

    floor_proto = scene.add_mesh(_local_box(ground_half, floor_m))
    scene.add_instance(floor_proto, world.get_pose(ground_id))

    for aid, color in brick_actors:
        mid = box_id(brick_half, brick_mat(color))
        scene.add_instance(mid, world.get_pose(aid))

    ball_mat = scene.add_material(
        lc.Material(base_color=(0.75, 0.78, 0.85), metallic=0.85, roughness=0.12)
    )
    ball_proto = scene.add_mesh(lc.make_uv_sphere((0, 0, 0), 0.22, ball_mat, 40, 20))
    scene.add_instance(ball_proto, world.get_pose(ball_id))

    # Lights
    scene.add_quad_light((-0.35, 2.85, -0.2), (0.7, 0, 0), (0, 0, 0.55), (6.0, 5.6, 5.0))
    scene.add_spot_light(
        position=(1.1, 2.6, 1.2),
        direction=(-0.15, -1.0, -0.35),
        emission=(70.0, 62.0, 52.0),
        angle_deg=22.0,
        penumbra_deg=12.0,
    )
    scene.add_spot_light(
        position=(-1.2, 2.5, 1.0),
        direction=(0.2, -1.0, -0.25),
        emission=(55.0, 58.0, 70.0),
        angle_deg=20.0,
        penumbra_deg=10.0,
    )

    scene.background_top = (0.18, 0.20, 0.24)
    scene.background_bottom = (0.06, 0.06, 0.07)

    camera = lc.Camera(
        eye=(3.6, 2.15, 4.4),
        lookat=(0.15, 0.75, -0.2),
        up=(0.0, 1.0, 0.0),
        fov_y_deg=38.0,
        aspect=2560 / 1440,
    )
    cfg = lc.RenderConfig(
        width=2560,
        height=1440,
        spp=spp,
        denoise=denoise,
        enable_nee=True,
        output_path=out,
    )
    print(f"[atelier] render → {out} @ {spp} spp", flush=True)
    lc.Renderer().render(scene, camera, cfg)

    del world
    print("[atelier] done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
