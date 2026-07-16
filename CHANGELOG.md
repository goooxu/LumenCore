# Changelog

All notable changes to LumenCore are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.10.0] - 2026-07-16

### Added

- **GGX microfacet** opaque BRDF (metallic-roughness) with VNDF sampling in the path tracer
- **Balance MIS** between BSDF sampling and next-event estimation (area lights, spots, HDRI)
- **HDRI environment maps**: `Scene.load_env_map` / `clear_env_map` (Radiance `.hdr` via stb), equirect miss + luminance CDF importance sampling
- Studio env asset `assets/env/studio.hdr` (`scripts/gen_studio_hdr.py`)
- Showcase scene `python/scenes/ggx_studio.py` + gallery `outputs/ggx_studio.png`
- `make_uv_sphere` now writes smooth vertex normals

### Changed

- Opaque shading path uses GGX eval/sample (glass remains ideal dielectric)
- `materials_ball` and `outdoor_env` load the studio HDRI as primary lighting

## [0.9.1] - 2026-07-16

### Changed

- Water pool demo is now **open deep water** (~4 m) with a wooden pier; Sparky + Capsule Mascot remain as reflection subjects
- Stronger Beer-Lambert absorption and a deep seabed (~3.5 m) so water color / depth read clearly

## [0.9.0] - 2026-07-16

### Added

- Optional **vertex normals** on `Mesh` / `HitGroupData` with barycentric shading in the path tracer

### Changed

- Rewrote `make_water_surface`: gentle ~1–2 cm ripples with **analytic heightfield normals**
- Redesigned `water_pool` as an enclosed stone pool with flush water, Sparky + Capsule Mascot deck reflections, and moderated absorption

## [0.8.2] - 2026-07-16

### Changed

- Water pool demo: open-front pool, stronger absorption / waves, dark backdrop, and lighting so the water surface reads clearly
- Water pool reflection subjects are now **Sparky** + **Capsule Mascot** (replacing chrome/colored spheres)
- Slightly increased procedural wave amplitude in `make_water_surface`

## [0.8.1] - 2026-07-16

### Changed

- **PhysX is GPU-only**: `PhysXWorld.init()` no longer falls back to CPU; missing `libPhysXGpu` / CUDA context makes init throw
- Removed `prefer_gpu` argument from C++/Python `PhysXWorld.init` and from `physx_collapse` CLI

## [0.8.0] - 2026-07-16

### Added

- Dielectric **Beer-Lambert absorption** (`Material.absorption`) with medium tracking in the path tracer
- Procedural water heightfield: `make_water_surface(..., time)`
- Water pool demo: `python/scenes/water_pool.py`, gallery `outputs/water_pool.png`

## [0.7.0] - 2026-07-16

### Added

- Mesh UV / texcoords, OBJ `vt` parsing, and albedo texture sampling in the path tracer
- `Scene.add_texture`, `Material.albedo_tex`, bilinear GPU sampling in `closesthit`
- `Scene.add_spot_light` (conical spot NEE) used for overhead key lights in the Sparky duo scene
- Original **Sparky** cartoon robot (`scripts/gen_sparky.py` → `sparky.obj` + `sparky_albedo.png`) — boxy tread design with glass visor, multi-material plastics/metal/emissive screens, chest label **SPARKY**
- **Capsule Mascot** asset (`capsule_mascot.obj`, CC0) co-starring with Sparky in `python/scenes/sparky.py`
- Demo scene `python/scenes/sparky.py` and gallery render `outputs/sparky.png`

### Removed

- Yellow Buddy character assets and `yellow_buddy` scene (replaced by Sparky)

## [0.6.0] - 2026-07-16

### Added

- Procedural **FlameVolume** lights: noise density + ray-marched emission/absorption in OptiX
- `Scene.add_flame_volume` (Python/C++) with automatic NEE proxy quad light
- Demo scene `python/scenes/fireplace.py` and gallery render `outputs/fireplace.png`

## [0.5.0] - 2026-07-16

### Added

- **PhysX 5** rigid-body integration (`PhysXWorld` / `Pose`) with GPU dynamics when `libPhysXGpu_64.so` is available, otherwise CPU fallback
- Python bindings for PhysX plus `apply_pose_to_box_mesh` / `apply_pose_to_sphere_mesh` / `apply_pose_to_mesh`
- Demo scene `python/scenes/physx_collapse.py` — brick tower + metal balls, multi-frame OptiX renders
- `scripts/setup_physx.sh` and vendored PhysX headers under `third_party/physx/include`
- Gallery asset `outputs/physx_collapse.png` (+ frame sequence / contact sheet)

### Changed

- README narrative is now **PhysX + OptiX** dual-stack; `docker/run.sh` adds PhysX GPU library path

## [0.4.0] - 2026-07-15

### Added

- Python API module `lumencore` (pybind11) exposing Scene / Material / Camera / Renderer / mesh helpers / OBJ load
- Python scene scripts under `python/scenes/` (`cornell`, `materials_ball`, `outdoor_env`, `yellow_buddy`)

### Changed

- Primary workflow is now Python; legacy C++ `examples/*.cc` removed from the default tree
- `docker/run.sh` sets `PYTHONPATH` and builds `lumencore-build:cuda13` with Python headers when needed

## [0.3.2] - 2026-07-15

### Changed

- Redesigned `yellow_buddy.obj` with richer structure (sculpted capsule body, overall straps/pockets, bent arms with gloves, boots, goggle stack) instead of only subdividing boxes (~17k triangles)
- Re-rendered `outputs/yellow_buddy.png`

## [0.3.1] - 2026-07-15

### Changed

- Regenerated `yellow_buddy.obj` at higher tessellation (~10,240 triangles, was ~1,764)
- Re-rendered `outputs/yellow_buddy.png` with the denser mesh

## [0.3.0] - 2026-07-15

### Changed

- Raised default example render resolutions to 2K class:
  - `cornell`: 2048×2048
  - `materials_ball`, `outdoor_env`, `yellow_buddy`: 2560×1440
- Regenerated gallery images under `outputs/` at the new resolutions

## [0.2.0] - 2026-07-15

### Added

- README gallery with scene descriptions and sample renders
- Wavefront OBJ loader (`load_obj`) with optional `usemtl` material mapping
- `transform_mesh` helper for translate / scale / rotate
- Original **Yellow Buddy** character asset (`assets/models/yellow_buddy.obj`)
- `yellow_buddy` example scene

## [0.1.0] - 2026-07-15

### Added

- Initial OptiX 9 + CUDA 13 unidirectional path tracer
- Next Event Estimation, Russian Roulette, simplified PBR materials
- Triangle-mesh GAS, progressive accumulation, OptiX Denoiser
- Example scenes: `cornell`, `materials_ball`, `outdoor_env`
- Docker-based build/run helper for RTX GPUs

[0.9.1]: https://github.com/goooxu/LumenCore/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/goooxu/LumenCore/compare/v0.8.2...v0.9.0
[0.8.2]: https://github.com/goooxu/LumenCore/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/goooxu/LumenCore/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/goooxu/LumenCore/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/goooxu/LumenCore/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/goooxu/LumenCore/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/goooxu/LumenCore/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/goooxu/LumenCore/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/goooxu/LumenCore/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/goooxu/LumenCore/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/goooxu/LumenCore/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/goooxu/LumenCore/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/goooxu/LumenCore/releases/tag/v0.1.0
