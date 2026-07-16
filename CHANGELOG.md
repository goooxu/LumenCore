# Changelog

All notable changes to LumenCore are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.6.0]: https://github.com/goooxu/LumenCore/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/goooxu/LumenCore/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/goooxu/LumenCore/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/goooxu/LumenCore/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/goooxu/LumenCore/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/goooxu/LumenCore/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/goooxu/LumenCore/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/goooxu/LumenCore/releases/tag/v0.1.0
