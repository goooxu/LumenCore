# Third-party dependencies

LumenCore **does not vendor** OptiX, PhysX, or stb in git.

On first CMake configure with `LUMENCORE_FETCH_DEPS=ON` (default):

| Dependency | Source | Install location |
|------------|--------|------------------|
| OptiX headers | [NVIDIA/optix-dev](https://github.com/NVIDIA/optix-dev) | CMake FetchContent under the build tree |
| PhysX 5 | [NVIDIA-Omniverse/PhysX](https://github.com/NVIDIA-Omniverse/PhysX) | `<build>/_deps/physx` via `scripts/fetch_physx.sh` |
| stb | [nothings/stb](https://github.com/nothings/stb) | CMake FetchContent (`stb_image.h` for HDRI) |
| pybind11 | GitHub tag `v2.13.6` | CMake FetchContent |

Use `./scripts/build.sh` for a one-shot Docker build. Offline: pass `-DLUMENCORE_FETCH_DEPS=OFF` and set `-DOPTIX_INCLUDE_DIR=`, `-DPHYSX_ROOT=`, `-DSTB_INCLUDE_DIR=`.
