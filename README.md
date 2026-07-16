# LumenCore

NVIDIA GPU dual-stack showcase: **PhysX 5** rigid-body dynamics + **OptiX 9 / CUDA 13** path tracing, validated on **RTX 5090**.

See [CHANGELOG.md](CHANGELOG.md) for version history.

## Gallery

### PhysX Collapse

![PhysX Collapse](outputs/physx_collapse.png)

Studio brick tower knocked over by heavy metal balls rolling down a ramp. **PhysX** advances GPU (or CPU-fallback) rigid bodies; each sampled frame rebuilds triangle meshes from actor poses and is path-traced with **OptiX**. Frame sequence: `outputs/physx_collapse/`; contact sheet: `outputs/physx_collapse/contact_sheet.png`.

### Cornell Box

![Cornell Box](outputs/cornell.png)

Classic enclosed room with red / green walls, a glass sphere, a metal sphere, and a ceiling area light. Shows soft shadows, color bleeding, refraction caustics, and Next Event Estimation.

### Materials Ball

![Materials Ball](outputs/materials_ball.png)

Material chart of diffuse, metal, and glass spheres under an area light. Useful for checking roughness / metallic / transmission response of the simplified PBR model.

### Outdoor Env

![Outdoor Env](outputs/outdoor_env.png)

Open ground scene with chrome and glass props, soft sunlight, and a gradient environment. Includes a light depth-of-field camera.

### Yellow Buddy (OBJ character)

![Yellow Buddy](outputs/yellow_buddy.png)

Studio portrait of **Yellow Buddy**, an original capsule character loaded from Wavefront OBJ (`assets/models/yellow_buddy.obj`, ~17k triangles with sculpted body, straps, arms, and boots). Multi-material `usemtl` groups drive yellow body, blue overalls, metal goggles, glass lens, and boots. Inspired by the familiar “yellow helper” silhouette; not affiliated with any trademarked property.

---

## Features

- **PhysX 5 + OptiX 9** — simulate with PhysX, image with OptiX (`PhysXWorld` → poses → meshes → path tracer)
- **Python scene API** (`import lumencore`) — each demo is a Python script
- Unidirectional path tracing + Next Event Estimation (quad area lights)
- Russian Roulette; diffuse / metal / glass materials
- Triangle-mesh GAS on OptiX RT Cores
- Wavefront **OBJ** import (`load_obj`, optional `usemtl` material map)
- Progressive accumulation + OptiX Denoiser (albedo/normal guided)
- ACES tone map + gamma PNG output

## Requirements

- NVIDIA GPU with RT Cores (tested: RTX 5090)
- Docker with CUDA 13+ toolkit (default base: `nvidia/cuda:13.0.1-devel-ubuntu24.04`; `docker/run.sh` builds `lumencore-build:cuda13` with Python headers)
- OptiX denoiser weights at `/usr/share/nvidia/nvoptix.bin`
- Vendored OptiX 9 headers under `third_party/optix`
- PhysX 5 static libs under `third_party/physx/lib` (run `scripts/setup_physx.sh` once; needs network on first fetch). GPU rigid bodies also need `third_party/physx/bin/libPhysXGpu_64.so` on `LD_LIBRARY_PATH` (`docker/run.sh` sets this). If GPU PhysX is unavailable, the demo falls back to CPU.
- Network on first CMake configure (FetchContent downloads pybind11)

## Quick start

```bash
chmod +x docker/run.sh scripts/setup_physx.sh

# One-time PhysX install (skip if third_party/physx/lib already populated)
./scripts/setup_physx.sh

# Configure + build Python module → /tmp/LumenCore-build/python/lumencore*.so
./docker/run.sh 'cmake -S /work -B /out -DCMAKE_CUDA_ARCHITECTURES=120 && cmake --build /out -j$(nproc)'

# Render scenes (PYTHONPATH is set by docker/run.sh)
./docker/run.sh 'python3 /work/python/scenes/cornell.py /results/cornell.png 256 1'
./docker/run.sh 'python3 /work/python/scenes/materials_ball.py /results/materials_ball.png 256 1'
./docker/run.sh 'python3 /work/python/scenes/outdoor_env.py /results/outdoor_env.png 256 1'
./docker/run.sh 'python3 /work/python/scenes/yellow_buddy.py /results/yellow_buddy.png 256 1'
./docker/run.sh 'python3 /work/python/scenes/physx_collapse.py /results/physx_collapse.png 128 1 1'
```

CLI: `python3 <scene.py> [out.png] [spp] [denoise=1|0]`

`physx_collapse` extra arg: `[prefer_gpu=1|0]` — writes a frame sequence under `<out_stem>/` plus a gallery hero PNG.

Example API usage:

```python
import lumencore as lc

# OptiX path trace
scene = lc.Scene()
mat = scene.add_material(lc.Material(base_color=(0.8, 0.8, 0.8), roughness=0.5))
scene.add_mesh(lc.make_quad((0, 0, 0), (1, 0, 0), (0, 0, 1), mat))
cam = lc.Camera(eye=(0.5, 0.5, -1.35), lookat=(0.5, 0.5, 0.5), fov_y_deg=40, aspect=1.0)
cfg = lc.RenderConfig(width=2048, height=2048, spp=64, denoise=True, output_path="out.png")
lc.Renderer().render(scene, cam, cfg)

# PhysX → mesh pose sync
world = lc.PhysXWorld()
world.init(prefer_gpu=True)
box = world.add_dynamic_box((0.2, 0.2, 0.2), 1.0, lc.Pose(position=(0, 2, 0)))
world.step(1.0 / 60.0)
pose = world.get_pose(box)
mesh = lc.apply_pose_to_box_mesh((0.2, 0.2, 0.2), pose, mat)
```

## Layout

| Path | Role |
|------|------|
| `bindings/` | pybind11 module `lumencore` |
| `python/scenes/` | Scene scripts (cornell, materials_ball, outdoor_env, yellow_buddy, physx_collapse) |
| `include/nrtx` | C++ host scene API + `PhysXWorld` |
| `src/device` | OptiX programs (`.cu` → OptiX-IR) |
| `src/host` | Context, GAS, PhysX wrapper, OBJ loader, denoiser, PNG I/O |
| `scripts/setup_physx.sh` | Fetch/build PhysX 5 into `third_party/physx` |
| `assets/models` | Character OBJ / MTL |
| `outputs/` | Sample renders from RTX 5090 |

## Performance (RTX 5090, denoised)

| Scene | Resolution | Notes |
|-------|------------|-------|
| cornell | 2048×2048 | ~1.51 s @ 256 spp |
| materials_ball | 2560×1440 | ~0.50 s @ 256 spp |
| outdoor_env | 2560×1440 | ~0.43 s @ 256 spp |
| yellow_buddy | 2560×1440 | ~0.73 s @ 256 spp |
| physx_collapse | 2560×1440 | ~0.24 s path-trace / frame @ 96 spp; PhysX backend `gpu` |

## License

Sample code for learning and experimentation. OptiX headers remain under NVIDIA’s OptiX SDK license terms. PhysX is under the NVIDIA PhysX SDK license (see upstream `NVIDIA-Omniverse/PhysX`). Yellow Buddy is an original asset bundled with this repository.
