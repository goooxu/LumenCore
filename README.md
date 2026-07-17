# LumenCore

NVIDIA GPU dual-stack showcase: **PhysX 5** rigid-body dynamics + **OptiX 9 / CUDA 13** path tracing. Gallery renders validated on **GB200** (`10.85.120.24`, 4×GPU) and previously on **RTX 5090**.

See [CHANGELOG.md](CHANGELOG.md) for version history.

**技术报告（中文，面向图形学初学者）**：[docs/report/](docs/report/) — 渲染方程、路径追踪、GGX/MIS/HDRI、OptiX 与 PhysX 实现说明。首页 Gallery 为两层结构；报告章节仍引用 `outputs/*.png` 旧单图。

## Gallery

### 综合展示 · Atelier

![Atelier showcase](outputs/gallery/showcase.png)

一帧里叠满 LumenCore 双栈能力：**PhysX** 短仿真后定格刚体砖堆，经 **OptiX IAS** 实例化再路径追踪；同框还有壁炉火焰体积、HDRI/面光/聚光与 NEE、GGX 金属与磨砂玻璃、Sparky 法线贴图、Capsule、**Spot** 奶牛，以及浅水池的 Beer-Lambert 吸收。脚本：`python/scenes/atelier.py`（2560×1440）。

### 特性对比（同机位 ON / OFF）

每组两张 **1024×1024**，只翻转一个开关。批量入口：`python/scenes/gallery_compare.py`；并行脚本：`scripts/render_gallery.sh`。

#### 法线贴图

面板浮雕有无：Sparky 胸口特写，`normal_tex` 开/关。

| ON | OFF |
|----|-----|
| ![normal on](outputs/gallery/compare/normal_on.png) | ![normal off](outputs/gallery/compare/normal_off.png) |

#### Next Event Estimation

暗环境 + 面光：开 NEE 后阴影更干净、方差更低。

| ON | OFF |
|----|-----|
| ![nee on](outputs/gallery/compare/nee_on.png) | ![nee off](outputs/gallery/compare/nee_off.png) |

#### OptiX Denoiser

低 spp 中景：噪点 vs 引导式去噪。

| ON | OFF |
|----|-----|
| ![denoiser on](outputs/gallery/compare/denoiser_on.png) | ![denoiser off](outputs/gallery/compare/denoiser_off.png) |

#### 火焰体积

壁炉局部：体积自发光有无（OFF 仅冷灰烬）。

| ON | OFF |
|----|-----|
| ![flame on](outputs/gallery/compare/flame_on.png) | ![flame off](outputs/gallery/compare/flame_off.png) |

#### Beer-Lambert

水下岩石：吸收系数正常 vs 全零（水深颜色衰减）。

| ON | OFF |
|----|-----|
| ![beer on](outputs/gallery/compare/beer_on.png) | ![beer off](outputs/gallery/compare/beer_off.png) |

---

## Features

- **PhysX 5 + OptiX 9** — GPU PhysX rigid bodies (required) + OptiX path tracing (`PhysXWorld` → poses → **IAS instances** → path tracer)
- **Procedural flame volumes** — `Scene.add_flame_volume` (noise density, ray-marched emission, NEE proxy light)
- **Python scene API** (`import lumencore`) — each demo is a Python script
- Unidirectional path tracing + Next Event Estimation (quad area lights + spot lights + HDRI)
- Russian Roulette; **GGX** opaque materials + **GGX rough glass** (microfacet transmission)
- **HDRI env maps** (`Scene.load_env_map`) with CDF importance sampling and balance MIS
- Triangle-mesh **GAS** + optional **IAS** instancing on OptiX RT Cores
- Wavefront **OBJ** import (`load_obj`, optional `usemtl` material map, **UV / `vt`**)
- Albedo + **tangent-space normal** textures (`Scene.add_texture`, `Material.albedo_tex` / `normal_tex`)
- Spot lights (`Scene.add_spot_light`)
- Dielectric **Beer-Lambert absorption** (`Material.absorption`) for water / tinted glass
- Procedural water surfaces (`make_water_surface` with analytic normals)
- Optional mesh **vertex normals** / auto **tangents** (`ensure_mesh_tangents`) for smooth shading and normal maps
- Progressive accumulation + OptiX Denoiser (albedo/normal guided)
- ACES tone map + gamma PNG output

## Requirements

- NVIDIA GPU with RT Cores (tested: GB200 @ `10.85.120.24`, RTX 5090)
- Docker with CUDA 13+ toolkit (default base: `nvidia/cuda:13.0.1-devel-ubuntu24.04`; `docker/run.sh` builds `lumencore-build:cuda13` with Python headers)
- OptiX denoiser weights at `/usr/share/nvidia/nvoptix.bin`
- Vendored OptiX 9 headers under `third_party/optix`
- PhysX 5 static libs under `third_party/physx/lib` (run `scripts/setup_physx.sh` once; needs network on first fetch). GPU rigid bodies require `third_party/physx/bin/libPhysXGpu_64.so` on `LD_LIBRARY_PATH` (`docker/run.sh` sets this). PhysX is GPU-only; init fails if GPU PhysX is unavailable.
- Network on first CMake configure (FetchContent downloads pybind11)

## Quick start

