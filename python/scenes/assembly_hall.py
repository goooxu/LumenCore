#!/usr/bin/env python3
"""LumenCore cover: Assembly Hall — toy factory with PhysX-frozen spill.

Noon HDR skylights, furnace flame vs frosted-glass glow, absorption smoke column,
candy Sparky line (one lit NEE screen), Capsule supervisor, mid-air Spot cows,
Beer-Lambert cooling pool, metal trusses, and a procedural cutout gear logo.
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


def add_gear_logo(scene: lc.Scene, center: tuple[float, float, float], mat_id: int) -> None:
    """Add a cutout-style gear as separate thin metal boxes on the back wall."""
    cx, cy, cz = center
    outer_r, inner_r, thickness = 0.85, 0.48, 0.06
    teeth = 12
    segs = 28
    for i in range(segs):
        a0 = 2.0 * math.pi * i / segs
        a1 = 2.0 * math.pi * (i + 1) / segs
        am = 0.5 * (a0 + a1)
        rm = 0.5 * (outer_r + inner_r)
        tw = (outer_r - inner_r) * 0.55
        arc = rm * (a1 - a0) * 1.1
        hx, hy, hz = thickness * 0.5, tw * 0.5, arc * 0.5
        # Gear lies in YZ plane on back wall (facing +Z into hall)
        box = lc.make_box((-hx, -hy, -hz), (hx, hy, hz), mat_id)
        py = cy + rm * math.sin(am)
        pz = cz + rm * math.cos(am)
        box = lc.transform_mesh(box, (cx, py, pz), (1.0, 1.0, 1.0), (0.0, 0.0, am))
        scene.add_mesh(box)
    for i in range(teeth):
        a = 2.0 * math.pi * i / teeth
        tooth_len = (outer_r - inner_r) * 0.9
        tw = outer_r * 0.11
        hx, hy, hz = thickness * 0.5, tooth_len * 0.5, tw * 0.5
        box = lc.make_box((-hx, -hy, -hz), (hx, hy, hz), mat_id)
        py = cy + (outer_r + tooth_len * 0.2) * math.sin(a)
        pz = cz + (outer_r + tooth_len * 0.2) * math.cos(a)
        box = lc.transform_mesh(box, (cx, py, pz), (1.0, 1.0, 1.0), (0.0, 0.0, a))
        scene.add_mesh(box)
    # Hub
    hub_r = inner_r * 0.5
    for i in range(12):
        a = 2.0 * math.pi * i / 12
        hx, hy, hz = thickness * 0.5, hub_r * 0.22, hub_r * 0.35
        box = lc.make_box((-hx, -hy, -hz), (hx, hy, hz), mat_id)
        py = cy + hub_r * 0.7 * math.sin(a)
        pz = cz + hub_r * 0.7 * math.cos(a)
        box = lc.transform_mesh(box, (cx, py, pz), (1.0, 1.0, 1.0), (0.0, 0.0, a))
        scene.add_mesh(box)


def sparky_materials(
    scene: lc.Scene,
    albedo: int,
    nmap: int,
    candy: tuple[float, float, float],
    accent: tuple[float, float, float],
    screen_emit: tuple[float, float, float] | None = None,
) -> tuple[dict, int]:
    """Candy dual-lobe plastic (GGX diffuse+specular stand-in for coated BSDF)."""
    glass_h = scene.add_material(
        lc.Material(base_color=(0.65, 0.85, 1.0), roughness=0.02, transmission=0.92, ior=1.45)
    )
    face_e = screen_emit if screen_emit else (0.15, 0.35, 0.45)
    chest_e = (
        (face_e[0] * 0.35, face_e[1] * 0.55, face_e[2] * 0.25)
        if screen_emit
        else (0.04, 0.14, 0.06)
    )
    screen_face = scene.add_material(
        lc.Material(
            base_color=(1, 1, 1),
            roughness=0.22,
            emission=face_e,
            albedo_tex=albedo,
            normal_tex=nmap,
        )
    )
    screen_chest = scene.add_material(
        lc.Material(
            base_color=(1, 1, 1),
            roughness=0.32,
            emission=chest_e,
            albedo_tex=albedo,
            normal_tex=nmap,
        )
    )
    screen_palm = scene.add_material(
        lc.Material(base_color=(1, 1, 1), roughness=0.45, albedo_tex=albedo, normal_tex=nmap)
    )
    # Low-roughness candy plastic ≈ coated dual-lobe look
    plastic_candy = scene.add_material(
        lc.Material(base_color=candy, roughness=0.22, metallic=0.08, normal_tex=nmap)
    )
    plastic_white = scene.add_material(
        lc.Material(base_color=(0.94, 0.95, 0.97), roughness=0.28, normal_tex=nmap)
    )
    metal_grey = scene.add_material(
        lc.Material(base_color=(0.55, 0.57, 0.60), metallic=0.7, roughness=0.28, normal_tex=nmap)
    )
    accent_m = scene.add_material(
        lc.Material(base_color=accent, roughness=0.28, metallic=0.05, normal_tex=nmap)
    )
    tread = scene.add_material(
        lc.Material(base_color=accent, roughness=0.45, normal_tex=nmap)
    )
    emit_y = scene.add_material(
        lc.Material(base_color=(1.0, 0.9, 0.3), roughness=0.3, emission=(1.8, 1.3, 0.25))
    )
    mtl = {
        "GlassHead": glass_h,
        "ScreenFace": screen_face,
        "ScreenChest": screen_chest,
        "ScreenPalm": screen_palm,
        "PlasticBlue": plastic_candy,
        "PlasticWhite": plastic_white,
        "MetalGrey": metal_grey,
        "AccentOrange": accent_m,
        "TreadOrange": tread,
        "EmitYellow": emit_y,
    }
    return mtl, plastic_white


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "outputs/gallery/assembly_hall.png"
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 192
    denoise = (int(sys.argv[3]) != 0) if len(sys.argv) > 3 else True
    sim_steps = int(sys.argv[4]) if len(sys.argv) > 4 else 48

    Path(out).parent.mkdir(parents=True, exist_ok=True)

    # --- PhysX: crate + toy cows mid-spill freeze ---------------------------------
    world = lc.PhysXWorld()
    world.init()
    print(f"[assembly] PhysX backend: {world.backend()}", flush=True)

    world.add_static_box((8.0, 0.2, 6.0), lc.Pose(position=(0.0, -0.2, 0.0)))
    # Conveyor collider
    world.add_static_box((3.2, 0.08, 0.45), lc.Pose(position=(1.2, 0.55, 1.4)))
    # Cooling pool rim
    world.add_static_box((1.6, 0.05, 1.1), lc.Pose(position=(-2.4, 0.05, 2.0)))

    crate_half = (0.55, 0.28, 0.40)
    crate_id = world.add_dynamic_box(
        crate_half,
        8.0,
        lc.Pose(
            position=(0.15, 2.35, -0.4),
            quat=quat_axis_angle((0.0, 0.0, 1.0), math.radians(38)),
        ),
    )
    world.set_linear_velocity(crate_id, (0.6, -1.8, 0.2))
    world.set_angular_velocity(crate_id, (0.4, 0.8, -1.2))

    spot_scale = 0.32
    spot_ymin, spot_ymax = -0.736784, 0.953646
    spot_h = (spot_ymax - spot_ymin) * spot_scale
    spot_half = (0.22, spot_h * 0.5, 0.32)
    spot_actors: list[int] = []
    for i in range(5):
        aid = world.add_dynamic_box(
            spot_half,
            3.5,
            lc.Pose(
                position=(-0.15 + i * 0.12, 2.9 + i * 0.08, -0.55 + (i % 3) * 0.1),
                quat=quat_axis_angle((1.0, 0.2, 0.0), math.radians(20 + i * 25)),
            ),
        )
        world.set_linear_velocity(aid, (0.4 + i * 0.1, -2.2, 0.15))
        spot_actors.append(aid)

    for _ in range(sim_steps):
        world.step(1.0 / 60.0, 1)
    print(f"[assembly] sim freeze after {sim_steps} steps", flush=True)

    # --- Render scene -------------------------------------------------------------
    scene = lc.Scene()
    hdri = resolve_asset("assets/env/noon_factory.hdr")
    if Path(hdri).is_file():
        scene.load_env_map(hdri)
        print(f"[assembly] HDRI {hdri}", flush=True)

    floor_m = scene.add_material(lc.Material(base_color=(0.36, 0.35, 0.33), roughness=0.88))
    wall_m = scene.add_material(lc.Material(base_color=(0.55, 0.54, 0.50), roughness=0.92))
    ceiling_m = scene.add_material(lc.Material(base_color=(0.62, 0.62, 0.60), roughness=0.9))
    metal_truss = scene.add_material(
        lc.Material(base_color=(0.70, 0.72, 0.75), metallic=1.0, roughness=0.25)
    )
    conveyor_m = scene.add_material(
        lc.Material(base_color=(0.25, 0.26, 0.28), metallic=0.5, roughness=0.45)
    )
    stone_m = scene.add_material(lc.Material(base_color=(0.32, 0.30, 0.28), roughness=0.9))
    ash_m = scene.add_material(lc.Material(base_color=(0.12, 0.11, 0.10), roughness=0.95))
    crate_m = scene.add_material(lc.Material(base_color=(0.48, 0.32, 0.16), roughness=0.72))
    frosted = scene.add_material(
        lc.Material(
            base_color=(0.95, 0.92, 0.88),
            roughness=0.42,
            transmission=0.92,
            ior=1.5,
            absorption=(0.05, 0.08, 0.12),
        )
    )
    water_m = scene.add_material(
        lc.Material(
            base_color=(0.45, 0.78, 0.90),
            roughness=0.02,
            transmission=1.0,
            ior=1.33,
            absorption=(0.48, 0.15, 0.06),
        )
    )
    gear_m = scene.add_material(
        lc.Material(base_color=(0.82, 0.78, 0.55), metallic=1.0, roughness=0.3)
    )
    dark_patch = scene.add_material(lc.Material(base_color=(0.12, 0.11, 0.10), roughness=0.95))

    # Hall shell
    scene.add_mesh(lc.make_quad((-7.0, 0.0, -5.0), (14.0, 0.0, 0.0), (0.0, 0.0, 10.0), floor_m))
    scene.add_mesh(lc.make_quad((-7.0, 0.0, -4.8), (14.0, 0.0, 0.0), (0.0, 6.5, 0.0), wall_m))
    scene.add_mesh(lc.make_quad((-7.0, 0.0, -4.8), (0.0, 0.0, 9.6), (0.0, 6.5, 0.0), wall_m))
    scene.add_mesh(lc.make_quad((7.0, 0.0, 4.8), (0.0, 0.0, -9.6), (0.0, 6.5, 0.0), wall_m))
    # Ceiling with skylight openings (leave gaps via side slabs)
    scene.add_mesh(lc.make_box((-7.0, 6.3, -4.8), (-1.2, 6.55, 4.8), ceiling_m))
    scene.add_mesh(lc.make_box((1.2, 6.3, -4.8), (7.0, 6.55, 4.8), ceiling_m))
    scene.add_mesh(lc.make_box((-1.2, 6.3, -4.8), (1.2, 6.55, -1.5), ceiling_m))
    scene.add_mesh(lc.make_box((-1.2, 6.3, 1.5), (1.2, 6.55, 4.8), ceiling_m))

    # Metal trusses
    for x in (-4.5, -1.5, 1.5, 4.5):
        scene.add_mesh(lc.make_box((x - 0.06, 5.2, -4.5), (x + 0.06, 6.35, 4.5), metal_truss))
    for z in (-3.0, 0.0, 3.0):
        scene.add_mesh(lc.make_box((-6.5, 5.6, z - 0.05), (6.5, 5.85, z + 0.05), metal_truss))

    # Gear logo on back wall
    add_gear_logo(scene, center=(-0.05, 3.6, -4.72), mat_id=gear_m)

    # Furnace block (left rear)
    scene.add_mesh(lc.make_box((-6.2, 0.0, -4.4), (-3.6, 2.4, -2.2), stone_m))
    scene.add_mesh(lc.make_box((-5.7, 0.2, -3.5), (-4.1, 1.6, -2.25), ash_m))
    # Open furnace mouth — sharp flame
    scene.add_flame_volume(
        center=(-4.9, 0.95, -2.55),
        half_extents=(0.35, 0.55, 0.22),
        emission_scale=(280.0, 100.0, 18.0),
        density_scale=3.2,
        absorption=1.4,
        noise_scale=3.0,
        time=1.55,
        add_proxy_light=True,
    )
    # Frosted glass booth with soft fire glow
    scene.add_mesh(lc.make_box((-6.15, 0.15, -2.15), (-5.55, 2.1, -0.6), frosted))
    scene.add_mesh(lc.make_box((-5.55, 0.15, -2.15), (-3.85, 2.1, -1.85), frosted))
    scene.add_mesh(lc.make_box((-5.55, 1.85, -2.15), (-3.85, 2.1, -0.6), frosted))
    scene.add_flame_volume(
        center=(-5.0, 0.9, -1.35),
        half_extents=(0.40, 0.50, 0.28),
        emission_scale=(120.0, 48.0, 10.0),
        density_scale=2.4,
        absorption=1.0,
        noise_scale=2.2,
        time=2.1,
        add_proxy_light=False,
    )
    # Pure-absorption smoke column into skylight beam + dark ground patch (vol shadow approx)
    scene.add_flame_volume(
        center=(-4.9, 3.4, -2.4),
        half_extents=(0.55, 2.2, 0.45),
        emission_scale=(0.0, 0.0, 0.0),
        density_scale=3.5,
        absorption=4.5,
        noise_scale=1.8,
        time=0.9,
        add_proxy_light=False,
    )
    scene.add_mesh(lc.make_quad((-5.8, 0.01, -3.2), (2.0, 0.0, 0.0), (0.0, 0.0, 2.4), dark_patch))

    # Conveyor belt
    scene.add_mesh(lc.make_box((-1.8, 0.35, 0.95), (4.4, 0.55, 1.85), conveyor_m))
    scene.add_mesh(lc.make_box((-1.8, 0.0, 0.95), (-1.55, 0.55, 1.85), metal_truss))
    scene.add_mesh(lc.make_box((4.15, 0.0, 0.95), (4.4, 0.55, 1.85), metal_truss))

    # Cooling pool
    scene.add_mesh(lc.make_box((-4.0, 0.0, 1.0), (-0.9, 0.08, 3.1), stone_m))
    scene.add_mesh(
        lc.make_water_surface(
            center=(-2.45, 0.12, 2.05),
            half_extents_xz=(1.4, 0.0, 0.9),
            y_base=0.12,
            material_id=water_m,
            nx=64,
            nz=48,
            time=1.4,
        )
    )

    # Textures / characters
    albedo = scene.add_texture(resolve_asset("assets/models/sparky_albedo.png"))
    nmap = scene.add_texture(resolve_asset("assets/models/sparky_normal.png"))
    spot_tex = scene.add_texture(resolve_asset("assets/models/spot_texture.png"))

    candy_colors = [
        ((0.95, 0.35, 0.45), (0.95, 0.55, 0.15)),
        ((0.35, 0.75, 0.95), (0.25, 0.55, 0.95)),
        ((0.45, 0.92, 0.40), (0.95, 0.85, 0.15)),
        ((0.92, 0.45, 0.85), (0.65, 0.25, 0.90)),
    ]
    sparky_ymin, sparky_ymax = -0.002721, 2.09
    sparky_scale = 0.42
    sparky_h = (sparky_ymax - sparky_ymin) * sparky_scale
    sparky_cy = sparky_ymin * sparky_scale + sparky_h * 0.5

    # Line of candy Sparkys on conveyor; last one is QC-awake with bright screen
    for i, (candy, accent) in enumerate(candy_colors):
        awake = i == 3
        emit = (2.8, 4.5, 5.5) if awake else None
        mtl, fallback = sparky_materials(scene, albedo, nmap, candy, accent, emit)
        mesh = lc.load_obj(resolve_asset("assets/models/sparky.obj"), mtl, fallback)
        mesh = lc.transform_mesh(
            mesh, (0.0, -sparky_cy, 0.0), (sparky_scale,) * 3, (0.0, 0.0, 0.0)
        )
        proto = scene.add_mesh(mesh)
        x = -0.6 + i * 1.15
        yaw = math.radians(-90)
        pose = lc.Pose(
            position=(x, 0.55 + sparky_h * 0.5, 1.40),
            quat=quat_axis_angle((0.0, 1.0, 0.0), yaw),
        )
        scene.add_instance(proto, pose)
        if awake:
            # Matching NEE quad in front of screen (uniform proxy for textured emission)
            scene.add_quad_light(
                (x - 0.12, 0.95, 1.55),
                (0.24, 0.0, 0.0),
                (0.0, 0.32, 0.0),
                (18.0, 28.0, 32.0),
            )

    # Capsule supervisor in skylight pool
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
    capsule_scale = 0.55
    capsule = lc.load_obj(resolve_asset("assets/models/capsule_mascot.obj"), capsule_mtl, yellow)
    capsule = lc.transform_mesh(
        capsule,
        (0.3, 0.0, -1.2),
        (capsule_scale,) * 3,
        (0.0, math.radians(15), 0.0),
    )
    scene.add_mesh(capsule)

    # Spot cow prototypes (PhysX instances) + crate
    spot_mat = scene.add_material(
        lc.Material(base_color=(1.0, 1.0, 1.0), roughness=0.55, albedo_tex=spot_tex)
    )
    spot_mesh = lc.load_obj(resolve_asset("assets/models/spot_triangulated.obj"), spot_mat)
    spot_cy = spot_ymin * spot_scale + spot_h * 0.5
    spot_mesh = lc.transform_mesh(
        spot_mesh, (0.0, -spot_cy, 0.0), (spot_scale,) * 3, (0.0, 0.0, 0.0)
    )
    spot_proto = scene.add_mesh(spot_mesh)
    for aid in spot_actors:
        scene.add_instance(spot_proto, world.get_pose(aid))

    crate_proto = scene.add_mesh(
        lc.make_box(
            (-crate_half[0], -crate_half[1], -crate_half[2]),
            (crate_half[0], crate_half[1], crate_half[2]),
            crate_m,
        )
    )
    scene.add_instance(crate_proto, world.get_pose(crate_id))
    print("[assembly] Spot / Sparky / Capsule + PhysX spill", flush=True)

    # Skylight NEE + warm furnace fill
    scene.add_quad_light((-0.9, 6.45, -1.2), (1.8, 0.0, 0.0), (0.0, 0.0, 2.4), (22.0, 21.0, 18.0))
    scene.add_spot_light(
        position=(-4.5, 4.5, 0.5),
        direction=(0.15, -1.0, -0.35),
        emission=(40.0, 28.0, 14.0),
        angle_deg=28.0,
        penumbra_deg=14.0,
    )
    scene.add_spot_light(
        position=(2.5, 5.0, 2.5),
        direction=(-0.2, -1.0, -0.3),
        emission=(35.0, 38.0, 42.0),
        angle_deg=24.0,
        penumbra_deg=12.0,
    )

    scene.background_top = (0.55, 0.62, 0.75)
    scene.background_bottom = (0.18, 0.17, 0.15)

    camera = lc.Camera(
        eye=(5.8, 3.2, 6.2),
        lookat=(-0.8, 1.2, -0.5),
        up=(0.0, 1.0, 0.0),
        fov_y_deg=40.0,
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
    print(f"[assembly] render → {out} @ {spp} spp", flush=True)
    lc.Renderer().render(scene, camera, cfg)

    del world
    print("[assembly] done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
