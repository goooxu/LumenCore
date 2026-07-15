# LumenCore

GPU path tracer built with **OptiX 9 + CUDA 13**, validated on **RTX 5090**.

## Features

- Unidirectional path tracing + Next Event Estimation (quad area lights)
- Russian Roulette; diffuse / metal / glass materials
- Triangle-mesh GAS on OptiX RT Cores
- Progressive accumulation + OptiX Denoiser (albedo/normal guided)
- ACES tone map + gamma PNG output

## Requirements

- NVIDIA GPU with RT Cores (tested: RTX 5090)
- Docker image with CUDA 13+ toolkit (default: `spectraldock-dev:cuda13.3`)
- OptiX denoiser weights at `/usr/share/nvidia/nvoptix.bin` (from the driver install)
- Vendored OptiX 9 headers under `third_party/optix`

## Quick start

```bash
chmod +x docker/run.sh

# Configure + build (artifacts under /tmp/LumenCore-build)
./docker/run.sh 'cmake -S /work -B /out -DCMAKE_CUDA_ARCHITECTURES=120 && cmake --build /out -j$(nproc)'

# Render examples → /tmp/LumenCore-out
./docker/run.sh './bin/cornell /results/cornell.png 256 1'
./docker/run.sh './bin/materials_ball /results/materials_ball.png 256 1'
./docker/run.sh './bin/outdoor_env /results/outdoor_env.png 256 1'
```

CLI: `program <output.png> [spp] [denoise=1|0]`

Set `NRTX_DOCKER_IMAGE` if your CUDA/OptiX container has a different name. Build and render outputs use local `/tmp` paths so NFS-mounted source trees stay read-only inside the container.

## Layout

| Path | Role |
|------|------|
| `include/nrtx` | Host scene API |
| `src/device` | OptiX programs (`.cu` → OptiX-IR) |
| `src/host` | Context, GAS, pipeline, denoiser, PNG I/O |
| `examples` | cornell / materials_ball / outdoor_env |
| `outputs/` | Sample renders from RTX 5090 |

## Performance (RTX 5090, 256 spp, denoised)

| Scene | Resolution | Path trace |
|-------|------------|------------|
| cornell | 800² | ~0.27 s |
| materials_ball | 1280×720 | ~0.13 s |
| outdoor_env | 1280×720 | ~0.12 s |

## License

Sample code for learning and experimentation. OptiX headers remain under NVIDIA’s OptiX SDK license terms.