```bash
chmod +x docker/run.sh scripts/setup_physx.sh

# One-time PhysX install (skip if third_party/physx/lib already populated)
./scripts/setup_physx.sh

# Configure + build Python module → /tmp/LumenCore-build/python/lumencore*.so
./docker/run.sh 'cmake -S /work -B /out -DCMAKE_CUDA_ARCHITECTURES=120 && cmake --build /out -j$(nproc)'

# Render scenes (PYTHONPATH is set by docker/run.sh)
./docker/run.sh 'python3 /work/python/scenes/atelier.py /results/gallery/showcase.png 192 1'
./docker/run.sh 'python3 /work/python/scenes/gallery_compare.py --feature normal --mode on --out /results/gallery/compare/normal_on.png'
# Or multi-GPU batch:
# NRTX_PHYSX_ROOT=/tmp/LumenCore-physx ./scripts/render_gallery.sh
./docker/run.sh 'python3 /work/python/scenes/ggx_studio.py /results/ggx_studio.png 256 1'
./docker/run.sh 'python3 /work/python/scenes/cornell.py /results/cornell.png 256 1'
./docker/run.sh 'python3 /work/python/scenes/materials_ball.py /results/materials_ball.png 256 1'
./docker/run.sh 'python3 /work/python/scenes/outdoor_env.py /results/outdoor_env.png 256 1'
./docker/run.sh 'python3 /work/python/scenes/sparky.py /results/sparky.png 256 1'
./docker/run.sh 'python3 /work/python/scenes/physx_collapse.py /results/physx_collapse.png 128 1 1'
./docker/run.sh 'python3 /work/python/scenes/fireplace.py /results/fireplace.png 256 1'
./docker/run.sh 'python3 /work/python/scenes/water_pool.py /results/water_pool.png 256 1'
```

CLI: `python3 <scene.py> [out.png] [spp] [denoise=1|0]`

`physx_collapse` writes a frame sequence under `<out_stem>/` plus a gallery hero PNG (pick any frame for the homepage).

`fireplace` extra arg: `[time]` — flame noise phase / scroll offset.

`water_pool` extra arg: `[time]` — procedural water wave phase.

Example API usage:

```python
import lumencore as lc

scene = lc.Scene()
mat = scene.add_material(lc.Material(base_color=(0.8, 0.8, 0.8), roughness=0.5))
scene.add_mesh(lc.make_quad((0, 0, 0), (1, 0, 0), (0, 0, 1), mat))
scene.add_flame_volume(
    center=(0.5, 0.4, 0.5),
    half_extents=(0.2, 0.4, 0.15),
    emission_scale=(40, 16, 3),
    time=1.5,
)
cam = lc.Camera(eye=(0.5, 0.5, -1.35), lookat=(0.5, 0.5, 0.5), fov_y_deg=40, aspect=1.0)
cfg = lc.RenderConfig(width=2048, height=2048, spp=64, denoise=True, output_path="out.png")
lc.Renderer().render(scene, cam, cfg)
```

## Layout

| Path | Role |
|------|------|
| `docs/report/` | 中文技术报告（分章 Markdown + `figures/`） |
| `bindings/` | pybind11 module `lumencore` |
| `python/scenes/` | Scene scripts (`atelier`, `gallery_compare`, plus legacy demos) |
| `include/nrtx` | C++ host scene API + `PhysXWorld` |
| `src/device` | OptiX programs (`.cu` → OptiX-IR) |
| `src/host` | Context, GAS, PhysX wrapper, OBJ/HDRI loaders, denoiser, PNG I/O |
| `scripts/setup_physx.sh` | Fetch/build PhysX 5 into `third_party/physx` (or `PHYSX_INSTALL`) |
| `scripts/render_gallery.sh` | Multi-GPU gallery showcase + compare renders |
| `scripts/gen_sparky.py` | Procedural Sparky OBJ + albedo atlas |
| `scripts/gen_studio_hdr.py` | Procedural studio Radiance HDR |
| `assets/models` | Character OBJ / MTL / textures |
| `assets/env` | HDRI environment maps |
| `outputs/` | Legacy per-scene stills (report chapters) |
| `outputs/gallery/` | Homepage two-tier gallery (`showcase.png` + `compare/`) |

## Performance (GB200 @ 10.85.120.24, denoised)

| Scene | Resolution | Notes |
|-------|------------|-------|
| gallery showcase (`atelier`) | 2560×1440 | PhysX settle + multi-feature still |
| gallery compare (×10) | 1024×1024 | ON/OFF pairs; denoiser uses low spp |
| Legacy demos (`outputs/*.png`) | 2K class | Still used by `docs/report/` chapters |

Parallel gallery render: `NRTX_PHYSX_ROOT=... ./scripts/render_gallery.sh` (uses `NRTX_GPU` round-robin).

## License

Sample code for learning and experimentation. OptiX headers remain under NVIDIA’s OptiX SDK license terms. PhysX is under the NVIDIA PhysX SDK license (see upstream `NVIDIA-Omniverse/PhysX`). **Sparky** and **Capsule Mascot** are AI-generated assets bundled with this repository. **Spot** is from Keenan Crane’s [CMU 3D Model Repository](https://www.cs.cmu.edu/~kmcrane/Projects/ModelRepository/).
