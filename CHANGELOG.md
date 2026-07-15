# Changelog

All notable changes to LumenCore are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.3.1]: https://github.com/goooxu/LumenCore/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/goooxu/LumenCore/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/goooxu/LumenCore/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/goooxu/LumenCore/releases/tag/v0.1.0
