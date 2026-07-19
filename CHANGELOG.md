# Changelog

All notable changes to LumenCore are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Emissive paths**: terminate after adding emission; denoiser albedo guide uses `base+clamp(emission)` so lights are not wiped (beauty estimator unchanged)
- Visible lamp panels use non-zero `base_color` (reflectance) separate from `emission`
- Gallery NEE compare framing keeps the ceiling lamp fully in view
- **Visible area lamps**: `add_quad_light(..., use_mis=True)` when paired with an emissive mesh
- **GGX VNDF**: Heitz 2018 visible-normal sampling + matching solid-angle PDF; exact Smith G1
- **Virtual lights**: quad/spot NEE weight is 1 by default; HDRI MIS unchanged
- **Self-intersection**: geometric-normal `offset_ray_origin` for continuation and shadow rays

## [0.16.0] - 2026-07-18

### Added

- **HDR AVIF** render output (10-bit PQ / BT.2020) from linear float buffers via libavif
- **AVIF** texture inputs (`Scene.add_texture`); albedo/normal assets shipped as `.avif`
- CMake auto-detects `CMAKE_CUDA_ARCHITECTURES` from `nvidia-smi compute_cap` (fail-closed if missing)

### Changed

- Removed ACES/γ 8-bit PNG write path; gallery/docs/scripts default to `.avif`
- `docker/run.sh` image tag `lumencore-build:cuda13-avif` installs `libavif-dev`; prefers host-matching multiarch lib dir; preloads `libcudart` in-container for PhysXGpu
- `scripts/render_gallery.sh` no longer falls back to CUDA arch 120

### Removed

- All project PNG render outputs and texture/diagram PNGs (PNG fully deprecated)

## [0.15.0] - 2026-07-17

### Added

- Gallery cover scenes after Atelier: `python/scenes/dusk_observatory.py` (暮潮观测站) and `python/scenes/assembly_hall.py` (Assembly Hall), both 2560×1440
- Procedural env maps `assets/env/dusk.hdr` and `assets/env/noon_factory.hdr` (`scripts/gen_studio_hdr.py dusk|noon`)
- README Gallery sections + `scripts/render_gallery.sh` jobs for both covers

## [0.14.0] - 2026-07-17

### Added

- **Two-tier README Gallery**: one 2K multi-feature showcase + five 1K ON/OFF feature compares
- `python/scenes/atelier.py` — PhysX-settled atelier still (flame, HDRI/NEE, GGX metal/glass, Sparky normals, Capsule, Spot cow, Beer-Lambert basin)
- `python/scenes/gallery_compare.py` — `--feature {normal,nee,denoiser,flame,beer} --mode on|off`
- `scripts/render_gallery.sh` — multi-GPU parallel render via `NRTX_GPU` / `docker/run.sh`
- Gallery assets under `outputs/gallery/` (`showcase.png` + `compare/*_{on,off}.png`)

### Changed

- README homepage Gallery no longer tiles the eight legacy demo stills (those PNGs remain for `docs/report/`)
- `docker/run.sh` accepts `NRTX_GPU=<index>` for `--gpus device=N` parallel jobs
- Docs/report intro + models README note Spot in `atelier`
- `docker/run.sh` / `scripts/setup_physx.sh`: aarch64 host support (`NRTX_PHYSX_ROOT`, multiarch OptiX libs, arch-matched CMake)

## [0.13.0] - 2026-07-17

### Added

- **Tangent-space normal mapping**: `Material.normal_tex` + per-vertex tangents (`Mesh.tangents` / `ensure_mesh_tangents`) uploaded in `HitGroupData`
- `sparky_normal.png` atlas (from `scripts/gen_sparky.py`) wired into `sparky`, `fireplace`, `water_pool`, and `physx_collapse` Sparky materials

### Changed

- Host upload computes missing vertex normals and Mikkt-style tangents before GAS/SBT build
- Shading uses mapped normals for BSDF/NEE; geometric normals still decide front/back faces
- Docs/report 01/04/07/08/10 + README updated for normal maps; gallery Sparky/Fireplace re-rendered

## [0.12.0] - 2026-07-17

### Added

- **OptiX IAS instancing** for PhysX: `Scene.add_instance(mesh_index, pose)` builds per-prototype GAS + IAS from rigid poses (no full-scene mesh merge each frame)
- `Scene.add_mesh` now returns a mesh index for instancing

### Changed

- `physx_collapse` uses object-space prototypes + pose instances; tower density increased to 10×14×10
- Renderer pipeline allows `SINGLE_GAS` and `SINGLE_LEVEL_INSTANCING` (traversable depth 2)
- Uninstanced meshes in an instanced scene automatically get an identity instance (flame proxies, light quads)
- Docs/report 01/07/08/09/10 + README + appendix updated for IAS dual-stack path; `physx-render-loop` figure shows instance/IAS loop

## [0.11.0] - 2026-07-17

### Added

- **GGX rough transmission** for dielectrics (`transmission > 0.5`): microfacet VNDF sample + Fresnel reflect/refract about the half-vector (`sample_dielectric_bsdf` in `bsdf.h`)
- `ggx_studio` glass roughness row; `materials_ball` glass row uses roughness gradient

### Changed

- Glass shading path no longer uses ideal delta Snell only; low roughness still reads as clear glass, high roughness as frosted
- Docs/report updated for rough glass (still no glass NEE/MIS in this release)
- `docker/run.sh`: auto-detect host `libnvidia-rtcore` / OptiX sonames; avoid bind-mounting `libnvoptix.so.1` (conflicts with nvidia-container-toolkit)

## [0.10.2] - 2026-07-16

### Added

- 中文分章技术报告 [`docs/report/`](docs/report/)：数学原理、OptiX/PhysX 实现、配图与演示对照

### Fixed

- 技术报告公式分隔符改为 GitHub 支持的 `$` / `$$`（原 `\(...\)` / `\[...\]` 在 GitHub 上不渲染）
- 含下标 `_` 的行内公式改用 `$`...`$`，块级改用 \`\`\`math，避免 Markdown 把 `_` 当斜体导致 MathJax 报错

## [0.10.1] - 2026-07-16

### Changed

- PhysX Collapse: larger **glass fireball** (procedural flame volume inside), darker studio lighting, and brick-sized **Sparky / Capsule Mascot** mixed into the tower
- PhysX Collapse homepage hero uses `frame_0010`
- Fireplace: stage Sparky / Capsule mascots with plastic, chrome, yellow, and glass material variants

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
